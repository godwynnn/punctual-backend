from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from organization.models import Organization
from employee.models import Employee
from organization.tasks import send_daily_whatsapp_reminders
from utils.whatsapp import send_employee_whatsapp_buttons

User = get_user_model()

class WhatsAppSchedulerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create users
        self.user1 = User.objects.create_user(email="emp1@test.com", password="password")
        self.user2 = User.objects.create_user(email="emp2@test.com", password="password")
        self.user3 = User.objects.create_user(email="emp3@test.com", password="password")
        
        # Create organizations
        self.org_social = Organization.objects.create(name="Org Social", use_social=True)
        self.org_no_social = Organization.objects.create(name="Org No Social", use_social=False)
        
        # Create active employee with whatsapp on social org
        self.emp_active_social = Employee.objects.create(
            user=self.user1,
            organization=self.org_social,
            status='active',
            is_active=True,
            whatsapp_no="+1234567890"
        )
        
        # Create inactive employee with whatsapp on social org
        self.emp_inactive_social = Employee.objects.create(
            user=self.user2,
            organization=self.org_social,
            status='pending',
            is_active=True,
            whatsapp_no="+111111111"
        )
        
        # Create active employee on non-social org
        self.emp_active_non_social = Employee.objects.create(
            user=self.user3,
            organization=self.org_no_social,
            status='active',
            is_active=True,
            whatsapp_no="+222222222"
        )

    def test_organization_fields(self):
        self.assertTrue(self.org_social.use_social)
        self.assertFalse(self.org_no_social.use_social)

    def test_employee_fields(self):
        self.assertEqual(self.emp_active_social.whatsapp_no, "+1234567890")

    @patch('django_rq.get_queue')
    def test_send_daily_whatsapp_reminders(self, mock_get_queue):
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        # Trigger scheduled task function
        send_daily_whatsapp_reminders()

        # Should only enqueue the active employee belonging to org_social
        mock_queue.enqueue.assert_called_once_with(send_employee_whatsapp_buttons, self.emp_active_social.id)

    @patch('requests.post')
    @patch.dict('os.environ', {
        'META_WA_PHONE_NUMBER_ID': '123456',
        'META_WA_ACCESS_TOKEN': 'secret_token'
    })
    def test_send_employee_whatsapp_buttons(self, mock_post):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        send_employee_whatsapp_buttons(self.emp_active_social.id)

        # Assert post is called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("123456/messages", args[0])
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer secret_token")
        
        payload = kwargs['json']
        self.assertEqual(payload['messaging_product'], "whatsapp")
        self.assertEqual(payload['type'], "interactive")
        self.assertEqual(payload['interactive']['type'], "button")
        
        buttons = payload['interactive']['action']['buttons']
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0]['reply']['id'], "clock_in")
        self.assertEqual(buttons[1]['reply']['id'], "clock_out")

    @patch('requests.post')
    @patch.dict('os.environ', {
        'META_WA_PHONE_NUMBER_ID': '123456',
        'META_WA_ACCESS_TOKEN': 'secret_token'
    })
    def test_send_whatsapp_location_request(self, mock_post):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        from utils.whatsapp import send_whatsapp_location_request
        send_whatsapp_location_request("+1234567890", "Tap below to verify location")

        # Assert post is called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("123456/messages", args[0])
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer secret_token")
        
        payload = kwargs['json']
        self.assertEqual(payload['messaging_product'], "whatsapp")
        self.assertEqual(payload['type'], "interactive")
        self.assertEqual(payload['interactive']['type'], "location_request_message")
        self.assertEqual(payload['interactive']['body']['text'], "Tap below to verify location")
        self.assertEqual(payload['interactive']['action']['name'], "send_location")

    @patch.dict('os.environ', {'META_WA_VERIFY_TOKEN': 'secret_verify_token'})
    def test_webhook_verification_get(self):
        response = self.client.get(
            '/api/employee/whatsapp-webhook/',
            {'hub.mode': 'subscribe', 'hub.verify_token': 'secret_verify_token', 'hub.challenge': '12345'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '12345')

        response = self.client.get(
            '/api/employee/whatsapp-webhook/',
            {'hub.mode': 'subscribe', 'hub.verify_token': 'wrong_token', 'hub.challenge': '12345'}
        )
        self.assertEqual(response.status_code, 403)

    @patch('utils.whatsapp.send_whatsapp_location_request')
    @patch('utils.whatsapp.send_whatsapp_text_message')
    def test_webhook_clock_in_success(self, mock_send_text, mock_send_location_req):
        # Configure geofence on organization
        self.org_social.office_latitude = 6.453053
        self.org_social.office_longitude = 3.395830
        self.org_social.allowed_radius = 100.0
        self.org_social.save()

        # Step 1: Click button
        payload_btn = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": "clock_in",
                                    "title": "Clock In"
                                }
                            }
                        }]
                    }
                }]
            }]
        }
        res_btn = self.client.post('/api/employee/whatsapp-webhook/', payload_btn, format='json')
        self.assertEqual(res_btn.status_code, 200)
        self.assertIn("Tap below to share location", mock_send_location_req.call_args[0][1])

        # Step 2: Send valid location
        mock_send_text.reset_mock()
        payload_loc = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "location",
                            "location": {
                                "latitude": 6.453060,
                                "longitude": 3.395840
                            }
                        }]
                    }
                }]
            }]
        }
        res_loc = self.client.post('/api/employee/whatsapp-webhook/', payload_loc, format='json')
        self.assertEqual(res_loc.status_code, 200)

        # Verify attendance record is created
        from attendance.models import Attendance
        attendance = Attendance.objects.filter(employee=self.emp_active_social).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.method, 'social_wa')
        self.assertIsNotNone(attendance.check_in)
        self.assertIsNone(attendance.check_out)
        
        self.assertIn("✅ *Clock In Successful!*", mock_send_text.call_args[0][1])

    @patch('utils.whatsapp.send_whatsapp_location_request')
    @patch('utils.whatsapp.send_whatsapp_text_message')
    def test_webhook_clock_out_success(self, mock_send_text, mock_send_location_req):
        from attendance.models import Attendance
        from django.utils import timezone
        
        self.org_social.office_latitude = 6.453053
        self.org_social.office_longitude = 3.395830
        self.org_social.allowed_radius = 100.0
        self.org_social.save()

        attendance = Attendance.objects.create(
            employee=self.emp_active_social,
            organization=self.org_social,
            date=timezone.localdate(),
            check_in=timezone.now(),
            method='social_wa'
        )

        # Step 1: Click button
        payload_btn = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": "clock_out",
                                    "title": "Clock Out"
                                }
                            }
                        }]
                    }
                }]
            }]
        }
        res_btn = self.client.post('/api/employee/whatsapp-webhook/', payload_btn, format='json')
        self.assertEqual(res_btn.status_code, 200)

        # Step 2: Send valid location
        mock_send_text.reset_mock()
        payload_loc = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "location",
                            "location": {
                                "latitude": 6.453060,
                                "longitude": 3.395840
                            }
                        }]
                    }
                }]
            }]
        }
        res_loc = self.client.post('/api/employee/whatsapp-webhook/', payload_loc, format='json')
        self.assertEqual(res_loc.status_code, 200)

        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.check_out)
        self.assertIn("✅ *Clock Out Successful!*", mock_send_text.call_args[0][1])

    @patch('utils.whatsapp.send_whatsapp_location_request')
    @patch('utils.whatsapp.send_whatsapp_text_message')
    def test_webhook_clock_out_failure_no_clock_in(self, mock_send_text, mock_send_location_req):
        self.org_social.office_latitude = 6.453053
        self.org_social.office_longitude = 3.395830
        self.org_social.allowed_radius = 100.0
        self.org_social.save()

        # Step 1: Click button
        payload_btn = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": "clock_out",
                                    "title": "Clock Out"
                                }
                            }
                        }]
                    }
                }]
            }]
        }
        res_btn = self.client.post('/api/employee/whatsapp-webhook/', payload_btn, format='json')
        self.assertEqual(res_btn.status_code, 200)

        # Step 2: Send location
        mock_send_text.reset_mock()
        payload_loc = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "location",
                            "location": {
                                "latitude": 6.453060,
                                "longitude": 3.395840
                            }
                        }]
                    }
                }]
            }]
        }
        res_loc = self.client.post('/api/employee/whatsapp-webhook/', payload_loc, format='json')
        self.assertEqual(res_loc.status_code, 200)
        self.assertIn("❌ *Error:* You need to clock in first", mock_send_text.call_args[0][1])

    @patch('utils.whatsapp.send_whatsapp_location_request')
    @patch('utils.whatsapp.send_whatsapp_text_message')
    def test_webhook_geofence_violation(self, mock_send_text, mock_send_location_req):
        # Configure geofence on organization
        self.org_social.office_latitude = 6.453053
        self.org_social.office_longitude = 3.395830
        self.org_social.allowed_radius = 100.0 # 100 meters
        self.org_social.save()

        # Step 1: Click button
        payload_btn = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": "clock_in",
                                    "title": "Clock In"
                                }
                            }
                        }]
                    }
                }]
            }]
        }
        self.client.post('/api/employee/whatsapp-webhook/', payload_btn, format='json')

        # Step 2: Send out of bounds location (e.g. London coordinates)
        mock_send_text.reset_mock()
        payload_loc = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "type": "location",
                            "location": {
                                "latitude": 51.5074,
                                "longitude": -0.1278
                            }
                        }]
                    }
                }]
            }]
        }
        res_loc = self.client.post('/api/employee/whatsapp-webhook/', payload_loc, format='json')
        self.assertEqual(res_loc.status_code, 200)
        
        # Verify attendance record is NOT created due to violation
        from attendance.models import Attendance
        attendance = Attendance.objects.filter(employee=self.emp_active_social).first()
        self.assertIsNone(attendance)
        self.assertIn("Geofence Violation", mock_send_text.call_args[0][1])

    @patch('utils.whatsapp.send_whatsapp_welcome_template')
    def test_update_profile(self, mock_send_whatsapp):
        # Authenticate the user
        self.client.force_authenticate(user=self.user1)

        payload = {
            "first_name": "Johnny",
            "last_name": "Doe",
            "phone_no": "+9876543210",
            "whatsapp_no": "+2345678901"
        }

        response = self.client.put(
            '/api/employee/profile/update/',
            payload,
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        
        # Verify database was updated
        self.user1.refresh_from_db()
        self.emp_active_social.refresh_from_db()
        
        self.assertEqual(self.user1.first_name, "Johnny")
        self.assertEqual(self.user1.last_name, "Doe")
        self.assertEqual(self.user1.phone_no, "+9876543210")
        self.assertEqual(self.emp_active_social.whatsapp_no, "+2345678901")

        # Verify welcome template was sent to the new WhatsApp number
        mock_send_whatsapp.assert_called_once_with(
            "+2345678901"
        )

    @patch('utils.whatsapp.send_whatsapp_welcome_template')
    def test_update_profile_no_whatsapp_change(self, mock_send_whatsapp):
        # Authenticate the user
        self.client.force_authenticate(user=self.user1)

        # Send same whatsapp_no as currently set (+1234567890)
        payload = {
            "first_name": "Johnny",
            "last_name": "Doe",
            "whatsapp_no": "+1234567890"
        }

        response = self.client.put(
            '/api/employee/profile/update/',
            payload,
            format='json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify database was updated
        self.emp_active_social.refresh_from_db()
        self.assertEqual(self.emp_active_social.whatsapp_no, "+1234567890")

        # Verify no welcome template was sent because the number did not change
        mock_send_whatsapp.assert_not_called()

