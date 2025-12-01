from flask_apscheduler import APScheduler
from app.models import SystemConfig
from app.services.manager import FeedManager
from flask import current_app
# FIX: Added ProgrammingError to catch Postgres "UndefinedTable" errors
from sqlalchemy.exc import OperationalError, ProgrammingError 

scheduler = APScheduler()

def run_schedule_task(app):
    """
    The actual function run by the background thread.
    """
    with app.app_context():
        print("Scheduler: Starting Auto-Pull...")
        try:
            FeedManager.sync_all_feeds()
            
            # Update Last Run Time
            from datetime import datetime, timezone
            from app.models import SystemConfig
            SystemConfig.set('last_run_timestamp', datetime.now(timezone.utc).isoformat())
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
            SchedulerService.update_job_interval()

    @staticmethod
    def update_job_interval():
        """
        Reads DB config and updates the APScheduler job.
        Handles missing DB tables gracefully.
        """
        try:
            # Try to read from DB
            val = SystemConfig.get('fetch_interval_minutes', 60)
            interval = int(val)
        # FIX: Catch ProgrammingError (Postgres) and OperationalError (SQLite)
        except (OperationalError, ProgrammingError, ValueError, TypeError, NameError):
            # If DB table doesn't exist yet, default to 60
            interval = 60
        except Exception as e:
            print(f"Scheduler Config Error: {e}")
            interval = 60

        # Remove existing job if it exists
        if scheduler.get_job('auto_pull_feeds'):
            scheduler.remove_job('auto_pull_feeds')

        if interval > 0:
            print(f"Scheduler: Registering job to run every {interval} minutes.")
            scheduler.add_job(
                id='auto_pull_feeds',
                func=run_schedule_task,
                args=[current_app._get_current_object()],
                trigger='interval',
                minutes=interval
            )
        else:
            print("Scheduler: Auto-pull disabled (Interval set to 0).")