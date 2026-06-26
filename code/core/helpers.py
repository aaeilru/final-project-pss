# core/helpers.py
from django.contrib.auth.models import User
from ninja.errors import HttpError


def get_authenticated_user(request):
    """Mendapatkan objek User dari request yang terautentikasi."""
    return User.objects.get(pk=request.user.id)


def get_role(user):
    """
    Mengembalikan role efektif user: 'admin', 'instructor', atau 'student'.
    Admin selalu ditentukan dari is_superuser, bukan dari Profile.

    Bekerja baik untuk User model asli (dengan relasi ORM 'profile') maupun
    untuk TokenUser stateless dari ninja_simple_jwt (yang tidak punya relasi
    ORM sama sekali, sehingga role harus diambil ulang dari database
    berdasarkan id yang ada di klaim JWT).
    """
    if getattr(user, "is_superuser", False):
        return "admin"

    profile = getattr(user, "profile", None)
    if profile is not None:
        return profile.role

    user_id = getattr(user, "id", None)
    if user_id is not None:
        from courses.models import Profile
        profile = Profile.objects.filter(user_id=user_id).first()
        if profile is not None:
            return profile.role

    return "student"


def require_role(user, allowed_roles):
    """Raise HttpError 403 jika role user tidak termasuk allowed_roles."""
    role = get_role(user)
    if role not in allowed_roles:
        raise HttpError(
            403,
            f"Aksi ini hanya untuk role: {', '.join(allowed_roles)}"
        )
    return role


def check_course_owner(course, user):
    """Memeriksa apakah user adalah pemilik course (TokenUser-safe: bandingkan id)."""
    if course.teacher_id != getattr(user, "id", None):
        raise HttpError(403, "Hanya pemilik course yang dapat melakukan aksi ini")


def check_owner_or_superadmin(obj_owner, user):
    """Memeriksa apakah user adalah pemilik objek atau superadmin."""
    if obj_owner != user and not user.is_superuser:
        raise HttpError(403, "Anda tidak memiliki izin untuk melakukan aksi ini")


def check_enrollment(user, course):
    """Memeriksa apakah user terdaftar di course tertentu."""
    from courses.models import CourseMember
    if not CourseMember.objects.filter(user_id=user, course_id=course).exists():
        raise HttpError(403, "Anda tidak terdaftar di course ini")

def get_object_or_404(model, **kwargs):
    """
    Mengambil satu object dari database.
    Raise HttpError 404 jika tidak ditemukan.
    """
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        model_name = model.__name__
        raise HttpError(404, f"{model_name} tidak ditemukan")