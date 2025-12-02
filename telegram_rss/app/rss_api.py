from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .db import get_session
from .models import Feed, FeedItem
from .config import load_config

router = APIRouter()
config = load_config()

@router.get("/rss/{language}/{topic}")
def get_rss(language: str, topic: str, db: Session = Depends(get_session)):
    feed = db.query(Feed).filter_by(language=language, topic=topic).first()
    if not feed:
        return Response(status_code=404, content="Feed not found")

    max_items = feed.max_items or config.staging.default_max_items

    items = (
        db.query(FeedItem)
        .filter(FeedItem.feed_id == feed.id)
        .join(FeedItem.message)
        .order_by(FeedItem.published_at.desc())
        .limit(max_items)
        .all()
    )

    # Build RSS XML (simple hand-built string)
    now = datetime.now(timezone.utc)
    channel_title = f"Telegram feed: {language}/{topic}"
    base_url = "http://localhost:8000"  # later: make configurable

    xml_items = []
    for fi in items:
        msg = fi.message
        title = (msg.text[:80] + "...") if len(msg.text) > 80 else msg.text
        link = msg.url or base_url
        pub_date = fi.published_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml_items.append(f"""
        <item>
          <title><![CDATA[{title}]]></title>
          <description><![CDATA[{msg.text}]]></description>
          <link>{link}</link>
          <pubDate>{pub_date}</pubDate>
        </item>
        """)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{channel_title}</title>
    <link>{base_url}/rss/{language}/{topic}</link>
    <description>Telegram RSS feed for {language}/{topic}</description>
    <lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>
    {''.join(xml_items)}
  </channel>
</rss>
"""

    return Response(content=xml, media_type="application/rss+xml")
