import logging
import django_rq
from employee.models import Employee
from utils.whatsapp import send_employee_whatsapp_buttons

logger = logging.getLogger(__name__)

def send_daily_whatsapp_reminders():
    logger.info("[Scheduler] Starting daily WhatsApp reminders task.")
    
    print('sending')
    # Query active employees belonging to organizations with use_social=True
    employees = Employee.objects.filter(
        status='active',
        is_active=True,
        organization__use_social=True,
        whatsapp_no__isnull=False
    ).exclude(whatsapp_no='')

    count = 0
    try:
        
        queue = django_rq.get_queue('default')
        for employee in employees:
            queue.enqueue(send_employee_whatsapp_buttons, employee.id)
            count += 1
        logger.info(f"[Scheduler] Successfully enqueued {count} WhatsApp reminders in RQ.")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to enqueue WhatsApp reminders: {str(e)}")
