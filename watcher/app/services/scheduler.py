from flask_apscheduler import APScheduler
from app.models import SystemConfig
from app.services.manager import FeedManager
from flask import current_app

scheduler = APScheduler()

def run_schedule_task(app):
    """
    The actual function run by the background thread.
    We need to push the app context to access the DB.
    """
    with app.app_context():
        print("Scheduler: Starting Auto-Pull...")
        try:
            FeedManager.sync_all_feeds()
            
            # Update Last Run Time
            from datetime import datetime
            SystemConfig.set('last_run_timestamp', datetime.utcnow().isoformat())
            print("Scheduler: Auto-Pull Complete.")
        except Exception as e:
            print(f"Scheduler Error: {e}")

class SchedulerService:
    @staticmethod
    def init_app(app):
        scheduler.init_app(app)
        scheduler.start()
        
        # Load saved interval or default to 60 minutes
        with app.app_context():
            # Check if job exists, if not create it
            SchedulerService.update_job_interval()

    @staticmethod
    def update_job_interval():
        """
        Reads DB config and updates the APScheduler job.
        """
        try:
            # Default to 60 minutes
            interval = int(SystemConfig.get('fetch_interval_minutes', 60))
        except (ValueError, TypeError):
            interval = 60

        # Remove existing job if it exists to reset the timer
        if scheduler.get_job('auto_pull_feeds'):
            scheduler.remove_job('auto_pull_feeds')

        if interval > 0:
            print(f"Scheduler: Registering job to run every {interval} minutes.")
            scheduler.add_job(
                id='auto_pull_feeds',
                func=run_schedule_task,
                args=[current_app._get_current_object()], # Pass the app object
                trigger='interval',
                minutes=interval
            )
        else:
            print("Scheduler: Auto-pull disabled (Interval set to 0).")