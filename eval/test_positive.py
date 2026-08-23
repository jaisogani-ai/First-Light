"""A genuinely safe command is proposed and verified end-to-end against the live backend."""


def test_safe_maneuver_is_verified(client, valid_command):
    assert valid_command["refused"] is False
    assert valid_command["proof"]["certificate"]["multipliers"] != [0.20, 0.0, 0.40]  # not the old hardcoded value

    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": valid_command["proof"],
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }
    resp = client.post("/api/commands/verify", json=body)
    assert resp.status_code == 200
    data = resp.json()

    assert data["verdict"] == "VERIFIED"
    assert data["trust"]["overall"] == "TRUSTED"
    assert data["verifier_time_ms"] < 5.0, "verifier should be sub-5ms cheap arithmetic"
    assert data["verifier_time_ms"] < valid_command["producer_time_ms"], "verifier must be faster than the solver"


def test_different_inputs_produce_different_certificates(client):
    a = client.post("/api/commands/propose", json={"maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation"}).json()
    b = client.post("/api/commands/propose", json={"maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "deep_space"}).json()
    assert a["proof"]["bound"]["max_rad_s"] != b["proof"]["bound"]["max_rad_s"]
    assert a["proof"]["certificate"]["constraints"] != b["proof"]["certificate"]["constraints"]
