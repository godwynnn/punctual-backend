from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, employees_attendance_sse

router = DefaultRouter()
router.register('', OrganizationViewSet, basename='organization')

urlpatterns = [
    path('employees_attendance/sse/', employees_attendance_sse, name='employees-attendance-sse'),
    path('', include(router.urls)),
]
