import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

def ping_keep_alive():
    """
    Pings the keep-alive endpoint to prevent the service from sleeping.
    """
    backend_url = os.getenv('BACKEND_URL')
    if not backend_url:
        # In production, BACKEND_URL should be set to the public URL (e.g. https://qrmarket.onrender.com)
        backend_url = "http://127.0.0.1:8000"
    
    url = f"{backend_url.rstrip('/')}/api/listener/keep-alive/"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            print(f"[Cron] Keep-alive ping successful to {url}")
        else:
            print(f"[Cron] Keep-alive ping failed: {response.status_code}")
    except Exception as e:
        print(f"[Cron] Keep-alive error: {str(e)}")


scheduler = BackgroundScheduler()


def start_scheduler():
    """
    Starts the background scheduler if not already running.
    """
    if not scheduler.running:
        scheduler.start()
        print("[Cron] Background scheduler started.")
    
    env = os.getenv('ENV', 'dev')
    if env == 'prod':
        if not scheduler.get_job('keep_alive_ping'):
            scheduler.add_job(ping_keep_alive, 'interval', minutes=10, id='keep_alive_ping')
            print("[Cron] Keep-alive ping registered.")
