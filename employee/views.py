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


@api_view(['GET', 'POST'])
@permission_classes([])  # Disable DRF default authentication
def whatsapp_clock_in_out(request):
    import os
    from rest_framework.permissions import AllowAny
    from django.http import HttpResponse
    
    # Explicitly set AllowAny permission
    request.user = None
    request.auth = None
    
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        expected_token = os.environ.get("META_WA_VERIFY_TOKEN", "verify_me")
        if mode == 'subscribe' and token == expected_token:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)
        
    elif request.method == 'POST':
        data = request.data or {}
        entry = data.get('entry', [])
        for e in entry:
            changes = e.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                for msg in messages:
                    wa_id = msg.get('from')
                    msg_type = msg.get('type')
                    if msg_type == 'interactive':
                        interactive = msg.get('interactive', {})
                        if interactive.get('type') == 'button_reply':
                            button_reply = interactive.get('button_reply', {})
                            button_id = button_reply.get('id') # 'clock_in' or 'clock_out'
                            
                            handle_button_click(wa_id, button_id)
                    elif msg_type == 'location':
                        location_data = msg.get('location', {})
                        lat = location_data.get('latitude')
                        lng = location_data.get('longitude')
                        
                        process_employee_attendance_with_location(wa_id, lat, lng)
                            
        return Response({"status": "success"}, status=status.HTTP_200_OK)


def handle_button_click(wa_id, button_id):
    from django.core.cache import cache
    from utils.whatsapp import send_whatsapp_text_message
    
    # Store action in cache for 5 minutes (300 seconds)
    cache.set(f"wa_action_{wa_id}", button_id, timeout=300)
    
    action_label = "Clock In" if button_id == 'clock_in' else "Clock Out"
    send_whatsapp_text_message(
        wa_id,
        f"📍 Please share your location to complete your *{action_label}*."
    )


def process_employee_attendance_with_location(wa_id, lat, lng):
    from django.core.cache import cache
    from utils.whatsapp import send_whatsapp_text_message
    from .models import Employee
    from attendance.models import Attendance
    
    # 1. Clean incoming phone number
    incoming_phone = "".join(filter(str.isdigit, wa_id))
    print(incoming_phone)
    
    # 2. Lookup employee
    active_employees = Employee.objects.filter(status='active', is_active=True).select_related('user', 'organization')
    employee = None
    for emp in active_employees:
        if emp.whatsapp_no:
            cleaned_emp_no = "".join(filter(str.isdigit, emp.whatsapp_no))
            if cleaned_emp_no == incoming_phone or cleaned_emp_no.endswith(incoming_phone) or incoming_phone.endswith(cleaned_emp_no):
                employee = emp
                break
                
    if not employee:
        send_whatsapp_text_message(
            wa_id,
            "❌ *Error:* We could not find an active employee account matching your WhatsApp number."
        )
        return

    organization = employee.organization
    if not organization:
        send_whatsapp_text_message(
            employee.whatsapp_no,
            "❌ *Error:* No organization is linked to your employee record."
        )
        return

    # 3. Retrieve pending action from cache
    button_id = cache.get(f"wa_action_{wa_id}")
    today_date = timezone.localdate()
    
    if not button_id:
        # Fallback if they sent a location without clicking a button first
        try:
            attendance = Attendance.objects.get(employee=employee, date=today_date)
            if attendance.check_out is None:
                button_id = 'clock_out'
            else:
                send_whatsapp_text_message(
                    employee.whatsapp_no,
                    "⚠️ *Warning:* You have already clocked in and out for today."
                )
                return
        except Attendance.DoesNotExist:
            button_id = 'clock_in'

    # 4. Geofence verification
    if organization.office_latitude is None or organization.office_longitude is None:
        send_whatsapp_text_message(
            employee.whatsapp_no,
            "❌ *Error:* Organization office geofence coordinates are not configured."
        )
        return

    org_lat = float(organization.office_latitude)
    org_lng = float(organization.office_longitude)
    allowed_radius = float(organization.allowed_radius or 100.0)

    # Calculate distance
    distance = get_distance(lat, lng, org_lat, org_lng)

    if distance > allowed_radius:
        send_whatsapp_text_message(
            employee.whatsapp_no,
            f"❌ *Geofence Violation:* You are outside the allowed area.\n\n"
            f"*Distance:* {round(distance, 1)}m\n"
            f"*Allowed Radius:* {allowed_radius}m\n"
            f"Please move closer and try again."
        )
        return

    # 5. Process attendance
    if button_id == 'clock_in':
        # Check if today's attendance record already exists
        try:
            attendance = Attendance.objects.get(employee=employee, date=today_date)
            send_whatsapp_text_message(
                employee.whatsapp_no,
                "⚠️ *Warning:* You have already clocked in for today."
            )
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

            Attendance.objects.create(
                employee=employee,
                organization=organization,
                date=today_date,
                check_in=check_in_now,
                status=attendance_status,
                method='social_wa'
            )

            # Clear cache action
            cache.delete(f"wa_action_{wa_id}")

            local_time_str = timezone.localtime(check_in_now).strftime('%I:%M %p')
            send_whatsapp_text_message(
                employee.whatsapp_no,
                f"✅ *Clock In Successful!*\n\n"
                f"*Time:* {local_time_str}\n"
                f"*Status:* {attendance_status.upper()}"
            )
            
    elif button_id == 'clock_out':
        try:
            attendance = Attendance.objects.get(employee=employee, date=today_date)
            if attendance.check_out is not None:
                send_whatsapp_text_message(
                    employee.whatsapp_no,
                    "⚠️ *Warning:* You have already clocked out for today."
                )
            else:
                checkout_now = timezone.now()
                attendance.check_out = checkout_now
                attendance.save()
                
                # Clear cache action
                cache.delete(f"wa_action_{wa_id}")
                
                local_time_str = timezone.localtime(checkout_now).strftime('%I:%M %p')
                send_whatsapp_text_message(
                    employee.whatsapp_no,
                    f"✅ *Clock Out Successful!*\n\n"
                    f"*Time:* {local_time_str}"
                )
        except Attendance.DoesNotExist:
            send_whatsapp_text_message(
                employee.whatsapp_no,
                "❌ *Error:* You need to clock in first before you can clock out."
            )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    try:
        employee = user.employee
    except Employee.DoesNotExist:
        return Response({'error': 'No employee record found for your user.'}, status=status.HTTP_404_NOT_FOUND)

    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')
    phone_no = request.data.get('phone_no')
    whatsapp_no = request.data.get('whatsapp_no')

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if phone_no is not None:
        user.phone_no = phone_no
    user.save()

    if whatsapp_no is not None:
        employee.whatsapp_no = whatsapp_no
        employee.save()

    from users.serializers import UserSerializer
    return Response({
        'status': 'success',
        'message': 'Profile updated successfully.',
        'user': UserSerializer(user).data
    }, status=status.HTTP_200_OK)

