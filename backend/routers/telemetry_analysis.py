"""Telemetry Analysis Engine endpoint — runs backend/engines/telemetry_analysis.py's
deterministic numpy computation over a mission's real telemetry rows and persists the
result via the shared agent_runs execution-audit framework."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.agents.base import run_agent
from backend.db import engine
from backend.engines.telemetry_analysis import run_telemetry_analysis
from backend.models import missions, telemetry

router = APIRouter(prefix="/api/missions/{mission_id}/telemetry-analysis", tags=["telemetry-analysis"])


def _require_mission(conn, mission_id: int) -> None:
    if conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone() is None:
        raise HTTPException(404, f"Mission {mission_id} not found")


@router.post("/run")
def run_analysis(mission_id: int):
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(telemetry).where(telemetry.c.mission_id == mission_id).order_by(telemetry.c.id)
        ).fetchall()
        telemetry_dicts = [dict(r._mapping) for r in rows]
        result = run_agent(conn, mission_id, "telemetry_analysis_engine",
                            lambda: run_telemetry_analysis(telemetry_dicts),
                            input_summary=f"{len(telemetry_dicts)} telemetry rows")
    return result
