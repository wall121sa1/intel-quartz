import logging

from celery import shared_task

from app.models import Article, Feed, db
from app.services.manager import FeedManager
from app.services.scraper import ScraperService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def fetch_feed_task(self, feed_id):
    """
    Task to process a SINGLE feed.
    Runs entries sequentially to keep memory usage low.
    """
    try:
        feed = Feed.query.get(feed_id)
        if not feed:
            return f"Feed {feed_id} not found"

        logger.info(f"Task: Syncing feed {feed.name}...")
        rss_data = ScraperService.parse_feed(feed.url)

        if not rss_data or not hasattr(rss_data, 'entries'):
            return f"Failed to parse {feed.name}"

        new_count = 0

        for entry in rss_data.entries:
            normalized_link = ScraperService.normalize_url(getattr(entry, "link", None))
            if not normalized_link:
                continue

            # Check duplication
            if Article.query.filter_by(url=normalized_link).first():
                continue

            # Process Article serially
            try:
                process_single_article(feed, entry, normalized_link)
                new_count += 1
            except Exception as e:
                logger.error(f"Error processing article {entry.link}: {e}")

        return f"Synced {feed.name}: {new_count} new articles."

    except Exception as e:
        db.session.rollback()
        logger.error(f"Feed Task Error: {e}")
        raise self.retry(exc=e, countdown=60)


def process_single_article(feed, entry, normalized_link: str):
    """Thin wrapper that reuses the sequential FeedManager path."""
    try:
        FeedManager._process_entry(feed.id, feed.vault_id, entry, normalized_link)
    except Exception:
        db.session.rollback()
        raise
