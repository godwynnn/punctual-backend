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
