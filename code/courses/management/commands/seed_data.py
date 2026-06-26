"""
Management command untuk mengisi database dengan data dummy.

Jalankan dengan:
    python manage.py seed_data

Data yang dibuat:
    - 3 akun demo dengan role jelas: admin01 (admin), dosen01 (instructor), mhs001 (student)
    - 8 Category (kategori mata kuliah)
    - 20 User pengajar (dosen01 - dosen20) dengan Profile role=instructor
    - 80 User mahasiswa (mhs001 - mhs080) dengan Profile role=student
    - 100 Course (mata kuliah), masing-masing terhubung ke Category
    - 500 CourseMember (anggota kelas / enrollment)
    - 300 CourseContent (konten/materi kelas)
    - 1000+ Comment (komentar pada konten)
    - Sebagian Progress (riwayat belajar) untuk mendemokan fitur progress & certificate

Semua operasi INSERT menggunakan bulk_create (sesuai Modul 05 Bagian 6).
Command ini idempoten: aman dijalankan berulang kali tanpa membuat duplikat.
"""

import random
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from courses.models import (
    Course, CourseMember, CourseContent, Comment,
    Category, Profile, Progress,
)


# =============================================================================
# Kamus data Indonesia untuk menghasilkan konten yang realistis
# =============================================================================

FIRST_NAMES = [
    'Budi', 'Siti', 'Ahmad', 'Dewi', 'Reza',
    'Putri', 'Andi', 'Rina', 'Hendra', 'Yuli',
    'Fajar', 'Nisa', 'Dimas', 'Ayu', 'Rizki',
    'Lestari', 'Wahyu', 'Maya', 'Bagas', 'Citra',
]

LAST_NAMES = [
    'Santoso', 'Wijaya', 'Kusuma', 'Rahayu', 'Pratama',
    'Sari', 'Hidayat', 'Permata', 'Nugroho', 'Lestari',
    'Wibowo', 'Mahendra', 'Putra', 'Dewi', 'Susanto',
    'Kurniawan', 'Handoko', 'Utama', 'Saputra', 'Prabowo',
]

CATEGORIES = [
    ('Pengembangan Web', 'Topik seputar pengembangan aplikasi web, frontend dan backend.'),
    ('Basis Data', 'Topik seputar perancangan dan pengelolaan database.'),
    ('Kecerdasan Buatan', 'Topik seputar machine learning, deep learning, dan AI.'),
    ('Keamanan Siber', 'Topik seputar keamanan sistem dan jaringan.'),
    ('Pemrograman Mobile', 'Topik seputar pengembangan aplikasi Android/iOS.'),
    ('Jaringan Komputer', 'Topik seputar infrastruktur dan jaringan komputer.'),
    ('Rekayasa Perangkat Lunak', 'Topik seputar metodologi dan praktik pengembangan software.'),
    ('Data Science', 'Topik seputar analisis data, statistika, dan visualisasi.'),
]

SUBJECTS = [
    'Pemrograman Web', 'Basis Data', 'Algoritma dan Struktur Data', 'Jaringan Komputer',
    'Sistem Operasi', 'Kecerdasan Buatan', 'Pemrograman Mobile', 'Keamanan Siber',
    'Rekayasa Perangkat Lunak', 'Pemrograman Python', 'Pemrograman Java',
    'Manajemen Proyek TI', 'Analisis dan Desain Sistem', 'Komputasi Awan',
    'Data Mining', 'Statistika', 'Matematika Diskrit', 'Arsitektur Komputer',
    'Grafika Komputer', 'Interaksi Manusia Komputer',
]

# Mapping kasar subject -> nama kategori (dipakai untuk seeding course.category)
SUBJECT_CATEGORY_MAP = {
    'Pemrograman Web': 'Pengembangan Web',
    'Basis Data': 'Basis Data',
    'Algoritma dan Struktur Data': 'Rekayasa Perangkat Lunak',
    'Jaringan Komputer': 'Jaringan Komputer',
    'Sistem Operasi': 'Jaringan Komputer',
    'Kecerdasan Buatan': 'Kecerdasan Buatan',
    'Pemrograman Mobile': 'Pemrograman Mobile',
    'Keamanan Siber': 'Keamanan Siber',
    'Rekayasa Perangkat Lunak': 'Rekayasa Perangkat Lunak',
    'Pemrograman Python': 'Pengembangan Web',
    'Pemrograman Java': 'Pengembangan Web',
    'Manajemen Proyek TI': 'Rekayasa Perangkat Lunak',
    'Analisis dan Desain Sistem': 'Rekayasa Perangkat Lunak',
    'Komputasi Awan': 'Jaringan Komputer',
    'Data Mining': 'Data Science',
    'Statistika': 'Data Science',
    'Matematika Diskrit': 'Data Science',
    'Arsitektur Komputer': 'Jaringan Komputer',
    'Grafika Komputer': 'Pengembangan Web',
    'Interaksi Manusia Komputer': 'Pengembangan Web',
}

