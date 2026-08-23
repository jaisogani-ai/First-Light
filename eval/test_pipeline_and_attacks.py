"""Confirms the multi-agent pipeline records real per-step data, and that every Attack
Library scenario produces a genuine rejection through the live backend."""

import pytest

from backend.attack_mutations import ATTACK_TYPES


def test_pipeline_steps_are_recorded_and_real(client, valid_command):
    run_id = valid_command["run_id"]
    resp = client.get(f"/api/pipeline/steps?run_id={run_id}")
    assert resp.status_code == 200
    steps = resp.json()

    assert [s["agent_name"] for s in steps] == [
        "Mission Planner Agent", "Dynamics Agent", "Safety Agent", "Proof Generator Agent", "Reviewer Agent",
    ]
    for step in steps:
        assert step["latency_ms"] >= 0.0
        assert step["reasoning_summary"]  # non-empty, no canned placeholder
        assert step["status"] == "COMPLETED"


@pytest.mark.parametrize("attack_type", ATTACK_TYPES)
def test_attack_library_scenario_is_detected(client, attack_type):
    resp = client.post("/api/attacks/run", json={"attack_type": attack_type, "mission_profile_key": "earth_observation"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "REJECTED"
    assert data["detected"] is True
