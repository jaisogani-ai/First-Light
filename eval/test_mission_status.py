"""Mission Status — orbit context (real SGP4), mission health, verification state, and
telemetry freshness. Every field is derived from real data or explicitly UNKNOWN/null —
never fabricated."""

import pytest

VALID_TLE_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9009"
VALID_TLE_LINE2 = "2 25544  51.6416 339.9700 0007133  92.8340 267.3805 15.49560792 27004"


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Status Target", "mission_profile_key": "earth_observation",
    }).json()


def test_orbit_context_requires_a_tle(client, mission):
    resp = client.get(f"/api/missions/{mission['id']}/orbit-context")
    assert resp.status_code == 409


def test_orbit_context_after_tle_import_is_real_sgp4(client, mission):
    client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2,
    })
    resp = client.get(f"/api/missions/{mission['id']}/orbit-context")
    assert resp.status_code == 200
    body = resp.json()
    assert -90 <= body["lat_deg"] <= 90
    assert -180 <= body["lon_deg"] <= 180
    assert 300 < body["altitude_km"] < 500  # ISS-like orbit from this TLE
    assert 85 < body["orbital_period_minutes"] < 95


def test_orbit_context_missing_mission_404s(client):
    resp = client.get("/api/missions/999999/orbit-context")
    assert resp.status_code == 404


def test_status_with_no_telemetry_is_honestly_unknown(client, mission):
    body = client.get(f"/api/missions/{mission['id']}/status").json()
    assert body["mission_health"]["overall"] == "UNKNOWN"
    assert body["telemetry_freshness_seconds"] is None
    assert body["verification_state"]["state"] == "NO_COMMANDS"


def test_status_reflects_real_verified_command(client, mission):
    propose = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission["id"],
    }).json()
    client.post("/api/commands/verify", json={
        "command_row_id": propose["command_row_id"], "proof": propose["proof"],
        "submitted_command_id": propose["command_id"], "submitted_u_cmd": propose["u_cmd"],
        "mission_id": mission["id"],
    })
    body = client.get(f"/api/missions/{mission['id']}/status").json()
    assert body["verification_state"]["verdict"] == "VERIFIED"
    assert body["verification_state"]["command_id"] == propose["command_id"]


def test_status_health_nominal_within_envelope(client, mission):
    csv_text = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms\n"
                "0.001,0.001,0.001,0.02,90.0,20.0,24.5,250.0,8.0\n")
    client.post(f"/api/missions/{mission['id']}/imports/csv-telemetry",
                files={"file": ("nominal.csv", csv_text, "text/csv")})
    body = client.get(f"/api/missions/{mission['id']}/status").json()
    assert body["mission_health"]["overall"] == "NOMINAL"
    assert body["telemetry_freshness_seconds"] is not None
    assert body["telemetry_freshness_seconds"] < 60


def test_status_health_critical_over_angular_rate_envelope(client, mission):
    # earth_observation profile's max_omega_rad_s is 0.05 — 0.2 is well over it
    csv_text = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms\n"
                "0.2,0.0,0.0,0.02,90.0,20.0,24.5,250.0,8.0\n")
    client.post(f"/api/missions/{mission['id']}/imports/csv-telemetry",
                files={"file": ("overrate.csv", csv_text, "text/csv")})
    body = client.get(f"/api/missions/{mission['id']}/status").json()
    assert body["mission_health"]["overall"] == "CRITICAL"
    assert any("angular rate" in r for r in body["mission_health"]["reasons"])


def test_status_health_critical_over_battery_low(client, mission):
    csv_text = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms\n"
                "0.001,0.001,0.001,0.02,5.0,20.0,24.5,250.0,8.0\n")
    client.post(f"/api/missions/{mission['id']}/imports/csv-telemetry",
                files={"file": ("lowbatt.csv", csv_text, "text/csv")})
    body = client.get(f"/api/missions/{mission['id']}/status").json()
    assert body["mission_health"]["overall"] == "CRITICAL"
    assert any("battery" in r for r in body["mission_health"]["reasons"])


def test_status_missing_mission_404s(client):
    resp = client.get("/api/missions/999999/status")
    assert resp.status_code == 404
