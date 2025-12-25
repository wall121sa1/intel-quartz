import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
import yaml
from telethon import TelegramClient
from telethon.tl.types import Channel as TLChannel, Chat as TLChat, User as TLUser


# Make "app" importable when running "python scripts/list_dialogs.py ..."
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.config import load_config
from app.credentials import get_bot_credentials, get_bot_env_keys
from app.db import init_db, get_session
from app.models import Bot as BotModel, Channel as ChannelModel


def get_bot_env_credentials(bot_name: str):
    api_id_env, api_hash_env = get_bot_env_keys(bot_name)
    api_id, api_hash, _ = get_bot_credentials(bot_name)

    if not api_id or not api_hash:
        raise SystemExit(
            f"Missing env vars {api_id_env} / {api_hash_env} for bot '{bot_name}'.\n"
            "Set them in your environment, credentials file, or .env file."
        )

    return int(api_id), api_hash


def ensure_bot_row(db, bot_name: str, config) -> BotModel:
    """Ensure a Bot row exists for this name (similar to sync in telegram_poller)."""
    # Find bot config
    bcfg = next((b for b in config.bots if b.name == bot_name), None)
    if not bcfg:
        raise SystemExit(f"Bot '{bot_name}' not found in config.yaml")

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


def guess_sensitivity(entity) -> str:
    """
    Heuristic:
      - Public channel with username -> "public"
      - Everything else (private groups, private chats) -> "sensitive"
    """
    username = getattr(entity, "username", None)
    if isinstance(entity, TLChannel) and username:
        return "public"
    return "sensitive"


def guess_telegram_id(dialog) -> str:
    """
    Use @username if available; otherwise use internal ID as string.
    """
    entity = dialog.entity
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    # fall back to numeric dialog id
    return str(dialog.id)


async def main_async(bot_name: str, do_import: bool):
    load_dotenv()
    config = load_config()  # uses env vars for DB URL & api creds

    # Init DB
    init_db(config.database.url)
    db = get_session()

    # Ensure bot row exists / updated
    bot_row = ensure_bot_row(db, bot_name, config)

    # Get env credentials
    api_id, api_hash = get_bot_env_credentials(bot_name)

    # Find bot config for session_name
    bcfg = next((b for b in config.bots if b.name == bot_name), None)
    if not bcfg:
        raise SystemExit(f"Bot '{bot_name}' not found in config.yaml")

    sessions_dir = ROOT / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    session_path = sessions_dir / bcfg.session_name

    client = TelegramClient(
        session=session_path.as_posix(),
        api_id=api_id,
        api_hash=api_hash,
    )

    async with client:
        print(f"Listing dialogs for bot '{bot_name}' using session {session_path}...\n")

        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            name = dialog.name
            eid = guess_telegram_id(dialog)

            # Classify type
            if isinstance(entity, TLChannel):
                dlg_type = "channel"
            elif isinstance(entity, TLChat):
                dlg_type = "group"
            elif isinstance(entity, TLUser):
                dlg_type = "user"
            else:
                dlg_type = type(entity).__name__

            sensitivity = guess_sensitivity(entity)

            print(f"- [{dlg_type}] {name!r}  id={eid}  sensitivity={sensitivity}")

            if do_import:
                # See if channel already exists
                existing = (
                    db.query(ChannelModel)
                    .filter(ChannelModel.telegram_id == eid)
                    .first()
                )
                if existing:
                    # Update bot_id if needed
                    if existing.bot_id != bot_row.id:
                        existing.bot_id = bot_row.id
                        db.commit()
                    continue

                # Default values; you can adjust later in dashboard
                channel = ChannelModel(
                    telegram_id=eid,
                    language="unknown",          # you can fix this via dashboard
                    topics=["unclassified"],     # you can fix this via dashboard
                    bot_id=bot_row.id,
                    sensitivity=sensitivity,
                )
                db.add(channel)
                db.commit()
                print(f"  -> imported into channels table with language='unknown', topics=['unclassified']")

        print("\nDone.")


def main():
    parser = argparse.ArgumentParser(
        description="List all dialogs for a bot, optionally importing them into the channels table."
    )
    parser.add_argument(
        "bot_name",
        help="Bot name as in config.yaml (e.g. MESS_BOT)",
    )
    parser.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="Import dialogs into the channels table with default language/topics.",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args.bot_name, args.do_import))


if __name__ == "__main__":
    main()
