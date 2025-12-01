from celery import shared_task
from app.models import db, Feed, Article, SystemConfig
from app.services.scraper import ScraperService
from app.services.nlp import NLPService
from app.services.translator import TranslatorService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def fetch_feed_task(self, feed_id):
    """
    Task to process a SINGLE feed.
    Running one task per feed allows better parallelism.
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
            # Check duplication
            if Article.query.filter_by(url=entry.link).first():
                continue

            # Process Article
            try:
                process_single_article(feed, entry)
                new_count += 1
            except Exception as e:
                logger.error(f"Error processing article {entry.link}: {e}")

        db.session.commit()
        return f"Synced {feed.name}: {new_count} new articles."

    except Exception as e:
        db.session.rollback()
        logger.error(f"Feed Task Error: {e}")
        raise self.retry(exc=e, countdown=60)

def process_single_article(feed, entry):
    # 1. Fetch
    full_text = ScraperService.fetch_full_text(entry.link)
    content_original = full_text if full_text and len(full_text) > 100 else entry.get('summary', entry.title)

    # 2. Detect & Translate
    detected_lang = TranslatorService.detect_language(content_original)
    content_english = content_original
    title_english = entry.title

    if detected_lang != 'en':
        content_english = TranslatorService.translate(content_original, detected_lang)
        title_english = TranslatorService.translate(entry.title, detected_lang)
        content_original = f"# {entry.title}\n\n{content_original}"

    # 3. NLP (Heavy Calculation - Now in Worker)
    nlp_result = NLPService.process_text(content_english)

    # 4. Create Object
    new_article = Article(
        feed_id=feed.id,
        title=title_english,
        url=entry.link,
        pub_date=ScraperService.normalize_date(entry),
        added_date=datetime.utcnow(),
        content_raw=content_english,
        content_edited=nlp_result['content_with_links'],
        language=detected_lang,
        content_original=content_original,
        organizations=",".join(nlp_result['entities']['orgs']),
        people=",".join(nlp_result['entities']['people']),
        locations=",".join(nlp_result['entities']['locs']),
        events=",".join(nlp_result['entities']['events']),
        tags=",".join(nlp_result['entities']['tags']),
        status='PENDING',
        vault_id=feed.vault_id
    )
    db.session.add(new_article)