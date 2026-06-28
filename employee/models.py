from django.db import models
from django.conf import settings
from django.utils import timezone
from utils.uuid_generator import generate_custom_id

def generate_employee_id():
    return f"emp_{generate_custom_id()}"

class Employee(models.Model):
    id = models.CharField(primary_key=True, max_length=50, default=generate_employee_id, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee'
    )
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='employees'
    )
    position = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    shift = models.ForeignKey(
        'shift.Shift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active/Accepted'),
        ('declined', 'Declined'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateField(default=timezone.now, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        user_email = self.user.email if self.user else "No User"
        return f"{user_email} - {self.organization.name if self.organization else 'No Org'}"
