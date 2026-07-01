from django.db import models
from django.conf import settings
from utils.uuid_generator import generate_custom_id

def generate_org_id():
    return f"org_{generate_custom_id()}"

class Organization(models.Model):
    id = models.CharField(primary_key=True, max_length=50, default=generate_org_id, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    whatsapp_contact = models.CharField(max_length=50, blank=True, null=True)
    telegram_contact = models.CharField(max_length=100, blank=True, null=True)
    attendance_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_organizations')
    office_latitude = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    office_longitude = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    allowed_radius = models.FloatField(default=100.0, help_text="Allowed radius in meters")
    require_qr = models.BooleanField(default=False)
    auto_qr_session = models.BooleanField(default=False)
    require_gps = models.BooleanField(default=False)
    allow_ussd = models.BooleanField(default=False)
    allow_remote = models.BooleanField(default=False)
    use_social = models.BooleanField(default=False)
    qr_refresh_interval = models.IntegerField(default=40, help_text="QR refresh interval in seconds")
    start_time = models.TimeField(null=True, blank=True, help_text="Daily operational start time")
    duration = models.IntegerField(null=True, blank=True, help_text="Daily operational duration in hours")
    location_data = models.JSONField(null=True, blank=True, help_text="Metadata from geolocation API")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
