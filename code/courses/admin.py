from django.contrib import admin
from .models import (
    Category,
    Course,
    Profile,
    CourseMember,
    CourseContent,
    Comment,
    Progress,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("user__username", "user__email")
    ordering = ("user__username",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "teacher", "category", "price", "created_at")
    list_filter = ("teacher", "category", "created_at")
    search_fields = ("name", "description", "teacher__username", "category__name")
    ordering = ("-created_at",)


@admin.register(CourseMember)
class CourseMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "course_id", "user_id", "roles")
    list_filter = ("roles", "course_id")
    search_fields = ("course_id__name", "user_id__username")


@admin.register(CourseContent)
class CourseContentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "course_id", "parent_id", "created_at")
    list_filter = ("course_id", "created_at")
    search_fields = ("name", "description", "course_id__name")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "content_id", "user_id", "comment")
    list_filter = ("content_id",)
    search_fields = ("comment", "content_id__name", "user_id__username")


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ("id", "enrollment", "content", "completed_at")
    list_filter = ("completed_at",)
    search_fields = (
        "enrollment__user_id__username",
        "enrollment__course_id__name",
        "content__name",
    )
    ordering = ("-completed_at",)