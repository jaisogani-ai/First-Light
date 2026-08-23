"""propose / verify / feed / export — replaces the fabricated commandsData array and alert()s."""

import time
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select

from backend.db import engine
from backend.models import commands, mission_profiles, pipeline_steps, sequence_state
from backend.persistence import persist_command, persist_pipeline_steps, persist_verification
from backend.schemas import ExplainData, ProposeRequest, TrustAssessment
from backend.verifier import verify_command
from backend.ws_manager import ws_manager
from backend.routers.metrics import COMMANDS_REJECTED, COMMANDS_VERIFIED, PRODUCER_LATENCY, VERIFIER_LATENCY
from producer.agent import MANEUVER_PRESETS
from producer.pipeline import MissionPipeline

router = APIRouter(prefix="/api/commands", tags=["commands"])


def _load_profile(conn, profile_key: str) -> dict:
    row = conn.execute(select(mission_profiles).where(mission_profiles.c.profile_key == profile_key)).fetchone()
    if not row:
        raise HTTPException(404, f"Unknown mission profile '{profile_key}'")
    return dict(row._mapping)


def _next_sequence(conn, stream_id: str) -> int:
    row = conn.execute(select(sequence_state).where(sequence_state.c.stream_id == stream_id)).fetchone()
    return (row.last_accepted_sequence if row else 1042) + 1


@router.post("/propose")
def propose(req: ProposeRequest):
    with engine.begin() as conn:
        profile = _load_profile(conn, req.mission_profile_key)

    seq_holder = {"value": None}

    def allocate_sequence():
        with engine.begin() as conn:
            seq_holder["value"] = _next_sequence(conn, req.mission_profile_key)
            return seq_holder["value"]

    pipeline = MissionPipeline(allocate_sequence)
    preset = MANEUVER_PRESETS.get(req.maneuver_type, {"x0": [0.0, 0.0, 0.0], "u_cmd": [0.0, 0.0, 0.0]})
    cmd_id = f"RCS_PULSE_{uuid.uuid4().hex[:8].upper()}"

    t0 = time.perf_counter()
    result = pipeline.run(cmd_id, req.maneuver_type, preset["x0"], preset["u_cmd"], profile)
    producer_time_ms = (time.perf_counter() - t0) * 1000
    PRODUCER_LATENCY.observe(producer_time_ms)

    command_row_id = None
    if not result["refused"]:
        with engine.begin() as conn:
            command_row_id = persist_command(
                conn, cmd_id, profile["id"], result["proof"], preset["u_cmd"], seq_holder["value"], producer_time_ms
            )
            persist_pipeline_steps(conn, command_row_id, result["run_id"], result["steps"])
    else:
        with engine.begin() as conn:
            persist_pipeline_steps(conn, None, result["run_id"], result["steps"])

    ws_manager.broadcast_nowait({"type": "pipeline_run", "run_id": result["run_id"], "steps": result["steps"],
                                  "refused": result["refused"]})

    return {
        "command_id": cmd_id,
        "command_row_id": command_row_id,
        "run_id": result["run_id"],
        "refused": result["refused"],
        "refusal_reason": result["refusal_reason"],
        "producer_time_ms": producer_time_ms,
        "proof": result["proof"],
        "u_cmd": preset["u_cmd"],
        "pipeline_steps": result["steps"],
    }


@router.post("/verify")
def verify(body: dict):
    """Verifies a proof payload against the actual command bytes it claims to cover.

    Accepts {command_row_id, proof, submitted_command_id, submitted_u_cmd, mission_profile_key}
    so the Attack Library / adversarial tests can submit tampered payloads directly.
    """
    proof = body["proof"]
    submitted_command_id = body["submitted_command_id"]
    submitted_u_cmd = body["submitted_u_cmd"]
    stream_id = body.get("mission_profile_key", "earth_observation")
    command_row_id = body.get("command_row_id")

    cmd_bytes = f"{submitted_command_id}:{submitted_u_cmd[0]}:{submitted_u_cmd[1]}:{submitted_u_cmd[2]}".encode("utf-8")

    with engine.begin() as conn:
        result = verify_command(conn, proof, cmd_bytes, stream_id=stream_id)
        if command_row_id is not None:
            persist_verification(conn, command_row_id, result)

    VERIFIER_LATENCY.observe(result.verifier_time_ms)
    if result.verdict == "VERIFIED":
        COMMANDS_VERIFIED.inc()
    else:
        COMMANDS_REJECTED.labels(reason=result.explain.failing_step or "unknown").inc()

    ws_manager.broadcast_nowait({"type": "verification", "command_id": submitted_command_id,
                                  "verdict": result.verdict, "trust": result.trust.model_dump()})

    return {
        "command_id": submitted_command_id,
        "verdict": result.verdict,
        "reject_reason": result.reject_reason,
        "verifier_time_ms": result.verifier_time_ms,
        "trust": result.trust.model_dump(),
        "explain": result.explain.model_dump(),
    }


@router.get("/feed")
def feed(limit: int = 25):
    with engine.connect() as conn:
        rows = conn.execute(
            select(commands, mission_profiles.c.display_name)
            .join(mission_profiles, commands.c.mission_profile_id == mission_profiles.c.id)
            .order_by(desc(commands.c.id)).limit(limit)
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/export")
def export():
    with engine.connect() as conn:
        rows = conn.execute(select(commands).order_by(desc(commands.c.id))).fetchall()
    return [dict(r._mapping) for r in rows]
