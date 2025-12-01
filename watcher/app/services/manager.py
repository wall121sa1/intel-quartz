from app.models import Feed, SystemConfig
from app.tasks import fetch_feed_task
from datetime import datetime, timezone

class FeedManager:
    @staticmethod
    def sync_all_feeds():
        """
        Dispatches a background task for every feed.
        This function returns almost immediately, preventing blocking.
        """
        feeds = Feed.query.all()
        print(f"Manager: Dispatching sync for {len(feeds)} feeds...")
        
        for feed in feeds:
            # Dispatch to Celery
            fetch_feed_task.delay(feed.id)
            
        # Update timestamp
        SystemConfig.set('last_run_timestamp', datetime.now(timezone.utc).isoformat())
        return {'status': 'dispatched', 'count': len(feeds)}