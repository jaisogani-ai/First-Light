"""Hand-corrupted Farkas multipliers must be rejected by the real Farkas arithmetic check.

The certificate's signature covers the whole payload, so external tampering with multipliers
alone is actually caught at the Signature step first (defense in depth — see
test_tampered_signature.py for that layer). To specifically exercise the Farkas layer, these
tests re-sign the corrupted certificate with the same key (modeling a producer-side bug or a
compromised signing key) so the request reaches the Farkas check intact.
"""

import copy

from backend.security import compute_hmac_signature


def _resign(proof: dict) -> dict:
    proof = copy.deepcopy(proof)
    without_sig = {k: v for k, v in proof.items() if k != "signature"}
    proof["signature"] = compute_hmac_signature(without_sig)
    return proof


def test_negative_multiplier_rejected(client, valid_command):
    proof = copy.deepcopy(valid_command["proof"])
    proof["certificate"]["multipliers"][0] = -1.0  # violates lambda >= 0
    proof = _resign(proof)

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
    assert data["explain"]["failing_step"] == "Farkas Inequality"


def test_arbitrary_multipliers_disconnected_from_state_rejected(client, valid_command):
    proof = copy.deepcopy(valid_command["proof"])
    proof["certificate"]["multipliers"] = [0.9] * len(proof["certificate"]["multipliers"])  # not derived from x_post
    proof = _resign(proof)

    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": proof,
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }
    resp = client.post("/api/commands/verify", json=body)
    data = resp.json()

    # The old code (0.01/0.014 magic-constant formula) would have accepted whatever was here.
    assert data["verdict"] == "REJECTED"
    assert data["explain"]["failing_step"] == "Farkas Inequality"
