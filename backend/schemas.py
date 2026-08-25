"""Pydantic request/response models for the FastAPI backend."""

from typing import Any

from pydantic import BaseModel


class ProposeRequest(BaseModel):
    maneuver_type: str = "SAFE_RCS_PULSE"
    mission_profile_key: str = "earth_observation"
    x0: list[float] | None = None
    u_cmd: list[float] | None = None
    mission_id: int | None = None


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
    mission_id: int | None = None


class MissionCreateRequest(BaseModel):
    mission_name: str
    objective: str | None = None
    mission_profile_key: str = "earth_observation"
    tle_line1: str | None = None
    tle_line2: str | None = None


class MissionStatusUpdate(BaseModel):
    status: str
    active: bool | None = None


class MissionResponse(BaseModel):
    id: int
    mission_name: str
    objective: str | None
    mission_profile_id: int
    mission_profile_key: str
    mission_profile_display_name: str
    tle_line1: str | None
    tle_line2: str | None
    status: str
    active: bool
    created_at: str
