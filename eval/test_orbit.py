"""Real SGP4 orbit propagation, checked against known physical facts about the ISS orbit
(inclination ~51.6 deg, altitude ~400km, period ~92-93 min) rather than exact reference
vectors — a garbage/fabricated implementation would not land in these physical bounds."""

# A real, published ISS TLE (Celestrak format). Exact epoch doesn't matter for these tests.
ISS_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9994"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49309239326859"


def test_orbital_period_matches_known_iss_period(client):
    resp = client.post("/api/orbit/period", json={"line1": ISS_LINE1, "line2": ISS_LINE2})
    assert resp.status_code == 200
    period = resp.json()["orbital_period_minutes"]
    assert 90 < period < 95


def test_propagate_altitude_and_inclination_are_physically_sane(client):
    resp = client.post("/api/orbit/propagate", json={"line1": ISS_LINE1, "line2": ISS_LINE2, "minutes_from_epoch": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert 380 < data["altitude_km"] < 430
    assert -51.7 <= data["lat_deg"] <= 51.7  # bounded by the ISS's real orbital inclination


def test_ground_track_moves_over_time(client):
    resp = client.post("/api/orbit/ground-track", json={
        "line1": ISS_LINE1, "line2": ISS_LINE2, "duration_minutes": 30, "step_minutes": 10,
    })
    points = resp.json()["points"]
    assert len(points) >= 3
    # A real propagation moves; a fabricated/static response would repeat the same point.
    assert points[0]["lat_deg"] != points[1]["lat_deg"]


def test_visibility_windows_are_physically_bounded(client):
    resp = client.post("/api/orbit/visibility", json={
        "line1": ISS_LINE1, "line2": ISS_LINE2,
        "station_lat_deg": 40.7, "station_lon_deg": -74.0,
        "duration_minutes": 1440, "step_minutes": 2, "min_elevation_deg": 10,
    })
    windows = resp.json()["windows"]
    for w in windows:
        assert 10 <= w["max_elevation_deg"] <= 90
        assert w["los_minutes"] > w["aos_minutes"]


def test_invalid_tle_is_rejected_not_silently_accepted(client):
    resp = client.post("/api/orbit/period", json={"line1": "not a real TLE", "line2": "also not real"})
    assert resp.status_code == 400
