"""A single flipped byte in the HMAC signature must be rejected by real HMAC recomputation —
the old code only checked for an 'hmac_sha256:' prefix, which this would have passed."""

import copy


def test_flipped_signature_byte_rejected(client, valid_command):
    proof = copy.deepcopy(valid_command["proof"])
    sig = proof["signature"]
    prefix, hexdigest = sig.split(":", 1)
    flipped_char = "0" if hexdigest[0] != "0" else "1"
    proof["signature"] = f"{prefix}:{flipped_char}{hexdigest[1:]}"

    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": proof,
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }
    resp = client.post("/api/commands/verify", json=body)
    data = resp.json()

    assert data["verdict"] == "REJECTED"
    assert data["explain"]["failing_step"] == "Signature Valid"


def test_prefix_only_forgery_rejected(client, valid_command):
    """The exact bug the old verifier had: `.startswith('hmac_sha256:')` would accept this."""
    proof = copy.deepcopy(valid_command["proof"])
    proof["signature"] = "hmac_sha256:" + "0" * 64

    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": proof,
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }
    resp = client.post("/api/commands/verify", json=body)
    data = resp.json()

    assert data["verdict"] == "REJECTED"
    assert data["explain"]["failing_step"] == "Signature Valid"
