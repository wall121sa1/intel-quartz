# Telegram RSS Service

Telegram RSS Service ingests messages from configured Telegram channels, stores them in PostgreSQL, and publishes filtered RSS feeds via FastAPI. It also exposes a lightweight dashboard for managing channels.

## Features
- Polls multiple Telegram accounts ("bots") for channel messages and stores them with minimal metadata.
- Releases new messages into topic/language-specific feeds on a schedule.
- Serves RSS feeds (`/rss/{language}/{topic}`) suitable for readers or downstream processing.
- Provides a basic dashboard to view bots, list channels, and add new channels.
- `app/models.py` — SQLAlchemy models for bots, channels, messages, feeds, and feed items.
- `config.yaml` — default configuration for polling, staging, database, and bot identities.
- `.env` (user-supplied) — secrets such as API IDs and hashes for each bot.
- `docker-compose.yml` — local stack with PostgreSQL and the application service.
- `docs/` — architecture overview and operational runbooks.

## Prerequisites
- Docker and Docker Compose (for the recommended setup).
- Telegram API ID and API hash for each configured bot account.
- Optional: local Python 3.11 environment if running outside Docker.

## Quickstart (Docker Compose)
1. Copy `.env.example` to `.env` and fill in values for every bot listed in `config.yaml`. Each bot expects `NAME_API_ID` and `NAME_API_HASH` where `NAME` is the uppercase bot `name` (e.g., `RU_CRIME_BOT_API_ID`).
2. (Optional, **only when pointing at an external database**) set `DATABASE_URL` in `.env` to override the database URL in `config.yaml`. When using the bundled Postgres service, leave this unset so the app targets the `postgres` container (inside Docker the hostname is `postgres` on port `3432`; using `localhost` from the app container will not reach it).
3. Start the stack:
   ```bash
   docker-compose up --build
   ```
4. Open the dashboard at http://localhost:2000/dashboard to view bots and channels.
5. Access RSS feeds at http://localhost:2000/rss/{language}/{topic} (for example, `/rss/ru/crime`).
6. The PostgreSQL service listens on non-default port `3432` in the container and is exposed on the same host port. Point DB clients to `localhost:3432` to match the configured `DATABASE_URL`.

## Configuration reference
### Environment variables (.env)
- `DATABASE_URL` — overrides `database.url` from `config.yaml` (PostgreSQL connection string). Skip this when running with `docker-compose` unless you intend to reach a remote database.
- `{BOT_NAME}_API_ID` / `{BOT_NAME}_API_HASH` — required for each bot listed under `bots` in `config.yaml` (e.g., `RU_CRIME_BOT_API_ID`).

### `config.yaml`
- `database.url` — default PostgreSQL URL; overridden by `DATABASE_URL` when set.
- `polling.interval_seconds` — how often each bot polls its channels.
- `polling.batch_size` — maximum messages fetched per polling cycle.
- `staging.release_interval_minutes` — how often new feed items are released.
- `staging.max_items_per_release` — cap on items promoted per release cycle.
- `staging.max_items_per_feed` — maximum items retained per feed (enforced by consumers).
- `staging.default_max_items` — default RSS item limit when a feed record has no `max_items` value.
- `bots` — list of bot entries with `name`, optional `theme`, and `session_name`. API credentials are injected from environment variables at runtime.

## Running without Docker
1. Ensure PostgreSQL is reachable and create the target database.
2. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Export required environment variables (or create a `.env` file) for each bot and optional `DATABASE_URL`.
4. Run the application:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Application endpoints
- `GET /dashboard` — summary of bots and links to channel management pages.
- `GET /dashboard/channels` — table of all channels.
- `GET /dashboard/channels/new` — form to add a channel.
- `POST /dashboard/channels` — creates a channel (fields: `telegram_id`, `language`, `topics`, `bot_id`).
- `GET /rss/{language}/{topic}` — RSS feed for the given language/topic combination.
- `GET /health` — simple health check for monitoring.

## Background processes
- **Telegram poller** (`app.telegram_poller.start_telegram_pollers`): starts one Telethon client per bot, ensures bot records exist, joins configured channels, and stores new messages at `polling.interval_seconds`.
- **Release scheduler** (`app.release_scheduler.start_release_scheduler`): periodically promotes recent messages into feed items based on `staging` settings.

## Data model
- **Bot** — Telegram account configuration (API credentials, theme, session name) and related channels.
- **Channel** — Telegram channel metadata (identifier, language, topics, assigned bot, last ingested message).
- **Message** — Stored Telegram message with timestamps, text, optional URL, and raw payload.
- **Feed** — Language/topic pair defining an RSS feed with optional item cap.
- **FeedItem** — Link between a feed and a message with publication timestamp.

## Session storage
Telethon stores session files under `/app/sessions` inside the container. The compose file mounts a host `./sessions` directory to persist authentication across restarts.

## Troubleshooting
- Missing API credentials: ensure each bot in `config.yaml` has matching `*_API_ID` and `*_API_HASH` values in `.env`.
- Database initialization errors: confirm PostgreSQL is running and `DATABASE_URL` points to a reachable instance.
- Connection refused to `127.0.0.1:5432` inside Docker: remove or update `DATABASE_URL`; the compose stack uses the `postgres` service on port `3432` instead of `localhost`.
- Empty feeds: verify channels are configured for the desired `language` and `topic`, and allow time for the poller and release scheduler to ingest and release messages.

## Security considerations
- Keep `.env` and `sessions/` out of version control; `.gitignore` already excludes them.
- Limit inbound traffic to the exposed port (default 2000) if deploying beyond local development.
- Rotate bot API credentials periodically and update `.env` accordingly.

## License
MIT
