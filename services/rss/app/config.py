import os
import yaml
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

from .credentials import get_bot_credentials

# Load .env if present (for local dev)
load_dotenv()

class BotConfig(BaseModel):
    name: str
    theme: Optional[str] = None
    session_name: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None

class PollingConfig(BaseModel):
    interval_seconds: int = 20
    batch_size: int = 100
    per_channel_delay_seconds: int = 1

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
        api_id, api_hash, _ = get_bot_credentials(name)

        if api_id is not None and api_hash is not None:
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
