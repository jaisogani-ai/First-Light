"""Mission Planner Agent's real LLM call — Claude proposes the RCS torque command.

This is the actual PCC principle applied to the producer itself: the AI proposes,
deterministic code proves. Claude's proposal here has no special authority — it flows
into the same Dynamics/Safety/Proof Generator/Reviewer chain as any other command, and
an unsafe proposal is refused by the real Z3/Farkas check exactly like a hardcoded
UNSAFE_RCS_PULSE preset would be.

Uses the Anthropic SDK's default credential resolution (ANTHROPIC_API_KEY or an `ant
auth login` profile) — no key is read or stored by this project directly.
"""

import json

from anthropic import Anthropic

_client: Anthropic | None = None

TORQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "u_cmd": {"type": "array", "items": {"type": "number"}},
        "reasoning": {"type": "string"},
    },
    "required": ["u_cmd", "reasoning"],
    "additionalProperties": False,
}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def propose_torque_llm(maneuver_type: str, x0: list, mission_profile: dict) -> tuple[list, str]:
    """Real Claude API call. Raises on any failure (missing credentials, network,
    malformed response) so the caller can fall back to the deterministic preset with an
    honest status — never silently substitutes a fabricated proposal."""
    client = _get_client()
    prompt = (
        f"You are the Mission Planner Agent for a spacecraft RCS pulse maneuver.\n"
        f"Mission profile: {mission_profile['display_name']} "
        f"(max angular rate {mission_profile['max_omega_rad_s']} rad/s).\n"
        f"Current angular velocity (rad/s), one value per axis: {x0}.\n"
        f"Maneuver intent: {maneuver_type}.\n\n"
        f"Propose a 3-axis RCS thruster torque command u_cmd = [ux, uy, uz] in Newton-meters "
        f"to accomplish this intent. Typical RCS pulses are roughly 0.0001-0.2 Nm per axis. "
        f"This proposal will be independently checked by a Z3 solver and a deterministic "
        f"safety verifier before any command executes — you do not need to prove safety "
        f"yourself, just propose a physically reasonable torque for the stated intent."
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": TORQUE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("LLM declined the proposal request")

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    u_cmd = [float(v) for v in data["u_cmd"]]
    if len(u_cmd) != 3:
        raise ValueError(f"LLM proposed {len(u_cmd)} torque components, expected 3")
    return u_cmd, data["reasoning"]
