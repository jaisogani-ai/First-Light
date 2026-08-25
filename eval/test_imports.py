"""Mission Import Pipeline: TLE, CSV telemetry, Mission JSON, Spacecraft Profile, and
Constraint Profile — validation, dry_run preview, provenance recording, and the explicit
safety boundary that constraint-profile imports never touch the live verifier's envelope."""

import pytest

# Checksum-valid (NORAD mod-10 checksum verified against both lines), 69 columns each.
VALID_TLE_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9009"
VALID_TLE_LINE2 = "2 25544  51.6416 339.9700 0007133  92.8340 267.3805 15.49560792 27004"


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Import Pipeline Test", "mission_profile_key": "earth_observation",
    }).json()


def test_valid_tle_import_persists_and_updates_mission(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["epoch"] is not None
    assert body["freshness_days"] is not None

    fetched = client.get(f"/api/missions/{mission['id']}").json()
    assert fetched["tle_line1"] == VALID_TLE_LINE1
    assert fetched["tle_line2"] == VALID_TLE_LINE2


def test_tle_bad_checksum_rejected_and_not_persisted(client, mission):
    corrupted = VALID_TLE_LINE1[:-1] + ("1" if VALID_TLE_LINE1[-1] != "1" else "2")
    resp = client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": corrupted, "line2": VALID_TLE_LINE2,
    })
    body = resp.json()
    assert body["valid"] is False
    assert any("checksum" in e for e in body["errors"])

    fetched = client.get(f"/api/missions/{mission['id']}").json()
    assert fetched["tle_line1"] is None


def test_tle_dry_run_does_not_persist(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/tle?dry_run=true", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2,
    })
    assert resp.json()["valid"] is True

    fetched = client.get(f"/api/missions/{mission['id']}").json()
    assert fetched["tle_line1"] is None


TELEMETRY_HEADER = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                     "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms")


def test_csv_telemetry_import_persists_rows(client, mission):
    csv_text = (TELEMETRY_HEADER + "\n"
                "0.01,0.02,0.03,0.02,90.0,12.0,24.5,250.0,8.0\n"
                "0.011,0.019,0.028,0.021,89.5,12.1,24.6,251.0,8.1\n")
    resp = client.post(
        f"/api/missions/{mission['id']}/imports/csv-telemetry",
        files={"file": ("pass1.csv", csv_text, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["row_count"] == 2

    telemetry = client.get("/api/telemetry/latest", params={"mission_id": mission["id"]}).json()
    assert len(telemetry) == 2
    assert telemetry[0]["mission_id"] == mission["id"]


def test_csv_telemetry_missing_required_column_rejected(client, mission):
    csv_text = "omega_x,omega_y\n0.01,0.02\n"
    resp = client.post(
        f"/api/missions/{mission['id']}/imports/csv-telemetry",
        files={"file": ("bad.csv", csv_text, "text/csv")},
    )
    body = resp.json()
    assert body["valid"] is False
    assert any("omega_z" in e for e in body["errors"])


def test_csv_telemetry_non_numeric_value_rejected_atomically(client, mission):
    csv_text = "omega_x,omega_y,omega_z\n0.01,not_a_number,0.03\n"
    resp = client.post(
        f"/api/missions/{mission['id']}/imports/csv-telemetry",
        files={"file": ("bad.csv", csv_text, "text/csv")},
    )
    body = resp.json()
    assert body["valid"] is False

    telemetry = client.get("/api/telemetry/latest", params={"mission_id": mission["id"]}).json()
    assert telemetry == []


def test_mission_json_import_updates_objective(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/mission-json", json={
        "objective": "Updated via manifest import",
    })
    assert resp.json()["valid"] is True
    assert client.get(f"/api/missions/{mission['id']}").json()["objective"] == "Updated via manifest import"


def test_mission_json_unknown_field_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/mission-json", json={
        "not_a_real_field": "value",
    })
    body = resp.json()
    assert body["valid"] is False


def test_spacecraft_profile_import_persists(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/spacecraft-profile", json={
        "name": "CubeSat-1", "inertia_ixx": 0.02, "inertia_iyy": 0.02, "inertia_izz": 0.01,
    })
    assert resp.json()["valid"] is True


def test_spacecraft_profile_negative_inertia_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/spacecraft-profile", json={
        "name": "Bad", "inertia_ixx": -0.02, "inertia_iyy": 0.02, "inertia_izz": 0.01,
    })
    body = resp.json()
    assert body["valid"] is False
    assert any("positive" in e for e in body["errors"])


def test_constraint_profile_import_never_touches_live_verifier_envelope(client, mission):
    """The core safety boundary: importing a constraint profile is recorded, but it must
    never alter what the real mission_profiles table (and therefore the verifier) enforces."""
    before = client.get("/api/profiles").json()

    resp = client.post(f"/api/missions/{mission['id']}/imports/constraint-profile", json={
        "max_omega_rad_s": 999.0,  # deliberately absurd — proves it can't leak into the verifier
        "power_reserve_w": 5.0, "thermal_max_c": 50.0, "thermal_min_c": -10.0,
    })
    body = resp.json()
    assert body["valid"] is True
    assert body["applied_to_verifier"] is False

    after = client.get("/api/profiles").json()
    assert before == after


