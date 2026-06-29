from django.urls import path
from .views import manual_clock_in_out

urlpatterns = [
    path('manual-clock/', manual_clock_in_out, name='manual-clock-in-out'),
]
