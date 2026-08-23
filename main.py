"""
Proof-Carrying Commands (PCC) for NASA cFS — CLI demonstration.

Runs the real multi-agent producer pipeline (producer/pipeline.py) and the real verifier
(backend/verifier.py) against a temporary SQLite database — the same code paths the FastAPI
backend and eval/ pytest suite use, not a separate reimplementation.
"""

import os
import tempfile

os.environ.setdefault("FIRST_LIGHT_DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")

from sqlalchemy import select

from backend.db import engine, init_db
from backend.models import mission_profiles, sequence_state
from backend.verifier import verify_command
from db.seed import seed as seed_profiles
from producer.agent import MANEUVER_PRESETS, MissionPlanningAgent


def run_demonstration():
    print("=" * 70)
    print("  PROOF-CARRYING COMMANDS (PCC) FOR NASA CORE FLIGHT SOFTWARE (cFS)")
    print("  International Innovation Challenge 3.0 — Manipal University Jaipur")
    print("=" * 70)
    print()

    init_db()
    seed_profiles()
    with engine.connect() as conn:
        profile = dict(conn.execute(
            select(mission_profiles).where(mission_profiles.c.profile_key == "earth_observation")
        ).fetchone()._mapping)

    def allocate_sequence():
        with engine.begin() as conn:
            row = conn.execute(select(sequence_state).where(sequence_state.c.stream_id == "earth_observation")).fetchone()
            return (row.last_accepted_sequence if row else 1042) + 1

    agent = MissionPlanningAgent(allocate_sequence, profile)

    print("[STEP 1] Multi-agent producer pipeline proposing a safe RCS pulse maneuver...")
    result = agent.propose_maneuver("SAFE_RCS_PULSE")
    for step in result["steps"]:
        print(f"  [{step['agent_name']}] {step['reasoning_summary']} ({step['latency_ms']:.3f} ms)")

    if result["refused"]:
        print(f"\n [REFUSED] {result['refusal_reason']}")
        return

    proof = result["proof"]
    u_cmd = MANEUVER_PRESETS["SAFE_RCS_PULSE"]["u_cmd"]
    print(f"\n -> Farkas Multipliers: {proof['certificate']['multipliers']}")
    print(f" -> Sequence No: {proof['sequence_no']}")

    print("\n[STEP 2] Sending command + proof payload to the real 5-step verifier...")
    cmd_bytes = f"{proof['command_id']}:{u_cmd[0]}:{u_cmd[1]}:{u_cmd[2]}".encode("utf-8")
    with engine.begin() as conn:
        verdict = verify_command(conn, proof, cmd_bytes, stream_id="earth_observation")

    print(f" -> Verifier completed in {verdict.verifier_time_ms:.4f} ms")
    print(f"    Trust: {verdict.trust.model_dump()}")

    producer_time_ms = sum(s["latency_ms"] for s in result["steps"])
    if verdict.verdict == "VERIFIED":
        print(f"\n [SUCCESS] COMMAND VERIFIED! {verdict.explain.narrative}")
        print(f"           Computational Asymmetry: Producer {producer_time_ms:.2f}ms vs "
              f"Verifier {verdict.verifier_time_ms:.4f}ms "
              f"({producer_time_ms / verdict.verifier_time_ms:.1f}x faster)")
    else:
        print(f"\n [REJECTED] {verdict.reject_reason}")

    print()
    print("=" * 70)
    print("  For the interactive Mission Control Dashboard: uvicorn backend.main:app --reload")
    print("=" * 70)


if __name__ == "__main__":
    run_demonstration()
