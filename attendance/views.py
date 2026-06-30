from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import json
import queue
from apscheduler.triggers.interval import IntervalTrigger

from .models import AttendanceSession, Attendance
from .serializers import AttendanceSessionSerializer, AttendanceSerializer
from organization.models import Organization
from employee.models import Employee
from utils.uuid_generator import generate_custom_id
from .scheduler import scheduler
from .sse_manager import sse_manager

def refresh_session_token(organization_id):
    try:
        session = AttendanceSession.objects.get(organization_id=organization_id)
        refresh_interval = session.organization.qr_refresh_interval or 40
        session.token = generate_custom_id(32)
        session.expires_at = timezone.now() + timedelta(seconds=refresh_interval)
        session.save()
        
        # Dispatch token update to all SSE subscribers
        sse_manager.notify(organization_id, {
            'token': session.token,
            'expires_at': session.expires_at.isoformat()
        })
    except AttendanceSession.DoesNotExist:
        try:
            scheduler.remove_job(f"org_{organization_id}")
        except Exception:
            pass

class AttendanceSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttendanceSessionSerializer
    queryset = AttendanceSession.objects.all()

    @action(detail=False, methods=['POST'], url_path='initialize')
    def initialize_qr_session(self, request):
        organization_id = request.data.get('organization_id')
        if not organization_id:
            return Response({'error': 'organization_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        organization = get_object_or_404(Organization, id=organization_id, owner=request.user)
        
        refresh_interval = organization.qr_refresh_interval or 40
        expires_at = timezone.now() + timedelta(seconds=refresh_interval)
        token = generate_custom_id(32)
        
        session, created = AttendanceSession.objects.update_or_create(
            organization=organization,
            defaults={
                'token': token,
                'expires_at': expires_at
            }
        )
        
        # Schedule the token refresh in APScheduler
        try:
            if scheduler.get_job(f"org_{organization.id}"):
                scheduler.remove_job(f"org_{organization.id}")
        except Exception:
            pass
            
        try:
            scheduler.add_job(
                refresh_session_token,
                trigger=IntervalTrigger(seconds=refresh_interval),
                args=[organization.id],
                id=f"org_{organization.id}",
                replace_existing=True
            )
        except Exception as e:
            print("Failed to schedule job in APScheduler:", e)

        # Notify active SSE connections immediately about the new initialized token
        sse_manager.notify(organization.id, {
            'token': session.token,
            'expires_at': session.expires_at.isoformat()
        })
        
        serializer = AttendanceSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AttendanceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        try:
            employee = Employee.objects.get(user=self.request.user)
            return Attendance.objects.filter(employee=employee).order_by('-date', '-created_at')
        except Employee.DoesNotExist:
            return Attendance.objects.none()

# Plain Django view for SSE streaming (bypasses DRF Content Negotiation to avoid 406 errors)
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def session_sse(request, org_id):
    # Extract token from query params or headers (since EventSource does not support headers natively)
    token_str = request.GET.get('token')
    if not token_str:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1]
            
    if not token_str:
        return JsonResponse({'error': 'Authentication credentials were not provided.'}, status=401)
        
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token_str)
        user = jwt_auth.get_user(validated_token)
    except (InvalidToken, TokenError):
        return JsonResponse({'error': 'Invalid or expired token.'}, status=401)

    # Verify user owns the organization
    organization = get_object_or_404(Organization, id=org_id, owner=user)
    
    response = StreamingHttpResponse(
        stream_session_tokens(org_id),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

def stream_session_tokens(org_id):
    # Yield the current session token if it is still valid
    try:
        session = AttendanceSession.objects.get(organization_id=org_id)
        if not session.is_expired():
            yield f"data: {json.dumps({'token': session.token, 'expires_at': session.expires_at.isoformat()})}\n\n"
    except AttendanceSession.DoesNotExist:
        pass

    q = sse_manager.register(org_id)
    try:
        while True:
            try:
                data = q.get(timeout=30)
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                # Send keep-alive comment to prevent connection close
                yield ": keep-alive\n\n"
    except GeneratorExit:
        pass
    finally:
        sse_manager.unregister(org_id, q)
