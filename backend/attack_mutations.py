"""One source of truth for 'what an attack looks like'. Shared by the Attack Library
endpoints and the eval/ adversarial pytest suite — each mutation takes a real, freshly
generated valid proposal and corrupts it for real; nothing here is scripted output."""

import copy

ATTACK_TYPES = [
    "tampered_command",
    "replay",
    "wrong_certificate",
    "missing_proof",
    "stale_telemetry",
    "wrong_sequence",
    "modified_payload",
]


def apply_attack(attack_type: str, proof: dict, submitted_command_id: str, submitted_u_cmd: list) -> dict:
    """Returns a dict with the (possibly mutated) proof, command_id, and u_cmd to submit,
    plus a human-readable description of what was actually changed."""
    proof = copy.deepcopy(proof)
    cmd_id = submitted_command_id
    u_cmd = list(submitted_u_cmd)

    if attack_type == "tampered_command":
        u_cmd = [u_cmd[0] + 0.5, u_cmd[1] + 0.5, u_cmd[2] + 0.5]
        desc = "Submitted different torque values than the ones the certificate was proven for."

    elif attack_type == "replay":
        # sequence_no left as-is on purpose: this simulates resubmitting an already-accepted proof.
        desc = "Resubmitted a previously-accepted (command, proof) pair unchanged."

    elif attack_type == "wrong_certificate":
        proof["certificate"]["multipliers"] = [0.9] * len(proof["certificate"]["multipliers"])
        desc = "Attached a certificate with arbitrary multipliers not derived from this state."

    elif attack_type == "missing_proof":
        proof["certificate"] = {"type": "farkas_linear_infeasibility", "multipliers": [], "constraints": [],
                                 "contradiction": ""}
        desc = "Submitted a command with an empty certificate (no proof at all)."

    elif attack_type == "stale_telemetry":
        proof["valid_until"] = "2000-01-01T00:00:00+00:00"
        desc = "Certificate's validity window was set to have already expired."

    elif attack_type == "wrong_sequence":
        proof["sequence_no"] = 1
        desc = "Certificate carries a sequence number far below the last accepted value."

    elif attack_type == "modified_payload":
        proof["bound"]["max_rad_s"] = 999.0
        desc = "Widened the stated safety bound after the certificate was signed."

    else:
        raise ValueError(f"Unknown attack_type: {attack_type}")

    return {"proof": proof, "submitted_command_id": cmd_id, "submitted_u_cmd": u_cmd, "description": desc}
