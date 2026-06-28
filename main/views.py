import json
import time
from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import AccessToken

from employee.models import Employee
from users.models import Notification
from organization.models import Organization

User = get_user_model()

from django.db import connection

def sse_event_stream(user):
    # 1. Sends initial connection message
    yield "data: {\"status\": \"connected\"}\n\n"
    
    # 2. Immediately send all existing unread notifications on initial connection
    try:
        unread_notifications = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).order_by('created_at')
        
        for notif in unread_notifications:
            payload = {
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'notification_type': notif.notification_type,
                'organization_id': notif.organization.id if notif.organization else None,
                'created_at': notif.created_at.isoformat()
            }
            yield f"data: {json.dumps(payload)}\n\n"
    except Exception as e:
        print(f"Error sending initial notifications: {e}")
    finally:
        connection.close()
        
    last_checked = timezone.now()
    
    # 3. Stream loop for subsequent new notifications
    while True:
        try:
            new_notifications = Notification.objects.filter(
                recipient=user,
                created_at__gt=last_checked
            ).order_by('created_at')
            
            current_check_time = timezone.now()
            for notif in new_notifications:
                payload = {
                    'id': notif.id,
                    'title': notif.title,
                    'message': notif.message,
                    'notification_type': notif.notification_type,
                    'organization_id': notif.organization.id if notif.organization else None,
                    'created_at': notif.created_at.isoformat()
                }
                yield f"data: {json.dumps(payload)}\n\n"
                
            last_checked = current_check_time
        except Exception as e:
            print(f"Error in SSE loop: {e}")
        finally:
            connection.close()
            
        time.sleep(3)

def sse_notifications(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    token_str = request.GET.get('token')
    if not token_str:
        return JsonResponse({'detail': 'Token parameter required'}, status=401)
        
    try:
        access_token = AccessToken(token_str)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
    except Exception as e:
        return JsonResponse({'detail': f'Invalid or expired token: {str(e)}'}, status=401)
        
    response = StreamingHttpResponse(sse_event_stream(user), content_type="text/event-stream")
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = '*'
    return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:20]
    data = []
    for notif in notifications:
        data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'notification_type': notif.notification_type,
            'organization_id': notif.organization.id if notif.organization else None,
            'is_read': notif.is_read,
            'created_at': notif.created_at.isoformat()
        })
    return Response(data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({'status': 'success'}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_invitation(request, org_id):
    try:
        employee = Employee.objects.get(user=request.user, organization_id=org_id)
        employee.status = 'active'
        employee.save()
        return Response({'status': 'success', 'message': 'You have successfully joined the organization.'}, status=status.HTTP_200_OK)
    except Employee.DoesNotExist:
        return Response({'error': 'Invitation or employee record not found.'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decline_invitation(request, org_id):
    try:
        employee = Employee.objects.get(user=request.user, organization_id=org_id)
        employee.status = 'declined'
        employee.save()
        return Response({'status': 'success', 'message': 'You have declined the invitation.'}, status=status.HTTP_200_OK)
    except Employee.DoesNotExist:
        return Response({'error': 'Invitation or employee record not found.'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_employee(request):
    email = request.data.get('email')
    org_id = request.data.get('organization_id')
    
    if not email or not org_id:
        return Response({'error': 'Email and organization_id are required fields.'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        organization = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        
    prefix = email.split('@')[0]
    parts = prefix.split('.')
    first_name = parts[0].capitalize() if len(parts) > 0 else 'First'
    last_name = parts[1].capitalize() if len(parts) > 1 else 'Last'
    
    try:
        invited_user = User.objects.get(email=email)
    except User.DoesNotExist:
        invited_user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        invited_user.set_unusable_password()
        invited_user.save()
        
    employee, created = Employee.objects.get_or_create(
        user=invited_user,
        defaults={
            'organization': organization,
            'position': 'Site Crew',
            'department': 'Operations'
        }
    )
    if not created:
        employee.organization = organization
        employee.save()
        
    notification = Notification.objects.create(
        recipient=invited_user,
        organization=organization,
        title='Organization Invitation',
        message=f'You have been invited to join the organization "{organization.name}".',
        notification_type='invitation'
    )
    
    subject = f'Invitation to join {organization.name} on TraceFlow'
    message = f'Hi {first_name},\n\nYou have been invited to join "{organization.name}" on TraceFlow.\nLog in to your account or register using this email to view your shifts.\n\nBest regards,\nTraceFlow Team'
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL or 'noreply@traceflow.com',
            [email],
            fail_silently=True
        )
    except Exception as email_err:
        print(f"Failed to send invite email: {email_err}")
        
    return Response({
        'message': 'Invitation sent successfully.',
        'employee': {
            'id': employee.id,
            'email': invited_user.email,
            'firstName': invited_user.first_name,
            'lastName': invited_user.last_name,
            'department': employee.department,
            'status': 'OFF DUTY',
            'location': 'Invited via Email',
            'ip': ''
        }
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([AllowAny])
def keep_alive_view(request):
    """
    Heartbeat endpoint for preventing service from sleeping.
    """
    print('Service is awake')
    return Response({"status": "active", "message": "Service is awake"}, status=status.HTTP_200_OK)
