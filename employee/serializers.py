from rest_framework import serializers
from .models import Employee
from organization.serializers import OrganizationSerializer
from shift.serializers import ShiftSerializer

class EmployeeSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    shift = ShiftSerializer(read_only=True)
    today_attendance = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            'id',
            'user',
            'organization',
            'position',
            'department',
            'shift',
            'status',
            'is_active',
            'today_attendance',
            'joined_at',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_today_attendance(self, obj):
        try:
            from django.utils import timezone
            from attendance.models import Attendance
            today = timezone.localdate()
            attendance = Attendance.objects.filter(employee=obj, date=today).first()
            if attendance:
                return {
                    'check_in': timezone.localtime(attendance.check_in).strftime('%I:%M %p') if attendance.check_in else None,
                    'check_out': timezone.localtime(attendance.check_out).strftime('%I:%M %p') if attendance.check_out else None,
                    'status': attendance.status
                }
        except Exception:
            pass
        return None
