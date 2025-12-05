from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from time import mktime
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from newspaper import Article as NewspaperArticle

class ScraperService:
    FEED_TIMEOUT = 10
    ARTICLE_TIMEOUT = 15
    PARSE_TIMEOUT = 10
    _session = None

    @staticmethod
    def normalize_url(url: str | None) -> str | None:
        """Normalize URLs to reduce duplicate articles from the same source.

        The normalization is intentionally conservative: it trims whitespace,
        lowercases the scheme/host, strips fragments, removes trailing slashes,
        and drops common tracking parameters (utm_*). Query parameters are
        re-encoded to provide stable ordering for comparisons.
        """

        if not url:
            return None

        cleaned = url.strip()
        if not cleaned:
            return None

        try:
            parsed = urlparse(cleaned)
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            filtered_query = [
                (k, v) for k, v in query_pairs if not k.lower().startswith("utm_")
            ]

            normalized = urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path.rstrip("/") or "/",
                    "",
                    urlencode(filtered_query, doseq=True),
                    "",
                )
            )

            return normalized
        except Exception:
            # If anything goes wrong, fall back to the trimmed value so we still
            # have a stable string to compare.
            return cleaned

    @staticmethod
    def parse_feed(feed_url):
        """Parses an RSS feed and returns a list of entry dictionaries."""
        try:
            response = ScraperService._get_session().get(
                feed_url,
                timeout=ScraperService.FEED_TIMEOUT,
            )
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception as e:
            print(f"Error parsing feed {feed_url}: {e}")
            return None

    @staticmethod
    def fetch_full_text(url):
        """Uses newspaper3k to download and parse article text."""
        try:
            response = ScraperService._get_session().get(
                url,
                timeout=ScraperService.ARTICLE_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()
            return ScraperService._parse_article_html(url, response.text)
        except Exception as e:
            print(f"Error scraping full text for {url}: {e}")
            return None

    @staticmethod
    def _parse_article_html(url, html):
        """Parse article HTML with a timeout to avoid hanging workers."""

        def parse():
            article = NewspaperArticle(url)
            article.set_html(html)
            article.parse()
            return article.text

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(parse)
            try:
                return future.result(timeout=ScraperService.PARSE_TIMEOUT)
            except FuturesTimeoutError:
                print(
                    f"Error scraping full text for {url}: parse exceeded "
                    f"{ScraperService.PARSE_TIMEOUT}s"
                )
                return None

    @staticmethod
    def normalize_date(entry):
        """Extracts a python datetime object from a feed entry."""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        return datetime.utcnow()

    @staticmethod
    def _get_session():
        """Return a configured requests session with retries and UA.

        The adapter pools are deliberately sized to 1 to prevent concurrent
        outbound fetches from this process. Combined with serial feed
        processing in FeedManager, this keeps memory usage predictable.
        """
        if ScraperService._session is None:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (compatible; IntelQuartzBot/1.0)",
            })

            retry = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
            )
            adapter = HTTPAdapter(
                max_retries=retry,
                pool_connections=1,
                pool_maxsize=1,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            ScraperService._session = session

        return ScraperService._session
