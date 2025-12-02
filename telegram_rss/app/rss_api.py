from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from .config import AppConfig
from .db import get_session
from .models import Feed, FeedItem

router = APIRouter()


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


@router.get("/rss/{language}/{topic}")
def get_rss(
    language: str,
    topic: str,
    db: Session = Depends(get_session),
    config: AppConfig = Depends(get_config),
    request: Request = None,
):
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

    now = datetime.now(timezone.utc)
    base_url = str(request.base_url).rstrip("/") if request else ""

    root = ET.Element("rss", attrib={"version": "2.0"})
    channel_el = ET.SubElement(root, "channel")
    ET.SubElement(channel_el, "title").text = f"Telegram feed: {language}/{topic}"
    ET.SubElement(channel_el, "link").text = f"{base_url}/rss/{language}/{topic}"
    ET.SubElement(channel_el, "description").text = (
        f"Telegram RSS feed for {language}/{topic}"
    )
    ET.SubElement(channel_el, "lastBuildDate").text = now.strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    for fi in items:
        msg = fi.message
        safe_text = msg.text or ""
        title = (safe_text[:80] + "...") if len(safe_text) > 80 else safe_text
        link = msg.url or base_url or ""
        pub_date = fi.published_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

        item_el = ET.SubElement(channel_el, "item")
        ET.SubElement(item_el, "title").text = title
        ET.SubElement(item_el, "description").text = safe_text
        ET.SubElement(item_el, "link").text = link
        ET.SubElement(item_el, "pubDate").text = pub_date

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(content=xml_bytes, media_type="application/rss+xml")
