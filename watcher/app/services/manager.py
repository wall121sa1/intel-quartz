from flask import current_app
from app.models import Article, Feed, SystemConfig, db
from app.services.scraper import ScraperService
from app.services.nlp import NLPService
from app.services.translator import TranslatorService
from datetime import datetime

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
        stats = {'added': 0, 'errors': 0, 'skipped': 0}

        for feed in feeds:
            current_app.logger.info("Syncing feed", extra={"feed": feed.name})

            existing_urls = {
                url for (url,) in db.session.query(Article.url).filter(Article.feed_id == feed.id).all()
            }

            rss_data = ScraperService.parse_feed(feed.url)
            if not rss_data or not hasattr(rss_data, 'entries'):
                stats['errors'] += 1
                continue

            for entry in rss_data.entries:
                if entry.link in existing_urls:
                    stats['skipped'] += 1
                    continue

                try:
                    # 1. Fetch Full Content
                    full_text = ScraperService.fetch_full_text(entry.link)
                    content_original = full_text if full_text and len(full_text) > 100 else entry.get('summary', entry.title)

                    # 2. Detect Language
                    detected_lang = TranslatorService.detect_language(content_original)
                    
                    # 3. Translate (if not English)
                    content_english = content_original
                    title_english = entry.title # Default to original
                    
                    if detected_lang != 'en':
                        print(f"Detected {detected_lang}. Translating content and title...")
                        content_english = TranslatorService.translate(content_original, detected_lang)
                        title_english = TranslatorService.translate(entry.title, detected_lang)
                        
                        # Prepend original title to original content for reference
                        content_original = f"# {entry.title}\n\n{content_original}"

                    # 4. Run NLP (On the English text)
                    nlp_result = NLPService.process_text(content_english)
                    
                    # 5. Save
                    new_article = Article(
                        feed_id=feed.id,
                        title=title_english,            # Saved as English (used for filename)
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
                    stats['added'] += 1

                except Exception as e:
                    current_app.logger.exception("Error processing entry", extra={"url": entry.link})
                    stats['errors'] += 1

            db.session.commit()
        SystemConfig.set('last_run_timestamp', datetime.utcnow().isoformat())

        return stats
