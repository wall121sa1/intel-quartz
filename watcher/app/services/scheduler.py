from flask_apscheduler import APScheduler
from app.models import SystemConfig
from app.services.manager import FeedManager
from flask import current_app
# FIX: Added ProgrammingError to catch Postgres "UndefinedTable" errors
from sqlalchemy.exc import OperationalError, ProgrammingError 

scheduler = APScheduler()
_current_interval_minutes = None

def run_schedule_task(app):
    """
    The actual function run by the background thread.
    """
    with app.app_context():
        print("Scheduler: Starting Auto-Pull...")
        try:
            stats = FeedManager.sync_all_feeds()

            from app.models import SystemConfig
            SystemConfig.set('scheduler_failures', 0)
            current_app.logger.info(
                "Scheduler auto-pull complete",
                extra={"added": stats['added'], "skipped": stats['skipped'], "errors": stats['errors']},
            )
            print("Scheduler: Auto-Pull Complete.")
        except Exception as e:
            from app.models import SystemConfig
            current_failures = int(SystemConfig.get('scheduler_failures', 0) or 0)
            SystemConfig.set('scheduler_failures', current_failures + 1)
            current_app.logger.exception("Scheduler Error")

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

        global _current_interval_minutes

        # Avoid tearing down/recreating the job when the interval hasn't changed
        if _current_interval_minutes == interval:
            return

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

        _current_interval_minutes = interval
