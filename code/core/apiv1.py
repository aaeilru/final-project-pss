from typing import List

from django.contrib.auth.models import User
from ninja import NinjaAPI
from ninja.errors import HttpError

from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth

from courses.models import Course, CourseMember, CourseContent, Comment
from core.schemas import (
    UserOut,
    UserUpdate,
    Register,
    CourseIn,
    CourseOut,
    DetailCourseOut,
    CourseMemberOut,
    CommentIn,
    CommentUpdate,
    ProgressIn,
    MessageOut,
)

from django.core.cache import cache
from ninja.errors import HttpError
from analytics.mongo_service import log_activity
from courses.tasks import send_enrollment_email, generate_certificate, update_course_statistics, export_course_report
from analytics.mongo_service import report_activity_by_action, report_activity_by_course
from core.rate_limit import rate_limit


# INIT API
apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
)

apiv1.add_router("/auth/", mobile_auth_router)
apiAuth = HttpJwtAuth()


# ================= AUTH =================

@apiv1.post("/register/", response={201: UserOut})
def register(request, data: Register):
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah digunakan")

    user = User.objects.create_user(**data.dict())
    return 201, user


@apiv1.get("/profile/", auth=apiAuth, response=UserOut)
def profile(request):
    return request.user


@apiv1.put("/profile/", auth=apiAuth, response=UserOut)
def update_profile(request, data: UserUpdate):
    user = request.user

    if User.objects.filter(email=data.email).exclude(id=user.id).exists():
        raise HttpError(400, "Email sudah digunakan")

    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.save()

    return user


@apiv1.get("/auth/me/", auth=apiAuth, response=UserOut)
def auth_me(request):
    return request.user


@apiv1.put("/auth/me/", auth=apiAuth, response=UserOut)
def auth_update_me(request, data: UserUpdate):
    user = request.user

    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.save()

    return user

# ================= COURSE =================

@apiv1.get("/enrollments/my-courses/", auth=apiAuth, response=List[CourseMemberOut])
def my_courses(request):
    return CourseMember.objects.filter(
        user_id=request.user
    ).select_related("course_id", "user_id")


@apiv1.get("/courses/", response=list, tags=["Courses"])
def listCourses(request):
    rate_limit(request)
    cache_key = "courses_list"

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    courses = []

    for course in Course.objects.select_related("teacher").all():
        courses.append({
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "price": course.price,
            "teacher": course.teacher.username,
        })

    cache.set(cache_key, courses, timeout=300)

    return courses


@apiv1.get("/courses/{id}", response=dict, tags=["Courses"])
def detailCourse(request, id: int):
    rate_limit(request)
    cache_key = f"course_detail:{id}"

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    course = Course.objects.filter(id=id).select_related("teacher").first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    data = {
        "id": course.id,
        "name": course.name,
        "description": course.description,
        "price": course.price,
        "teacher": course.teacher.username,
    }

    cache.set(cache_key, data, timeout=300)

    return data


@apiv1.post("/courses/", auth=apiAuth, response={201: CourseOut})
def createCourse(request, data: CourseIn):

    if data.price < 0:
        raise HttpError(400, "Harga tidak boleh negatif")

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


@apiv1.put("/courses/{id}", auth=apiAuth, response=CourseOut)
def updateCourse(request, id: int, data: CourseIn):
    if data.price < 0:
        raise HttpError(400, "Harga tidak boleh negatif")

    course = Course.objects.filter(id=id).first()

    if not course:
        raise HttpError(404, "Course tidak ditemukan")

    if course.teacher.id != request.user.id:
        raise HttpError(403, "Bukan pemilik course")

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


@apiv1.delete("/courses/{id}", auth=apiAuth)
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


# ================= ENROLL =================

@apiv1.post("/course/{id}/enroll/", auth=apiAuth, response=MessageOut)
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


@apiv1.post("/enrollments/{id}/progress/", auth=apiAuth, response=MessageOut)
def mark_progress(request, id: int, data: ProgressIn):
    enrollment = CourseMember.objects.filter(
        id=id,
        user_id=request.user
    ).first()

    if not enrollment:
        raise HttpError(404, "Enrollment tidak ditemukan")

    content = CourseContent.objects.filter(
        id=data.content_id,
        course_id=enrollment.course_id
    ).first()

    if not content:
        raise HttpError(404, "Konten tidak ditemukan di course ini")

    return {"message": "Progress berhasil ditandai selesai"}

# ================= COMMENT =================

@apiv1.post("/comments/", auth=apiAuth)
def postComment(request, data: CommentIn):
    content = CourseContent.objects.filter(id=data.content_id).first()

    if not content:
        raise HttpError(404, "Content tidak ditemukan")

    Comment.objects.create(
        comment=data.comment,
        user_id=request.user,
        content_id=content
    )

    return {"message": "Komentar berhasil"}


@apiv1.put("/comments/{id}", auth=apiAuth)
def updateComment(request, id: int, data: CommentUpdate):
    comment = Comment.objects.filter(id=id).first()

    if not comment:
        raise HttpError(404, "Komentar tidak ditemukan")

    if comment.user_id != request.user:
        raise HttpError(403, "Bukan pemilik komentar")

    comment.comment = data.comment
    comment.save()

    return {"message": "Komentar diupdate"}


@apiv1.delete("/comments/{id}", auth=apiAuth)
def deleteComment(request, id: int):
    comment = Comment.objects.select_related("content_id__course_id")\
        .filter(id=id).first()

    if not comment:
        raise HttpError(404, "Komentar tidak ditemukan")

    if (
        comment.user_id == request.user
        or comment.content_id.course_id.teacher == request.user
        or request.user.is_superuser
    ):
        comment.delete()
        return {"message": "Komentar dihapus"}

    raise HttpError(403, "Tidak punya akses")

@apiv1.get("/analytics/activity-by-action/", auth=apiAuth, tags=["Analytics"])
def activity_by_action(request):
    if not request.user.is_superuser:
        raise HttpError(403, "Admin only")

    data = report_activity_by_action()

    for item in data:
        item["_id"] = str(item["_id"])

    return data


@apiv1.get("/analytics/activity-by-course/", auth=apiAuth, tags=["Analytics"])
def activity_by_course(request):
    if not request.user.is_superuser:
        raise HttpError(403, "Admin only")

    data = report_activity_by_course()

    for item in data:
        item["_id"] = str(item["_id"])

    return data