"""Shared mechanics for the Paper Review, Algorithm Review, and Scientific Comparison
agents — all three ground on one or two whole Mission Files (backend/documents/grounding.py
retrieve_document_evidence) rather than a query-driven search like the Mission Knowledge
Agent. Not itself an agent; every public agent module in backend/agents/ imports from here
to avoid duplicating the same refuse-if-no-evidence / force-a-schema / never-guess mechanics
three times."""

import json

from anthropic import Anthropic

NOT_STATED = "Not stated in the uploaded document."
NO_EVIDENCE_REFUSAL = "I cannot find this information in the uploaded documents."

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(timeout=10.0)
    return _client


def call_grounded(prompt: str, schema: dict, max_tokens: int = 1536):
    """Real Claude call, forced to the given JSON schema (same output_config pattern as
    producer/llm_planner.py) so every response has the exact structure callers/tests
    expect — never a freeform string this code would have to parse-and-guess."""
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5", max_tokens=max_tokens,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Assistant declined to respond")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def grounding_instructions(sentinel: str = NOT_STATED) -> str:
    return (
        "Use ONLY the evidence text below — a real excerpt from a document the operator uploaded. "
        "Do NOT use any knowledge you have outside this evidence, and do NOT invent, estimate, or "
        f"infer anything the text does not actually say. For any requested field the evidence does "
        f"not address, respond with exactly this string: \"{sentinel}\" — do not paraphrase it, do "
        f"not add detail to it. Never state a complexity, equation, citation, or reference that is "
        f"not literally present in the evidence text."
    )
