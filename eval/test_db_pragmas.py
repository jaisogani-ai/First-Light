"""SQLite concurrency pragmas — a real gap found in review: no WAL/busy_timeout meant
concurrent writers (e.g. two missions importing CSV telemetry at once) could raise
'database is locked' immediately instead of waiting. Verifies the pragmas are actually
active on real connections from the app's engine, not just present in db.py's source."""

from backend.db import engine


def test_wal_mode_is_active_on_real_connections():
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
    assert mode.lower() == "wal"


def test_busy_timeout_is_active_on_real_connections():
    with engine.connect() as conn:
        timeout_ms = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
    assert timeout_ms == 5000
