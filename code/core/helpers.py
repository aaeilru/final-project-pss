# core/helpers.py
from django.contrib.auth.models import User
from ninja.errors import HttpError


def get_authenticated_user(request):
    """Mendapatkan objek User dari request yang terautentikasi."""
    return User.objects.get(pk=request.user.id)


def check_course_owner(course, user):
    """Memeriksa apakah user adalah pemilik course."""
    if course.teacher != user:
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