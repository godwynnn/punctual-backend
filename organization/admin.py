from django.contrib import admin
from .models import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'allowed_radius', 'require_qr', 'require_gps', 'use_social', 'owner', 'created_at')
    search_fields = ('name', 'attendance_id', 'owner__email', 'owner__employee_id')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'slug', 'description', 'owner')
        }),
        ('Contacts', {
            'fields': ('whatsapp_contact', 'telegram_contact', 'attendance_id')
        }),
        ('Office Location & Radius', {
            'fields': ('office_latitude', 'office_longitude', 'allowed_radius')
        }),
        ('Verification Policies', {
            'fields': ('require_qr', 'require_gps', 'allow_ussd', 'allow_remote', 'use_social', 'qr_refresh_interval')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
