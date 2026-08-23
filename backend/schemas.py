"""Pydantic request/response models for the FastAPI backend."""

from typing import Any

from pydantic import BaseModel


class ProposeRequest(BaseModel):
    maneuver_type: str = "SAFE_RCS_PULSE"
    mission_profile_key: str = "earth_observation"
    x0: list[float] | None = None
    u_cmd: list[float] | None = None


class TrustAssessment(BaseModel):
    proof_valid: bool
    telemetry_fresh: bool
    sequence_valid: bool
    signature_valid: bool
    safety_satisfied: bool
    overall: str  # "TRUSTED" | "REJECTED"


class ExplainData(BaseModel):
    constraint_checked: str
    expected_max: float
    actual: float
    failing_step: str | None
    narrative: str


class VerifyResponse(BaseModel):
    command_id: str
    verdict: str
    reject_reason: str | None
    producer_time_ms: float
    verifier_time_ms: float
    trust: TrustAssessment
    explain: ExplainData
    pipeline_steps: list[dict[str, Any]]
    run_id: str


class AttackRequest(BaseModel):
    attack_type: str
    mission_profile_key: str = "earth_observation"
