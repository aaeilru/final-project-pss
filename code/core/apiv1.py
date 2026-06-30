from typing import List

import os
from django.http import FileResponse
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from ninja import NinjaAPI
from ninja.errors import HttpError

from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth

from celery.result import AsyncResult

from courses.models import Course, CourseMember, CourseContent, Comment, Category, Profile, Progress, Certificate, CourseStatistics
from core.schemas import (
    UserOut,
    UserRoleOut,
    UserUpdate,
    RoleUpdate,
    Register,
    CategoryIn,
    CategoryOut,
    CourseIn,
    CourseOut,
    DetailCourseOut,
    CourseMemberOut,
    CourseContentIn,
    CourseContentOut,
    CommentIn,
    CommentUpdate,
    ProgressIn,
    ProgressOut,
    MessageOut,
    TaskTriggerOut,
    TaskStatusOut,
    CertificateOut,
    CourseReportOut,
)

from django.core.cache import cache
from analytics.mongo_service import (
    log_activity,
    save_learning_analytics,
    report_activity_by_action,
    report_daily_active_users,
    report_course_popularity,
    report_completion_summary,
)
from courses.tasks import (
    send_enrollment_email,
    generate_certificate,
    update_course_statistics,
    export_course_report,
)
from core.rate_limit import rate_limit
from core.helpers import get_role, require_role


# INIT API
apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
)

apiv1.add_router("/auth/", mobile_auth_router)
apiAuth = HttpJwtAuth()


# ================= AUTH =================

@apiv1.post("/register/", response={201: UserOut}, tags=["Authentication"])
def register(request, data: Register):
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah digunakan")

    # Admin TIDAK BOLEH dibuat lewat self-registration. Hanya "student"
    # atau "instructor" yang valid; nilai lain otomatis jadi "student".
    role = data.role if data.role in ("student", "instructor") else "student"

    payload = data.dict()
    payload.pop("role")

    user = User.objects.create_user(**payload)
    Profile.objects.create(user=user, role=role)

    return 201, user


@apiv1.get("/profile/", auth=apiAuth, response=UserOut, tags=["Authentication"])
def profile(request):
    return request.user


@apiv1.put("/profile/", auth=apiAuth, response=UserOut, tags=["Authentication"])
def update_profile(request, data: UserUpdate):
    # request.user bisa berupa TokenUser stateless (tidak punya .save()),
    # jadi harus diambil ulang sebagai User asli dari database.
    user = User.objects.get(id=request.user.id)

    if User.objects.filter(email=data.email).exclude(id=user.id).exists():
        raise HttpError(400, "Email sudah digunakan")

    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.save()

    return user


@apiv1.get("/auth/me/", auth=apiAuth, response=UserOut, tags=["Authentication"])
def auth_me(request):
    return request.user


@apiv1.put("/auth/me/", auth=apiAuth, response=UserOut, tags=["Authentication"])
def auth_update_me(request, data: UserUpdate):
    user = User.objects.get(id=request.user.id)

    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.save()

    return user


# ================= ADMIN: USER MANAGEMENT (RBAC) =================

@apiv1.get("/admin/users/", auth=apiAuth, response=List[UserRoleOut], tags=["Admin"])
def admin_list_users(request):
    require_role(request.user, ["admin"])

    users = User.objects.select_related("profile").all().order_by("id")
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_superuser": u.is_superuser,
            "role": get_role(u),
        })
    return result


@apiv1.put("/admin/users/{id}/role/", auth=apiAuth, response=MessageOut, tags=["Admin"])
def admin_update_user_role(request, id: int, data: RoleUpdate):
    require_role(request.user, ["admin"])

    if data.role not in ("student", "instructor"):
        raise HttpError(400, "Role hanya boleh 'student' atau 'instructor'")

    user = User.objects.filter(id=id).first()
    if not user:
        raise HttpError(404, "User tidak ditemukan")

    Profile.objects.update_or_create(user=user, defaults={"role": data.role})

    return {"message": f"Role {user.username} diubah menjadi {data.role}"}


# ================= CATEGORY =================

@apiv1.get("/categories/", response=List[CategoryOut], tags=["Categories"])
def list_categories(request):
    return Category.objects.all().order_by("name")


