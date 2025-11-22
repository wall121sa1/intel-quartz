from app import db
from app.models import Feed, Article
from app.services.scraper import ScraperService
from app.services.nlp import NLPService
from datetime import datetime

class FeedManager:
    @staticmethod
    def sync_all_feeds():
        """
        Main entry point:
        1. Iterates all feeds in DB
        2. Scrapes new items
        3. Runs NLP
        4. Saves to DB as 'PENDING'
        """
        feeds = Feed.query.all()
        stats = {'added': 0, 'errors': 0, 'skipped': 0}
        
        for feed in feeds:
            print(f"Syncing feed: {feed.name}...")
            
            # 1. Parse RSS
            rss_data = ScraperService.parse_feed(feed.url)
            if not rss_data or not hasattr(rss_data, 'entries'):
                print(f"Failed to parse {feed.url}")
                stats['errors'] += 1
                continue

            for entry in rss_data.entries:
                # 2. Check De-duplication
                if Article.query.filter_by(url=entry.link).first():
                    stats['skipped'] += 1
                    continue

                try:
                    # 3. Fetch Full Content
                    # Fallback to summary if full text fails
                    full_text = ScraperService.fetch_full_text(entry.link)
                    content_raw = full_text if full_text and len(full_text) > 100 else entry.get('summary', entry.title)

                    # 4. Run NLP
                    nlp_result = NLPService.process_text(content_raw)
                    
                    # 5. Create DB Object
                    # Convert lists to CSV strings for simple SQLite storage
                    new_article = Article(
                        feed_id=feed.id,
                        title=entry.title,
                        url=entry.link,
                        pub_date=ScraperService.normalize_date(entry),
                        added_date=datetime.utcnow(),
                        content_raw=content_raw,
                        content_edited=nlp_result['content_with_links'], # Pre-filled with links
                        organizations=",".join(nlp_result['entities']['orgs']),
                        people=",".join(nlp_result['entities']['people']),
                        locations=",".join(nlp_result['entities']['locs']),
                        status='PENDING', # Waiting for user review
                        vault_id=feed.vault_id
                    )

                    db.session.add(new_article)
                    stats['added'] += 1

                except Exception as e:
                    print(f"Error processing entry {entry.link}: {e}")
                    stats['errors'] += 1
            
            # Commit per feed to save progress
            db.session.commit()
            
        return stats