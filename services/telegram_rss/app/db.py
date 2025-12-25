from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
SessionLocal = None

def init_db(database_url: str):
    global _engine, SessionLocal
    _engine = create_engine(database_url, future=True)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

def get_session():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized; call init_db() first")
    return SessionLocal()

def create_all_tables():
    from . import models  # ensure models are imported
    Base.metadata.create_all(bind=_engine)
    _apply_schema_patches()


def _apply_schema_patches():
    """
    Apply lightweight, idempotent schema fixes for deployments without
    migrations. These statements should be safe to run on every startup.
    """

    with _engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS channels
                ADD COLUMN IF NOT EXISTS telegram_numeric_id BIGINT
                """
            )
        )
        conn.commit()
