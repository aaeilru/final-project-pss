from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField("nama kategori", max_length=100, unique=True)
    slug = models.SlugField("slug", max_length=120, unique=True, blank=True)
    description = models.TextField("deskripsi", default='-', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategori"


class Course(models.Model):
    name = models.CharField("nama matkul", max_length=100)
    description = models.TextField("deskripsi", default='-')
    price = models.IntegerField("harga", default=10000)
    image = models.ImageField("gambar", null=True, blank=True)

    teacher = models.ForeignKey(
        User,
        verbose_name="pengajar",
        on_delete=models.RESTRICT
    )

    category = models.ForeignKey(
        Category,
        verbose_name="kategori",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Mata Kuliah"
        verbose_name_plural = "Mata Kuliah"
        indexes = [
            # Index untuk filter/sort berdasarkan harga
            models.Index(fields=['price'], name='idx_course_price'),

            # Index komposit untuk query course berdasarkan teacher dan harga
            models.Index(fields=['teacher', 'price'], name='idx_course_teacher_price'),

            # Index untuk sorting course terbaru
            models.Index(fields=['created_at'], name='idx_course_created_at'),

            # Index tambahan untuk filter course berdasarkan kategori
            models.Index(fields=['category'], name='idx_course_category'),
        ]


ACCOUNT_ROLE_OPTIONS = [
    ('instructor', "Instructor"),
    ('student', "Student"),
]


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        "role",
        max_length=12,
        choices=ACCOUNT_ROLE_OPTIONS,
        default='student'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profil"


ROLE_OPTIONS = [
    ('std', "Siswa"),
    ('ast', "Asisten"),
]


class CourseMember(models.Model):
    course_id = models.ForeignKey(
        Course,
        verbose_name="matkul",
        on_delete=models.RESTRICT
    )

    user_id = models.ForeignKey(
        User,
        verbose_name="siswa",
        on_delete=models.RESTRICT
    )

    roles = models.CharField(
        "peran",
        max_length=3,
        choices=ROLE_OPTIONS,
        default='std'
    )

    def __str__(self):
        return f"{self.user_id} - {self.course_id} ({self.roles})"

    class Meta:
        verbose_name = "Anggota Kelas"
        verbose_name_plural = "Anggota Kelas"
        indexes = [
            # Sering dipakai: semua member dari course tertentu
            models.Index(fields=['course_id'], name='idx_coursemember_course'),

            # Sering dipakai: semua course yang diikuti user tertentu
            models.Index(fields=['user_id'], name='idx_coursemember_user'),

            # Filter berdasarkan role dalam sebuah course
            models.Index(fields=['course_id', 'roles'], name='idx_coursemember_course_role'),
        ]


class CourseContent(models.Model):
    name = models.CharField("judul konten", max_length=200)
    description = models.TextField("deskripsi", default='-')

    video_url = models.CharField(
        'URL Video',
        max_length=200,
        null=True,
        blank=True
    )

    file_attachment = models.FileField(
        "File",
        null=True,
        blank=True
    )

    course_id = models.ForeignKey(
        Course,
        verbose_name="matkul",
        on_delete=models.RESTRICT
    )

    parent_id = models.ForeignKey(
        "self",
        verbose_name="induk",
        on_delete=models.RESTRICT,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Konten Kelas"
        verbose_name_plural = "Konten Kelas"
        indexes = [
            # Sering dipakai: semua konten dari course tertentu
            models.Index(fields=['course_id'], name='idx_coursecontent_course'),
        ]


class Progress(models.Model):
    enrollment = models.ForeignKey(
        CourseMember,
        verbose_name="enrollment",
        on_delete=models.CASCADE,
        related_name="progress_set"
    )

    content = models.ForeignKey(
        CourseContent,
        verbose_name="konten",
        on_delete=models.CASCADE,
        related_name="progress_set"
    )

    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.enrollment.user_id} selesai {self.content}"

    class Meta:
        verbose_name = "Progress"
        verbose_name_plural = "Progress"
        constraints = [
            models.UniqueConstraint(
                fields=['enrollment', 'content'],
                name='uniq_progress_member_content'
            )
        ]
        indexes = [
            # Sering dipakai untuk melihat progress milik enrollment tertentu
            models.Index(fields=['enrollment'], name='idx_progress_enrollment'),

            # Sering dipakai untuk melihat siapa saja yang menyelesaikan konten tertentu
            models.Index(fields=['content'], name='idx_progress_content'),
        ]


class Comment(models.Model):
    content_id = models.ForeignKey(
        CourseContent,
        verbose_name="konten",
        on_delete=models.CASCADE
    )

    user_id = models.ForeignKey(
        User,
        verbose_name="pengguna",
        on_delete=models.CASCADE
    )

    comment = models.TextField('komentar')

    def __str__(self):
        return f"Komentar oleh {self.user_id} pada {self.content_id}"

    class Meta:
        verbose_name = "Komentar"
        verbose_name_plural = "Komentar"
        indexes = [
            # Sering dipakai: semua komentar pada konten tertentu
            models.Index(fields=['content_id'], name='idx_comment_content'),
        ]

class Certificate(models.Model):
    """
    Dibuat otomatis (async, lewat Celery) ketika seorang student
    menyelesaikan 100% konten sebuah course. Field `code` adalah kode unik
    yang bisa dipakai untuk verifikasi (mirip nomor seri sertifikat asli).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    code = models.CharField(max_length=40, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate {self.code} - {self.user.username} - {self.course.name}"

    class Meta:
        verbose_name = "Certificate"
        verbose_name_plural = "Certificates"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'course'],
                name='uniq_certificate_user_course',
            )
        ]


class CourseStatistics(models.Model):
    """
    Snapshot statistik per course. Diperbarui secara periodik oleh Celery
    Beat task `update_course_statistics` (setiap 5 menit) — bukan dihitung
    real-time di setiap request, supaya endpoint laporan tetap ringan.
    """
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="statistics")
    enrollment_count = models.IntegerField(default=0)
    completed_count = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0.0)  # dalam persen, 0-100
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Statistik {self.course.name} ({self.completion_rate}% selesai)"

    class Meta:
        verbose_name = "Statistik Course"
        verbose_name_plural = "Statistik Course"