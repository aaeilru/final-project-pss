"""
Settings override untuk testing lokal tanpa Docker.
Gunakan dengan: DJANGO_SETTINGS_MODULE=lms.settings_test python manage.py test
Atau: python manage.py test --settings=lms.settings_test
"""

import os

from .settings import *  # noqa: F401, F403

os.environ.pop("CELERY_BROKER_URL", None)
os.environ.pop("CELERY_RESULT_BACKEND", None)

# Override database ke SQLite untuk testing lokal (tanpa Docker/PostgreSQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_test.sqlite3",
    }
}

# Cache in-memory untuk testing (tidak butuh Redis berjalan)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery jalan secara synchronous (tanpa RabbitMQ/worker terpisah) saat test
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Result backend in-memory (built-in Celery), supaya endpoint task_status
# bisa dites tanpa perlu Redis asli berjalan.
CELERY_RESULT_BACKEND = "cache+memory://"
# Wajib di-set True agar hasil task TETAP disimpan ke backend walau
# CELERY_TASK_ALWAYS_EAGER=True (default-nya tidak disimpan).
CELERY_TASK_STORE_EAGER_RESULT = True

# Pakai mongomock (simulasi MongoDB in-memory) saat testing -- supaya
# aggregation pipeline MongoDB (Paket 5) bisa benar-benar diuji tanpa
# perlu container MongoDB asli berjalan.
MONGO_USE_MOCK = True

# Password hasher cepat agar test User.objects.create_user() tidak lambat
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]