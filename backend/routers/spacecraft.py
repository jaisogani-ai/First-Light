"""Spacecraft Configuration Engine endpoints. Distinct from the simple inertia-only
POST /api/missions/{id}/imports/spacecraft-profile (backend/routers/imports.py, unchanged):
this is the richer, component-aware configuration path — reaction wheels, thrusters,
solar arrays, battery packs, payloads, thermal/comm systems, sensors, attitude control,
fuel tanks — validated by the deterministic backend/engines/spacecraft_config.py, never
an LLM call."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.agents.base import run_agent
from backend.db import engine
from backend.engines.spacecraft_config import validate_configuration
from backend.models import missions, spacecraft, spacecraft_components

router = APIRouter(prefix="/api/missions/{mission_id}/spacecraft", tags=["spacecraft"])


def _require_mission(conn, mission_id: int) -> None:
    if conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone() is None:
        raise HTTPException(404, f"Mission {mission_id} not found")


def _run_config_engine(conn, mission_id: int, data: dict) -> dict:
    validation = validate_configuration(data)
    if not validation["valid"]:
        return validation

    result = conn.execute(spacecraft.insert().values(
        mission_id=mission_id, name=data["name"],
        inertia_ixx=data["inertia_ixx"], inertia_iyy=data["inertia_iyy"], inertia_izz=data["inertia_izz"],
    ))
    spacecraft_id = result.inserted_primary_key[0]

    for comp in validation["components"]:
        conn.execute(spacecraft_components.insert().values(
            spacecraft_id=spacecraft_id, component_type=comp["component_type"], name=comp["name"],
            parameters_json=json.dumps(comp["parameters"]),
        ))

    return {**validation, "spacecraft_id": spacecraft_id, "component_count": len(validation["components"])}


@router.post("/configure")
def configure_spacecraft(mission_id: int, body: dict, dry_run: bool = False):
    if dry_run:
        return {"dry_run": True, **validate_configuration(body)}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        result = run_agent(conn, mission_id, "spacecraft_configuration_engine",
                            lambda: _run_config_engine(conn, mission_id, body),
                            input_summary=f"configure spacecraft '{body.get('name', '?')}'")
    return {"dry_run": False, **result}


@router.get("/model")
def get_spacecraft_model(mission_id: int):
    """Returns the full structured spacecraft model (all spacecraft rows + their
    components) for a mission — real DB state, not a recomputed summary."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        sc_rows = conn.execute(select(spacecraft).where(spacecraft.c.mission_id == mission_id)).fetchall()
        spacecrafts = []
        for sc in sc_rows:
            sc_dict = dict(sc._mapping)
            comp_rows = conn.execute(
                select(spacecraft_components).where(spacecraft_components.c.spacecraft_id == sc_dict["id"])
            ).fetchall()
            components = []
            for c in comp_rows:
                cd = dict(c._mapping)
                cd["parameters"] = json.loads(cd.pop("parameters_json"))
                components.append(cd)
            sc_dict["components"] = components
            spacecrafts.append(sc_dict)
    return {"mission_id": mission_id, "spacecraft": spacecrafts}
