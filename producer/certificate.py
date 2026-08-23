"""Z3 SMT Solver & Farkas Certificate Generator (Proof Generator Agent).

Every field in the returned certificate is derived from the actual x0/u_cmd/max_omega
inputs for this call — nothing here is a fixed constant. Z3 is used to independently
confirm (via a real SMT UNSAT check) that the propagated state cannot satisfy the negated
safety property; the explicit Farkas multipliers/constraints are then derived in closed
form from the box-constraint structure (see producer/rules.py) so the verifier can
recompute the exact same arithmetic from the payload alone.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import z3

from backend.config import settings
from producer.dynamics_model import SpacecraftDynamics
from producer.rules import RULE_REGISTRY


class FarkasCertificateGenerator:
    def __init__(self, model_id: str = "linear_rigid_body_v1"):
        self.model_id = model_id
        self.dynamics = SpacecraftDynamics()

    def generate_proof(self, command_id, x0, u_cmd, max_omega, seq_no, dt=0.1):
        A, B = self.dynamics.discrete_step_matrices(dt)
        x_post = A @ np.array(x0, dtype=np.float64) + B @ np.array(u_cmd, dtype=np.float64)

        z3_ok, z3_result = self._z3_confirm_safe(x_post, max_omega)
        if not z3_ok:
            raise ValueError(
                f"Command UNSAFE: Z3 found a satisfying (unsafe) assignment ({z3_result}) "
                f"for post-maneuver state {list(x_post)}"
            )

        rule = RULE_REGISTRY["angular_rate"]
        rule_result = rule.evaluate({"omega": list(x_post)}, {"max_omega_rad_s": max_omega})
        if not rule_result.satisfied:
            raise ValueError(f"Command UNSAFE: {rule_result.detail}")

        multipliers = [1.0 if i == rule_result.binding_index else 0.0 for i in range(len(rule_result.constraints))]
        contradiction_str = f"sum(lambda_i * constraint_i) = {rule_result.binding_value:.6f} < 0"

        cmd_bytes = f"{command_id}:{u_cmd[0]}:{u_cmd[1]}:{u_cmd[2]}".encode("utf-8")
        cmd_hash = "sha256:" + hashlib.sha256(cmd_bytes).hexdigest()

        now = datetime.now(timezone.utc)
        cert_payload = {
            "command_id": command_id,
            "command_hash": cmd_hash,
            "sequence_no": seq_no,
            "valid_from": now.isoformat(),
            "valid_until": (now + timedelta(seconds=30)).isoformat(),
            "property": "post_maneuver_omega_bound",
            "bound": {"axis": "all", "max_rad_s": max_omega},
            "model_id": self.model_id,
            "context_ref": f"telemetry_frame:{int(time.time())}",
            "certificate": {
                "type": "farkas_linear_infeasibility",
                "multipliers": multipliers,
                "constraints": [float(c) for c in rule_result.constraints],
                "contradiction": contradiction_str,
            },
        }

        payload_str = json.dumps(cert_payload, sort_keys=True)
        sig = hmac.new(settings.hmac_secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
        cert_payload["signature"] = f"hmac_sha256:{sig}"

        return cert_payload, cmd_bytes, x_post

    @staticmethod
    def _z3_confirm_safe(x_post, max_omega):
        """Real Z3 SMT call: assert the negation of the safety property and expect UNSAT.

        Returns (True, "unsat") when Z3 proves no assignment can violate the bound given the
        concrete propagated state; (False, "sat") if Z3 finds the state actually is unsafe.
        """
        y = [z3.Real(f"omega_{i}") for i in range(3)]
        solver = z3.Solver()
        for i in range(3):
            solver.add(y[i] == z3.RealVal(repr(float(x_post[i]))))
        unsafe = z3.Or(*[z3.Or(y[i] > max_omega, y[i] < -max_omega) for i in range(3)])
        solver.add(unsafe)
        result = solver.check()
        return (result == z3.unsat), str(result)


if __name__ == "__main__":
    gen = FarkasCertificateGenerator()
    proof, cmd_bytes, x_post = gen.generate_proof(
        "RCS_PULSE_0042", [0.01, 0.01, 0.00], [0.001, -0.002, 0.001], max_omega=0.05, seq_no=1043
    )
    print("Generated Proof Payload:\n", json.dumps(proof, indent=2))
