import csv
import os
import time
import uuid

from celery import shared_task
from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import send_mail

from courses.models import Course, CourseMember, CourseContent, Progress, Certificate, CourseStatistics


@shared_task
def send_enrollment_email(user_id, course_id):
    """
    Mengirim email konfirmasi enrollment secara async lewat Django email
    backend (di development/testing pakai console/locmem backend, jadi
    "terkirim" dalam arti tercatat di log/outbox -- ini yang dimaksud
    "mock email" di soal final project).
    """
    user = User.objects.get(id=user_id)
    course = Course.objects.get(id=course_id)

    # Simulasi proses yang agak berat (mis. rendering template email)
    time.sleep(1)

    send_mail(
        subject=f"Berhasil enroll: {course.name}",
        message=(
            f"Halo {user.first_name or user.username},\n\n"
            f"Anda berhasil mendaftar ke course \"{course.name}\".\n"
            f"Selamat belajar!"
        ),
        from_email="no-reply@simplelms.local",
        recipient_list=[user.email],
        fail_silently=False,
    )

    return f"Email enrollment dikirim ke {user.email} untuk course {course.name}"


@shared_task
def generate_certificate(user_id, course_id):
    """
    Dipicu otomatis saat student menyelesaikan 100% konten sebuah course
    (lihat endpoint mark_progress di core/apiv1.py). Idempoten: jika
    certificate untuk pasangan user+course ini sudah ada, tidak dibuat
    ulang -- cukup dikembalikan code yang sudah ada.
    """
    user = User.objects.get(id=user_id)
    course = Course.objects.get(id=course_id)

    time.sleep(1)

    certificate = Certificate.objects.filter(user=user, course=course).first()
    if certificate is None:
        code = f"CERT-{uuid.uuid4().hex[:10].upper()}"
        certificate = Certificate.objects.create(user=user, course=course, code=code)

    return {
        "certificate_code": certificate.code,
        "user": user.username,
        "course": course.name,
    }


@shared_task
def update_course_statistics():
    """
    Celery Beat task (jalan otomatis tiap 5 menit, lihat CELERY_BEAT_SCHEDULE
    di settings.py). Menghitung ulang enrollment_count, completed_count, dan
    completion_rate untuk SETIAP course, lalu menyimpannya ke tabel
    CourseStatistics -- supaya endpoint laporan (Paket 5: Course analytics
    report) tinggal baca data yang sudah dihitung, tanpa query berat
    setiap kali ada request.
    """
    updated = []

    for course in Course.objects.all():
        enrollment_count = CourseMember.objects.filter(course_id=course).count()
        total_content = CourseContent.objects.filter(course_id=course).count()

        completed_count = 0
        if total_content > 0:
            for enrollment in CourseMember.objects.filter(course_id=course):
                done = Progress.objects.filter(enrollment=enrollment).count()
                if done >= total_content:
                    completed_count += 1

        completion_rate = (
            round((completed_count / enrollment_count) * 100, 2)
            if enrollment_count else 0.0
        )

        CourseStatistics.objects.update_or_create(
            course=course,
            defaults={
                "enrollment_count": enrollment_count,
                "completed_count": completed_count,
                "completion_rate": completion_rate,
            },
        )

        updated.append({
            "course_id": course.id,
            "course_name": course.name,
            "enrollment_count": enrollment_count,
            "completion_rate": completion_rate,
        })

    return updated


@shared_task
def export_course_report():
    """Generate file CSV laporan course (background task, dipicu admin)."""
    report_dir = os.path.join(settings.BASE_DIR, "reports")
    os.makedirs(report_dir, exist_ok=True)

    file_path = os.path.join(report_dir, "course_report.csv")

    courses = Course.objects.select_related("teacher").all()

    with open(file_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Course ID", "Course Name", "Teacher", "Price", "Enrollment Count"
        ])

        for course in courses:
            enrollment_count = CourseMember.objects.filter(course_id=course).count()
            writer.writerow([
                course.id, course.name, course.teacher.username,
                course.price, enrollment_count,
            ])

    return file_path