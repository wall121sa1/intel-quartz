import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.utils import telethon_to_safe_json

from dotenv import load_dotenv
from telethon import TelegramClient

# Make project-root 'app' importable


from app.config import load_config
from app.db import init_db, get_session
from app.models import Bot as BotModel, Channel as ChannelModel, Message as MessageModel, Feed, FeedItem
from app.release_scheduler import run_release_cycle_once

def get_bot_env_credentials(bot_name: str):
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
        raise SystemExit(
            f"Missing env vars {api_id_env} / {api_hash_env} for bot '{bot_name}'.\n"
            f"Set them in your environment or in a .env file."
        )

    return int(api_id), api_hash


def choose_bot(db, config) -> BotModel:
    bots: List[BotModel] = db.query(BotModel).all()
    if not bots:
        # maybe not synced yet, build from config
        for bcfg in config.bots:
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
        bots = db.query(BotModel).all()

    print("\nAvailable bots:")
    for i, bot in enumerate(bots, 1):
        print(f" [{i}] {bot.name} (theme={bot.theme or '–'})")

    while True:
        choice = input("Select bot by number: ").strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(bots):
            return bots[idx - 1]
        print("Invalid selection.")


def choose_channel(db, bot: BotModel) -> ChannelModel:
    channels: List[ChannelModel] = (
        db.query(ChannelModel)
        .filter(ChannelModel.bot_id == bot.id)
        .order_by(ChannelModel.telegram_id.asc())
        .all()
    )

    if not channels:
        raise SystemExit(
            f"No channels found for bot '{bot.name}'. "
            "Use the dashboard or dialog sync to add some first."
        )

    print(f"\nChannels for bot {bot.name}:")
    for i, ch in enumerate(channels, 1):
        topics_str = ", ".join(ch.topics) if ch.topics else ""
        print(
            f" [{i}] id={ch.id} telegram_id={ch.telegram_id} "
            f"lang={ch.language} topics=[{topics_str}] sensitivity={ch.sensitivity} "
            f"enabled={'yes' if ch.enabled else 'no'}"
        )

    while True:
        choice = input("Select channel by number: ").strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(channels):
            return channels[idx - 1]
        print("Invalid selection.")


def configure_channel_fields(db, channel: ChannelModel):
    print("\nConfigure channel parameters (leave blank to keep current value):")

    lang_current = channel.language or ""
    lang_new = input(f" Language [{lang_current}]: ").strip()
    if lang_new:
        channel.language = lang_new

    topics_current = ", ".join(channel.topics) if channel.topics else ""
    topics_new = input(f" Topics (comma-separated) [{topics_current or 'unclassified'}]: ").strip()
    if topics_new:
        channel.topics = [t.strip() for t in topics_new.split(",") if t.strip()]
    elif not channel.topics:
        channel.topics = ["unclassified"]

    sens_current = channel.sensitivity or "public"
    sens_new = input(f" Sensitivity (public/sensitive) [{sens_current}]: ").strip().lower()
    if sens_new in ("public", "sensitive"):
        channel.sensitivity = sens_new

    enabled_current = "yes" if channel.enabled else "no"
    enabled_new = input(f" Enabled? (yes/no) [{enabled_current}]: ").strip().lower()
    if enabled_new in ("yes", "no"):
        channel.enabled = (enabled_new == "yes")

    db.commit()
    print(
        f"\nChannel updated: lang={channel.language}, topics={channel.topics}, "
        f"sensitivity={channel.sensitivity}, enabled={channel.enabled}"
    )


def ask_limit() -> Optional[int]:
    print("\nHow many messages to backfill?")
    print(" - Enter a number (e.g. 500) to limit the count")
    print(" - Leave blank to fetch ALL available history")

    val = input(" Backfill message count [all]: ").strip()
    if not val:
        return None
    if not val.isdigit():
        print("Invalid number, defaulting to ALL.")
        return None
    return int(val)


