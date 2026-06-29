from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    employee = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'employee_id', 'first_name', 'last_name', 'employee')

    def get_employee(self, obj):
        try:
            if hasattr(obj, 'employee') and obj.employee:
                from employee.serializers import EmployeeSerializer
                return EmployeeSerializer(obj.employee).data
        except Exception:
            pass
        return None

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name')

    def create(self, validated_data):
        emp_id = validated_data.get('employee_id', None)
        if not emp_id or emp_id.strip() == '':
            emp_id = None
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            employee_id=emp_id,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom claims payload
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
        }
        return data
