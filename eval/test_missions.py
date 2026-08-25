"""Mission Workspace CRUD, and that commands/telemetry actually attach to a mission_id."""

from backend.constants import INITIAL_SEQUENCE_NO


def test_create_and_get_mission(client):
    resp = client.post("/api/missions", json={
        "mission_name": "ISS Reboost", "objective": "Raise orbit 2km",
        "mission_profile_key": "earth_observation",
    })
    assert resp.status_code == 200
    mission = resp.json()
    assert mission["mission_name"] == "ISS Reboost"
    assert mission["mission_profile_key"] == "earth_observation"
    assert mission["status"] == "ACTIVE"
    assert mission["active"] is True

    fetched = client.get(f"/api/missions/{mission['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == mission


def test_create_mission_unknown_profile_rejected(client):
    resp = client.post("/api/missions", json={
        "mission_name": "Bad Profile", "mission_profile_key": "does_not_exist",
    })
    assert resp.status_code == 404


def test_get_missing_mission_404s(client):
    resp = client.get("/api/missions/999999")
    assert resp.status_code == 404


def test_list_missions_filters_by_status(client):
    created = client.post("/api/missions", json={
        "mission_name": "Filter Target", "mission_profile_key": "deep_space",
    }).json()

    active = client.get("/api/missions", params={"status": "ACTIVE"}).json()
    assert any(m["id"] == created["id"] for m in active)

    completed = client.get("/api/missions", params={"status": "COMPLETED"}).json()
    assert all(m["id"] != created["id"] for m in completed)


def test_update_mission_status(client):
    created = client.post("/api/missions", json={
        "mission_name": "Status Flip", "mission_profile_key": "lunar_orbiter",
    }).json()

    resp = client.patch(f"/api/missions/{created['id']}/status", json={"status": "PAUSED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAUSED"


def test_update_mission_status_rejects_invalid_status(client):
    created = client.post("/api/missions", json={
        "mission_name": "Bad Status", "mission_profile_key": "lunar_orbiter",
    }).json()

    resp = client.patch(f"/api/missions/{created['id']}/status", json={"status": "NOT_A_STATUS"})
    assert resp.status_code == 400


def test_update_status_missing_mission_404s(client):
    resp = client.patch("/api/missions/999999/status", json={"status": "PAUSED"})
    assert resp.status_code == 404


def test_propose_without_mission_id_falls_back_to_default(client):
    resp = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
    })
    assert resp.status_code == 200
    assert resp.json()["mission_id"] is not None


def test_propose_with_explicit_mission_id_attaches_command(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Attach Check", "mission_profile_key": "earth_observation",
    }).json()

    resp = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission["id"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["mission_id"] == mission["id"]

    feed = client.get("/api/commands/feed", params={"limit": 5}).json()
    row = next(r for r in feed if r["command_id"] == body["command_id"])
    assert row["mission_id"] == mission["id"]


def test_activate_mission_tags_telemetry(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Telemetry Tag", "mission_profile_key": "earth_observation",
    }).json()

    resp = client.post(f"/api/missions/{mission['id']}/activate")
    assert resp.status_code == 200
    assert resp.json()["active_mission_id"] == mission["id"]


def test_activate_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/activate")
    assert resp.status_code == 404


def test_sequence_state_is_scoped_per_mission_not_per_profile(client):
    """Two missions sharing the same mission_profile_key must not share a replay-protection
    sequence counter — a real cross-mission collision found in review (sequence_state was
    previously keyed by mission_profile_key). Regression: fully accept a command on mission A
    (advancing its sequence stream to 1), then confirm mission B's next proposal still starts
    at sequence 1 rather than inheriting mission A's counter as 2."""
    mission_a = client.post("/api/missions", json={
        "mission_name": "Sequence Isolation A", "mission_profile_key": "earth_observation",
    }).json()
    mission_b = client.post("/api/missions", json={
        "mission_name": "Sequence Isolation B", "mission_profile_key": "earth_observation",
    }).json()

    propose_a = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission_a["id"],
    }).json()
    verify_a = client.post("/api/commands/verify", json={
        "command_row_id": propose_a["command_row_id"], "proof": propose_a["proof"],
        "submitted_command_id": propose_a["command_id"], "submitted_u_cmd": propose_a["u_cmd"],
        "mission_id": mission_a["id"],
    }).json()
    assert verify_a["verdict"] == "VERIFIED"
    assert propose_a["proof"]["sequence_no"] == INITIAL_SEQUENCE_NO + 1

    propose_b = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission_b["id"],
    }).json()
    assert propose_b["proof"]["sequence_no"] == INITIAL_SEQUENCE_NO + 1, (
        "mission B inherited mission A's sequence counter — streams are not mission-scoped"
    )
    verify_b = client.post("/api/commands/verify", json={
        "command_row_id": propose_b["command_row_id"], "proof": propose_b["proof"],
        "submitted_command_id": propose_b["command_id"], "submitted_u_cmd": propose_b["u_cmd"],
        "mission_id": mission_b["id"],
    }).json()
    assert verify_b["verdict"] == "VERIFIED"