CONTENT_PREFIXES = [
    'Pengantar', 'Konsep Dasar', 'Praktikum', 'Latihan', 'Kuis',
    'Modul', 'Materi', 'Diskusi', 'Proyek', 'Tugas',
]

CONTENT_TOPICS = [
    'Variabel dan Tipe Data', 'Struktur Kontrol', 'Fungsi dan Prosedur', 'Array dan List',
    'Object Oriented Programming', 'Database Design', 'Query SQL', 'Normalisasi Database',
    'REST API', 'Autentikasi dan Otorisasi', 'Deployment Aplikasi', 'Unit Testing',
    'Debugging dan Profiling', 'Optimasi Kode', 'Git dan Version Control',
    'Docker dan Containerisasi', 'Arsitektur Microservices', 'Design Pattern',
    'Clean Code', 'Dokumentasi API',
]

COMMENTS = [
    'Materi ini sangat membantu, terima kasih!',
    'Apakah ada referensi tambahan untuk topik ini?',
    'Saya belum paham bagian ini, bisa dijelaskan lagi?',
    'Keren sekali materinya, langsung saya coba praktikkan.',
    'Tugas ini cukup menantang tapi sangat bermanfaat!',
    'Mohon bantuannya untuk soal ini, sudah dicoba tapi masih bingung.',
    'Sudah dicoba tapi masih error, kira-kira kenapa ya?',
    'Terima kasih penjelasannya, sekarang sudah lebih jelas.',
    'Apakah boleh menggunakan library lain selain yang disebutkan?',
    'Saya setuju dengan pendapat teman di atas.',
    'Kapan deadline pengumpulan tugasnya?',
    'Boleh minta contoh kode yang sudah selesai sebagai referensi?',
    'Bagian ini yang paling susah menurut saya, perlu penjelasan lebih.',
    'Alhamdulillah, sudah berhasil mengerjakan!',
    'Materinya sangat relevan dengan kebutuhan industri saat ini.',
    'Apakah ada video penjelasan tambahan untuk materi ini?',
    'Terima kasih atas feedback-nya, sangat membantu perbaikan.',
    'Sudah saya coba ulang dan berhasil, terima kasih!',
    'Materinya padat dan informatif, suka sekali gaya penjelasannya.',
    'Ada yang bisa bantu explain perbedaannya dengan konsep sebelumnya?',
]

PRICES = [50000, 75000, 100000, 125000, 150000, 200000, 250000]


