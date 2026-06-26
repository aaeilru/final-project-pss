"""
Test suite untuk Simple LMS Final Project.

Jalankan dengan (tanpa Docker, pakai SQLite + Celery eager):
    DJANGO_SETTINGS_MODULE=lms.settings_test python manage.py test courses -v 2
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from courses.models import Category, Course, CourseContent, CourseMember, Profile, Progress
from django.core import mail
from courses.models import (
    Category, Course, CourseContent, CourseMember, Profile, Progress,
    Certificate, CourseStatistics,
)
from courses.tasks import update_course_statistics, generate_certificate
from analytics.mongo_service import activity_logs, learning_analytics


class BaseAPITestCase(TestCase):
    """Helper umum: bikin user dengan role, login, dapat access token."""

    def create_user(self, username, password="password123", role="student", superuser=False):
        if superuser:
            user = User.objects.create_superuser(
                username=username, email=f"{username}@test.com", password=password
            )
        else:
            user = User.objects.create_user(
                username=username, email=f"{username}@test.com", password=password
            )
            Profile.objects.create(user=user, role=role)
        return user

    def login(self, username, password="password123"):
        response = self.client.post(
            "/api/v1/auth/sign-in",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["access"]

    def auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class ProfileUpdateTests(BaseAPITestCase):
    """Regression test: request.user (TokenUser stateless) tidak boleh di .save()."""

    def setUp(self):
        self.user = self.create_user("profileuser", role="student")

    def test_update_profile_endpoint(self):
        token = self.login("profileuser")
        response = self.client.put(
            "/api/v1/profile/",
            data=json.dumps({
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@test.com",
            }),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.email, "updated@test.com")

    def test_update_auth_me_endpoint(self):
        token = self.login("profileuser")
        response = self.client.put(
            "/api/v1/auth/me/",
            data=json.dumps({
                "first_name": "AnotherUpdate",
                "last_name": "Name",
                "email": "anotherupdate@test.com",
            }),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "AnotherUpdate")


class RegistrationTests(BaseAPITestCase):
    def test_register_default_role_is_student(self):
        response = self.client.post(
            "/api/v1/register/",
            data=json.dumps({
                "username": "newstudent",
                "password": "password123",
                "email": "newstudent@test.com",
                "first_name": "New",
                "last_name": "Student",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        user = User.objects.get(username="newstudent")
        self.assertEqual(user.profile.role, "student")

    def test_register_can_choose_instructor_role(self):
        response = self.client.post(
            "/api/v1/register/",
            data=json.dumps({
                "username": "newinstructor",
                "password": "password123",
                "email": "newinstructor@test.com",
                "first_name": "New",
                "last_name": "Instructor",
                "role": "instructor",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        user = User.objects.get(username="newinstructor")
        self.assertEqual(user.profile.role, "instructor")

    def test_register_cannot_self_assign_admin_role(self):
        """Mencoba daftar dengan role='admin' harus otomatis jatuh ke 'student'."""
        response = self.client.post(
            "/api/v1/register/",
            data=json.dumps({
                "username": "sneaky",
                "password": "password123",
                "email": "sneaky@test.com",
                "first_name": "Sneaky",
                "last_name": "User",
                "role": "admin",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        user = User.objects.get(username="sneaky")
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.role, "student")

    def test_register_duplicate_username_rejected(self):
        self.create_user("duplicate", role="student")
        response = self.client.post(
            "/api/v1/register/",
            data=json.dumps({
                "username": "duplicate",
                "password": "password123",
                "email": "duplicate2@test.com",
                "first_name": "A",
                "last_name": "B",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class CourseRBACTests(BaseAPITestCase):
    def setUp(self):
        self.student = self.create_user("student1", role="student")
        self.instructor = self.create_user("instructor1", role="instructor")
        self.admin = self.create_user("admin1", superuser=True)

    def test_student_cannot_create_course(self):
        token = self.login("student1")
        response = self.client.post(
            "/api/v1/courses/",
            data=json.dumps({"name": "Course X", "description": "desc", "price": 10000}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_instructor_can_create_course(self):
        token = self.login("instructor1")
        response = self.client.post(
            "/api/v1/courses/",
            data=json.dumps({"name": "Course Y", "description": "desc", "price": 10000}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Course.objects.filter(name="Course Y").exists())

    def test_admin_can_create_course(self):
        token = self.login("admin1")
        response = self.client.post(
            "/api/v1/courses/",
            data=json.dumps({"name": "Course Z", "description": "desc", "price": 10000}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_course_create_rejects_negative_price(self):
        token = self.login("instructor1")
        response = self.client.post(
            "/api/v1/courses/",
            data=json.dumps({"name": "Course Negative", "description": "desc", "price": -100}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_course_list_is_public(self):
        Course.objects.create(name="Public Course", teacher=self.instructor)
        response = self.client.get("/api/v1/courses/")
        self.assertEqual(response.status_code, 200)
        names = [c["name"] for c in response.json()]
        self.assertIn("Public Course", names)

    def test_only_owner_can_update_course(self):
        course = Course.objects.create(name="Owned Course", teacher=self.instructor)
        self.create_user("instructor2", role="instructor")

        token = self.login("instructor2")
        response = self.client.put(
            f"/api/v1/courses/{course.id}",
            data=json.dumps({"name": "Hacked", "description": "x", "price": 1000}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)


class CategoryTests(BaseAPITestCase):
    def setUp(self):
        self.student = self.create_user("catstudent", role="student")
        self.instructor = self.create_user("catinstructor", role="instructor")

    def test_anyone_can_list_categories(self):
        Category.objects.create(name="Web Development")
        response = self.client.get("/api/v1/categories/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_student_cannot_create_category(self):
        token = self.login("catstudent")
        response = self.client.post(
            "/api/v1/categories/",
            data=json.dumps({"name": "Data Science"}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_instructor_can_create_category(self):
        token = self.login("catinstructor")
        response = self.client.post(
            "/api/v1/categories/",
            data=json.dumps({"name": "Mobile Development"}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Category.objects.filter(name="Mobile Development").exists())


class EnrollmentProgressTests(BaseAPITestCase):
    def setUp(self):
        self.instructor = self.create_user("teacher_x", role="instructor")
        self.student = self.create_user("student_x", role="student")
        self.course = Course.objects.create(name="Django Basics", teacher=self.instructor)
        self.content1 = CourseContent.objects.create(name="Lesson 1", course_id=self.course)
        self.content2 = CourseContent.objects.create(name="Lesson 2", course_id=self.course)

    def test_enroll_then_progress_partial_not_completed(self):
        token = self.login("student_x")

        response = self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)

        enrollment = CourseMember.objects.get(course_id=self.course, user_id=self.student)

        response = self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content1.id}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertFalse(body["completed"])
        self.assertEqual(body["progress_percentage"], 50.0)

    def test_complete_all_content_marks_course_completed(self):
        token = self.login("student_x")
        self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        enrollment = CourseMember.objects.get(course_id=self.course, user_id=self.student)

        self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content1.id}),
            content_type="application/json",
            **self.auth_header(token),
        )
        response = self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content2.id}),
            content_type="application/json",
            **self.auth_header(token),
        )

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["completed"])
        self.assertEqual(body["progress_percentage"], 100.0)
        self.assertEqual(Progress.objects.filter(enrollment=enrollment).count(), 2)

    def test_cannot_progress_on_enrollment_of_other_user(self):
        other_student = self.create_user("student_y", role="student")
        enrollment = CourseMember.objects.create(course_id=self.course, user_id=other_student)

        token = self.login("student_x")
        response = self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content1.id}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 404)

    def test_duplicate_enroll_rejected(self):
        token = self.login("student_x")
        self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        response = self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 400)


class CommentPermissionTests(BaseAPITestCase):
    """Regression test untuk bug TokenUser vs Model instance equality."""

    def setUp(self):
        self.instructor = self.create_user("teacher_c", role="instructor")
        self.student = self.create_user("student_c", role="student")
        self.other_student = self.create_user("student_d", role="student")
        self.course = Course.objects.create(name="Comment Course", teacher=self.instructor)
        self.content = CourseContent.objects.create(name="Lesson C", course_id=self.course)

    def test_owner_can_update_own_comment(self):
        token = self.login("student_c")
        response = self.client.post(
            "/api/v1/comments/",
            data=json.dumps({"comment": "Halo", "content_id": self.content.id}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)

        from courses.models import Comment
        comment = Comment.objects.get(content_id=self.content)

        response = self.client.put(
            f"/api/v1/comments/{comment.id}",
            data=json.dumps({"comment": "Halo, sudah diedit"}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_non_owner_cannot_update_comment(self):
        from courses.models import Comment
        comment = Comment.objects.create(content_id=self.content, user_id=self.student, comment="Halo")

        token = self.login("student_d")
        response = self.client.put(
            f"/api/v1/comments/{comment.id}",
            data=json.dumps({"comment": "Coba edit punya orang"}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_course_teacher_can_delete_any_comment_on_their_course(self):
        from courses.models import Comment
        comment = Comment.objects.create(content_id=self.content, user_id=self.student, comment="Halo")

        token = self.login("teacher_c")
        response = self.client.delete(
            f"/api/v1/comments/{comment.id}",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)


class AdminOnlyEndpointTests(BaseAPITestCase):
    def setUp(self):
        self.student = self.create_user("plain_student", role="student")
        self.instructor = self.create_user("plain_instructor", role="instructor")
        self.admin = self.create_user("plain_admin", superuser=True)

    def test_student_cannot_access_analytics(self):
        token = self.login("plain_student")
        response = self.client.get(
            "/api/v1/analytics/activity-by-action/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_instructor_cannot_access_analytics(self):
        token = self.login("plain_instructor")
        response = self.client.get(
            "/api/v1/analytics/activity-by-action/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_analytics(self):
        token = self.login("plain_admin")
        response = self.client.get(
            "/api/v1/analytics/activity-by-action/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_trigger_admin_task(self):
        token = self.login("plain_instructor")
        response = self.client.post(
            "/api/v1/admin/tasks/update-statistics/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_trigger_export_report_task(self):
        """CELERY_TASK_ALWAYS_EAGER=True di settings_test -> task langsung jalan sync."""
        token = self.login("plain_admin")
        response = self.client.post(
            "/api/v1/admin/tasks/export-report/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("task_id", response.json())

    def test_admin_can_list_users_with_role(self):
        token = self.login("plain_admin")
        response = self.client.get(
            "/api/v1/admin/users/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        usernames = {u["username"]: u["role"] for u in response.json()}
        self.assertEqual(usernames["plain_student"], "student")
        self.assertEqual(usernames["plain_instructor"], "instructor")
        self.assertEqual(usernames["plain_admin"], "admin")

    def test_admin_can_promote_student_to_instructor(self):
        token = self.login("plain_admin")
        response = self.client.put(
            f"/api/v1/admin/users/{self.student.id}/role/",
            data=json.dumps({"role": "instructor"}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.student.refresh_from_db()
        self.assertEqual(self.student.profile.role, "instructor")

# =============================================================================
# PAKET 6 — Async Processing & Notification
# =============================================================================

class EmailNotificationAsyncTests(BaseAPITestCase):
    """Fitur: Email notification async."""

    def setUp(self):
        self.instructor = self.create_user("email_teacher", role="instructor")
        self.student = self.create_user("email_student", role="student")
        self.course = Course.objects.create(name="Async Email Course", teacher=self.instructor)
        mail.outbox = []

    def test_enroll_sends_email_via_celery_task(self):
        token = self.login("email_student")
        response = self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)

        # CELERY_TASK_ALWAYS_EAGER=True -> task jalan sync, email langsung
        # masuk ke outbox tanpa perlu worker terpisah.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Async Email Course", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["email_student@test.com"])


class CertificateGenerationAsyncTests(BaseAPITestCase):
    """Fitur: Generate certificate/report async."""

    def setUp(self):
        self.instructor = self.create_user("cert_teacher", role="instructor")
        self.student = self.create_user("cert_student", role="student")
        self.course = Course.objects.create(name="Certificate Course", teacher=self.instructor)
        self.content = CourseContent.objects.create(name="Only Lesson", course_id=self.course)

    def test_certificate_created_when_course_completed(self):
        token = self.login("cert_student")
        self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        enrollment = CourseMember.objects.get(course_id=self.course, user_id=self.student)

        response = self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content.id}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["completed"])

        certificate = Certificate.objects.filter(user=self.student, course=self.course).first()
        self.assertIsNotNone(certificate)
        self.assertTrue(certificate.code.startswith("CERT-"))

    def test_certificate_generation_is_idempotent(self):
        """Generate certificate 2x untuk user+course yang sama -> tidak duplikat."""
        generate_certificate(self.student.id, self.course.id)
        generate_certificate(self.student.id, self.course.id)

        count = Certificate.objects.filter(user=self.student, course=self.course).count()
        self.assertEqual(count, 1)

    def test_my_certificates_endpoint(self):
        generate_certificate(self.student.id, self.course.id)

        token = self.login("cert_student")
        response = self.client.get(
            "/api/v1/certificates/my/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["course_name"], "Certificate Course")


class ScheduledTaskStatisticsTests(BaseAPITestCase):
    """Fitur: Scheduled task (Celery Beat) -- update_course_statistics."""

    def setUp(self):
        self.instructor = self.create_user("stats_teacher", role="instructor")
        self.admin = self.create_user("stats_admin", superuser=True)
        self.course = Course.objects.create(name="Stats Course", teacher=self.instructor)
        self.content = CourseContent.objects.create(name="Lesson", course_id=self.course)

        # 2 student enroll, hanya 1 yang menyelesaikan lesson-nya
        self.student1 = self.create_user("stats_student1", role="student")
        self.student2 = self.create_user("stats_student2", role="student")
        self.enrollment1 = CourseMember.objects.create(course_id=self.course, user_id=self.student1)
        self.enrollment2 = CourseMember.objects.create(course_id=self.course, user_id=self.student2)
        Progress.objects.create(enrollment=self.enrollment1, content=self.content)

    def test_update_course_statistics_persists_correct_numbers(self):
        update_course_statistics()

        stats = CourseStatistics.objects.get(course=self.course)
        self.assertEqual(stats.enrollment_count, 2)
        self.assertEqual(stats.completed_count, 1)
        self.assertEqual(stats.completion_rate, 50.0)

    def test_course_report_endpoint_reads_statistics_table(self):
        update_course_statistics()

        token = self.login("stats_admin")
        response = self.client.get(
            "/api/v1/analytics/course-report/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        report = next(r for r in response.json() if r["course_name"] == "Stats Course")
        self.assertEqual(report["enrollment_count"], 2)
        self.assertEqual(report["completion_rate"], 50.0)

    def test_instructor_can_also_view_course_report(self):
        update_course_statistics()
        token = self.login("stats_teacher")
        response = self.client.get(
            "/api/v1/analytics/course-report/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200)

    def test_student_cannot_view_course_report(self):
        update_course_statistics()
        token = self.login("stats_student1")
        response = self.client.get(
            "/api/v1/analytics/course-report/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 403)


class ExportReportDownloadTests(BaseAPITestCase):
    """Fitur: Generate report async + download hasilnya."""

    def setUp(self):
        self.admin = self.create_user("export_admin", superuser=True)
        Course.objects.create(name="Export Course", teacher=self.create_user("export_teacher", role="instructor"))

        # File CSV report ditulis ke disk (bukan ke database test yang
        # otomatis di-rollback), jadi harus dibersihkan manual supaya tidak
        # bocor antar test / antar test class.
        import os
        from django.conf import settings as django_settings
        self.report_path = os.path.join(django_settings.BASE_DIR, "reports", "course_report.csv")
        if os.path.exists(self.report_path):
            os.remove(self.report_path)

    def tearDown(self):
        import os
        if os.path.exists(self.report_path):
            os.remove(self.report_path)

    def test_download_before_export_returns_404(self):
        token = self.login("export_admin")
        response = self.client.get(
            "/api/v1/admin/tasks/export-report/download/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 404)

    def test_export_then_download_returns_csv(self):
        token = self.login("export_admin")

        response = self.client.post(
            "/api/v1/admin/tasks/export-report/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.get(
            "/api/v1/admin/tasks/export-report/download/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content)
        self.assertIn(b"Export Course", content)


class TaskStatusEndpointTests(BaseAPITestCase):
    """Fitur: Task status endpoint."""

    def setUp(self):
        self.admin = self.create_user("taskstatus_admin", superuser=True)

    def test_task_status_returns_success_after_eager_execution(self):
        token = self.login("taskstatus_admin")

        trigger = self.client.post(
            "/api/v1/admin/tasks/update-statistics/",
            **self.auth_header(token),
        )
        task_id = trigger.json()["task_id"]

        response = self.client.get(
            f"/api/v1/tasks/{task_id}/status/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        # CELERY_TASK_ALWAYS_EAGER=True -> task selesai sebelum response trigger dikirim
        self.assertEqual(response.json()["status"], "SUCCESS")


# =============================================================================
# PAKET 5 — Analytics & Activity Tracking
# =============================================================================

class ActivityLoggingMongoTests(BaseAPITestCase):
    """Fitur: Activity logging ke MongoDB."""

    def setUp(self):
        activity_logs.delete_many({})
        self.instructor = self.create_user("alog_teacher", role="instructor")

    def test_create_course_writes_activity_log(self):
        token = self.login("alog_teacher")
        response = self.client.post(
            "/api/v1/courses/",
            data=json.dumps({"name": "Logged Course", "description": "x", "price": 1000}),
            content_type="application/json",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 201, response.content)

        log = activity_logs.find_one({"action": "create_course", "course_name": "Logged Course"})
        self.assertIsNotNone(log)
        self.assertEqual(log["user_id"], self.instructor.id)


class LearningAnalyticsCollectionTests(BaseAPITestCase):
    """Fitur: Learning analytics collection."""

    def setUp(self):
        learning_analytics.delete_many({})
        self.instructor = self.create_user("lac_teacher", role="instructor")
        self.student = self.create_user("lac_student", role="student")
        self.course = Course.objects.create(name="Analytics Course", teacher=self.instructor)
        self.content = CourseContent.objects.create(name="Lesson", course_id=self.course)

    def test_mark_progress_saves_snapshot_to_mongo(self):
        token = self.login("lac_student")
        self.client.post(
            f"/api/v1/course/{self.course.id}/enroll/",
            content_type="application/json",
            **self.auth_header(token),
        )
        enrollment = CourseMember.objects.get(course_id=self.course, user_id=self.student)

        self.client.post(
            f"/api/v1/enrollments/{enrollment.id}/progress/",
            data=json.dumps({"content_id": self.content.id}),
            content_type="application/json",
            **self.auth_header(token),
        )

        snapshot = learning_analytics.find_one({
            "user_id": self.student.id,
            "course_id": self.course.id,
        })
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["progress_percentage"], 100.0)
        self.assertTrue(snapshot["completed"])


class MongoAggregationTests(BaseAPITestCase):
    """Fitur: Aggregation query MongoDB (DAU, course popularity, completion summary)."""

    def setUp(self):
        activity_logs.delete_many({})
        learning_analytics.delete_many({})
        self.admin = self.create_user("agg_admin", superuser=True)

        from datetime import datetime
        activity_logs.insert_many([
            {"user_id": 1, "action": "enroll", "course_id": 10, "course_name": "Math",
             "timestamp": datetime(2026, 6, 1), "metadata": {}},
            {"user_id": 2, "action": "enroll", "course_id": 10, "course_name": "Math",
             "timestamp": datetime(2026, 6, 1), "metadata": {}},
            {"user_id": 1, "action": "progress", "course_id": 10, "course_name": "Math",
             "timestamp": datetime(2026, 6, 2), "metadata": {}},
            {"user_id": 3, "action": "enroll", "course_id": 20, "course_name": "Physics",
             "timestamp": datetime(2026, 6, 2), "metadata": {}},
        ])

        learning_analytics.insert_many([
            {"user_id": 1, "course_id": 10, "progress_percentage": 100.0, "completed": True,
             "timestamp": datetime(2026, 6, 2)},
            {"user_id": 2, "course_id": 10, "progress_percentage": 50.0, "completed": False,
             "timestamp": datetime(2026, 6, 2)},
            {"user_id": 3, "course_id": 20, "progress_percentage": 100.0, "completed": True,
             "timestamp": datetime(2026, 6, 2)},
        ])

    def test_daily_active_users(self):
        token = self.login("agg_admin")
        response = self.client.get(
            "/api/v1/analytics/daily-active-users/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = {item["_id"]: item["total_active_users"] for item in response.json()}
        self.assertEqual(data["2026-06-01"], 2)  # user 1 dan 2
        self.assertEqual(data["2026-06-02"], 2)  # user 1 dan 3

    def test_course_popularity(self):
        token = self.login("agg_admin")
        response = self.client.get(
            "/api/v1/analytics/course-popularity/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        math_entry = next(item for item in data if item["_id"] == "Math")
        self.assertEqual(math_entry["total_activity"], 3)
        self.assertEqual(math_entry["unique_user_count"], 2)

    def test_completion_summary(self):
        token = self.login("agg_admin")
        response = self.client.get(
            "/api/v1/analytics/completion-summary/",
            **self.auth_header(token),
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = {item["_id"]: item for item in response.json()}
        self.assertEqual(data[10]["completed_snapshots"], 1)
        self.assertEqual(data[10]["total_snapshots"], 2)
        self.assertEqual(data[10]["completion_ratio_percent"], 50.0)
        self.assertEqual(data[20]["completion_ratio_percent"], 100.0)

    def test_non_admin_cannot_access_aggregation_endpoints(self):
        student = self.create_user("agg_student", role="student")
        token = self.login("agg_student")
        for path in [
            "/api/v1/analytics/daily-active-users/",
            "/api/v1/analytics/course-popularity/",
            "/api/v1/analytics/completion-summary/",
        ]:
            response = self.client.get(path, **self.auth_header(token))
            self.assertEqual(response.status_code, 403, f"{path} should be admin-only")