@apiv1.post("/categories/", auth=apiAuth, response={201: CategoryOut}, tags=["Categories"])
def create_category(request, data: CategoryIn):
    require_role(request.user, ["admin", "instructor"])

    if Category.objects.filter(name__iexact=data.name).exists():
        raise HttpError(400, "Kategori dengan nama tersebut sudah ada")

    category = Category.objects.create(**data.dict())
    return 201, category


# ================= COURSE =================

@apiv1.get("/enrollments/my-courses/", auth=apiAuth, response=List[CourseMemberOut], tags=["Enrollment"])
def my_courses(request):
    return CourseMember.objects.filter(
        user_id=request.user
    ).select_related("course_id", "user_id", "course_id__category", "course_id__teacher")


@apiv1.get("/courses/", response=list, tags=["Courses"])
def listCourses(request, category_id: int = None, search: str = None):
    rate_limit(request)

    # Cache hanya dipakai untuk query tanpa filter (kasus paling umum/berat).
    use_cache = category_id is None and not search
    cache_key = "courses_list"

    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

    qs = Course.objects.select_related("teacher", "category").all()

    if category_id is not None:
        qs = qs.filter(category_id=category_id)
    if search:
        qs = qs.filter(name__icontains=search)

    courses = []
    for course in qs:
        courses.append({
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "price": course.price,
            "teacher": course.teacher.username,
            "category": course.category.name if course.category else None,
        })

    if use_cache:
        cache.set(cache_key, courses, timeout=300)

    return courses


@apiv1.get("/courses/{id}", response=dict, tags=["Courses"])
def detailCourse(request, id: int):
    rate_limit(request)
    cache_key = f"course_detail:{id}"

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    course = Course.objects.filter(id=id).select_related("teacher", "category").first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    data = {
        "id": course.id,
        "name": course.name,
        "description": course.description,
        "price": course.price,
        "teacher": course.teacher.username,
        "category": course.category.name if course.category else None,
    }

    cache.set(cache_key, data, timeout=300)

    return data


@apiv1.post("/courses/", auth=apiAuth, response={201: CourseOut}, tags=["Courses"])
def createCourse(request, data: CourseIn):
    # Hanya instructor atau admin yang boleh membuat course.
    require_role(request.user, ["admin", "instructor"])

    if data.price < 0:
        raise HttpError(400, "Harga tidak boleh negatif")

    # Swagger UI sering ngisi default "0" untuk field integer opsional yang
    # dikosongkan. ID asli di database mulai dari 1, jadi 0 dianggap "tidak
    # pilih kategori" -- bukan dianggap error.
    if not data.category_id:
        data.category_id = None

    if data.category_id is not None and not Category.objects.filter(id=data.category_id).exists():
        raise HttpError(400, "Kategori tidak ditemukan")

    teacher = User.objects.get(id=request.user.id)

    course = Course.objects.create(
        **data.dict(),
        teacher=teacher
    )

    cache.delete("courses_list")

    log_activity(
        user_id=request.user.id,
        action="create_course",
        course_id=course.id,
        course_name=course.name
    )

    return 201, course


@apiv1.put("/courses/{id}", auth=apiAuth, response=CourseOut, tags=["Courses"])
def updateCourse(request, id: int, data: CourseIn):
    if data.price < 0:
        raise HttpError(400, "Harga tidak boleh negatif")

    course = Course.objects.filter(id=id).first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    if course.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Bukan pemilik course")

    # Sama seperti createCourse: 0 dianggap "tidak pilih kategori".
    if not data.category_id:
        data.category_id = None

    if data.category_id is not None and not Category.objects.filter(id=data.category_id).exists():
        raise HttpError(400, "Kategori tidak ditemukan")

    for key, value in data.dict().items():
        setattr(course, key, value)

    course.save()

    # Cache invalidation
    cache.delete("courses_list")
    cache.delete(f"course_detail:{id}")

    # MongoDB activity log
    log_activity(
        user_id=request.user.id,
        action="update_course",
        course_id=course.id,
        course_name=course.name,
        metadata={
            "price": course.price,
            "teacher": request.user.username
        }
    )

    return course


