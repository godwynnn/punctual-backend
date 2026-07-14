from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from organization.models import Organization
from employee.models import Employee
from task.models import Task, TaskAssignment
from task.tasks import notify_task_assignment_whatsapp
from utils.whatsapp import send_task_assignment_whatsapp_notification
import datetime
from django.utils import timezone

User = get_user_model()

class TaskWhatsAppNotificationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create users
        self.user_owner = User.objects.create_user(email="owner@test.com", password="password")
        self.user_emp1 = User.objects.create_user(email="emp1@test.com", password="password")
        self.user_emp2 = User.objects.create_user(email="emp2@test.com", password="password")
        
        # Create organization owned by owner
        self.org = Organization.objects.create(name="Test Org", owner=self.user_owner, use_social=True)
        
        # Create active employees
        self.emp1 = Employee.objects.create(
            user=self.user_emp1,
            organization=self.org,
            status='active',
            is_active=True,
            whatsapp_no="+1234567890"
        )
        self.emp2 = Employee.objects.create(
            user=self.user_emp2,
            organization=self.org,
            status='active',
            is_active=True,
            whatsapp_no="+1987654321"
        )
        
        # Authenticate owner
        self.client.force_authenticate(user=self.user_owner)

    @patch('django_rq.enqueue')
    def test_create_task_enqueues_notification(self, mock_enqueue):
        payload = {
            "title": "New Project Task",
            "description": "Complete the design specification.",
            "organization_id": self.org.id,
            "assignee_ids": [self.emp1.id],
            "due_date": "2026-08-01T12:00:00Z"
        }
        
        response = self.client.post('/api/tasks/create_assign/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Verify enqueue was called once with notify_task_assignment_whatsapp, emp1.id, and the task id
        task_id = response.data['id']
        mock_enqueue.assert_called_once_with(notify_task_assignment_whatsapp, self.emp1.id, task_id)

    @patch('django_rq.enqueue')
    def test_update_task_enqueues_new_assignments_only(self, mock_enqueue):
        # Create existing task and assign to emp1
        task = Task.objects.create(
            title="Existing Task",
            description="Initial description",
            organization=self.org
        )
        TaskAssignment.objects.create(task=task, employee=self.emp1)
        
        payload = {
            "assignee_ids": [self.emp1.id, self.emp2.id]  # emp2 is new, emp1 is existing
        }
        
        response = self.client.put(f'/api/tasks/{task.id}/update_assign/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Verify enqueue was called exactly once for the new assignee (emp2)
        mock_enqueue.assert_called_once_with(notify_task_assignment_whatsapp, self.emp2.id, task.id)

    @patch('task.tasks.send_task_assignment_whatsapp_notification')
    def test_notify_task_assignment_whatsapp_task(self, mock_send_notification):
        task = Task.objects.create(
            title="Sample Task",
            description="Sample Desc",
            organization=self.org
        )
        # Invoke background task function directly
        notify_task_assignment_whatsapp(self.emp1.id, task.id)
        mock_send_notification.assert_called_once_with(self.emp1, task)

    @patch('requests.post')
    @patch.dict('os.environ', {
        'META_WA_PHONE_NUMBER_ID': '123456',
        'META_WA_ACCESS_TOKEN': 'secret_token'
    })
    def test_send_task_assignment_whatsapp_notification_payload(self, mock_post):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create task with attachments and due date
        due_date = timezone.make_aware(datetime.datetime(2026, 8, 1, 12, 0))
        task = Task.objects.create(
            title="Important Task",
            description="Finish the docs.",
            organization=self.org,
            due_date=due_date,
            file_attach="https://cloudinary.com/doc.pdf",
            link_attach="https://github.com/repo"
        )
        
        send_task_assignment_whatsapp_notification(self.emp1, task)
        
        # Assert API payload structure
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("123456/messages", args[0])
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer secret_token")
        
        payload = kwargs['json']
        self.assertEqual(payload['messaging_product'], "whatsapp")
        self.assertEqual(payload['type'], "text")
        
        body_text = payload['text']['body']
        self.assertIn("📋 *New Task Assigned*", body_text)
        self.assertIn("*Title:* Important Task", body_text)
        self.assertIn("*Description:* Finish the docs.", body_text)
        self.assertIn("*Due Date:* 2026-08-01 12:00 PM", body_text)
        self.assertIn("*File:* https://cloudinary.com/doc.pdf", body_text)
        self.assertIn("*Link:* https://github.com/repo", body_text)

    @patch('utils.cloudinary_utils.upload_to_cloudinary')
    @patch('django_rq.enqueue')
    def test_create_task_with_file_upload(self, mock_enqueue, mock_upload):
        # Mock cloudinary upload
        mock_upload.return_value = {"url": "https://cloudinary.com/uploaded_file.png"}
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("test.png", b"file_content", content_type="image/png")
        
        payload = {
            "title": "Task with File",
            "description": "Desc",
            "organization_id": self.org.id,
            "file_attach": test_file
        }
        
        # We must use multipart format for file uploads
        response = self.client.post('/api/tasks/create_assign/', payload, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['file_attach'], "https://cloudinary.com/uploaded_file.png")

    @patch('utils.cloudinary_utils.upload_to_cloudinary')
    def test_update_task_with_file_upload(self, mock_upload):
        mock_upload.return_value = {"url": "https://cloudinary.com/updated_file.png"}
        
        task = Task.objects.create(
            title="Task to update",
            organization=self.org
        )
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("test_update.png", b"file_content", content_type="image/png")
        
        payload = {
            "file_attach": test_file
        }
        
        response = self.client.put(f'/api/tasks/{task.id}/update_assign/', payload, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['file_attach'], "https://cloudinary.com/updated_file.png")

    @patch('utils.cloudinary_utils.upload_to_cloudinary')
    def test_submit_assignment_with_file_upload(self, mock_upload):
        mock_upload.return_value = {"url": "https://cloudinary.com/submission.png"}
        
        task = Task.objects.create(
            title="Task for submission",
            organization=self.org
        )
        assignment = TaskAssignment.objects.create(task=task, employee=self.emp1)
        
        # Authenticate as emp1
        self.client.force_authenticate(user=self.user_emp1)
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("test_sub.png", b"file_content", content_type="image/png")
        
        payload = {
            "status": "completed",
            "file_attach": test_file
        }
        
        response = self.client.post(f'/api/tasks/{task.id}/submit_assignment/', payload, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['file_attach'], "https://cloudinary.com/submission.png")
