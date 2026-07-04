from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Task, TaskAssignment
from organization.models import Organization
from employee.models import Employee
from .serializers import (
    TaskSerializer, 
    CreateTaskSerializer, 
    UpdateTaskSerializer, 
    SubmitAssignmentSerializer,
    TaskAssignmentSerializer
)
from utils.cloudinary_utils import upload_to_cloudinary

class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = self.request.user
        # If user is an employee, they see tasks assigned to them
        if hasattr(user, 'employee'):
            return Task.objects.filter(assignees=user.employee).distinct().order_by('-created_at')
        
        # If user is an employer, they see tasks in organizations they own
        owned_orgs = Organization.objects.filter(owner=user)
        return Task.objects.filter(organization__in=owned_orgs).distinct().order_by('-created_at')

    @action(detail=False, methods=['POST'], url_path='create_assign')
    def creating_assign_task(self, request):
        serializer = CreateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        org_id = serializer.validated_data['organization_id']
        # Check organization ownership
        organization = get_object_or_404(Organization, id=org_id)
        if organization.owner != request.user:
            return Response(
                {"error": "You do not own this organization."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Check files/urls
        file_url = None
        uploaded_file = request.FILES.get('file_attach')
        if uploaded_file:
            try:
                upload_res = upload_to_cloudinary(uploaded_file)
                file_url = upload_res['url']
            except Exception as e:
                return Response({"error": f"Failed to upload file to Cloudinary: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            file_url = serializer.validated_data.get('file_attach')

        # Create Task
        task = Task.objects.create(
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', ''),
            organization=organization,
            due_date=serializer.validated_data.get('due_date'),
            file_attach=file_url,
            link_attach=serializer.validated_data.get('link_attach')
        )

        # Assign to employees
        assignee_ids = serializer.validated_data.get('assignee_ids', [])
        valid_employees = Employee.objects.filter(id__in=assignee_ids, organization=organization)
        
        from users.models import Notification
        assignments = []
        for emp in valid_employees:
            assignment, created = TaskAssignment.objects.get_or_create(task=task, employee=emp)
            assignments.append(assignment)
            if created:
                Notification.objects.create(
                    recipient=emp.user,
                    organization=organization,
                    title="New Task Assigned",
                    message=f"You have been assigned to task: '{task.title}'",
                    notification_type="task"
                )

        task_serializer = TaskSerializer(task)
        return Response(task_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['PUT', 'PATCH'], url_path='update_assign')
    def update_assign_task(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        
        # Check organization ownership
        if task.organization.owner != request.user:
            return Response(
                {"error": "You do not own this organization."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = UpdateTaskSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Update Task Fields
        if 'title' in serializer.validated_data:
            task.title = serializer.validated_data['title']
        if 'description' in serializer.validated_data:
            task.description = serializer.validated_data['description']
        if 'due_date' in serializer.validated_data:
            task.due_date = serializer.validated_data['due_date']

        # Check files/urls
        uploaded_file = request.FILES.get('file_attach')
        if uploaded_file:
            try:
                upload_res = upload_to_cloudinary(uploaded_file)
                task.file_attach = upload_res['url']
            except Exception as e:
                return Response({"error": f"Failed to upload file to Cloudinary: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        elif 'file_attach' in serializer.validated_data:
            task.file_attach = serializer.validated_data['file_attach']
            
        if 'link_attach' in serializer.validated_data:
            task.link_attach = serializer.validated_data['link_attach']

        task.save()

        # Update Assignees if provided
        from users.models import Notification
        if 'assignee_ids' in serializer.validated_data:
            assignee_ids = serializer.validated_data['assignee_ids']
            valid_employees = Employee.objects.filter(id__in=assignee_ids, organization=task.organization)
            
            # Remove old assignments not in the new list
            TaskAssignment.objects.filter(task=task).exclude(employee__in=valid_employees).delete()
            
            # Add new assignments
            for emp in valid_employees:
                assignment, created = TaskAssignment.objects.get_or_create(task=task, employee=emp)
                if created:
                    Notification.objects.create(
                        recipient=emp.user,
                        organization=task.organization,
                        title="New Task Assigned",
                        message=f"You have been assigned to task: '{task.title}'",
                        notification_type="task"
                    )
                else:
                    Notification.objects.create(
                        recipient=emp.user,
                        organization=task.organization,
                        title="Task Updated",
                        message=f"The details of your assigned task '{task.title}' have been updated.",
                        notification_type="task"
                    )
        else:
            # If details like due_date or title updated, notify all currently assigned employees
            for assignment in task.assignments.all():
                Notification.objects.create(
                    recipient=assignment.employee.user,
                    organization=task.organization,
                    title="Task Details Updated",
                    message=f"The details of your assigned task '{task.title}' have been updated.",
                    notification_type="task"
                )

        task_serializer = TaskSerializer(task)
        return Response(task_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], url_path='submit_assignment')
    def submit_task_assignment(self, request, pk=None):
        task = get_object_or_404(Task, id=pk)
        
        # Verify request user is an employee
        if not hasattr(request.user, 'employee'):
            return Response(
                {"error": "Only employees can submit task assignments."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        employee = request.user.employee
        assignment = get_object_or_404(TaskAssignment, task=task, employee=employee)

        serializer = SubmitAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment.status = serializer.validated_data.get('status', 'completed')
        assignment.notes = serializer.validated_data.get('notes', '')

        # Check files/urls
        uploaded_file = request.FILES.get('file_attach')
        if uploaded_file:
            try:
                upload_res = upload_to_cloudinary(uploaded_file)
                assignment.file_attach = upload_res['url']
            except Exception as e:
                return Response({"error": f"Failed to upload file to Cloudinary: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        elif 'file_attach' in serializer.validated_data:
            assignment.file_attach = serializer.validated_data['file_attach']

        if 'link_attach' in serializer.validated_data:
            assignment.link_attach = serializer.validated_data['link_attach']

        assignment.save()

        assignment_serializer = TaskAssignmentSerializer(assignment)
        return Response(assignment_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'], url_path='employee_task')
    def employee_task(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({"error": "Only employees can access this endpoint."}, status=status.HTTP_403_FORBIDDEN)
        tasks = Task.objects.filter(assignees=request.user.employee).distinct().order_by('-created_at')
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'], url_path='employee_task_detail')
    def employee_task_detail(self, request, pk=None):
        if not hasattr(request.user, 'employee'):
            return Response({"error": "Only employees can access this endpoint."}, status=status.HTTP_403_FORBIDDEN)
        task = get_object_or_404(Task, id=pk, assignees=request.user.employee)
        serializer = TaskSerializer(task)
        return Response(serializer.data)
