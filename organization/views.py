from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Organization
from .serializers import OrganizationSerializer, EmployeeAttendanceSerializer

from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError



class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        # List all organizations owned by the user/employer
        return Organization.objects.filter(owner=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        # Automatically assign the logged-in user as the owner of the organization
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['GET'], url_path='employees_attendance')
    def employees_attendance(self, request):
        # 1. Get all organizations owned by the user
        organizations = Organization.objects.filter(owner=request.user)
        # 2. Get all employees in these organizations
        from employee.models import Employee
        employees = Employee.objects.filter(organization__in=organizations)
        # 3. Get all attendance records for these employees
        from attendance.models import Attendance
        attendances = Attendance.objects.filter(employee__in=employees).order_by('-date', '-created_at')

        # 4. Paginate and return the results
        page = self.paginate_queryset(attendances)
        if page is not None:
            serializer = EmployeeAttendanceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EmployeeAttendanceSerializer(attendances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'], url_path='employees')
    def list_employees(self, request):
        organizations = Organization.objects.filter(owner=request.user)
        from employee.models import Employee
        employees = Employee.objects.filter(organization__in=organizations)
        
        data = []
        for emp in employees:
            data.append({
                'id': emp.id,
                'name': f"{emp.user.first_name} {emp.user.last_name}".strip() or emp.user.email,
                'email': emp.user.email,
                'position': emp.position,
                'department': emp.department,
                'status': emp.status,
                'organization_id': emp.organization.id,
                'organization_name': emp.organization.name
            })
        return Response(data)

def empty_stream():
    yield ": keep-alive\n\n"

def stream_employees_attendance(user, org_ids):
    import json
    import queue
    from attendance.sse_manager import sse_manager
    from .serializers import EmployeeAttendanceSerializer
    from employee.models import Employee
    from attendance.models import Attendance

    # 1. Stream the initial list of last 20 attendance records
    employees = Employee.objects.filter(organization_id__in=org_ids)
    initial_attendances = Attendance.objects.filter(employee__in=employees).order_by('-date', '-created_at')[:20]
    initial_data = EmployeeAttendanceSerializer(initial_attendances, many=True).data
    yield f"data: {json.dumps({'type': 'initial', 'data': initial_data})}\n\n"

    # 2. Register a queue under all organization IDs owned by this user
    q = queue.Queue(maxsize=50)
    with sse_manager.lock:
        for org_id in org_ids:
            if org_id not in sse_manager.listeners:
                sse_manager.listeners[org_id] = []
            sse_manager.listeners[org_id].append(q)

    # 3. Yield updates as they arrive
    try:
        while True:
            try:
                data = q.get(timeout=30)
                yield f"data: {json.dumps({'type': 'update', 'data': data})}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"
    except GeneratorExit:
        pass
    finally:
        with sse_manager.lock:
            for org_id in org_ids:
                if org_id in sse_manager.listeners:
                    if q in sse_manager.listeners[org_id]:
                        sse_manager.listeners[org_id].remove(q)
                    if not sse_manager.listeners[org_id]:
                        del sse_manager.listeners[org_id]

@csrf_exempt
def employees_attendance_sse(request):
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

    # Get all organization IDs owned by this user
    org_ids = list(Organization.objects.filter(owner=user).values_list('id', flat=True))
    if not org_ids:
        response = StreamingHttpResponse(
            empty_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    response = StreamingHttpResponse(
        stream_employees_attendance(user, org_ids),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
