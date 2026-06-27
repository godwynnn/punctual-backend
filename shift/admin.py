from django.contrib import admin
from .models import Shift

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization_name', 'start_time', 'end_time', 'grace_period', 'created_at')
    list_filter = ('organization', 'start_time', 'end_time')
    search_fields = ('name', 'organization__name')

    def organization_name(self, obj):
        return obj.organization.name if obj.organization else "-"
    organization_name.short_description = 'Organization'
