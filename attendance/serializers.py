from rest_framework import serializers
from .models import AttendanceSession, Attendance

class AttendanceSessionSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = AttendanceSession
        fields = (
            'id',
            'organization',
            'token',
            'expires_at',
            'is_expired',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'is_expired', 'created_at', 'updated_at')

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = (
            'id',
            'employee',
            'organization',
            'date',
            'check_in',
            'check_out',
            'status',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
