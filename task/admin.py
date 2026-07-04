from django.contrib import admin
from .models import Task, TaskAssignment

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'organization', 'due_date', 'created_at', 'updated_at')
    search_fields = ('title', 'description', 'organization__name')
    list_filter = ('organization', 'due_date', 'created_at')
    raw_id_fields = ('organization',)

@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'employee', 'status', 'assigned_at')
    list_filter = ('status', 'assigned_at')
    search_fields = ('task__title', 'employee__user__email', 'employee__user__first_name', 'employee__user__last_name')
    raw_id_fields = ('task', 'employee')
