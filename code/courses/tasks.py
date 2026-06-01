import csv
import os
import time

from celery import shared_task
from django.contrib.auth.models import User
from django.conf import settings

from courses.models import Course, CourseMember


@shared_task
def send_enrollment_email(user_id, course_id):
    user = User.objects.get(id=user_id)
    course = Course.objects.get(id=course_id)

    time.sleep(2)

    message = f"Email enrollment sent to {user.email} for course {course.name}"
    print(message)

    return message


@shared_task
def generate_certificate(user_id, course_id):
    user = User.objects.get(id=user_id)
    course = Course.objects.get(id=course_id)

    time.sleep(3)

    certificate_text = f"Certificate generated for {user.username} - {course.name}"
    print(certificate_text)

    return certificate_text


@shared_task
def update_course_statistics():
    updated = []

    for course in Course.objects.all():
        enrollment_count = CourseMember.objects.filter(course_id=course).count()
        updated.append({
            "course_id": course.id,
            "course_name": course.name,
            "enrollment_count": enrollment_count,
        })

    print("Course statistics updated")
    return updated


@shared_task
def export_course_report():
    report_dir = os.path.join(settings.BASE_DIR, "reports")
    os.makedirs(report_dir, exist_ok=True)

    file_path = os.path.join(report_dir, "course_report.csv")

    courses = Course.objects.all()

    with open(file_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Course ID",
            "Course Name",
            "Teacher",
            "Price",
            "Enrollment Count"
        ])

        for course in courses:
            enrollment_count = CourseMember.objects.filter(course_id=course).count()
            writer.writerow([
                course.id,
                course.name,
                course.teacher.username,
                course.price,
                enrollment_count,
            ])

    return file_path