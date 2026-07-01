from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    name = 'organization'

    def ready(self):
        import os
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('RUN_MAIN'):
            from attendance.scheduler import scheduler
            from apscheduler.triggers.cron import CronTrigger
            from .tasks import send_daily_whatsapp_reminders
            
            # Avoid adding duplicate jobs if ready is called multiple times
            if not any(job.id == 'daily_whatsapp_reminders' for job in scheduler.get_jobs()):
                try:
                    scheduler.add_job(
                        send_daily_whatsapp_reminders,
                        trigger=CronTrigger(hour=5, minute=0),
                        # trigger='interval',
                        # seconds=30,
                        id="daily_whatsapp_reminders",
                        replace_existing=True
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"[Scheduler] Error scheduling daily WhatsApp reminders: {str(e)}")
