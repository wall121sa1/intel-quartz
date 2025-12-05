"""Dedicated worker entrypoint for scraping/translation jobs.

This process runs outside the main web container so heavy dependencies like
newspaper3k and Argos Translate don't compete for memory with the UI.
"""
import os
import time

from app import create_app, db
from app.services.scheduler import SchedulerService


def main() -> None:
    # Force-enable the scheduler in this process even if the default is disabled.
    os.environ.setdefault("ENABLE_SCHEDULER", "true")

    app = create_app()

    with app.app_context():
        db.create_all()
        SchedulerService.update_job_interval()

    app.logger.info("Background worker started; awaiting scheduled feed sync tasks.")

    try:
        while True:
            with app.app_context():
                try:
                    # Pull the latest interval so user changes take effect without a restart
                    SchedulerService.update_job_interval()
                except Exception:
                    app.logger.exception("Failed to refresh scheduler interval; retaining previous schedule.")
            time.sleep(60)
    except KeyboardInterrupt:
        app.logger.info("Background worker shutting down")


if __name__ == "__main__":
    main()