@apiv1.delete("/courses/{id}", auth=apiAuth, tags=["Courses"])
def deleteCourse(request, id: int):
    course = Course.objects.filter(id=id).first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    if course.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Tidak punya akses")

    course_id = course.id
    course_name = course.name

    course.delete()

    # Cache invalidation
    cache.delete("courses_list")
    cache.delete(f"course_detail:{id}")

    # MongoDB activity log
    log_activity(
        user_id=request.user.id,
        action="delete_course",
        course_id=course_id,
        course_name=course_name,
        metadata={
            "deleted_by": request.user.username
        }
    )

    return {"message": "Course berhasil dihapus"}


# ================= COURSE CONTENT (Lesson) =================

@apiv1.get("/courses/{course_id}/contents/", response=List[CourseContentOut], tags=["Course Content"])
def list_course_contents(request, course_id: int):
    """Daftar lesson/konten sebuah course. Publik, gak perlu login (sama seperti list course)."""
    course = Course.objects.filter(id=course_id).first()
    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    return CourseContent.objects.filter(course_id=course).order_by("id")


@apiv1.post("/contents/", auth=apiAuth, response={201: CourseContentOut}, tags=["Course Content"])
def create_course_content(request, data: CourseContentIn):
    """Tambah lesson baru ke sebuah course. Hanya pemilik course (instructor) atau admin."""
    # Swagger UI sering ngisi default "0" untuk field integer opsional yang
    # dikosongkan. ID asli mulai dari 1, jadi 0 dianggap "tidak ada parent".
    if not data.parent_id:
        data.parent_id = None

    course = Course.objects.filter(id=data.course_id).first()
    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    if course.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Hanya pemilik course yang bisa menambah lesson")

    parent = None
    if data.parent_id is not None:
        parent = CourseContent.objects.filter(id=data.parent_id, course_id=course).first()
        if not parent:
            raise HttpError(400, "Parent lesson tidak ditemukan di course ini")

    # course_id & parent_id adalah nama RELASI ForeignKey (bukan kolom
    # mentah) -- harus diisi instance Course/CourseContent asli, bukan
    # int mentah dari data.dict(), makanya tidak pakai **data.dict() di sini.
    content = CourseContent.objects.create(
        name=data.name,
        description=data.description,
        video_url=data.video_url,
        course_id=course,
        parent_id=parent,
    )

    log_activity(
        user_id=request.user.id,
        action="create_content",
        course_id=course.id,
        course_name=course.name,
        metadata={"content_name": content.name},
    )

    return 201, content


@apiv1.put("/contents/{id}", auth=apiAuth, response=CourseContentOut, tags=["Course Content"])
def update_course_content(request, id: int, data: CourseContentIn):
    if not data.parent_id:
        data.parent_id = None

    content = CourseContent.objects.filter(id=id).select_related("course_id").first()
    if not content:
        raise HttpError(404, "Lesson tidak ditemukan")

    if content.course_id.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Hanya pemilik course yang bisa mengubah lesson")

    new_course = Course.objects.filter(id=data.course_id).first()
    if not new_course:
        raise HttpError(400, "Course tidak ditemukan")
    if new_course.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Tidak bisa memindahkan lesson ke course milik orang lain")

    new_parent = None
    if data.parent_id is not None:
        new_parent = CourseContent.objects.filter(id=data.parent_id, course_id=new_course).first()
        if not new_parent:
            raise HttpError(400, "Parent lesson tidak ditemukan di course ini")

    content.name = data.name
    content.description = data.description
    content.video_url = data.video_url
    content.course_id = new_course
    content.parent_id = new_parent
    content.save()

    return content


@apiv1.delete("/contents/{id}", auth=apiAuth, tags=["Course Content"])
def delete_course_content(request, id: int):
    content = CourseContent.objects.filter(id=id).select_related("course_id").first()
    if not content:
        raise HttpError(404, "Lesson tidak ditemukan")

    if content.course_id.teacher.id != request.user.id and not request.user.is_superuser:
        raise HttpError(403, "Hanya pemilik course yang bisa menghapus lesson")

    content.delete()
    return {"message": "Lesson berhasil dihapus"}


# ================= ENROLL =================

