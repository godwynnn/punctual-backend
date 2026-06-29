from django.urls import path
from .views import list_shifts, create_shift

urlpatterns = [
    path('<str:org_id>/', list_shifts, name='list-shifts'),
    path('<str:org_id>/create/', create_shift, name='create-shift'),
]
