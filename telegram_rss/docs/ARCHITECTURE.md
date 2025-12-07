# Architecture

This document describes how the Telegram RSS Service is assembled and how data flows through its components.

## Runtime topology
- **FastAPI application (`app.main`)** — exposes HTTP endpoints and wires up lifespan hooks.
- **PostgreSQL database** — stores bots, channels, messages, feeds, and feed items.
- **Background tasks** —
  - `telegram_poller.start_telegram_pollers`: starts one Telethon client per configured bot and ingests messages.
  - `release_scheduler.start_release_scheduler`: periodically publishes new `FeedItem` records from recently ingested messages.

The FastAPI lifespan handler loads configuration, initializes the database engine, and starts both background tasks. On shutdown it cancels and awaits those tasks for a graceful exit.

## Configuration loading
- Static defaults live in `config.yaml` (polling intervals, staging limits, database URL, and bot identities).
- At startup `app.config.load_config` reads the YAML, injects secrets from environment variables (`{BOT}_API_ID`/`{BOT}_API_HASH`), and optionally overrides the database URL from `DATABASE_URL` (intended for non-Docker or remote database setups).
- The resulting `AppConfig` instance is attached to `app.state.config` for request handlers and background workers.

## Database layer
- SQLAlchemy `Base` and session factory are initialized via `app.db.init_db` during startup.
- Models in `app.models` define the relational schema:
  - **Bot** — Telegram API credentials and session information.
  - **Channel** — Telegram channel metadata and assignment to a bot.
  - **Message** — Persisted Telegram messages with metadata and raw payload.
  - **Feed** — Language/topic combinations that define RSS feeds.
  - **FeedItem** — Join table connecting feeds to messages and recording publication times.
- Tables are created on startup through `app.db.create_all_tables`.

## Message ingestion
1. Poller bootstraps bot rows from configuration (`_sync_bots_from_config`).
2. Each bot runs its own Telethon client, fetching channels assigned to the bot (`Channel.bot_id`).
3. For each channel with an active feed (language/topic present in `feeds`), `_poll_single_channel` ensures membership, iterates recent messages newer than `last_msg_id`, and stores unseen messages.
4. Channels are polled with a short configurable delay (`polling.per_channel_delay_seconds`) between each request to stay within Telegram API rate limits.
5. Channels track `last_msg_id` to resume efficiently between polling cycles.

## Releasing feed items
1. On each cycle (configured by `staging.release_interval_minutes`), all feeds are scanned.
2. Channels matching each feed's `language` and `topic` are located via the `topics` array column.
3. Messages newer than the feed's `last_release_at` are promoted into `FeedItem` rows, capped by `staging.max_items_per_release`.
4. `last_release_at` is advanced to the most recent promoted message timestamp, preventing duplicates.

## RSS rendering
- `app.rss_api.get_rss` selects a feed by `language` and `topic`, then fetches the newest items ordered by `published_at`.
- Item counts respect per-feed limits (`Feed.max_items`) or the global default (`staging.default_max_items`).
- Responses are serialized as RSS 2.0 XML using Python's `xml.etree.ElementTree`.

## Dashboard and channel management
- `app.dashboard` offers HTML views of bots and channels plus a form to add channels.
- Channels require a Telegram identifier, language, topics list, and associated bot. Validation ensures required fields exist and the bot is present before inserting.

## Session storage
- Telethon session files are stored under `/app/sessions` in the container. `docker-compose.yml` mounts the host `./sessions` directory into that path to persist login state across restarts.

## Logging and observability
- The poller and release scheduler print basic progress/error messages to stdout. When running under Docker, these appear in container logs. For production use, replace prints with structured logging and monitoring.
