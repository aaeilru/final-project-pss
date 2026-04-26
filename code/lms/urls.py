"""
URL configuration untuk Simple LMS - Lab 05

Routes:
  /admin/       → Django Admin panel
  /             → Semua URL dari app courses (lihat courses/urls.py)
"""

from django.contrib import admin
from django.urls import path, include
from core.apiv1 import apiv1

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', apiv1.urls),
    path('', include('courses.urls')),
]
