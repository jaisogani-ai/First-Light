"""Single source of truth for the 'load a mission profile by key or 404' query,
previously duplicated across commands.py, attacks.py, and missions.py."""

from fastapi import HTTPException
from sqlalchemy import select

from backend.models import mission_profiles


def load_profile(conn, profile_key: str) -> dict:
    row = conn.execute(select(mission_profiles).where(mission_profiles.c.profile_key == profile_key)).fetchone()
    if not row:
        raise HTTPException(404, f"Unknown mission profile '{profile_key}'")
    return dict(row._mapping)
