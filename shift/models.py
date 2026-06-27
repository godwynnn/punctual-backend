from django.db import models
from utils.uuid_generator import generate_custom_id

def generate_shift_id():
    return f"shf_{generate_custom_id()}"

class Shift(models.Model):
    id = models.CharField(primary_key=True, max_length=50, default=generate_shift_id, editable=False)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='shifts'
    )
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_period = models.IntegerField(default=15, help_text="Late check-in tolerance in minutes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
