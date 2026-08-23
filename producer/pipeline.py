"""Multi-agent producer pipeline: Mission Planner -> Dynamics -> Safety -> Proof Generator -> Reviewer.

Every step is a real computation over the actual inputs and returns a uniform record
{inputs, outputs, latency_ms, confidence, reasoning_summary, status, dependencies,
timestamp} — this is what backs the AI Agent Observatory and Multi-Agent Timeline.
Nothing here is scripted: change x0, u_cmd, or the mission profile and every field below
changes accordingly. `dependencies` is computed, not declared: each step's inputs are
diffed against every earlier step's outputs for actual matching values (a real data
dependency); if none match, the step still depends on its immediate predecessor by
control flow (it only ran because the prior step completed).
"""

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np

from producer.certificate import FarkasCertificateGenerator
from producer.dynamics_model import SpacecraftDynamics
from producer.llm_planner import propose_torque_llm
from producer.rules import RULE_REGISTRY

MANEUVER_PRESETS = {
    "SAFE_RCS_PULSE": {"x0": [0.01, 0.01, 0.00], "u_cmd": [0.001, -0.002, 0.001]},
    "UNSAFE_RCS_PULSE": {"x0": [0.04, 0.03, 0.02], "u_cmd": [0.100, 0.200, 0.150]},
}


@dataclass(frozen=True)
class AgentStepRecord:
    step_order: int
    agent_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    latency_ms: float
    confidence: float
    reasoning_summary: str
    status: str
    dependencies: list[dict] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _compute_dependencies(inputs: dict, previous_steps: list[AgentStepRecord]) -> list[dict]:
    deps = []
    for prev in previous_steps:
        shared = [k for k, v in prev.outputs.items() if k in inputs and inputs[k] == v]
        if shared:
            deps.append({"step_order": prev.step_order, "agent_name": prev.agent_name,
                         "shared_fields": shared, "kind": "data"})
    if not deps and previous_steps:
        prev = previous_steps[-1]
        deps.append({"step_order": prev.step_order, "agent_name": prev.agent_name,
                     "shared_fields": [], "kind": "control"})
    return deps


