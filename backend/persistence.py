"""Write helpers shared by the commands/attacks routers — one place that persists a command,
its certificate, its pipeline-step trace, and its verification result."""

import json

from backend.audit_chain import append_to_chain
from backend.models import commands, pipeline_steps, proof_certificates, verification_results


def persist_command(conn, command_id: str, mission_profile_id: int, proof: dict, u_cmd, sequence_no: int,
                     producer_time_ms: float) -> int:
    result = conn.execute(commands.insert().values(
        command_id=command_id,
        mission_profile_id=mission_profile_id,
        command_hash=proof["command_hash"],
        sequence_no=sequence_no,
        u_torque_x=u_cmd[0], u_torque_y=u_cmd[1], u_torque_z=u_cmd[2],
        producer_time_ms=producer_time_ms,
        verdict="PENDING",
    ))
    row_id = result.inserted_primary_key[0]

    cert = proof["certificate"]
    conn.execute(proof_certificates.insert().values(
        command_id=row_id,
        property=proof["property"],
        bound_json=json.dumps(proof["bound"]),
        constraints_json=json.dumps(cert["constraints"]),
        multipliers_json=json.dumps(cert["multipliers"]),
        derived_contradiction=cert["contradiction"],
        model_id=proof["model_id"],
        signature=proof["signature"],
    ))

    append_to_chain(conn, row_id, proof["command_hash"], proof["signature"], sequence_no)
    return row_id


def persist_pipeline_steps(conn, command_row_id: int | None, run_id: str, steps: list[dict]) -> None:
    for step in steps:
        conn.execute(pipeline_steps.insert().values(
            command_id=command_row_id,
            run_id=run_id,
            step_order=step["step_order"],
            agent_name=step["agent_name"],
            inputs_json=json.dumps(step["inputs"]),
            outputs_json=json.dumps(step["outputs"]),
            latency_ms=step["latency_ms"],
            confidence=step["confidence"],
            reasoning_summary=step["reasoning_summary"],
            status=step["status"],
            dependencies_json=json.dumps(step.get("dependencies", [])),
            step_timestamp=step.get("timestamp"),
        ))


def persist_verification(conn, command_row_id: int, result) -> None:
    conn.execute(verification_results.insert().values(
        command_id=command_row_id,
        sequence_ok=int(result.trust.sequence_valid),
        hash_ok=int(result.explain.failing_step != "Command Hash Match"),
        signature_ok=int(result.trust.signature_valid),
        model_ok=int(result.explain.failing_step != "Model Version Match"),
        farkas_ok=int(result.trust.proof_valid),
        overall_trusted=int(result.trust.overall == "TRUSTED"),
        explain_json=json.dumps(result.explain.model_dump()),
    ))
    conn.execute(commands.update().where(commands.c.id == command_row_id).values(
        verdict=result.verdict,
        reject_reason=result.reject_reason,
        verifier_time_ms=result.verifier_time_ms,
    ))
