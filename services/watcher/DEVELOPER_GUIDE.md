# Watcher Developer Guide

This guide gives new contributors a concise overview of the Watcher service, how to run it locally, and how to package it for Docker deployments.

## What the service does

Watcher is a Flask-based ingestion pipeline that pulls RSS feeds, scrapes the full article content, enriches it with spaCy-powered entity extraction, and lets an administrator review and export Markdown into an Obsidian-ready vault. Key responsibilities include:

- Managing users, authentication, and optional SSO providers through Authlib and Flask-Login.
- Fetching and deduplicating feeds with `feedparser`, `newspaper3k`, and SQLAlchemy models defined in `app/models.py`.
- Running background jobs for feed syncing via `Flask-APScheduler` (`app/services/scheduler.py`).
- Persisting processed articles and emitting Markdown files under the configured vault root.

## Repository layout

- `app/__init__.py` – application factory wiring Flask, SQLAlchemy, login, OAuth, rate limiting, and the scheduler. SSO providers are registered dynamically when their environment variables are present.【F:watcher/app/__init__.py†L1-L63】
- `app/models.py` – database schema for users, feeds, articles, and related metadata (SQLAlchemy).
- `app/routes/` – blueprints for the main UI, authentication, and settings pages (feeds, tags, MFA, tenants, users, dictionary, etc.).
- `app/services/` – ingestion services: `manager.py` orchestrates feed syncing, `scraper.py` pulls full text, `nlp.py` applies spaCy/entity rules, `storage.py` writes Markdown, `scheduler.py` wires periodic jobs, and `security.py` guards encryption/SSO flows.
- `run.py` – production-ready entry point that creates the app, updates the scheduler interval, and can bootstrap the first admin when explicitly enabled.【F:watcher/run.py†L1-L36】
- `init_db.py` – waits for the database, creates tables, and seeds an admin user during container startup when none exists.【F:watcher/init_db.py†L1-L64】
- `entrypoint.sh` – container entrypoint that runs `init_db.py` before starting the configured server command.【F:watcher/entrypoint.sh†L1-L16】
- `watcher_readme.md` – high-level product overview and user-facing workflow.

## Local development

1. **Python & virtualenv** – Use Python 3.10+ and create an isolated environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **spaCy model** – Download the English model required by `app/services/nlp.py`.
   ```bash
   python -m spacy download en_core_web_sm
   ```

3. **Configuration** – Environment variables override defaults in `config.py`. Common ones:
   - `SECRET_KEY` (required in production).
   - `ENCRYPTION_KEY` (required in production; persisted to `.dev_encryption_key` in development).【F:watcher/config.py†L1-L43】
   - `DATABASE_URL` (defaults to SQLite `watcher/app.db`).
   - `VAULT_ROOT` (directory for exported Markdown when using local storage).
   - `STORAGE_TYPE` (`local` or `s3`) plus `S3_BUCKET`, `S3_REGION`, and optional AWS credentials when you want Markdown files to land in an S3 bucket instead of the container filesystem.【F:watcher/config.py†L35-L41】【F:watcher/app/services/storage.py†L13-L52】
   - `ALLOW_BOOTSTRAP_ADMIN`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` for one-time admin creation on startup.【F:watcher/run.py†L9-L35】
   - Optional SSO provider IDs/secrets for Google, Microsoft, Okta, or Cloudflare.【F:watcher/app/__init__.py†L16-L53】

4. **Initialize the database** – For local SQLite, tables are created on first run. To seed an admin explicitly, run:
   ```bash
   python init_db.py
   ```

5. **Run the server** – Start the Flask app (includes the scheduler job wiring):
   ```bash
   python run.py
   ```
   Visit `http://127.0.0.1:5000` and log in with your bootstrap admin credentials.

## Recommended Docker deployment

Containerizing Watcher keeps the ingestion stack consistent between hosts. The existing startup scripts (`entrypoint.sh` and `init_db.py`) handle database readiness and initial admin creation, so the container only needs to supply environment variables and a persistent volume for the database/vault output.

### Example Dockerfile

```dockerfile
FROM python:3.11-slim

# System deps for newspaper3k, spaCy, and lxml
RUN apt-get update \ 
    && apt-get install -y --no-install-recommends \ 
       build-essential python3-dev libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \ 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY watcher ./
RUN pip install --no-cache-dir --upgrade pip \ 
    && pip install --no-cache-dir -r requirements.txt \ 
    && python -m spacy download en_core_web_sm

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 5000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:5000", "run:app"]
```

### Runtime configuration

- **Secrets:** set `SECRET_KEY` and `ENCRYPTION_KEY` for session signing and credential encryption. `ENCRYPTION_KEY` must be stable across restarts.
- **Database:** set `DATABASE_URL` to point at Postgres/MySQL for production or leave unset for SQLite. `init_db.py` will wait for the DB before migrations.【F:watcher/init_db.py†L9-L33】
- **Admin bootstrap:** provide `ADMIN_EMAIL`/`ADMIN_PASSWORD` to auto-create the first admin on fresh databases.【F:watcher/init_db.py†L33-L60】
- **Vault output:** bind-mount `VAULT_ROOT` (defaults to `vault_data/`) so generated Markdown persists across containers.

### docker-compose snippet

```yaml
services:
  watcher:
    build: .
    environment:
      FLASK_ENV: production
      SECRET_KEY: change-me
      ENCRYPTION_KEY: change-me
      DATABASE_URL: postgresql+psycopg2://watcher:password@db:5432/watcher
      ADMIN_EMAIL: admin@example.com
      ADMIN_PASSWORD: strong-password
    depends_on:
      - db
    ports:
      - "5000:5000"
    volumes:
      - watcher_vault:/app/vault_data
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: watcher
      POSTGRES_USER: watcher
      POSTGRES_PASSWORD: password
    volumes:
      - watcher_db:/var/lib/postgresql/data
volumes:
  watcher_vault:
  watcher_db:
```

With this setup, `entrypoint.sh` runs `init_db.py` to apply schema and bootstrap the admin before Gunicorn starts, ensuring the service comes up cleanly in new environments.【F:watcher/entrypoint.sh†L1-L16】【F:watcher/init_db.py†L9-L64】
