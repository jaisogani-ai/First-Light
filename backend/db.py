"""SQLAlchemy engine/session setup, backed by db/schema.sql as the source of truth DDL."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Apply the DDL in db/schema.sql. Idempotent (all statements are CREATE ... IF NOT EXISTS)."""
    ddl = SCHEMA_PATH.read_text()
    raw = engine.raw_connection()
    try:
        raw.executescript(ddl)
        raw.commit()
    finally:
        raw.close()


def get_session() -> Session:
    return SessionLocal()
