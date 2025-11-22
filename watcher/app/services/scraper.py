import feedparser
import ssl
from newspaper import Article as NewspaperArticle
from datetime import datetime
from time import mktime

# Fix for SSL context issues on some environments
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

class ScraperService:
    @staticmethod
    def parse_feed(feed_url):
        """Parses an RSS feed and returns a list of entry dictionaries."""
        try:
            return feedparser.parse(feed_url)
        except Exception as e:
            print(f"Error parsing feed {feed_url}: {e}")
            return None

    @staticmethod
    def fetch_full_text(url):
        """Uses newspaper3k to download and parse article text."""
        try:
            article = NewspaperArticle(url)
            article.download()
            article.parse()
            return article.text
        except Exception as e:
            print(f"Error scraping full text for {url}: {e}")
            return None

    @staticmethod
    def normalize_date(entry):
        """Extracts a python datetime object from a feed entry."""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        return datetime.utcnow()