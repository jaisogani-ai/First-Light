"""SQLAlchemy engine/session setup, backed by db/schema.sql as the source of truth DDL."""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

# Columns added to pre-existing tables after their CREATE TABLE was first shipped.
# CREATE TABLE IF NOT EXISTS in schema.sql only creates missing *tables*, not missing
# *columns* on tables that already exist on disk — this list is the migration path for
# a database file created before the Mission Workspace columns were added.
_ADDED_COLUMNS = [
    ("commands", "mission_id", "INTEGER REFERENCES missions(id)"),
    ("telemetry", "mission_id", "INTEGER REFERENCES missions(id)"),
    ("mission_imports", "checksum", "TEXT"),
    ("mission_imports", "source", "TEXT"),
    ("mission_imports", "schema_version", "TEXT"),
    ("mission_imports", "freshness_days", "REAL"),
]

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _):
        """WAL lets readers proceed while a writer holds the lock (instead of every
        reader blocking on SQLite's default rollback-journal exclusive write lock), and
        busy_timeout makes a genuinely concurrent writer (e.g. two missions importing CSV
        telemetry at once) wait and retry for 5s instead of immediately raising
        'database is locked' — a real concurrency gap found in review, not a hypothetical."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def _add_missing_columns(raw) -> None:
    for table, column, coltype in _ADDED_COLUMNS:
        try:
            raw.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise


def init_db() -> None:
    """Apply the DDL in db/schema.sql. Idempotent (all statements are CREATE ... IF NOT EXISTS),
    plus a defensive ALTER TABLE pass for columns added to already-existing tables."""
    ddl = SCHEMA_PATH.read_text()
    raw = engine.raw_connection()
    try:
        raw.executescript(ddl)
        _add_missing_columns(raw)
        raw.commit()
    finally:
        raw.close()


def get_session() -> Session:
    return SessionLocal()
