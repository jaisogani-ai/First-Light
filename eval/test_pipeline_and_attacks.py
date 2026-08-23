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


def test_pipeline_graph_reflects_real_data_flow(client, valid_command):
    run_id = valid_command["run_id"]
    graph = client.get(f"/api/pipeline/graph?run_id={run_id}").json()

    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {"step-1", "step-2", "step-3", "step-4", "step-5", "verifier"}

    # Dynamics Agent's x_post output must be the real edge into Safety Agent's x_post input.
    dyn_to_safety = next(e for e in graph["edges"] if e["source"] == "step-2" and e["target"] == "step-3")
    assert dyn_to_safety["kind"] == "data"
    assert "x_post" in dyn_to_safety["shared_fields"]

    # Proof Generator's multipliers/constraints must be the real edge into the Reviewer.
    proof_to_reviewer = next(e for e in graph["edges"] if e["source"] == "step-4" and e["target"] == "step-5")
    assert proof_to_reviewer["kind"] == "data"
    assert "multipliers" in proof_to_reviewer["shared_fields"]
    assert "constraints" in proof_to_reviewer["shared_fields"]


@pytest.mark.parametrize("attack_type", ATTACK_TYPES)
def test_attack_library_scenario_is_detected(client, attack_type):
    resp = client.post("/api/attacks/run", json={"attack_type": attack_type, "mission_profile_key": "earth_observation"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "REJECTED"
    assert data["detected"] is True
