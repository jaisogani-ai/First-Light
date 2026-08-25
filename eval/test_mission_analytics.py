"""Mission Timeline, Analytics, Compare, Export, Reports — verifies every number comes
from real DB rows for that specific mission (not global, not fabricated)."""

import pytest


@pytest.fixture
def mission_with_command(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Analytics Target", "mission_profile_key": "earth_observation",
    }).json()
    propose = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission["id"],
    }).json()
    client.post("/api/commands/verify", json={
        "command_row_id": propose["command_row_id"], "proof": propose["proof"],
        "submitted_command_id": propose["command_id"], "submitted_u_cmd": propose["u_cmd"],
        "mission_id": mission["id"],
    })
    return mission


def test_analytics_reflects_real_commands_for_this_mission_only(client, mission_with_command):
    other_mission = client.post("/api/missions", json={
        "mission_name": "Untouched Mission", "mission_profile_key": "earth_observation",
    }).json()

    stats = client.get(f"/api/missions/{mission_with_command['id']}/analytics").json()
    assert stats["total_commands"] == 1
    assert stats["acceptance_rate"] == 1.0

    other_stats = client.get(f"/api/missions/{other_mission['id']}/analytics").json()
    assert other_stats["total_commands"] == 0
    assert other_stats["acceptance_rate"] is None


def test_replay_endpoint_filters_by_mission_id(client, mission_with_command):
    other_mission = client.post("/api/missions", json={
        "mission_name": "Replay Other", "mission_profile_key": "earth_observation",
    }).json()

    scoped = client.get("/api/missions/replay", params={"mission_id": mission_with_command["id"]}).json()
    assert len(scoped) == 1

    other_scoped = client.get("/api/missions/replay", params={"mission_id": other_mission["id"]}).json()
    assert other_scoped == []


def test_analytics_missing_mission_404s(client):
    resp = client.get("/api/missions/999999/analytics")
    assert resp.status_code == 404


def test_timeline_includes_command_and_import_events(client, mission_with_command):
    client.post(f"/api/missions/{mission_with_command['id']}/imports/mission-json", json={
        "objective": "Timeline check",
    })
    events = client.get(f"/api/missions/{mission_with_command['id']}/timeline").json()
    kinds = {e["kind"] for e in events}
    assert kinds == {"command", "import"}


def test_export_returns_full_mission_record(client, mission_with_command):
    export = client.get(f"/api/missions/{mission_with_command['id']}/export").json()
    assert export["mission"]["id"] == mission_with_command["id"]
    assert len(export["commands"]) == 1
    assert export["commands"][0]["verdict"] == "VERIFIED"


def test_generate_report_persists_and_lists(client, mission_with_command):
    generated = client.post(f"/api/missions/{mission_with_command['id']}/reports/generate").json()
    assert generated["generated_by"] == "deterministic"
    assert generated["content"]["total_commands"] == 1

    listed = client.get(f"/api/missions/{mission_with_command['id']}/reports").json()
    assert len(listed) == 1
    assert listed[0]["content"]["total_commands"] == 1


def test_compare_missions_returns_independent_analytics(client, mission_with_command):
    other = client.post("/api/missions", json={
        "mission_name": "Compare B", "mission_profile_key": "earth_observation",
    }).json()

    result = client.get("/api/missions/compare", params={"ids": f"{mission_with_command['id']},{other['id']}"}).json()
    assert len(result) == 2
    by_id = {r["mission_id"]: r for r in result}
    assert by_id[mission_with_command["id"]]["total_commands"] == 1
    assert by_id[other["id"]]["total_commands"] == 0


def test_compare_with_missing_mission_404s(client, mission_with_command):
    resp = client.get("/api/missions/compare", params={"ids": f"{mission_with_command['id']},999999"})
    assert resp.status_code == 404


def test_evidence_package_composes_real_data_across_subsystems(client, mission_with_command):
    package = client.get(f"/api/missions/{mission_with_command['id']}/evidence-package").json()

    assert package["mission"]["id"] == mission_with_command["id"]
    assert package["analytics"]["total_commands"] == 1
    assert len(package["command_history"]) == 1
    assert package["command_history"][0]["command"]["verdict"] == "VERIFIED"
    assert package["command_history"][0]["certificate"] is not None
    assert package["command_history"][0]["verification"] is not None
    # audit_chain_verification is deliberately GLOBAL, not mission-scoped (see the endpoint's
    # docstring) — other tests in this shared session intentionally corrupt certificates to
    # test tamper detection, so 'valid' isn't guaranteed True here; just check the shape.
    assert "audit_chain_verification" in package
    assert isinstance(package["audit_chain_verification"]["valid"], bool)
    assert package["reports"] == []
    assert package["imports"] == []


def test_evidence_package_includes_imports_and_reports(client, mission_with_command):
    client.post(f"/api/missions/{mission_with_command['id']}/imports/mission-json", json={"objective": "x"})
    client.post(f"/api/missions/{mission_with_command['id']}/reports/generate")

    package = client.get(f"/api/missions/{mission_with_command['id']}/evidence-package").json()
    assert len(package["imports"]) == 1
    assert len(package["reports"]) == 1


def test_evidence_package_missing_mission_404s(client):
    resp = client.get("/api/missions/999999/evidence-package")
    assert resp.status_code == 404


def test_compare_route_not_shadowed_by_mission_id_path(client):
    """Regression: /api/missions/compare must not be swallowed by GET /api/missions/{mission_id}
    (which would try to int()-parse 'compare' and 422 instead of reaching the compare route)."""
    m = client.post("/api/missions", json={
        "mission_name": "Route Order Check", "mission_profile_key": "earth_observation",
    }).json()
    resp = client.get("/api/missions/compare", params={"ids": str(m["id"])})
    assert resp.status_code == 200
