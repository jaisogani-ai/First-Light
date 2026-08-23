"""Attack Library — judge-selectable, real attacks. Each endpoint proposes a genuinely valid
command through the real producer pipeline, mutates it via backend/attack_mutations.py, and
runs it through the actual /api/commands/verify path — the rejection is real, not scripted."""

import time
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.attack_mutations import ATTACK_TYPES, apply_attack
from backend.db import engine
from backend.models import mission_profiles, security_events
from backend.persistence import persist_command, persist_pipeline_steps, persist_verification
from backend.schemas import AttackRequest
from backend.verifier import verify_command
from producer.agent import MANEUVER_PRESETS
from producer.pipeline import MissionPipeline

router = APIRouter(prefix="/api/attacks", tags=["attacks"])


@router.get("/types")
def list_attack_types():
    return ATTACK_TYPES


@router.post("/run")
def run_attack(req: AttackRequest):
    if req.attack_type not in ATTACK_TYPES:
        raise HTTPException(400, f"Unknown attack_type '{req.attack_type}'")

    with engine.begin() as conn:
        profile_row = conn.execute(
            select(mission_profiles).where(mission_profiles.c.profile_key == req.mission_profile_key)
        ).fetchone()
        if not profile_row:
            raise HTTPException(404, f"Unknown mission profile '{req.mission_profile_key}'")
        profile = dict(profile_row._mapping)

    seq_holder = {"value": None}

    def allocate_sequence():
        from backend.models import sequence_state
        with engine.begin() as conn:
            row = conn.execute(select(sequence_state).where(sequence_state.c.stream_id == req.mission_profile_key)).fetchone()
            seq_holder["value"] = (row.last_accepted_sequence if row else 1042) + 1
            return seq_holder["value"]

    pipeline = MissionPipeline(allocate_sequence)
    preset = MANEUVER_PRESETS["SAFE_RCS_PULSE"]
    cmd_id = f"RCS_PULSE_{uuid.uuid4().hex[:8].upper()}"
    # Explicit u_cmd (not LLM-proposed): the Attack Library needs a deterministic, reliably
    # safe baseline to mutate — that's what's under test here, not the Planner's LLM call.
    result = pipeline.run(cmd_id, "SAFE_RCS_PULSE", preset["x0"], profile, u_cmd=preset["u_cmd"])

    if result["refused"]:
        raise HTTPException(500, "Baseline proposal for attack scenario was unexpectedly refused")

    with engine.begin() as conn:
        command_row_id = persist_command(
            conn, cmd_id, profile["id"], result["proof"], preset["u_cmd"], seq_holder["value"], 0.0
        )
        persist_pipeline_steps(conn, command_row_id, result["run_id"], result["steps"])

    if req.attack_type == "replay":
        # Genuinely accept the original once first, so the replay attempt has something to replay against.
        cmd_bytes = f"{cmd_id}:{preset['u_cmd'][0]}:{preset['u_cmd'][1]}:{preset['u_cmd'][2]}".encode("utf-8")
        with engine.begin() as conn:
            verify_command(conn, result["proof"], cmd_bytes, stream_id=req.mission_profile_key)

    mutation = apply_attack(req.attack_type, result["proof"], cmd_id, preset["u_cmd"])
    cmd_bytes = f"{mutation['submitted_command_id']}:{mutation['submitted_u_cmd'][0]}:" \
                f"{mutation['submitted_u_cmd'][1]}:{mutation['submitted_u_cmd'][2]}".encode("utf-8")

    with engine.begin() as conn:
        verdict = verify_command(conn, mutation["proof"], cmd_bytes, stream_id=req.mission_profile_key)
        detected = verdict.verdict == "REJECTED"
        conn.execute(security_events.insert().values(
            command_id=command_row_id,
            attack_type=req.attack_type,
            detected=int(detected),
            detail_json=verdict.explain.model_dump_json(),
        ))

    return {
        "attack_type": req.attack_type,
        "description": mutation["description"],
        "verdict": verdict.verdict,
        "reject_reason": verdict.reject_reason,
        "detected": detected,
        "trust": verdict.trust.model_dump(),
        "explain": verdict.explain.model_dump(),
    }
