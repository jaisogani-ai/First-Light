"""Resubmitting a previously-accepted (command, proof) pair must be rejected by the real,
DB-backed sequence-freshness check — not an in-memory magic number."""


def test_replayed_proof_rejected_after_first_acceptance(client, valid_command):
    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": valid_command["proof"],
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }

    first = client.post("/api/commands/verify", json=body).json()
    assert first["verdict"] == "VERIFIED"

    replay = client.post("/api/commands/verify", json=body).json()
    assert replay["verdict"] == "REJECTED"
    assert replay["explain"]["failing_step"] == "Sequence Freshness"
