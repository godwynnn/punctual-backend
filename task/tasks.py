import logging
from employee.models import Employee
from task.models import Task
from utils.whatsapp import send_task_assignment_whatsapp_notification

logger = logging.getLogger(__name__)

def notify_task_assignment_whatsapp(employee_id, task_id):
    try:
        employee = Employee.objects.get(id=employee_id)
        task = Task.objects.get(id=task_id)
        send_task_assignment_whatsapp_notification(employee, task)
    except Employee.DoesNotExist:
        logger.error(f"[Task WhatsApp Notification] Employee {employee_id} not found.")
    except Task.DoesNotExist:
        logger.error(f"[Task WhatsApp Notification] Task {task_id} not found.")
    except Exception as e:
        logger.error(f"[Task WhatsApp Notification] Error sending notification for employee {employee_id} and task {task_id}: {str(e)}")
