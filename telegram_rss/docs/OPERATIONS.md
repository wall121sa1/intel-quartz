# Operations and Maintenance

This guide covers routine operational tasks for the Telegram RSS Service.

## Starting and stopping
- **Docker Compose** (recommended):
  - Start: `docker-compose up --build`
  - Stop: `docker-compose down`
- **Local process**:
  - Start with Uvicorn: `uvicorn app.main:app --reload --port 8000`
  - Stop with `Ctrl+C`.

## Managing credentials
- Store Telegram API IDs and hashes in `.env` (one pair per bot). The bot names come from the `bots` list in `config.yaml`.
- Rotate credentials by updating `.env`, restarting the app, and re-authenticating if Telethon prompts.
- Keep `.env` and `sessions/` private; they are ignored by Git.

## Working with bots and channels
- Bots are synchronized from configuration at startup; ensure every bot in `config.yaml` has corresponding credentials.
- Use `/dashboard/channels/new` to create channels. Fields:
  - `telegram_id` — `@username` or invite link.
  - `language` — short code used by feeds (e.g., `ru`, `fa`).
  - `topics` — comma-separated tags; feeds join on the `topic` value.
  - `bot_id` — assign the channel to one of the configured bots.
- Disable a channel by marking `enabled=false` directly in the database (UI toggle is not yet available).

## Database care
- PostgreSQL data is stored in the `pgdata` volume (Docker) or your configured host database.
- Back up regularly using `pg_dump` against the `telegram_rss` database.
- If schema changes are introduced, recreate tables by dropping and restarting (migrations are not currently included).

## Observability and debugging
- Review container logs for poller and scheduler output:
  - `docker-compose logs -f telegram_rss`
  - `docker-compose logs -f postgres` for database issues.
- Health endpoint: `GET /health` responds with `{"status": "ok"}` when the app is running.
- RSS endpoint returns `404` when a feed is missing; ensure `feeds` table has entries matching `language` and `topic`.

## Maintenance tips
- Limit `polling.batch_size` and `staging.max_items_per_release` to control throughput and database load.
- Prune old feed items by adjusting `staging.max_items_per_feed` and rebuilding feeds as needed.
- If Telethon session files become corrupted, delete the relevant file from `sessions/` and restart; you may need to re-authorize the account.