@apiv1.post("/course/{id}/enroll/", auth=apiAuth, response=MessageOut, tags=["Enrollment"])
def enroll(request, id: int):
    if not request.user or not getattr(request.user, "id", None):
        raise HttpError(401, "Silakan login terlebih dahulu")

    try:
        user = User.objects.get(id=request.user.id)
    except User.DoesNotExist:
        raise HttpError(401, "User tidak ditemukan. Silakan login ulang.")

    course = Course.objects.filter(id=id).first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    if CourseMember.objects.filter(user_id=user, course_id=course).exists():
        raise HttpError(400, "Sudah enroll")

    CourseMember.objects.create(
        user_id=user,
        course_id=course,
        roles="std"
    )

    log_activity(
        user_id=user.id,
        action="enroll",
        course_id=course.id,
        course_name=course.name
    )

    send_enrollment_email.delay(user.id, course.id)

    return {"message": "Berhasil enroll course"}


@apiv1.post("/enrollments/{id}/progress/", auth=apiAuth, response=ProgressOut, tags=["Enrollment"])
def mark_progress(request, id: int, data: ProgressIn):
    enrollment = CourseMember.objects.filter(
        id=id,
        user_id=request.user
    ).select_related("course_id").first()

    if not enrollment:
        raise HttpError(404, "Enrollment tidak ditemukan")

    content = CourseContent.objects.filter(
        id=data.content_id,
        course_id=enrollment.course_id
    ).first()

    if not content:
        raise HttpError(404, "Konten tidak ditemukan di course ini")

    progress, created = Progress.objects.get_or_create(
        enrollment=enrollment,
        content=content,
    )

    total_content = CourseContent.objects.filter(course_id=enrollment.course_id).count()
    completed_content = Progress.objects.filter(enrollment=enrollment).count()
    percentage = round((completed_content / total_content) * 100, 2) if total_content else 0.0
    is_completed = total_content > 0 and completed_content >= total_content

    # Simpan snapshot progress sebagai dokumen analitik di MongoDB.
    save_learning_analytics(
        user_id=request.user.id,
        course_id=enrollment.course_id.id,
        progress_percentage=percentage,
        completed=is_completed,
    )

    log_activity(
        user_id=request.user.id,
        action="progress",
        course_id=enrollment.course_id.id,
        course_name=enrollment.course_id.name,
        metadata={"content_id": content.id, "percentage": percentage},
    )

    # Course baru selesai pada percobaan ini -> generate certificate async.
    if is_completed and created:
        generate_certificate.delay(request.user.id, enrollment.course_id.id)

    message = "Progress berhasil ditandai selesai" if created else "Konten sudah pernah ditandai selesai sebelumnya"

    return {
        "message": message,
        "progress_percentage": percentage,
        "completed": is_completed,
    }


# ================= COMMENT =================

@apiv1.post("/comments/", auth=apiAuth, tags=["Comments"])
def postComment(request, data: CommentIn):
    content = CourseContent.objects.filter(id=data.content_id).first()

    if not content:
        raise HttpError(404, "Content tidak ditemukan")

    # request.user bisa berupa TokenUser stateless yang TIDAK BOLEH
    # diassign langsung ke ForeignKey (Django mewajibkan instance User asli).
    user = User.objects.get(id=request.user.id)

    Comment.objects.create(
        comment=data.comment,
        user_id=user,
        content_id=content
    )

    return {"message": "Komentar berhasil"}


@apiv1.put("/comments/{id}", auth=apiAuth, tags=["Comments"])
def updateComment(request, id: int, data: CommentUpdate):
    comment = Comment.objects.filter(id=id).first()

    if not comment:
        raise HttpError(404, "Komentar tidak ditemukan")

    if comment.user_id_id != request.user.id:
        raise HttpError(403, "Bukan pemilik komentar")

    comment.comment = data.comment
    comment.save()

    return {"message": "Komentar diupdate"}


@apiv1.delete("/comments/{id}", auth=apiAuth, tags=["Comments"])
def deleteComment(request, id: int):
    comment = Comment.objects.select_related("content_id__course_id")\
        .filter(id=id).first()

    if not comment:
        raise HttpError(404, "Komentar tidak ditemukan")

    is_owner = comment.user_id_id == request.user.id
    is_course_teacher = comment.content_id.course_id.teacher_id == request.user.id
    is_admin = bool(getattr(request.user, "is_superuser", False))

    if is_owner or is_course_teacher or is_admin:
        comment.delete()
        return {"message": "Komentar dihapus"}

    raise HttpError(403, "Tidak punya akses")


