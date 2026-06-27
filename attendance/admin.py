from django.contrib import admin
from .models import AttendanceSession, Attendance

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization_name', 'token', 'expires_at', 'is_expired_status')
    search_fields = ('organization__name', 'token')

    def organization_name(self, obj):
        return obj.organization.name if obj.organization else "-"
    organization_name.short_description = 'Organization'

    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = 'Is Expired?'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee_email', 'organization_name', 'date', 'check_in', 'check_out', 'status')
    list_filter = ('status', 'date', 'organization')
    search_fields = ('employee__user__email', 'employee__user__first_name', 'employee__user__last_name', 'organization__name')

    def employee_email(self, obj):
        return obj.employee.user.email if obj.employee and obj.employee.user else "-"
    employee_email.short_description = 'Employee Email'

    def organization_name(self, obj):
        return obj.organization.name if obj.organization else "-"
    organization_name.short_description = 'Organization'
