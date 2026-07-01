from django.urls import path
from .views import manual_clock_in_out, qr_clock_in, whatsapp_clock_in_out, update_profile

urlpatterns = [
    path('manual-clock/', manual_clock_in_out, name='manual-clock-in-out'),
    path('qr-clock/<str:token>/', qr_clock_in, name='qr-clock-in'),
    path('whatsapp-webhook/', whatsapp_clock_in_out, name='whatsapp-webhook'),
    path('profile/update/', update_profile, name='update-profile'),
]