class Command(BaseCommand):
    help = 'Seed database dengan data dummy untuk Simple LMS Final Project'

    def handle(self, *args, **options):
        random.seed(42)

        self.stdout.write(self.style.HTTP_INFO('=' * 55))
        self.stdout.write(self.style.HTTP_INFO('  Seeding Data - Simple LMS Final Project'))
        self.stdout.write(self.style.HTTP_INFO('=' * 55))

        self._seed_demo_accounts()
        categories = self._seed_categories()
        teachers = self._seed_teachers()
        students = self._seed_students()
        courses = self._seed_courses(teachers, categories)
        members = self._seed_members(courses, students)
        contents = self._seed_contents(courses)
        self._seed_comments(contents, members)
        self._seed_progress(members, contents)

        self._print_summary()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Seeding selesai! Akun demo siap dipakai (lihat README).'))

    def _seed_demo_accounts(self):
        self.stdout.write('\n[0/7] Membuat akun demo (admin01 / dosen01 / mhs001)...')

        if not User.objects.filter(username='admin01').exists():
            User.objects.create_superuser(
                username='admin01',
                email='admin01@univ.ac.id',
                password='admin12345',
            )
            self.stdout.write('  → admin01 dibuat (superuser / role admin)')
        else:
            self.stdout.write('  → admin01 sudah ada (skip)')

    def _seed_categories(self):
        self.stdout.write('\n[1/7] Membuat kategori course...')

        existing = set(Category.objects.values_list('name', flat=True))
        to_create = [
            Category(name=name, description=desc)
            for name, desc in CATEGORIES
            if name not in existing
        ]
        if to_create:
            for cat in to_create:
                cat.save()  # pakai save() satu-satu agar slug ter-generate otomatis

        categories = {c.name: c for c in Category.objects.all()}
        self.stdout.write(f'  → {len(categories)} kategori tersedia')
        return categories

    def _seed_teachers(self):
        self.stdout.write('\n[2/7] Membuat pengajar (dosen01 - dosen20)...')

        existing = set(
            User.objects.filter(username__startswith='dosen')
            .values_list('username', flat=True)
        )

        to_create = []
        for i in range(1, 21):
            username = f'dosen{i:02d}'
            if username not in existing:
                fname = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
                lname = LAST_NAMES[(i - 1) % len(LAST_NAMES)]
                to_create.append(User(
                    username=username,
                    first_name=fname,
                    last_name=lname,
                    email=f'{username}@univ.ac.id',
                    is_staff=False,
                    # make_password() diperlukan karena bulk_create tidak memanggil
                    # set_password() -> password harus di-hash sebelum bulk_create
                    password=make_password('dosen12345'),
                ))

        if to_create:
            User.objects.bulk_create(to_create, ignore_conflicts=True)

        teachers = list(User.objects.filter(username__startswith='dosen'))
        self._ensure_profiles(teachers, role='instructor')
        self.stdout.write(f'  → {len(teachers)} pengajar tersedia (role=instructor)')
        return teachers

    def _seed_students(self):
        self.stdout.write('\n[3/7] Membuat mahasiswa (mhs001 - mhs080)...')

        existing = set(
            User.objects.filter(username__startswith='mhs')
            .values_list('username', flat=True)
        )

        to_create = []
        for i in range(1, 81):
            username = f'mhs{i:03d}'
            if username not in existing:
                to_create.append(User(
                    username=username,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    email=f'{username}@student.univ.ac.id',
                    password=make_password('mhs12345'),
                ))

        if to_create:
            User.objects.bulk_create(to_create, ignore_conflicts=True)

        students = list(User.objects.filter(username__startswith='mhs'))
        self._ensure_profiles(students, role='student')
        self.stdout.write(f'  → {len(students)} mahasiswa tersedia (role=student)')
        return students

    def _ensure_profiles(self, users, role):
        """Buat Profile untuk user yang belum punya, dengan role tertentu."""
        existing_ids = set(
            Profile.objects.filter(user__in=users).values_list('user_id', flat=True)
        )
        to_create = [
            Profile(user=u, role=role)
            for u in users
            if u.id not in existing_ids
        ]
        if to_create:
            Profile.objects.bulk_create(to_create, batch_size=200)

    def _seed_courses(self, teachers, categories):
        self.stdout.write('\n[4/7] Membuat 100 mata kuliah...')

        existing_count = Course.objects.count()
        to_create = []

        for i in range(existing_count, 100):
            subject = SUBJECTS[i % len(SUBJECTS)]
            category_name = SUBJECT_CATEGORY_MAP.get(subject)
            category = categories.get(category_name)
            kelas_idx = i // len(SUBJECTS)
            name = subject if kelas_idx == 0 else f'{subject} - Kelas {chr(65 + kelas_idx - 1)}'
            to_create.append(Course(
                name=name,
                description=(
                    f'Mata kuliah {subject} membahas konsep dasar hingga lanjutan '
                    f'dengan pendekatan teori dan praktikum. Mahasiswa akan mampu '
                    f'menerapkan ilmu ini di dunia kerja.'
                ),
                price=random.choice(PRICES),
                teacher=random.choice(teachers),
                category=category,
            ))

        if to_create:
            Course.objects.bulk_create(to_create, batch_size=500)

        courses = list(Course.objects.all()[:100])
        self.stdout.write(f'  → {Course.objects.count()} mata kuliah tersedia')
        return courses

    def _seed_members(self, courses, students):
        self.stdout.write('\n[5/7] Membuat 500 anggota kelas...')

        existing_count = CourseMember.objects.count()
        existing_pairs = set(
            CourseMember.objects.values_list('course_id_id', 'user_id_id')
        )

        to_create = []
        attempts = 0
        target = 500 - existing_count

        while len(to_create) < target and attempts < 10000:
            attempts += 1
            course = random.choice(courses)
            student = random.choice(students)
            pair = (course.id, student.id)

            if pair not in existing_pairs:
                existing_pairs.add(pair)
                role = 'ast' if random.random() < 0.1 else 'std'  # 10% asisten
                to_create.append(CourseMember(
                    course_id=course,
                    user_id=student,
                    roles=role,
                ))

        if to_create:
            CourseMember.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)

        members = list(CourseMember.objects.all())
        self.stdout.write(f'  → {CourseMember.objects.count()} anggota kelas tersedia')
        return members

    def _seed_contents(self, courses):
        self.stdout.write('\n[6/7] Membuat 300 konten kelas...')

        existing_count = CourseContent.objects.count()
        to_create = []

        for i in range(existing_count, 300):
            course = courses[i % len(courses)]
            prefix = CONTENT_PREFIXES[i % len(CONTENT_PREFIXES)]
            topic = random.choice(CONTENT_TOPICS)
            to_create.append(CourseContent(
                name=f'{prefix} {topic}',
                description=(
                    f'Materi {prefix.lower()} mengenai {topic.lower()} '
                    f'dalam konteks {course.name}. '
                    f'Pelajari konsep ini dengan seksama sebelum mengerjakan latihan.'
                ),
                course_id=course,
                parent_id=None,
            ))

        if to_create:
            CourseContent.objects.bulk_create(to_create, batch_size=500)

        self.stdout.write(f'  → {CourseContent.objects.count()} konten tersedia')
        return list(CourseContent.objects.all()[:300])

    def _seed_comments(self, contents, members):
        self.stdout.write('\n[7/7] Membuat 1000+ komentar...')

        existing_count = Comment.objects.count()
        target = 1000 - existing_count

        if target <= 0:
            self.stdout.write(f'  → {Comment.objects.count()} komentar tersedia (skip)')
            return

        # Pre-build dict: course_id -> list of members untuk efisiensi
        members_by_course = {}
        for member in members:
            cid = member.course_id_id
            members_by_course.setdefault(cid, []).append(member)

        to_create = []
        fallback_members = members[:20]

        for _ in range(target):
            content = random.choice(contents)
            course_members = members_by_course.get(content.course_id_id, fallback_members)
            member = random.choice(course_members)
            to_create.append(Comment(
                content_id=content,
                user_id=member.user_id,  # FIX: member adalah CourseMember -> ambil User-nya
                comment=random.choice(COMMENTS),
            ))

        Comment.objects.bulk_create(to_create, batch_size=500)
        self.stdout.write(f'  → {Comment.objects.count()} komentar tersedia')

    def _seed_progress(self, members, contents):
        self.stdout.write('\n[bonus] Membuat sebagian riwayat progress belajar...')

        if Progress.objects.exists():
            self.stdout.write(f'  → {Progress.objects.count()} progress tersedia (skip)')
            return

        contents_by_course = {}
        for content in contents:
            contents_by_course.setdefault(content.course_id_id, []).append(content)

        to_create = []
        sample_members = members[:100]
        for member in sample_members:
            course_contents = contents_by_course.get(member.course_id_id, [])
            if not course_contents:
                continue
            if random.random() < 0.7:
                selected = course_contents
            else:
                k = max(1, len(course_contents) // 2)
                selected = random.sample(course_contents, k)

            for content in selected:
                to_create.append(Progress(enrollment=member, content=content))

        if to_create:
            Progress.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)

        self.stdout.write(f'  → {Progress.objects.count()} progress tersedia')

    def _print_summary(self):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('-' * 55))
        self.stdout.write(self.style.HTTP_INFO('  Ringkasan Data'))
        self.stdout.write(self.style.HTTP_INFO('-' * 55))
        self.stdout.write(f'  Kategori        : {Category.objects.count()}')
        self.stdout.write(f"  User pengajar   : {User.objects.filter(username__startswith='dosen').count()}")
        self.stdout.write(f"  User mahasiswa  : {User.objects.filter(username__startswith='mhs').count()}")
        self.stdout.write(f'  Course          : {Course.objects.count()}')
        self.stdout.write(f'  CourseMember    : {CourseMember.objects.count()}')
        self.stdout.write(f'  CourseContent   : {CourseContent.objects.count()}')
        self.stdout.write(f'  Comment         : {Comment.objects.count()}')
        self.stdout.write(f'  Progress        : {Progress.objects.count()}')
        self.stdout.write(self.style.HTTP_INFO('-' * 55))