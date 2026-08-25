"""Mission Assistant — Claude explains real, already-computed mission data to an operator.
It never participates in verification and has no path back into the producer/verifier
pipeline: it is handed a snapshot of real analytics/timeline data (already computed by
backend/routers/mission_analytics.py) and asked only to narrate it in plain language.
If Claude is unavailable (no credentials, network failure, malformed response), the
deterministic fallback below still answers from the same real data — every field it
references actually exists in the snapshot; nothing is invented either way.

Same real-Claude-call pattern as producer/llm_planner.py: default SDK credential
resolution, honest 'generated_by' label on every response, no silent substitution."""

import json

from anthropic import Anthropic

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _deterministic_summary(snapshot: dict) -> str:
    a = snapshot["analytics"]
    lines = [
        f"Mission '{snapshot['mission']['mission_name']}' (status: {snapshot['mission']['status']}).",
        f"{a['total_commands']} command(s) proposed.",
    ]
    if a["total_commands"]:
        lines.append(f"Acceptance rate: {a['acceptance_rate']:.0%}, rejection rate: {a['rejection_rate']:.0%}.")
        lines.append(f"Average producer latency {a['avg_producer_latency_ms']:.2f}ms, "
                      f"average verifier latency {a['avg_verifier_latency_ms']:.4f}ms.")
    if a["attacks_simulated"]:
        lines.append(f"{a['attacks_detected']}/{a['attacks_simulated']} simulated attacks were detected "
                      f"({a['attack_detection_rate']:.0%}).")
    lines.append(f"{a['imports_recorded']} import(s) recorded for this mission.")
    return " ".join(lines)


def explain_mission(snapshot: dict, question: str | None = None) -> tuple[str, str]:
    """snapshot is real data only (mission row + analytics dict, both already computed
    from the DB by the caller). Returns (text, generated_by) — generated_by is always
    'claude' or 'deterministic_fallback', literally, never implied."""
    try:
        client = _get_client()
        prompt = (
            "You are the Mission Assistant for a Proof-Carrying Commands spacecraft flight "
            "software research platform. You explain real, already-verified mission data to "
            "a human operator — you do NOT verify commands, propose maneuvers, or influence "
            "any safety decision; that has already happened deterministically before you see "
            "this data. Use only the JSON snapshot below; do not invent any number not present "
            "in it.\n\n"
            f"Snapshot:\n{json.dumps(snapshot, default=str)}\n\n"
            f"Operator question: {question or 'Give a concise mission status summary.'}"
        )
        response = client.messages.create(
            model="claude-haiku-4-5", max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Assistant declined to respond")
        text = next(b.text for b in response.content if b.type == "text")
        return text, "claude"
    except Exception:
        return _deterministic_summary(snapshot), "deterministic_fallback"
