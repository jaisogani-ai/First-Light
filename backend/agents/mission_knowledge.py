"""Mission Knowledge Agent — the first of the citation-grounded document agents. Retrieval
happens BEFORE any Claude call (backend/documents/grounding.py); if nothing real backs the
question, this returns the exact honest refusal WITHOUT calling Claude at all — a
deterministic short-circuit, not a hoped-for prompt behavior. When evidence exists, Claude
is given ONLY that evidence (never the whole document, never its own training knowledge)
and instructed to cite [filename, page] for every claim it makes. The evidence list is
returned alongside the answer so every citation is independently checkable, not just
trusted."""

from anthropic import Anthropic

from backend.documents.grounding import has_sufficient_evidence, retrieve_evidence

REFUSAL = "I cannot find this information in the uploaded documents."

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(timeout=10.0)
    return _client


def _format_evidence(evidence: list[dict]) -> str:
    parts = []
    for e in evidence:
        page = f", page {e['page_number']}" if e.get("page_number") is not None else ""
        parts.append(f"[{e['filename']}{page}, {e['section_type']}]\n{e['snippet']}")
    return "\n\n".join(parts)


def answer_question(conn, mission_id: int, question: str) -> dict:
    evidence = retrieve_evidence(conn, mission_id, question)

    if not has_sufficient_evidence(evidence):
        return {"answer": REFUSAL, "generated_by": "deterministic_refusal", "evidence": []}

    try:
        client = _get_client()
        prompt = (
            "You are the Mission Knowledge Agent for a spacecraft research platform. Answer the "
            "operator's question using ONLY the evidence below — real excerpts from documents they "
            "uploaded to this mission. Do NOT use any knowledge you have outside this evidence. "
            "For every claim, cite it like [filename, page N]. If the evidence only partially answers "
            "the question, say exactly what it does and doesn't cover. If the evidence doesn't answer "
            "the question at all, say so plainly instead of guessing.\n\n"
            f"Evidence:\n{_format_evidence(evidence)}\n\nQuestion: {question}"
        )
        response = client.messages.create(
            model="claude-haiku-4-5", max_tokens=768,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Assistant declined to respond")
        text = next(b.text for b in response.content if b.type == "text")
        return {"answer": text, "generated_by": "claude", "evidence": evidence}
    except Exception:
        # Real, honest fallback: list the evidence found without a synthesized narrative —
        # never silently substitute a fabricated answer for a failed Claude call.
        return {
            "answer": "Claude was unavailable to synthesize an answer. Relevant evidence was found "
                      "in the uploaded documents (see 'evidence' below) but has not been summarized.",
            "generated_by": "deterministic_fallback", "evidence": evidence,
        }