def ensure_feeds_for_channel(db, channel: ChannelModel):
    """
    Ensure Feed rows exist for each topic of this channel, so the scheduler
    can promote messages into the right RSS feeds.
    """
    from app.models import Feed  # imported here to avoid circulars in some setups

    for topic in channel.topics or []:
        slug = f"{channel.language}_{topic}"
        existing = (
            db.query(Feed)
            .filter(Feed.language == channel.language, Feed.topic == topic)
            .first()
        )
        if not existing:
            feed = Feed(language=channel.language, topic=topic, slug=slug)
            db.add(feed)
            db.commit()
            print(f" Created feed: language={channel.language}, topic={topic}, slug={slug}")


async def backfill_messages_for_channel(
    bot: BotModel,
    channel: ChannelModel,
    limit: Optional[int],
    config,
):
    """
    Use Telethon to fetch historical messages for one channel and store them
    in the messages table. Then trigger a release cycle so they appear in feeds.
    """
    from datetime import timezone

    api_id, api_hash = get_bot_env_credentials(bot.name)

    # find matching bot config for session_name
    bcfg = next((b for b in config.bots if b.name == bot.name), None)
    if not bcfg:
        raise SystemExit(f"Bot '{bot.name}' not found in config.yaml")

    sessions_dir = ROOT / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    session_path = sessions_dir / bcfg.session_name

    client = TelegramClient(
        session=session_path.as_posix(),
        api_id=api_id,
        api_hash=api_hash,
    )

    print(
        f"\nBackfilling messages for channel {channel.telegram_id} "
        f"(limit={'ALL' if limit is None else limit})..."
    )

    async with client:
        db = get_session()
        new_count = 0
        max_seen_id = channel.last_msg_id or 0

        # iter_messages returns newest first; we'll insert, and our unique
        # constraint prevents duplicates. If you request ALL, this may be a lot.
        async for m in client.iter_messages(channel.telegram_id, limit=limit):
            if not m.message:
                continue

            exists = (
                db.query(MessageModel)
                .filter(
                    MessageModel.channel_id == channel.id,
                    MessageModel.telegram_msg_id == m.id,
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
            if isinstance(channel.telegram_id, str) and channel.telegram_id.startswith("@"):
                username = channel.telegram_id.lstrip("@")
                url = f"https://t.me/{username}/{m.id}"

            msg_row = MessageModel(
                channel_id=channel.id,
                telegram_msg_id=m.id,
                sent_at=sent_at,
                text=text,
                url=url,
                raw_json=telethon_to_safe_json(m) if hasattr(m, "to_dict") else None,
            )
            db.add(msg_row)
            new_count += 1

            if m.id > max_seen_id:
                max_seen_id = m.id

            # flush occasionally
            if new_count and new_count % 500 == 0:
                db.commit()
                print(f"  ...inserted {new_count} messages so far")

        # final commit
        db.commit()

        # update last_msg_id so normal poller doesn't refetch all of them
        if max_seen_id > (channel.last_msg_id or 0):
            channel.last_msg_id = max_seen_id
            db.commit()

        db.close()

    print(f"Backfill complete. Inserted {new_count} new messages.")


async def main_async():
    load_dotenv()
    config = load_config()

    # init DB
    init_db(config.database.url)
    db = get_session()

    # Choose bot & channel
    bot = choose_bot(db, config)
    channel = choose_channel(db, bot)

    # Configure metadata
    configure_channel_fields(db, channel)

    # Ensure feed rows exist for this channel's topics
    ensure_feeds_for_channel(db, channel)

    # Ask for limit
    limit = ask_limit()

    # Backfill
    await backfill_messages_for_channel(bot, channel, limit, config)

    # Trigger one release cycle so messages appear in feeds
    print("\nTriggering release scheduler once so messages show up in RSS feeds...")
    await run_release_cycle_once()
    print("Release cycle complete. Check your RSS feeds now.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill old messages for a selected channel into the database and feed."
    )
    # no args for now; interactive
    _ = parser.parse_args()

    asyncio.run(main_async())


if __name__ == "__main__":
    main()
