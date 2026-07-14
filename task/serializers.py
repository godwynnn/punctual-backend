from rest_framework import serializers
from .models import Task, TaskAssignment
from employee.models import Employee

class EmployeeDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Employee
        fields = ('id', 'name', 'email', 'position', 'department')

    def get_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return "No User"

class TaskAssignmentSerializer(serializers.ModelSerializer):
    employee = EmployeeDetailSerializer(read_only=True)

    class Meta:
        model = TaskAssignment
        fields = ('id', 'employee', 'assigned_at', 'status', 'notes', 'file_attach', 'link_attach')

class TaskSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    assignments = TaskAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = (
            'id', 
            'title', 
            'description', 
            'organization', 
            'organization_name', 
            'due_date', 
            'file_attach',
            'link_attach',
            'created_at', 
            'updated_at', 
            'assignments'
        )

class CreateTaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    organization_id = serializers.CharField(max_length=50)
    assignee_ids = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=[]
    )
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    file_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    link_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)

class UpdateTaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    assignee_ids = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False
    )
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    file_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    link_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)

class SubmitAssignmentSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[('in_progress', 'In Progress'), ('completed', 'Completed')], default='completed')
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    file_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    link_attach = serializers.URLField(required=False, allow_blank=True, allow_null=True)
