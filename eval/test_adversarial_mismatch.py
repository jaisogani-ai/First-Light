"""A valid certificate attached to a different (unsafe) command must be rejected at the
real hash-match step — not a reimplementation of the check, the actual /api/commands/verify path."""


def test_mismatched_command_rejected_by_real_verifier(client, valid_command):
    tampered_u_cmd = [0.5, 0.5, 0.5]  # different torque than what the certificate was proven for
    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": valid_command["proof"],
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": tampered_u_cmd,
        "mission_profile_key": "earth_observation",
    }
    resp = client.post("/api/commands/verify", json=body)
    data = resp.json()

    assert data["verdict"] == "REJECTED"
    assert data["explain"]["failing_step"] == "Command Hash Match"
    assert data["trust"]["overall"] == "REJECTED"
