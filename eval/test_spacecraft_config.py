"""Spacecraft Configuration Engine — deterministic, no LLM. Real per-component-type
validation, real inconsistency/missing-subsystem detection, real persistence to
spacecraft_components."""

import pytest


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Spacecraft Config Target", "mission_profile_key": "earth_observation",
    }).json()


VALID_CONFIG = {
    "name": "CubeSat-Alpha", "inertia_ixx": 0.02, "inertia_iyy": 0.02, "inertia_izz": 0.01,
    "components": [
        {"component_type": "REACTION_WHEEL", "name": "RW-X", "parameters": {"max_torque_nm": 0.02, "max_momentum_nms": 0.05}},
        {"component_type": "BATTERY", "name": "Main Battery", "parameters": {"capacity_wh": 150.0, "nominal_voltage_v": 7.4}},
        {"component_type": "THERMAL_SYSTEM", "name": "Passive Thermal", "parameters": {"operating_range_min_c": -20, "operating_range_max_c": 50}},
    ],
}


def test_valid_configuration_persists_spacecraft_and_components(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=VALID_CONFIG)
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["component_count"] == 3
    assert body["status"] == "OK"

    model = client.get(f"/api/missions/{mission['id']}/spacecraft/model").json()
    assert len(model["spacecraft"]) == 1
    assert len(model["spacecraft"][0]["components"]) == 3
    rw = next(c for c in model["spacecraft"][0]["components"] if c["component_type"] == "REACTION_WHEEL")
    assert rw["parameters"]["max_torque_nm"] == 0.02


def test_missing_required_parameter_rejected(client, mission):
    bad = {**VALID_CONFIG, "components": [
        {"component_type": "REACTION_WHEEL", "name": "RW-X", "parameters": {"max_torque_nm": 0.02}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=bad)
    body = resp.json()
    assert body["valid"] is False
    assert any("max_momentum_nms" in e for e in body["errors"])


def test_unknown_component_type_rejected(client, mission):
    bad = {**VALID_CONFIG, "components": [
        {"component_type": "WARP_DRIVE", "name": "Nonsense", "parameters": {}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=bad)
    body = resp.json()
    assert body["valid"] is False
    assert any("unknown component_type" in e for e in body["errors"])


def test_negative_parameter_value_rejected(client, mission):
    bad = {**VALID_CONFIG, "components": [
        {"component_type": "BATTERY", "name": "Bad Battery", "parameters": {"capacity_wh": -50, "nominal_voltage_v": 7.4}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=bad)
    body = resp.json()
    assert body["valid"] is False
    assert any("must be positive" in e for e in body["errors"])


def test_inverted_thermal_range_rejected(client, mission):
    bad = {**VALID_CONFIG, "components": [
        {"component_type": "THERMAL_SYSTEM", "name": "Bad Thermal", "parameters": {"operating_range_min_c": 50, "operating_range_max_c": -20}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=bad)
    body = resp.json()
    assert body["valid"] is False
    assert any("operating_range_min_c must be less than" in e for e in body["errors"])


def test_missing_battery_and_attitude_control_produce_warnings(client, mission):
    minimal = {"name": "Minimal Sat", "inertia_ixx": 0.02, "inertia_iyy": 0.02, "inertia_izz": 0.01, "components": []}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=minimal)
    body = resp.json()
    assert body["valid"] is True
    assert any("No battery pack" in w for w in body["warnings"])
    assert any("No thermal system" in w for w in body["warnings"])
    assert any("attitude control" in w for w in body["warnings"])


def test_duplicate_component_names_warned(client, mission):
    dup = {**VALID_CONFIG, "components": [
        {"component_type": "REACTION_WHEEL", "name": "RW-1", "parameters": {"max_torque_nm": 0.02, "max_momentum_nms": 0.05}},
        {"component_type": "REACTION_WHEEL", "name": "RW-1", "parameters": {"max_torque_nm": 0.02, "max_momentum_nms": 0.05}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=dup)
    body = resp.json()
    assert body["valid"] is True
    assert any("Duplicate component name" in w for w in body["warnings"])


def test_torque_outside_sanity_bound_warned_not_rejected(client, mission):
    extreme = {**VALID_CONFIG, "components": [
        {"component_type": "REACTION_WHEEL", "name": "Big-RW", "parameters": {"max_torque_nm": 50.0, "max_momentum_nms": 5.0}},
    ]}
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=extreme)
    body = resp.json()
    assert body["valid"] is True  # sanity bounds warn, never reject
    assert any("outside the typical smallsat range" in w for w in body["warnings"])


def test_dry_run_does_not_persist(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/spacecraft/configure?dry_run=true", json=VALID_CONFIG)
    assert resp.json()["valid"] is True
    model = client.get(f"/api/missions/{mission['id']}/spacecraft/model").json()
    assert model["spacecraft"] == []


def test_configure_agent_run_persisted_to_audit_trail(client, mission):
    client.post(f"/api/missions/{mission['id']}/spacecraft/configure", json=VALID_CONFIG)
    runs = client.get(f"/api/missions/{mission['id']}/agent-runs", params={"agent_name": "spacecraft_configuration_engine"}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "OK"
    assert runs[0]["output"]["component_count"] == 3


def test_configure_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/spacecraft/configure", json=VALID_CONFIG)
    assert resp.status_code == 404
