# Telegram RSS Service

## Configuration
1. Copy `.env.example` to `.env` and fill in your Telegram API credentials for each bot.
2. (Optional) Set `DATABASE_URL` in `.env` to override the database connection string from `config.yaml`.
3. Run `docker-compose up --build` to start the stack.

The application loads environment variables from `.env` at startup, and the compose file forwards them into the container so API keys and hashes are never hardcoded.
