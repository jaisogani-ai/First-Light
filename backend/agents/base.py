"""Execution framework for Mission Ops engineering agents (Mission Intake, and future
Telemetry Analysis / Spacecraft Configuration / Mission Knowledge agents).

NOT the locked Proof-Carrying Commands multi-agent pipeline (producer/pipeline.py's
Planner/Dynamics/Safety/Proof Generator/Reviewer chain) — that is frozen research and
completely untouched by this module. These are separate, deterministic, rule-based
engineering agents that read mission context (documents, imports, telemetry) and produce
structured findings; none of them can propose commands or influence verification.

Every agent call here is timed, logged, and persisted to agent_runs — a real execution
history/audit trail, not a decorative log line. An agent that raises is recorded as a
real failure (status='ERROR', error_message=str(exc)), never silently swallowed."""

import json
import time

from backend.logs import log_event
from backend.models import agent_runs

# Single source of truth for every engineering agent's version — bumped by hand whenever
# an agent's actual logic changes meaningfully. Real, if coarse: this is a first-release
# platform, so every agent starts at 1.0.0 rather than a fabricated version history.
AGENT_VERSIONS = {
    "mission_intake": "1.0.0",
    "spacecraft_configuration_engine": "1.0.0",
    "telemetry_analysis_engine": "1.0.0",
    "mission_knowledge_agent": "1.0.0",
    "paper_review_agent": "1.0.0",
    "algorithm_review_agent": "1.0.0",
    "scientific_comparison_agent": "1.0.0",
}


def run_agent(conn, mission_id: int, agent_name: str, fn, input_summary: str | None = None) -> dict:
    """Runs fn() (a zero-arg callable that returns a JSON-serializable dict), times it,
    persists the result to agent_runs (including a real 'agent_version' inside output_json,
    so it's retrievable from both the live response and the /agent-runs execution history),
    and returns the same dict the agent produced plus run_id/status/latency/version."""
    t0 = time.perf_counter()
    try:
        output = fn()
        status = "OK"
        error_message = None
    except Exception as exc:
        output = {}
        status = "ERROR"
        error_message = str(exc)
    latency_ms = (time.perf_counter() - t0) * 1000
    version = AGENT_VERSIONS.get(agent_name, "unversioned")
    output_with_version = {**output, "agent_version": version}

    result = conn.execute(agent_runs.insert().values(
        mission_id=mission_id, agent_name=agent_name, status=status,
        input_summary=input_summary, output_json=json.dumps(output_with_version),
        error_message=error_message, latency_ms=latency_ms,
    ))
    run_id = result.inserted_primary_key[0]

    log_event("agent.run", mission_id=mission_id, agent_name=agent_name, status=status,
              latency_ms=round(latency_ms, 3), run_id=run_id, agent_version=version)

    return {**output_with_version, "run_id": run_id, "status": status, "error_message": error_message,
            "latency_ms": round(latency_ms, 3)}
