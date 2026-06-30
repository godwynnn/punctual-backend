from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        import os
        # Only start scheduler once in the main runserver thread
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('RUN_MAIN'):
            from .scheduler import scheduler
            if not scheduler.running:
                scheduler.start()
