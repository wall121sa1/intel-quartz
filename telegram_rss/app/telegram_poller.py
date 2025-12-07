import asyncio
from pathlib import Path
from datetime import timezone
from typing import Dict, List
from .utils import telethon_to_safe_json

import sqlalchemy as sa
from sqlalchemy.orm import Session
from telethon import TelegramClient

from .config import AppConfig
from .db import get_session
from telethon.tl.types import Channel as TLChannel, Chat as TLChat, User as TLUser

from .models import Bot as BotModel, Channel, ChannelNameHistory, Feed, Message

SESSION_DIR = Path("/app/sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _entity_display_name(entity) -> str:
    if hasattr(entity, "title") and entity.title:
        return entity.title
    parts = []
    for attr in ("first_name", "last_name", "username"):
        val = getattr(entity, attr, None)
        if val:
            parts.append(val)
    return " ".join(parts)


def _infer_dialog_type(entity) -> str:
    if isinstance(entity, TLChannel):
        return "channel"
    if isinstance(entity, TLChat):
        return "group"
    if isinstance(entity, TLUser):
        return "user"
    return type(entity).__name__


async def start_telegram_pollers(config: AppConfig):
    """Start a polling loop for each bot defined in config."""
    print("[telegram_poller] Starting pollers...")

    # Ensure bots exist in DB, then start one client per bot
    db = get_session()
    try:
        # Sync BotModel rows with config.bots (idempotent)
        bots = _sync_bots_from_config(db, config)
    finally:
        db.close()

    if not bots:
        print("[telegram_poller] No bots configured; poller will not start.")
        return

    # One supervised task per bot
    tasks = []
    for bot in bots:
        # Find matching config for this bot
        cfg = next((b for b in config.bots if b.name == bot.name), None)
        if not cfg:
            continue

        tasks.append(asyncio.create_task(_run_bot_poller_safe(cfg, bot, config)))

    await asyncio.gather(*tasks)


async def _run_bot_poller_safe(bot_cfg, bot_model: BotModel, config: AppConfig):
    """Run a bot poller with self-recovery on errors."""

    while True:
        try:
            await _run_bot_poller(bot_cfg, bot_model, config)
        except asyncio.CancelledError:
            # Allow graceful shutdown
            raise
        except Exception as e:
            print(
                f"[telegram_poller] Poller for {bot_cfg.name} crashed: {e}. "
                f"Restarting after backoff..."
            )
            await asyncio.sleep(5)


def _sync_bots_from_config(db: Session, config: AppConfig) -> List[BotModel]:
    """Ensure Bot rows exist for each config entry."""
    from .models import Bot as BotModel  # local import

    bots: List[BotModel] = []
    for bcfg in config.bots:
        bot = db.query(BotModel).filter_by(name=bcfg.name).first()
        if not bot:
            bot = BotModel(
                name=bcfg.name,
                theme=bcfg.theme,
                api_id=bcfg.api_id,
                api_hash=bcfg.api_hash,
                session_name=bcfg.session_name,
                enabled=True,
            )
            db.add(bot)
        else:
            bot.api_id = bcfg.api_id
            bot.api_hash = bcfg.api_hash
            bot.session_name = bcfg.session_name
            bot.theme = bcfg.theme

        bots.append(bot)

    db.commit()
    return bots


async def _run_bot_poller(bot_cfg, bot_model: BotModel, config: AppConfig):
    """Run polling loop for a single bot (one Telegram user/account)."""

    print(f"[telegram_poller] Starting bot poller: {bot_cfg.name}")

    client = TelegramClient(
        session=str(SESSION_DIR / bot_cfg.session_name),
        api_id=bot_cfg.api_id,
        api_hash=bot_cfg.api_hash,
    )

    await client.start()  # may prompt on first run (for CLI; in Docker you'd pre-authorize)

    try:
        while True:
            await _poll_bot_channels(client, bot_model.id, config)
            await asyncio.sleep(config.polling.interval_seconds)
    finally:
        await client.disconnect()


async def _poll_bot_channels(client: TelegramClient, bot_id: int, config: AppConfig):
    """Poll all channels assigned to a given bot_id."""
    db: Session = get_session()
    try:
    active_feed_exists = sa.exists(
        sa.select(Feed.id).where(
            Feed.language == Channel.language,
            Channel.topics.any(Feed.topic),
        )
    )

    channels = (
        db.query(Channel)
        .filter(
            Channel.bot_id == bot_id,
            Channel.enabled.is_(True),
            active_feed_exists,
        )
        .all()
    )

        if not channels:
            print(
                "[telegram_poller] No channels with active RSS feeds assigned to "
                f"bot {bot_id}; skipping this cycle."
            )
            return

        for idx, ch in enumerate(channels):
            await _poll_single_channel(db, client, ch, config)
            if idx < len(channels) - 1:
                await asyncio.sleep(config.polling.per_channel_delay_seconds)
    finally:
        db.close()


async def _poll_single_channel(
    db: Session,
    client: TelegramClient,
    channel: Channel,
    config: AppConfig,
):
    """Fetch new messages for one channel and store them."""
    last_msg_id = channel.last_msg_id or 0
    max_batch = config.polling.batch_size

    try:
        # Ensure we've joined the channel if needed
        try:
            entity = await client.get_entity(channel.telegram_id)
        except Exception:
            # Try join by username; for private channels you need an invite link
            print(f"[telegram_poller] Joining channel {channel.telegram_id}")
            entity = await client.join_channel(channel.telegram_id)

        # Track name/ID changes for dialogs we already know about
        current_name = _entity_display_name(entity)
        dialog_type = _infer_dialog_type(entity)
        numeric_id = getattr(entity, "id", None)

        metadata_changed = False
        if current_name and current_name != channel.display_name:
            db.add(
                ChannelNameHistory(
                    channel_id=channel.id,
                    old_name=channel.display_name,
                    new_name=current_name,
                )
            )
            channel.display_name = current_name
            metadata_changed = True
        if numeric_id and channel.telegram_numeric_id != numeric_id:
            channel.telegram_numeric_id = numeric_id
            metadata_changed = True
        if dialog_type != channel.dialog_type:
            channel.dialog_type = dialog_type
            metadata_changed = True

        if metadata_changed:
            db.commit()

        # Fetch messages newer than last_msg_id
        from telethon.tl.functions.messages import GetHistoryRequest

        # For simplicity we use client.iter_messages; Telethon handles pagination nicely
        new_msgs = []
        async for msg in client.iter_messages(
            channel.telegram_id,
            limit=max_batch,
            min_id=last_msg_id,
        ):
            if msg.message:
                new_msgs.append(msg)

        if not new_msgs:
            return

        # Telethon iter_messages gives newest first by default; sort ascending
        new_msgs.sort(key=lambda m: m.id)

        for m in new_msgs:
            exists = (
                db.query(Message)
                .filter(
                    Message.channel_id == channel.id,
                    Message.telegram_msg_id == m.id,
                )
                .first()
            )
            if exists:
                continue

            sent_at = m.date
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)

            text = m.message or ""
            url = None
            # If it's a public channel, we can construct a t.me link
            if isinstance(channel.telegram_id, str) and channel.telegram_id.startswith("@"):
                username = channel.telegram_id.lstrip("@")
                url = f"https://t.me/{username}/{m.id}"

            msg_row = Message(
                channel_id=channel.id,
                telegram_msg_id=m.id,
                sent_at=sent_at,
                text=text,
                url=url,
                raw_json=telethon_to_safe_json(m) if hasattr(m, "to_dict") else None,
            )
            db.add(msg_row)

            # Update last_msg_id as we go
            channel.last_msg_id = m.id

        db.commit()

        print(
            f"[telegram_poller] Channel {channel.telegram_id}: "
            f"stored {len(new_msgs)} new messages."
        )
    except Exception as e:
        print(f"[telegram_poller] Error polling {channel.telegram_id}: {e}")
        db.rollback()
