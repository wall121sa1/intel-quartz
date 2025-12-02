import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel as TLChannel, Chat as TLChat, User as TLUser

from .config import load_config
from .db import get_session
from .models import Bot as BotModel, Channel as ChannelModel


def _guess_sensitivity(entity) -> str:
    """
    Heuristic:
      - Public channel with username -> "public"
      - Everything else (private groups, private chats) -> "sensitive"
    """
    username = getattr(entity, "username", None)
    if isinstance(entity, TLChannel) and username:
        return "public"
    return "sensitive"


def _guess_telegram_id(dialog) -> str:
    """
    Use @username if available; otherwise use internal dialog id as string.
    """
    entity = dialog.entity
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    return str(dialog.id)


def _get_bot_env_credentials(bot_name: str):
    """
    For a bot named 'MESS_BOT', expect:
      MESS_BOT_API_ID
      MESS_BOT_API_HASH
    """
    env_prefix = bot_name.upper()
    api_id_env = f"{env_prefix}_API_ID"
    api_hash_env = f"{env_prefix}_API_HASH"

    api_id = os.getenv(api_id_env)
    api_hash = os.getenv(api_hash_env)

    if not api_id or not api_hash:
        raise RuntimeError(
            f"Missing env vars {api_id_env} / {api_hash_env} for bot '{bot_name}'. "
            f"Set them in your environment or .env file."
        )

    return int(api_id), api_hash


def _ensure_bot_row(db, bot_name: str, config) -> BotModel:
    """Ensure a Bot row exists/updated to match config."""
    bcfg = next((b for b in config.bots if b.name == bot_name), None)
    if not bcfg:
        raise RuntimeError(f"Bot '{bot_name}' not found in config.yaml")

    bot = db.query(BotModel).filter_by(name=bot_name).first()
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
        db.commit()
    else:
        bot.api_id = bcfg.api_id
        bot.api_hash = bcfg.api_hash
        bot.session_name = bcfg.session_name
        bot.theme = bcfg.theme
        db.commit()
    return bot


async def sync_dialogs_for_bot(bot_name: str, import_new: bool = True) -> int:
    """
    Discover dialogs for the given bot and (optionally) import them
    into the channels table with default language/topics.

    Returns the number of dialogs imported (new channels created).
    """
    load_dotenv()
    config = load_config()
    db = get_session()

    # Ensure bot row is present/updated
    bot_row = _ensure_bot_row(db, bot_name, config)

    # Credentials & session
    api_id, api_hash = _get_bot_env_credentials(bot_name)
    bcfg = next((b for b in config.bots if b.name == bot_name), None)
    if not bcfg:
        raise RuntimeError(f"Bot '{bot_name}' not found in config.yaml")

    sessions_dir = Path("sessions")
    sessions_dir.mkdir(exist_ok=True)
    session_path = sessions_dir / bcfg.session_name

    client = TelegramClient(
        session=session_path.as_posix(),
        api_id=api_id,
        api_hash=api_hash,
    )

    imported_count = 0

    async with client:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            name = dialog.name
            eid = _guess_telegram_id(dialog)

            # Classify type (not yet stored, but could be useful later)
            if isinstance(entity, TLChannel):
                dlg_type = "channel"
            elif isinstance(entity, TLChat):
                dlg_type = "group"
            elif isinstance(entity, TLUser):
                dlg_type = "user"
            else:
                dlg_type = type(entity).__name__

            sensitivity = _guess_sensitivity(entity)

            if not import_new:
                # If not importing, just skip writing; we could log somewhere if needed.
                continue

            existing = (
                db.query(ChannelModel)
                .filter(ChannelModel.telegram_id == eid)
                .first()
            )
            if existing:
                # Make sure it's assigned to the right bot
                if existing.bot_id != bot_row.id:
                    existing.bot_id = bot_row.id
                    db.commit()
                continue

            channel = ChannelModel(
                telegram_id=eid,
                language="unknown",         # you can edit via dashboard
                topics=["unclassified"],    # you can edit via dashboard
                bot_id=bot_row.id,
                sensitivity=sensitivity,
                enabled=True,
            )
            db.add(channel)
            db.commit()
            imported_count += 1

    db.close()
    return imported_count
