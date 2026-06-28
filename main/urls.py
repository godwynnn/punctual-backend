from django.urls import path
from .views import (
    invite_employee, list_notifications, mark_notifications_read,
    sse_notifications, accept_invitation, decline_invitation, keep_alive_view
)

urlpatterns = [
    path('invite/', invite_employee, name='invite-employee'),
    path('notifications/', list_notifications, name='list-notifications'),
    path('notifications/read/', mark_notifications_read, name='mark-notifications-read'),
    path('notifications/stream/', sse_notifications, name='sse-notifications'),
    path('invitations/<str:org_id>/accept/', accept_invitation, name='accept-invitation'),
    path('invitations/<str:org_id>/decline/', decline_invitation, name='decline-invitation'),
    path('keep-alive/', keep_alive_view, name='keep-alive'),
]
