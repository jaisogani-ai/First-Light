"""Mission Assistant endpoint — assembles a real data snapshot for one mission and asks
backend.mission_assistant to narrate it. Read-only: never writes to commands, telemetry,
or verification tables; only ever appends to mission_reports."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.db import engine
from backend.logs import log_event
from backend.mission_assistant import explain_mission
from backend.models import missions, mission_reports
from backend.routers.mission_analytics import _compute_mission_analytics

router = APIRouter(prefix="/api/missions/{mission_id}/assistant", tags=["mission-assistant"])


@router.post("/explain")
def explain(mission_id: int, body: dict | None = None):
    body = body or {}
    question = body.get("question")

    with engine.begin() as conn:
        mission_row = conn.execute(select(missions).where(missions.c.id == mission_id)).fetchone()
        if not mission_row:
            raise HTTPException(404, f"Mission {mission_id} not found")
        analytics = _compute_mission_analytics(conn, mission_id)
        snapshot = {"mission": dict(mission_row._mapping), "analytics": analytics}

        text, generated_by = explain_mission(snapshot, question)

        result = conn.execute(mission_reports.insert().values(
            mission_id=mission_id, report_type="assistant_explanation", generated_by=generated_by,
            content_json=json.dumps({"question": question, "answer": text}),
        ))
        report_id = result.inserted_primary_key[0]

    log_event("mission.assistant.explained", mission_id=mission_id, report_id=report_id, generated_by=generated_by)
    return {"report_id": report_id, "generated_by": generated_by, "answer": text}