# ================= ANALYTICS (MongoDB aggregation, admin only) — Paket 5 =================

@apiv1.get("/analytics/activity-by-action/", auth=apiAuth, tags=["Analytics"])
def activity_by_action(request):
    require_role(request.user, ["admin"])

    data = report_activity_by_action()

    for item in data:
        item["_id"] = str(item["_id"])

    return data


@apiv1.get("/analytics/daily-active-users/", auth=apiAuth, tags=["Analytics"])
def daily_active_users(request):
    """Aggregation query MongoDB - daily active users"""
    require_role(request.user, ["admin"])
    return report_daily_active_users()


@apiv1.get("/analytics/course-popularity/", auth=apiAuth, tags=["Analytics"])
def course_popularity(request):
    """Aggregation query MongoDB - course popularity"""
    require_role(request.user, ["admin"])

    data = report_course_popularity()
    for item in data:
        item["_id"] = str(item["_id"])
    return data


@apiv1.get("/analytics/completion-summary/", auth=apiAuth, tags=["Analytics"])
def completion_summary(request):
    """Aggregation query MongoDB - completion summary"""
    require_role(request.user, ["admin"])
    return report_completion_summary()


@apiv1.get("/analytics/course-report/", auth=apiAuth, response=List[CourseReportOut], tags=["Analytics"])
def course_report(request):
    """
    Course analytics report' -- statistik popularitas, total
    enrollment, completion rate per course. Sumber data: tabel
    CourseStatistics di PostgreSQL, yang diperbarui otomatis tiap 5 menit
    oleh Celery Beat task `update_course_statistics`.
    """
    require_role(request.user, ["admin", "instructor"])

    stats = CourseStatistics.objects.select_related("course").all()

    return [
        {
            "course_id": s.course.id,
            "course_name": s.course.name,
            "enrollment_count": s.enrollment_count,
            "completed_count": s.completed_count,
            "completion_rate": s.completion_rate,
            "updated_at": s.updated_at,
        }
        for s in stats
    ]


# ================= CERTIFICATES =================

@apiv1.get("/certificates/my/", auth=apiAuth, response=List[CertificateOut], tags=["Certificates"])
def my_certificates(request):
    return Certificate.objects.filter(user_id=request.user.id).select_related("course")


# ================= ADMIN TASKS (Celery async, admin only) =================

@apiv1.post("/admin/tasks/export-report/", auth=apiAuth, response=TaskTriggerOut, tags=["Admin Tasks"])
def trigger_export_report(request):
    require_role(request.user, ["admin"])

    task = export_course_report.delay()
    return {"message": "Export report CSV dijadwalkan sebagai background task", "task_id": task.id}


@apiv1.post("/admin/tasks/update-statistics/", auth=apiAuth, response=TaskTriggerOut, tags=["Admin Tasks"])
def trigger_update_statistics(request):
    require_role(request.user, ["admin"])

    task = update_course_statistics.delay()
    return {"message": "Update statistik course dijadwalkan sebagai background task", "task_id": task.id}


@apiv1.get("/admin/tasks/export-report/download/", auth=apiAuth, tags=["Admin Tasks"])
def download_course_report(request):
    """Download hasil CSV terakhir dari task export_course_report."""
    require_role(request.user, ["admin"])

    file_path = os.path.join(django_settings.BASE_DIR, "reports", "course_report.csv")

    if not os.path.exists(file_path):
        raise HttpError(404, "Report belum pernah dibuat. Jalankan POST /admin/tasks/export-report/ dulu.")

    return FileResponse(open(file_path, "rb"), as_attachment=True, filename="course_report.csv")


@apiv1.get("/tasks/{task_id}/status/", auth=apiAuth, response=TaskStatusOut, tags=["Admin Tasks"])
def task_status(request, task_id: str):
    """Cek status Celery task: PENDING, STARTED, SUCCESS, FAILURE."""
    result = AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": result.status,
        "result": str(result.result) if result.ready() else None,
    }