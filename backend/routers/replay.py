"""Mission Replay — steps back through real persisted history: every command, proof,
rejection, and attack, pulled from the DB (nothing synthesized for the replay view)."""

import json

from fastapi import APIRouter
from sqlalchemy import select

from backend.db import engine
from backend.models import commands, mission_profiles, pipeline_steps, proof_certificates, verification_results

router = APIRouter(prefix="/api/missions", tags=["replay"])


@router.get("/replay")
def replay(limit: int = 50):
    with engine.connect() as conn:
        cmd_rows = conn.execute(
            select(commands, mission_profiles.c.display_name.label("mission_profile"))
            .join(mission_profiles, commands.c.mission_profile_id == mission_profiles.c.id)
            .order_by(commands.c.id).limit(limit)
        ).fetchall()

        history = []
        for row in cmd_rows:
            cmd = dict(row._mapping)
            cert_row = conn.execute(
                select(proof_certificates).where(proof_certificates.c.command_id == cmd["id"])
            ).fetchone()
            verif_row = conn.execute(
                select(verification_results).where(verification_results.c.command_id == cmd["id"])
                .order_by(verification_results.c.id.desc())
            ).fetchone()
            step_rows = conn.execute(
                select(pipeline_steps).where(pipeline_steps.c.command_id == cmd["id"])
                .order_by(pipeline_steps.c.step_order)
            ).fetchall()

            history.append({
                "command": cmd,
                "certificate": dict(cert_row._mapping) if cert_row else None,
                "verification": dict(verif_row._mapping) if verif_row else None,
                "explain": json.loads(verif_row.explain_json) if verif_row else None,
                "pipeline_steps": [dict(s._mapping) for s in step_rows],
            })
    return history
