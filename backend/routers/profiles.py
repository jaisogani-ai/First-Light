"""Mission Knowledge Base access — profiles drive safety limits instead of hardcoded constants."""

from fastapi import APIRouter
from sqlalchemy import select

from backend.db import engine
from backend.models import mission_profiles

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
def list_profiles():
    with engine.connect() as conn:
        rows = conn.execute(select(mission_profiles)).fetchall()
    return [dict(r._mapping) for r in rows]
