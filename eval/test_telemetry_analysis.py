"""Telemetry Analysis Engine — deterministic numpy statistics over real telemetry rows.
No LLM, no fabrication: every number traces to real DB data via db/seed.py-seeded imports."""

import pytest

TELEMETRY_HEADER = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                     "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms,ts")


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Telemetry Analysis Target", "mission_profile_key": "earth_observation",
    }).json()


def _import_csv(client, mission_id, rows_csv):
    return client.post(f"/api/missions/{mission_id}/imports/csv-telemetry",
                        files={"file": ("t.csv", TELEMETRY_HEADER + "\n" + rows_csv, "text/csv")})


def test_no_telemetry_yields_honest_empty_result(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run")
    body = resp.json()
    assert body["record_count"] == 0
    assert "No telemetry recorded" in body["message"]


def test_regular_cadence_produces_real_sampling_stats(client, mission):
    rows = "\n".join(
        f"0.01,0.01,0.01,0.02,{90.0 - i},20.0,24.5,250.0,8.0,2026-01-01T00:0{i}:00.000000Z"
        for i in range(6)
    )
    _import_csv(client, mission["id"], rows)
    body = client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run").json()

    assert body["record_count"] == 6
    assert body["sampling"]["median_interval_seconds"] == pytest.approx(60.0, rel=0.01)
    assert body["sampling"]["sampling_frequency_hz"] == pytest.approx(1 / 60.0, rel=0.01)
    assert body["packet_gaps"] == []
    assert body["time_synchronization"]["monotonically_increasing"] is True


def test_real_gap_detected_between_samples(client, mission):
    rows = "\n".join([
        "0.01,0.01,0.01,0.02,90.0,20.0,24.5,250.0,8.0,2026-01-01T00:00:00.000000Z",
        "0.01,0.01,0.01,0.02,89.0,20.0,24.5,250.0,8.0,2026-01-01T00:01:00.000000Z",
        "0.01,0.01,0.01,0.02,88.0,20.0,24.5,250.0,8.0,2026-01-01T00:02:00.000000Z",
        "0.01,0.01,0.01,0.02,87.0,20.0,24.5,250.0,8.0,2026-01-01T00:20:00.000000Z",  # 18-minute gap
    ])
    _import_csv(client, mission["id"], rows)
    body = client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run").json()

    assert len(body["packet_gaps"]) == 1
    assert body["packet_gaps"][0]["gap_seconds"] == pytest.approx(18 * 60, rel=0.01)
    assert body["missing_packets_estimate"] >= 1


def test_sensor_statistics_are_real_numpy_values(client, mission):
    rows = "\n".join([
        "0.01,0.01,0.01,0.02,100.0,20.0,24.5,250.0,8.0,2026-01-01T00:00:00.000000Z",
        "0.02,0.01,0.01,0.02,50.0,25.0,24.5,250.0,8.0,2026-01-01T00:01:00.000000Z",
        "0.03,0.01,0.01,0.02,0.0,30.0,24.5,250.0,8.0,2026-01-01T00:02:00.000000Z",
    ])
    _import_csv(client, mission["id"], rows)
    body = client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run").json()

    batt = body["sensor_statistics"]["battery_soc_pct"]
    assert batt["min"] == 0.0
    assert batt["max"] == 100.0
    assert batt["mean"] == pytest.approx(50.0)
    assert batt["sample_count"] == 3


def test_declining_battery_trend_detected(client, mission):
    rows = "\n".join(
        f"0.01,0.01,0.01,0.02,{100.0 - i * 5},20.0,24.5,250.0,8.0,2026-01-01T00:0{i}:00.000000Z"
        for i in range(6)
    )
    _import_csv(client, mission["id"], rows)
    body = client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run").json()
    assert body["trends"]["battery_soc_pct"]["direction"] == "decreasing"
    assert body["trends"]["battery_soc_pct"]["slope_per_sample"] < 0


def test_agent_run_persisted_with_real_output(client, mission):
    rows = "0.01,0.01,0.01,0.02,90.0,20.0,24.5,250.0,8.0,2026-01-01T00:00:00.000000Z"
    _import_csv(client, mission["id"], rows)
    client.post(f"/api/missions/{mission['id']}/telemetry-analysis/run")

    runs = client.get(f"/api/missions/{mission['id']}/agent-runs",
                       params={"agent_name": "telemetry_analysis_engine"}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "OK"
    assert runs[0]["output"]["record_count"] == 1


def test_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/telemetry-analysis/run")
    assert resp.status_code == 404