class MissionPipeline:
    def __init__(self, sequence_allocator: Callable[[], int]):
        self.dynamics = SpacecraftDynamics()
        self.cert_gen = FarkasCertificateGenerator()
        self.sequence_allocator = sequence_allocator

    @staticmethod
    def _make_step(steps: list[AgentStepRecord], step_order: int, agent_name: str, inputs: dict,
                    outputs: dict, latency_ms: float, confidence: float, reasoning_summary: str,
                    status: str) -> AgentStepRecord:
        record = AgentStepRecord(
            step_order=step_order, agent_name=agent_name, inputs=inputs, outputs=outputs,
            latency_ms=latency_ms, confidence=confidence, reasoning_summary=reasoning_summary,
            status=status, dependencies=_compute_dependencies(inputs, steps),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        steps.append(record)
        return record

    def run(self, command_id: str, maneuver_type: str, x0, mission_profile: dict, u_cmd=None, dt: float = 0.1) -> dict:
        run_id = str(uuid.uuid4())
        steps: list[AgentStepRecord] = []
        max_omega = mission_profile["max_omega_rad_s"]

        # 1. Mission Planner Agent — real Claude API call proposes u_cmd unless the caller
        # provided an explicit override (e.g. sandbox sliders). This is the PCC principle
        # applied to the producer itself: the AI proposes, the deterministic pipeline proves.
        t0 = time.perf_counter()
        preset = MANEUVER_PRESETS.get(maneuver_type, {"u_cmd": [0.0, 0.0, 0.0]})
        if u_cmd is not None:
            planner_reasoning = f"Using explicit torque override for {maneuver_type} (sandbox)."
            source = "explicit_override"
        else:
            try:
                u_cmd, llm_reasoning = propose_torque_llm(maneuver_type, list(x0), mission_profile)
                planner_reasoning = f"Claude proposed u_cmd={u_cmd}: {llm_reasoning}"
                source = "llm"
            except Exception as err:
                u_cmd = preset["u_cmd"]
                planner_reasoning = (
                    f"LLM proposal unavailable ({err}); fell back to the deterministic "
                    f"{maneuver_type} preset u_cmd={u_cmd}."
                )
                source = "deterministic_fallback"

        self._make_step(
            steps, 1, "Mission Planner Agent",
            inputs={"maneuver_type": maneuver_type, "x0": list(x0),
                    "mission_profile": mission_profile["profile_key"]},
            outputs={"command_id": command_id, "maneuver_type": maneuver_type, "u_cmd": list(u_cmd), "source": source},
            latency_ms=(time.perf_counter() - t0) * 1000, confidence=1.0,
            reasoning_summary=planner_reasoning, status="COMPLETED",
        )

        # 2. Dynamics Agent
        t0 = time.perf_counter()
        A, B = self.dynamics.discrete_step_matrices(dt)
        x_post = A @ np.array(x0, dtype=np.float64) + B @ np.array(u_cmd, dtype=np.float64)
        self._make_step(
            steps, 2, "Dynamics Agent",
            inputs={"x0": list(x0), "u_cmd": list(u_cmd), "dt": dt},
            outputs={"x_post": [float(v) for v in x_post]},
            latency_ms=(time.perf_counter() - t0) * 1000, confidence=1.0,
            reasoning_summary=f"Propagated post-maneuver rate to |omega|={np.linalg.norm(x_post):.5f} rad/s.",
            status="COMPLETED",
        )

        # 3. Safety Agent
        t0 = time.perf_counter()
        rule = RULE_REGISTRY["angular_rate"]
        rule_result = rule.evaluate({"omega": list(x_post)}, mission_profile)
        margin = -rule_result.binding_value
        confidence = max(0.0, min(1.0, margin / max_omega)) if max_omega else 0.0
        self._make_step(
            steps, 3, "Safety Agent",
            inputs={"x_post": [float(v) for v in x_post], "max_omega_rad_s": max_omega},
            outputs={"satisfied": rule_result.satisfied, "binding_index": rule_result.binding_index,
                     "binding_value": rule_result.binding_value},
            latency_ms=(time.perf_counter() - t0) * 1000, confidence=confidence,
            reasoning_summary=rule_result.detail,
            status="COMPLETED" if rule_result.satisfied else "REFUSED",
        )
        if not rule_result.satisfied:
            return self._result(run_id, steps, refused=True, refusal_reason=rule_result.detail)

        # 4. Proof Generator Agent
        t0 = time.perf_counter()
        seq_no = self.sequence_allocator()
        try:
            proof, cmd_bytes, _ = self.cert_gen.generate_proof(command_id, x0, u_cmd, max_omega, seq_no, dt=dt)
        except ValueError as err:
            self._make_step(
                steps, 4, "Proof Generator Agent",
                inputs={"x0": list(x0), "u_cmd": list(u_cmd), "max_omega_rad_s": max_omega, "sequence_no": seq_no},
                outputs={}, latency_ms=(time.perf_counter() - t0) * 1000, confidence=0.0,
                reasoning_summary=str(err), status="REFUSED",
            )
            return self._result(run_id, steps, refused=True, refusal_reason=str(err))

        self._make_step(
            steps, 4, "Proof Generator Agent",
            inputs={"x0": list(x0), "u_cmd": list(u_cmd), "max_omega_rad_s": max_omega, "sequence_no": seq_no},
            outputs={"multipliers": proof["certificate"]["multipliers"],
                     "constraints": proof["certificate"]["constraints"],
                     "contradiction": proof["certificate"]["contradiction"]},
            latency_ms=(time.perf_counter() - t0) * 1000, confidence=confidence,
            reasoning_summary="Z3 confirmed UNSAT for the negated safety property; Farkas multipliers derived from the binding box constraint.",
            status="COMPLETED",
        )

        # 5. Reviewer Agent — independent recheck before signing
        t0 = time.perf_counter()
        m = proof["certificate"]["multipliers"]
        c = proof["certificate"]["constraints"]
        recomputed = sum(mi * ci for mi, ci in zip(m, c))
        all_nonneg = all(mi >= 0 for mi in m)
        reviewer_pass = all_nonneg and recomputed < 0.0
        self._make_step(
            steps, 5, "Reviewer Agent",
            inputs={"multipliers": m, "constraints": c},
            outputs={"recomputed_sum": recomputed, "all_multipliers_nonneg": all_nonneg},
            latency_ms=(time.perf_counter() - t0) * 1000, confidence=1.0 if reviewer_pass else 0.0,
            reasoning_summary=(
                f"Independent recheck: sum(lambda*constraint)={recomputed:.6f} — "
                f"{'confirmed' if reviewer_pass else 'REJECTED'} before signing."
            ),
            status="COMPLETED" if reviewer_pass else "REFUSED",
        )
        if not reviewer_pass:
            return self._result(run_id, steps, refused=True, refusal_reason="Reviewer Agent rejected the certificate before signing")

        return self._result(run_id, steps, proof=proof, cmd_bytes=cmd_bytes)

    @staticmethod
    def _result(run_id, steps, proof=None, cmd_bytes=None, refused=False, refusal_reason=None) -> dict:
        return {
            "run_id": run_id,
            "steps": [s.to_dict() for s in steps],
            "proof": proof,
            "cmd_bytes": cmd_bytes,
            "refused": refused,
            "refusal_reason": refusal_reason,
        }
