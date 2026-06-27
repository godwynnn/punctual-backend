from django.contrib import admin
from .models import Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'organization_name', 'position', 'department', 'is_active', 'joined_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'organization__name', 'position', 'department')
    list_filter = ('is_active', 'organization', 'department')

    def user_email(self, obj):
        return obj.user.email if obj.user else "-"
    user_email.short_description = 'User Email'

    def organization_name(self, obj):
        return obj.organization.name if obj.organization else "-"
    organization_name.short_description = 'Organization'
