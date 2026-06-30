from django.urls import path
from .views import manual_clock_in_out, qr_clock_in

urlpatterns = [
    path('manual-clock/', manual_clock_in_out, name='manual-clock-in-out'),
    path('qr-clock/<str:token>/', qr_clock_in, name='qr-clock-in'),
]
