from rest_framework import serializers
from .models import Shift

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = (
            'id',
            'organization',
            'name',
            'start_time',
            'end_time',
            'grace_period',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