def test_constraint_profile_inverted_thermal_bounds_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/constraint-profile", json={
        "max_omega_rad_s": 0.05, "power_reserve_w": 5.0, "thermal_max_c": -10.0, "thermal_min_c": 50.0,
    })
    body = resp.json()
    assert body["valid"] is False


def test_imports_are_listed_with_provenance(client, mission):
    client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2, "source": "test_suite",
    })
    listing = client.get(f"/api/missions/{mission['id']}/imports").json()
    assert len(listing) == 1
    assert listing[0]["import_type"] == "TLE"
    assert listing[0]["imported_at"] is not None


def test_import_against_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/imports/mission-json", json={"objective": "x"})
    assert resp.status_code == 404


def test_import_provenance_includes_checksum_source_and_schema_version(client, mission):
    client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2, "source": "celestrak",
    })
    listing = client.get(f"/api/missions/{mission['id']}/imports").json()
    record = listing[0]
    assert record["checksum"].startswith("sha256:")
    assert record["source"] == "celestrak"
    assert record["schema_version"] == "1.0"
    assert record["freshness_days"] is not None


def test_identical_tle_content_produces_identical_checksum(client, mission):
    other_mission = client.post("/api/missions", json={
        "mission_name": "Checksum Compare", "mission_profile_key": "earth_observation",
    }).json()
    client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2,
    })
    client.post(f"/api/missions/{other_mission['id']}/imports/tle", json={
        "line1": VALID_TLE_LINE1, "line2": VALID_TLE_LINE2,
    })
    checksum_a = client.get(f"/api/missions/{mission['id']}/imports").json()[0]["checksum"]
    checksum_b = client.get(f"/api/missions/{other_mission['id']}/imports").json()[0]["checksum"]
    assert checksum_a == checksum_b


def test_csv_telemetry_row_cap_rejected(client, mission, monkeypatch):
    import backend.routers.imports as imports_router
    monkeypatch.setattr(imports_router, "MAX_CSV_TELEMETRY_ROWS", 1)

    csv_text = (TELEMETRY_HEADER + "\n"
                "0.01,0.02,0.03,0.02,90.0,12.0,24.5,250.0,8.0\n"
                "0.011,0.019,0.028,0.021,89.5,12.1,24.6,251.0,8.1\n")
    resp = client.post(
        f"/api/missions/{mission['id']}/imports/csv-telemetry",
        files={"file": ("toobig.csv", csv_text, "text/csv")},
    )
    body = resp.json()
    assert body["valid"] is False
    assert any("row limit" in e for e in body["errors"])

    telemetry = client.get("/api/telemetry/latest", params={"mission_id": mission["id"]}).json()
    assert telemetry == []


VALID_OMM = {
    "CLASSIFICATION_TYPE": "U", "OBJECT_ID": "1998-067A", "EPHEMERIS_TYPE": "0",
    "ELEMENT_SET_NO": "900", "REV_AT_EPOCH": "2700", "EPOCH": "2024-01-01T12:00:00.000000",
    "ARG_OF_PERICENTER": "92.8340", "BSTAR": "0.00010270", "ECCENTRICITY": "0.0007133",
    "INCLINATION": "51.6416", "MEAN_ANOMALY": "267.3805", "MEAN_MOTION_DDOT": "0.0",
    "MEAN_MOTION_DOT": "0.00016717", "MEAN_MOTION": "15.49560792", "RA_OF_ASC_NODE": "339.9700",
    "NORAD_CAT_ID": "25544",
}


def test_valid_omm_import_recorded_with_real_sgp4_validation(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/omm", json=VALID_OMM)
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["epoch"] == "2024-01-01T12:00:00+00:00"
    assert body["freshness_days"] is not None

    listing = client.get(f"/api/missions/{mission['id']}/imports").json()
    assert listing[0]["import_type"] == "OMM"
    assert listing[0]["schema_version"] == "CCSDS-502.0-B-2"
    assert listing[0]["checksum"].startswith("sha256:")


def test_omm_missing_required_fields_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/omm", json={"CLASSIFICATION_TYPE": "U"})
    body = resp.json()
    assert body["valid"] is False
    assert "Missing required CCSDS OMM fields" in body["errors"][0]


def test_omm_non_numeric_field_rejected_by_real_sgp4_library(client, mission):
    bad = {**VALID_OMM, "ECCENTRICITY": "not-a-number"}
    resp = client.post(f"/api/missions/{mission['id']}/imports/omm", json=bad)
    body = resp.json()
    assert body["valid"] is False
    assert "sgp4.omm rejected" in body["errors"][0]


def test_omm_dry_run_does_not_persist(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/imports/omm?dry_run=true", json=VALID_OMM)
    assert resp.json()["valid"] is True
    assert client.get(f"/api/missions/{mission['id']}/imports").json() == []


def test_csv_telemetry_byte_size_cap_rejected(client, mission, monkeypatch):
    import backend.routers.imports as imports_router
    monkeypatch.setattr(imports_router, "MAX_CSV_TELEMETRY_BYTES", 10)

    csv_text = TELEMETRY_HEADER + "\n0.01,0.02,0.03,0.02,90.0,12.0,24.5,250.0,8.0\n"
    resp = client.post(
        f"/api/missions/{mission['id']}/imports/csv-telemetry",
        files={"file": ("toobig.csv", csv_text, "text/csv")},
    )
    assert resp.status_code == 413
