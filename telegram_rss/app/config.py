import os
import yaml
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Load .env if present (for local dev)
load_dotenv()

class BotConfig(BaseModel):
    name: str
    theme: Optional[str] = None
    session_name: str
    api_id: int
    api_hash: str

class PollingConfig(BaseModel):
    interval_seconds: int = 20
    batch_size: int = 100

class StagingConfig(BaseModel):
    release_interval_minutes: int = 10
    max_items_per_release: int = 500
    max_items_per_feed: int = 200
    default_max_items: int = 200

class DatabaseConfig(BaseModel):
    url: str

class AppConfig(BaseModel):
    database: DatabaseConfig
    polling: PollingConfig
    staging: StagingConfig
    bots: List[BotConfig]


def _inject_bot_secrets(raw_data: dict) -> None:
    """Fill in api_id/api_hash for each bot from environment variables."""
    bots = raw_data.get("bots", [])
    for bot in bots:
        name = bot["name"]  # e.g. "ru_crime_bot"
        env_prefix = name.upper()  # RU_CRIME_BOT
        api_id_env = f"{env_prefix}_API_ID"
        api_hash_env = f"{env_prefix}_API_HASH"

        api_id = os.getenv(api_id_env)
        api_hash = os.getenv(api_hash_env)

        if api_id is None or api_hash is None:
            raise RuntimeError(
                f"Missing env vars {api_id_env} / {api_hash_env} for bot '{name}'"
            )

        bot["api_id"] = int(api_id)
        bot["api_hash"] = api_hash


def load_config(path: str = "config.yaml") -> AppConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    # Override DB URL with env if present
    db_url_env = os.getenv("DATABASE_URL")
    if db_url_env:
        raw.setdefault("database", {})
        raw["database"]["url"] = db_url_env

    # Inject secrets for bots
    _inject_bot_secrets(raw)

    return AppConfig(**raw)
