"""The real 5-step cFS Gate verifier — deterministic arithmetic, no search, no re-solving.

Every check operates on the actual submitted payload against actual persisted state:
1. Sequence freshness   — DB-backed last_accepted_sequence, transactional.
2. Command hash match   — real SHA-256 recomputation over the submitted command bytes.
3. Signature valid      — real HMAC-SHA256 recomputation over the certificate payload.
4. Model version match  — checked against an explicit accepted-model registry.
5. Farkas inequality    — recompute sum(multiplier_i * constraint_i) from the payload's own
                           numbers, require all multipliers >= 0 and the sum strictly < 0.

This module is the single source of truth used by the FastAPI routes, the Attack Library,
and the eval/ pytest suite — there is exactly one place these checks are implemented.
"""

import time
from datetime import datetime, timezone

from sqlalchemy import select

from backend.models import sequence_state
from backend.schemas import ExplainData, TrustAssessment
from backend.security import verify_command_hash, verify_signature

ACCEPTED_MODEL_IDS = {"linear_rigid_body_v1"}
DEFAULT_STREAM_ID = "default"


class VerificationResult:
    def __init__(self, verdict, reject_reason, verifier_time_ms, trust: TrustAssessment, explain: ExplainData):
        self.verdict = verdict
        self.reject_reason = reject_reason
        self.verifier_time_ms = verifier_time_ms
        self.trust = trust
        self.explain = explain


def verify_command(conn, proof: dict, cmd_bytes: bytes, stream_id: str = DEFAULT_STREAM_ID) -> VerificationResult:
    t0 = time.perf_counter()

    row = conn.execute(select(sequence_state).where(sequence_state.c.stream_id == stream_id)).fetchone()
    last_accepted = row.last_accepted_sequence if row else 0

    now = datetime.now(timezone.utc)
    valid_from = datetime.fromisoformat(proof["valid_from"])
    valid_until = datetime.fromisoformat(proof["valid_until"])
    window_ok = valid_from <= now <= valid_until
    sequence_ok = (proof["sequence_no"] > last_accepted) and window_ok

    hash_ok = verify_command_hash(cmd_bytes, proof["command_hash"])
    signature_ok = verify_signature(proof)
    model_ok = proof["model_id"] in ACCEPTED_MODEL_IDS

    cert = proof["certificate"]
    multipliers = cert["multipliers"]
    constraints = cert["constraints"]
    all_nonneg = all(m >= 0 for m in multipliers)
    recomputed_sum = sum(m * c for m, c in zip(multipliers, constraints))
    # A weighted sum of nonneg multipliers over per-constraint slacks is < 0 for almost any
    # nonneg lambda whenever the true state is safe (every slack is negative) — that alone
    # would let a forged multiplier vector cherry-pick a comfortable constraint and hide a
    # violated one. The only sound reading of the one-hot binding-constraint construction is
    # requiring the weighted sum to exactly reproduce the true worst-case (max) constraint;
    # a convex combination of values <= max(constraints) can equal max(constraints) only if
    # all weight sits on the maximal constraint(s), which is exactly what soundness requires.
    max_constraint = max(constraints) if constraints else 0.0
    farkas_ok = all_nonneg and abs(recomputed_sum - max_constraint) < 1e-9 and max_constraint < 0.0

    overall_ok = sequence_ok and hash_ok and signature_ok and model_ok and farkas_ok

    if overall_ok:
        if row:
            conn.execute(
                sequence_state.update()
                .where(sequence_state.c.stream_id == stream_id)
                .values(last_accepted_sequence=proof["sequence_no"], updated_at=now.isoformat())
            )
        else:
            conn.execute(sequence_state.insert().values(
                stream_id=stream_id, last_accepted_sequence=proof["sequence_no"], updated_at=now.isoformat()
            ))

    reject_reason = None
    failing_step = None
    if not sequence_ok:
        reject_reason = "Sequence freshness check failed (replay or stale window)"
        failing_step = "Sequence Freshness"
    elif not hash_ok:
        reject_reason = "Command hash mismatch (payload tampering)"
        failing_step = "Command Hash Match"
    elif not signature_ok:
        reject_reason = "HMAC signature invalid (forged or corrupted certificate)"
        failing_step = "Signature Valid"
    elif not model_ok:
        reject_reason = "Unrecognized dynamics model_id"
        failing_step = "Model Version Match"
    elif not farkas_ok:
        reject_reason = "Farkas inequality does not hold for the submitted multipliers/constraints"
        failing_step = "Farkas Inequality"

    max_omega = proof["bound"]["max_rad_s"]
    binding_value = max(constraints) if constraints else 0.0
    actual_rate = abs(binding_value + max_omega)

    explain = ExplainData(
        constraint_checked=proof.get("property", "post_maneuver_omega_bound"),
        expected_max=max_omega,
        actual=actual_rate,
        failing_step=failing_step,
        narrative=(
            f"Angular rate bound {max_omega:.4f} rad/s; binding-axis rate {actual_rate:.4f} rad/s -> "
            f"{'proof valid, command accepted' if overall_ok else f'{failing_step} failed, command rejected'}."
        ),
    )

    trust = TrustAssessment(
        proof_valid=farkas_ok,
        telemetry_fresh=sequence_ok,
        sequence_valid=sequence_ok,
        signature_valid=signature_ok,
        safety_satisfied=farkas_ok,
        overall="TRUSTED" if overall_ok else "REJECTED",
    )

    verifier_time_ms = (time.perf_counter() - t0) * 1000
    return VerificationResult(
        verdict="VERIFIED" if overall_ok else "REJECTED",
        reject_reason=reject_reason,
        verifier_time_ms=verifier_time_ms,
        trust=trust,
        explain=explain,
    )
