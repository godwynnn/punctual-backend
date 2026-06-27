from django.urls import path,include
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterAPIView, LoginAPIView, logout_view,VerifySocialLogin

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/', include('drf_social_oauth2.urls', namespace='drf')),
    path('auth/social/<str:backend>/', VerifySocialLogin, name='social-login'),
]
