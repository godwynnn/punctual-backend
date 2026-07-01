import os
import sys
import logging
import requests
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)



def send_employee_whatsapp_buttons(employee_id):
    print(employee_id)
    from employee.models import Employee
    try:
        employee = Employee.objects.select_related('user', 'organization').get(id=employee_id)
    except Employee.DoesNotExist:
        logger.error(f"[WhatsApp] Employee {employee_id} not found.")
        return

    recipient_phone = employee.whatsapp_no
    print(recipient_phone)
    if not recipient_phone:
        logger.warning(f"[WhatsApp] Employee {employee.id} has no WhatsApp number configured.")
        return

    # Clean recipient phone number (remove leading +, other non-digits)
    if recipient_phone.startswith("+"):
        recipient_phone = recipient_phone[1:]
    recipient_phone = "".join(filter(str.isdigit, recipient_phone))

    org_name = employee.organization.name if employee.organization else "your organization"
    first_name = employee.user.first_name if employee.user else "Employee"

    # Message text
    message_body = f"Hello {first_name}, please clock in or clock out for {org_name}."

    # Development Fallback: Always print to console safely
    print("\n" + "="*50)
    print(f"--- WHATSAPP BUTTONS MESSAGE SENT TO {employee.whatsapp_no} ---")
    try:
        print(message_body)
        print("Buttons: [Clock In] [Clock Out]")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'ascii'
        print(message_body.encode(encoding, errors='replace').decode(encoding))
    print("="*50 + "\n")

    # Meta Cloud API Send Logic
    phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID")
    access_token = os.getenv("META_WA_ACCESS_TOKEN")

    if phone_number_id and access_token:
        print('sending')
        url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Structure for 2 reply buttons: clock in and clock out
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": message_body
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "clock_in",
                                "title": "Clock In"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "clock_out",
                                "title": "Clock Out"
                            }
                        }
                    ]
                }
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f"[WhatsApp] Successfully sent buttons message to employee {employee.id} ({recipient_phone}).")
            else:
                logger.error(f"[WhatsApp] Meta API error (Status {response.status_code}): {response.text}")
                response.raise_for_status()
        except Exception as e:
            logger.error(f"[WhatsApp] Failed to send buttons message to employee {employee.id}: {str(e)}")


def send_whatsapp_text_message(recipient_phone, message_body):
    # Clean recipient phone number (remove leading +, other non-digits)
    if recipient_phone.startswith("+"):
        recipient_phone = recipient_phone[1:]
    recipient_phone = "".join(filter(str.isdigit, recipient_phone))

    print("\n" + "="*50)
    print(f"--- WHATSAPP TEXT MESSAGE SENT TO {recipient_phone} ---")
    try:
        print(message_body)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'ascii'
        print(message_body.encode(encoding, errors='replace').decode(encoding))
    print("="*50 + "\n")

    # Meta Cloud API Send Logic
    phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID")
    access_token = os.getenv("META_WA_ACCESS_TOKEN")

    if phone_number_id and access_token:
        url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "body": message_body
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f"[WhatsApp] Successfully sent text message to {recipient_phone}.")
            else:
                logger.error(f"[WhatsApp] Meta API error (Status {response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"[WhatsApp] Failed to send text message to {recipient_phone}: {str(e)}")

