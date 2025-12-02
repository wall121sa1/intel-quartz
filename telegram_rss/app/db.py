from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
SessionLocal = None

def init_db(database_url: str):
    global _engine, SessionLocal
    _engine = create_engine(database_url, future=True)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()

def create_all_tables():
    from . import models  # ensure models are imported
    Base.metadata.create_all(bind=_engine)
