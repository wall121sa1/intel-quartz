from datetime import datetime
from time import mktime

import feedparser
import requests
from newspaper import Article as NewspaperArticle

class ScraperService:
    FEED_TIMEOUT = 10
    ARTICLE_TIMEOUT = 15
    _session = requests.Session()

    @staticmethod
    def parse_feed(feed_url):
        """Parses an RSS feed and returns a list of entry dictionaries."""
        try:
            response = ScraperService._session.get(feed_url, timeout=ScraperService.FEED_TIMEOUT)
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception as e:
            print(f"Error parsing feed {feed_url}: {e}")
            return None

    @staticmethod
    def fetch_full_text(url):
        """Uses newspaper3k to download and parse article text."""
        try:
            response = ScraperService._session.get(url, timeout=ScraperService.ARTICLE_TIMEOUT)
            response.raise_for_status()

            article = NewspaperArticle(url)
            article.set_html(response.text)
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