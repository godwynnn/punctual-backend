import math
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import Employee
from organization.models import Organization
from attendance.models import Attendance, AttendanceSession

def get_distance(lat1, lon1, lat2, lon2):
    # radius of Earth in meters
    R = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return distance

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_clock_in_out(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({'error': 'No employee record found for your user.'}, status=status.HTTP_400_BAD_REQUEST)

    if employee.status != 'active':
        return Response({'error': f'Your employee status is currently "{employee.status}". You must accept the organization invitation first.'}, status=status.HTTP_400_BAD_REQUEST)

    organization = employee.organization
    if not organization:
        return Response({'error': 'No organization linked to your employee record.'}, status=status.HTTP_400_BAD_REQUEST)

    # Get coordinates from request payload
    latitude_str = request.data.get('latitude')
    longitude_str = request.data.get('longitude')

    if latitude_str is None or longitude_str is None:
        return Response({'error': 'Latitude and longitude coordinates are required for manual clock-in/out.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_lat = float(latitude_str)
        user_lng = float(longitude_str)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid latitude or longitude coordinate values.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check organization coordinate configs
    if organization.office_latitude is None or organization.office_longitude is None:
        return Response({'error': 'Organization office geofence coordinates are not configured.'}, status=status.HTTP_400_BAD_REQUEST)

    org_lat = float(organization.office_latitude)
    org_lng = float(organization.office_longitude)
    allowed_radius = float(organization.allowed_radius or 100.0)

    # Calculate distance
    distance = get_distance(user_lat, user_lng, org_lat, org_lng)
    print(distance)

    # Validation: user must be within geofence radius
    if distance > allowed_radius:
        return Response({
            'error': f'Geofence violation: You are outside the allowed area.',
            'distance': round(distance, 1),
            'allowed_radius': allowed_radius
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get today's local date
    today_date = timezone.localdate()

    # Check for existing attendance record for today
    try:
        attendance = Attendance.objects.get(employee=employee, date=today_date)
        
        # If check-out is already set, block duplicate clock out
        if attendance.check_out is not None:
            return Response({'error': 'You have already clocked out for today.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Set check-out time
        attendance.check_out = timezone.now()
        attendance.save()

        # Format local check-out time for response display
        checkout_local = timezone.localtime(attendance.check_out)
        checkout_str = checkout_local.strftime('%I:%M %p')

        return Response({
            'status': 'success',
            'action': 'clock_out',
            'time': checkout_str,
            'message': 'Clocked out successfully.'
        }, status=status.HTTP_200_OK)

    except Attendance.DoesNotExist:
        # Create new clock-in attendance record
        check_in_now = timezone.now()
        
        # Precedence check for target start time (Shift vs Organization)
        target_start = None
        grace_minutes = 0

        if employee.shift and employee.shift.start_time:
            target_start = employee.shift.start_time
            grace_minutes = employee.shift.grace_period or 0
        elif organization.start_time:
            target_start = organization.start_time

        # Check late status
        attendance_status = 'present'
        if target_start:
            # Create datetime objects comparing locally
            local_checkin = timezone.localtime(check_in_now)
            threshold_datetime = timezone.make_aware(
                timezone.datetime.combine(local_checkin.date(), target_start)
            )
            # Add grace period threshold
            if grace_minutes > 0:
                threshold_datetime += timezone.timedelta(minutes=grace_minutes)

            if local_checkin > threshold_datetime:
                attendance_status = 'late'

        attendance = Attendance.objects.create(
            employee=employee,
            organization=organization,
            date=today_date,
            check_in=check_in_now,
            status=attendance_status,
            method='manual'
        )

        checkin_local = timezone.localtime(attendance.check_in)
        checkin_str = checkin_local.strftime('%I:%M %p')

        return Response({
            'status': 'success',
            'action': 'clock_in',
            'time': checkin_str,
            'status_label': attendance_status.capitalize(),
            'message': f'Clocked in successfully as {attendance_status.upper()}.'
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def qr_clock_in(request, token):
    latitude_str = request.data.get('latitude')
    longitude_str = request.data.get('longitude')

    try:
        session = AttendanceSession.objects.get(token=token)
    except AttendanceSession.DoesNotExist:
        return Response({'error': 'Invalid or expired QR code session.'}, status=status.HTTP_400_BAD_REQUEST)

    if session.is_expired():
        return Response({'error': 'The scanned QR code has expired. Please scan a fresh QR code.'}, status=status.HTTP_400_BAD_REQUEST)

    organization = session.organization

    try:
        employee = Employee.objects.get(user=request.user, organization=organization)
    except Employee.DoesNotExist:
        return Response({'error': 'You do not belong to the organization associated with this session.'}, status=status.HTTP_403_FORBIDDEN)

    if employee.status != 'active':
        return Response({'error': 'Your employee account is not active.'}, status=status.HTTP_400_BAD_REQUEST)

    if organization.require_gps:
        if latitude_str is None or longitude_str is None:
            return Response({'error': 'GPS coordinates are required for verification.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_lat = float(latitude_str)
            user_lng = float(longitude_str)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid coordinate format.'}, status=status.HTTP_400_BAD_REQUEST)

        org_lat = float(organization.office_latitude)
        org_lng = float(organization.office_longitude)
        allowed_radius = float(organization.allowed_radius or 100.0)

        distance = get_distance(user_lat, user_lng, org_lat, org_lng)
        if distance > allowed_radius:
            return Response({
                'error': 'Geofence violation: You are outside the allowed area.',
                'distance': round(distance, 1),
                'allowed_radius': allowed_radius
            }, status=status.HTTP_400_BAD_REQUEST)

    today_date = timezone.localdate()

    try:
        attendance = Attendance.objects.get(employee=employee, date=today_date)
        if attendance.check_out is not None:
            return Response({'error': 'You have already clocked out for today.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance.check_out = timezone.now()
        attendance.save()

        checkout_local = timezone.localtime(attendance.check_out)
        checkout_str = checkout_local.strftime('%I:%M %p')
        return Response({
            'status': 'success',
            'action': 'clock_out',
            'time': checkout_str,
            'message': 'Clocked out successfully using QR code.'
        }, status=status.HTTP_200_OK)

    except Attendance.DoesNotExist:
        check_in_now = timezone.now()
        target_start = None
        grace_minutes = 0

        if employee.shift and employee.shift.start_time:
            target_start = employee.shift.start_time
            grace_minutes = employee.shift.grace_period or 0
        elif organization.start_time:
            target_start = organization.start_time

        attendance_status = 'present'
        if target_start:
            local_checkin = timezone.localtime(check_in_now)
            threshold_datetime = timezone.make_aware(
                timezone.datetime.combine(local_checkin.date(), target_start)
            )
            if grace_minutes > 0:
                threshold_datetime += timezone.timedelta(minutes=grace_minutes)

            if local_checkin > threshold_datetime:
                attendance_status = 'late'

        attendance = Attendance.objects.create(
            employee=employee,
            organization=organization,
            date=today_date,
            check_in=check_in_now,
            status=attendance_status,
            method='qr'
        )

        checkin_local = timezone.localtime(attendance.check_in)
        checkin_str = checkin_local.strftime('%I:%M %p')
        return Response({
            'status': 'success',
            'action': 'clock_in',
            'time': checkin_str,
            'status_label': attendance_status.capitalize(),
            'message': f'Clocked in successfully using QR code as {attendance_status.upper()}.'
        }, status=status.HTTP_201_CREATED)
