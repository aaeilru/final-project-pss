from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: jangan gunakan key ini di production!
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-simple-lms-local-development-key"
)

# SECURITY WARNING: matikan DEBUG di production!
DEBUG = True

ALLOWED_HOSTS = ['*']


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

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": 60 * 60,       # 1 jam
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24, # 1 hari
    "ALGORITHM": "RS256",
    "SIGNING_KEY": open(BASE_DIR / "jwt-signing.pem").read(),
    "VERIFYING_KEY": open(BASE_DIR / "jwt-signing.pub").read(),
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
# Berbeda dengan Lab-compliance yang menggunakan SQLite,
# lab ini menggunakan PostgreSQL agar optimasi index terlihat nyata.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "simple_lms",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",  # Nama service di docker-compose.yml
        "PORT": "5432",
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

# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "TIMEOUT": 300,
    }
}

# Celery
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL",
    "amqp://admin:password@rabbitmq:5672//"
)

CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    "redis://redis:6379/2"
)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Jakarta"

CELERY_BEAT_SCHEDULE = {
    "update-course-statistics-every-5-minutes": {
        "task": "courses.tasks.update_course_statistics",
        "schedule": 300.0,
    },
}

# MongoDB
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://admin:password@mongodb:27017/?authSource=admin"
)

MONGO_DB_NAME = "lms_analytics"