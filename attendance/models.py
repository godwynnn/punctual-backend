from django.db import models
from django.utils import timezone
from utils.uuid_generator import generate_custom_id

def generate_session_id():
    return f"attses_{generate_custom_id()}"

def generate_attendance_id():
    return f"att_{generate_custom_id()}"

class AttendanceSession(models.Model):
    id = models.CharField(primary_key=True, max_length=50, default=generate_session_id, editable=False)
    organization = models.OneToOneField(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='attendance_session'
    )
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Session for {self.organization.name} - Exp: {self.expires_at}"

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]

    id = models.CharField(primary_key=True, max_length=50, default=generate_attendance_id, editable=False)
    employee = models.ForeignKey(
        'employee.Employee',
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(blank=True, null=True)
    check_out = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Prevent duplicate attendance for an employee on the same date
        unique_together = ('employee', 'date')

    def __str__(self):
        user_email = self.employee.user.email if self.employee and self.employee.user else "No User"
        return f"{user_email} - {self.date} ({self.status})"
