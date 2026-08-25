"""Mission Workspace CRUD — the container an operator creates/opens before anything else.
mission_profile_key still drives the safety envelope (unchanged, locked); a mission just
records which profile it uses and scopes commands/telemetry/replay to itself via mission_id."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from backend.db import engine
from backend.logs import log_event
from backend.models import missions, mission_profiles
from backend.profile_lookup import load_profile
from backend.routers.telemetry import set_active_mission
from backend.schemas import MissionCreateRequest, MissionResponse, MissionStatusUpdate
from backend.security import rate_limiter

router = APIRouter(prefix="/api/missions", tags=["missions"])

VALID_STATUSES = {"ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED"}


def _to_response(row) -> dict:
    m = dict(row._mapping)
    return {
        "id": m["id"],
        "mission_name": m["mission_name"],
        "objective": m["objective"],
        "mission_profile_id": m["mission_profile_id"],
        "mission_profile_key": m["profile_key"],
        "mission_profile_display_name": m["display_name"],
        "tle_line1": m["tle_line1"],
        "tle_line2": m["tle_line2"],
        "status": m["status"],
        "active": bool(m["active"]),
        "created_at": m["created_at"],
    }


def _select_with_profile():
    return select(
        missions, mission_profiles.c.profile_key, mission_profiles.c.display_name
    ).join(mission_profiles, missions.c.mission_profile_id == mission_profiles.c.id)


@router.post("", response_model=MissionResponse)
def create_mission(req: MissionCreateRequest, request: Request):
    client_key = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_key):
        raise HTTPException(429, "Rate limit exceeded")

    with engine.begin() as conn:
        profile = load_profile(conn, req.mission_profile_key)

        result = conn.execute(missions.insert().values(
            mission_name=req.mission_name,
            objective=req.objective,
            mission_profile_id=profile["id"],
            tle_line1=req.tle_line1,
            tle_line2=req.tle_line2,
            status="ACTIVE",
            active=1,
        ))
        mission_id = result.inserted_primary_key[0]
        row = conn.execute(_select_with_profile().where(missions.c.id == mission_id)).fetchone()
    log_event("mission.created", mission_id=mission_id, mission_name=req.mission_name,
              mission_profile_key=req.mission_profile_key)
    return _to_response(row)


@router.get("", response_model=list[MissionResponse])
def list_missions(status: str | None = None):
    query = _select_with_profile().order_by(missions.c.id.desc())
    if status:
        query = query.where(missions.c.status == status)
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return [_to_response(r) for r in rows]


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission(mission_id: int):
    with engine.connect() as conn:
        row = conn.execute(_select_with_profile().where(missions.c.id == mission_id)).fetchone()
    if not row:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return _to_response(row)


@router.patch("/{mission_id}/status", response_model=MissionResponse)
def update_mission_status(mission_id: int, req: MissionStatusUpdate):
    if req.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status '{req.status}', must be one of {sorted(VALID_STATUSES)}")
    with engine.begin() as conn:
        existing = conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone()
        if not existing:
            raise HTTPException(404, f"Mission {mission_id} not found")
        values = {"status": req.status}
        if req.active is not None:
            values["active"] = int(req.active)
        conn.execute(missions.update().where(missions.c.id == mission_id).values(**values))
        row = conn.execute(_select_with_profile().where(missions.c.id == mission_id)).fetchone()
    return _to_response(row)


@router.post("/{mission_id}/activate")
def activate_mission(mission_id: int):
    """Marks this mission as the one the live Digital Twin stream currently tags its
    telemetry ticks with. The twin remains a single simulation (see backend/digital_twin.py)
    — this only changes which mission_id its ticks are persisted under."""
    with engine.connect() as conn:
        row = conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone()
    if not row:
        raise HTTPException(404, f"Mission {mission_id} not found")
    set_active_mission(mission_id)
    return {"active_mission_id": mission_id}
