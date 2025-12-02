import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .config import AppConfig
from .db import get_session
from .models import Feed, Channel, Message, FeedItem


async def start_release_scheduler(config: AppConfig):
    """Background task: periodically promote new messages to feed_items."""
    interval = config.staging.release_interval_minutes * 60

    while True:
        try:
            await _run_release_cycle(config)
        except Exception as e:
            # In production, you'd log this properly
            print(f"[release_scheduler] Error: {e}")
        await asyncio.sleep(interval)


async def run_release_cycle_once(config: AppConfig):
    """Run a single release cycle (useful for tests or manual invocations)."""
    await _run_release_cycle(config)


async def _run_release_cycle(config: AppConfig):
    print("[release_scheduler] Running release cycle...")
    db: Session = get_session()
    try:
        _ensure_feeds_exist(db, config)
        feeds = db.query(Feed).all()
        for feed in feeds:
            _release_for_feed(db, feed, config)
    finally:
        db.close()


def _release_for_feed(db: Session, feed: Feed, config: AppConfig):
    now = datetime.now(timezone.utc)
    last_release = feed.last_release_at or datetime.min.replace(tzinfo=timezone.utc)

    # Find channels that belong to this feed
    channels = (
        db.query(Channel)
        .filter(
            Channel.language == feed.language,
            Channel.topics.any(feed.topic),
            Channel.enabled.is_(True),
        )
        .all()
    )
    if not channels:
        # Nothing for this feed
        feed.last_release_at = now
        db.commit()
        return

    channel_ids = [c.id for c in channels]

    # Get messages newer than last_release
    max_batch = config.staging.max_items_per_release

    new_messages = (
        db.query(Message)
        .filter(
            Message.channel_id.in_(channel_ids),
            Message.sent_at > last_release,
        )
        .order_by(Message.sent_at.asc())
        .limit(max_batch)
        .all()
    )

    if not new_messages:
        feed.last_release_at = now
        db.commit()
        return

    # Promote messages to feed_items
    for msg in new_messages:
        exists = (
            db.query(FeedItem)
            .filter(FeedItem.feed_id == feed.id, FeedItem.message_id == msg.id)
            .first()
        )
        if exists:
            continue

        fi = FeedItem(
            feed_id=feed.id,
            message_id=msg.id,
            published_at=now,
        )
        db.add(fi)

    # Set last_release_at to last message's sent_at
    feed.last_release_at = new_messages[-1].sent_at
    db.commit()

    print(
        f"[release_scheduler] Feed {feed.language}/{feed.topic}: "
        f"released {len(new_messages)} messages."
    )


def _ensure_feeds_exist(db: Session, config: AppConfig) -> None:
    """Create feeds for any language/topic pairs referenced by channels."""

    channels = db.query(Channel).filter(Channel.enabled.is_(True)).all()
    existing = {(f.language, f.topic) for f in db.query(Feed).all()}

    created = False
    for channel in channels:
        for topic in channel.topics:
            key = (channel.language, topic)
            if key in existing:
                continue

            slug = f"{channel.language}-{topic}"
            feed = Feed(
                language=channel.language,
                topic=topic,
                slug=slug,
                max_items=config.staging.max_items_per_feed,
            )
            db.add(feed)
            existing.add(key)
            created = True

    if created:
        db.commit()
