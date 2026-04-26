from django.urls import path

from . import views

urlpatterns = [
    # -----------------------------------------------------------------
    # Endpoint 1: Course + Teacher (demonstrasi N+1 pada ForeignKey)
    # -----------------------------------------------------------------
    path('lab/course-list/baseline/',  views.course_list_baseline,  name='course-list-baseline'),
    path('lab/course-list/optimized/', views.course_list_optimized, name='course-list-optimized'),

    # -----------------------------------------------------------------
    # Endpoint 2: Course + Members + Konten + Komentar
    # -----------------------------------------------------------------
    path('lab/course-members/baseline/',  views.course_members_baseline,  name='course-members-baseline'),
    path('lab/course-members/optimized/', views.course_members_optimized, name='course-members-optimized'),

    # -----------------------------------------------------------------
    # Endpoint 3: Statistik Dashboard Dosen
    # -----------------------------------------------------------------
    path('lab/course-dashboard/baseline/',  views.course_dashboard_baseline,  name='course-dashboard-baseline'),
    path('lab/course-dashboard/optimized/', views.course_dashboard_optimized, name='course-dashboard-optimized'),

    # -----------------------------------------------------------------
    # Bonus: Bulk Operations
    # -----------------------------------------------------------------
    path('lab/bulk-create/', views.bulk_create_demo, name='bulk-create-demo'),
    path('lab/bulk-update/', views.bulk_update_demo, name='bulk-update-demo'),
]
