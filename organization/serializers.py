from rest_framework import serializers
from .models import Organization

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            'id',
            'name',
            'slug',
            'description',
            'whatsapp_contact',
            'telegram_contact',
            'attendance_id',
            'owner',
            'office_latitude',
            'office_longitude',
            'allowed_radius',
            'require_qr',
            'auto_qr_session',
            'require_gps',
            'allow_ussd',
            'allow_remote',
            'use_social',
            'qr_refresh_interval',
            'start_time',
            'duration',
            'location_data',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'slug', 'created_at', 'updated_at')

from attendance.models import Attendance

class EmployeeAttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_email = serializers.EmailField(source='employee.user.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)

    class Meta:
        model = Attendance
        fields = (
            'id',
            'employee',
            'employee_name',
            'employee_email',
            'organization',
            'organization_name',
            'department',
            'date',
            'check_in',
            'check_out',
            'status',
            'method',
            'created_at',
            'updated_at'
        )

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            user = obj.employee.user
            full_name = f"{user.first_name} {user.last_name}".strip()
            return full_name or user.email
        return ""
