from pathlib import Path
import os

try:
    # Memuat .env secara otomatis saat manage.py dijalankan LANGSUNG (di luar
    # Docker). Di dalam Docker, environment sudah disuplai oleh docker-compose
    # lewat env_file, jadi baris ini hanya berguna untuk pengembangan lokal.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# Security
# =============================================================================
# SECURITY WARNING: SECRET_KEY HARUS diisi lewat environment variable di
# production. Fallback di bawah hanya untuk kenyamanan development lokal.
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-simple-lms-local-development-key"
)

# SECURITY WARNING: matikan DEBUG di production!
DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")


# =============================================================================
# Aplikasi yang terdaftar
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'ninja_simple_jwt',
    # Local apps
    'courses',
    'analytics',
]


def _read_key_file(path: Path):
    """
    Baca file RSA key untuk JWT. Mengembalikan None jika file belum ada
    (misalnya sebelum `python manage.py make_jwt_key` dijalankan), sehingga
    Django settings tetap bisa di-import tanpa crash.
    """
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": 60 * 60,       # 1 jam
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24,  # 1 hari
    "ALGORITHM": "RS256",
    "SIGNING_KEY": _read_key_file(BASE_DIR / "jwt-signing.pem"),
    "VERIFYING_KEY": _read_key_file(BASE_DIR / "jwt-signing.pub"),
}


# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lms.wsgi.application"


# =============================================================================
# Database - PostgreSQL (sesuai docker-compose.yml)
# =============================================================================
# Semua kredensial dibaca dari environment variable. Lihat .env.example.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "simple_lms"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}


# =============================================================================
# Password validation
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# =============================================================================
# Internationalization
# =============================================================================

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True


# =============================================================================
# Static dan Media files
# =============================================================================

STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Redis Cache
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "TIMEOUT": 300,
    }
}

# =============================================================================
# Celery
# =============================================================================

CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL",
    "amqp://guest:guest@rabbitmq:5672//"
)

CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    "redis://redis:6379/2"
)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Jakarta"
CELERY_TASK_STORE_EAGER_RESULT = True

CELERY_BEAT_SCHEDULE = {
    "update-course-statistics-every-5-minutes": {
        "task": "courses.tasks.update_course_statistics",
        "schedule": 300.0,
    },
}

# =============================================================================
# MongoDB
# =============================================================================

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://mongo:mongo@mongodb:27017/?authSource=admin"
)

MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "lms_analytics")


# =============================================================================
# Logging (supaya warning dari analytics/mongo_service.py terlihat di console)
# =============================================================================

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}