from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceSessionViewSet, AttendanceViewSet, session_sse

router = DefaultRouter()
router.register('session', AttendanceSessionViewSet, basename='attendance-session')
router.register('history', AttendanceViewSet, basename='attendance-history')

urlpatterns = [
    path('session/<str:org_id>/sse/', session_sse, name='session-sse'),
    path('', include(router.urls)),
]
