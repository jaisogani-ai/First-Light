"""Scientific Comparison Agent — compares two uploaded documents (Paper A vs Paper B,
Algorithm A vs Algorithm B), grounded on both documents' real extracted text at once.
Mission A vs Mission B and Constraint Profile A vs B comparison already exist as real,
tested, deterministic endpoints (GET /api/missions/compare, backend/routers/mission_analytics.py)
— this agent does not duplicate that; it covers the document-grounded case those endpoints
cannot (they compare structured DB aggregates, not document content)."""

from backend.agents._grounded_review import NO_EVIDENCE_REFUSAL, NOT_STATED, call_grounded, grounding_instructions
from backend.documents.grounding import retrieve_document_evidence

FIELDS = ["similarities", "differences", "assumptions_comparison", "conflicts", "future_work_comparison"]

COMPARISON_SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "string"} for f in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def compare_documents(conn, mission_id: int, document_id_a: int, document_id_b: int) -> dict:
    evidence_a = retrieve_document_evidence(conn, mission_id, document_id_a)
    evidence_b = retrieve_document_evidence(conn, mission_id, document_id_b)

    if evidence_a is None or evidence_b is None:
        missing = document_id_a if evidence_a is None else document_id_b
        return {"compared": False, "reason": f"Document {missing} not found for this mission",
                "comparison": None, "generated_by": None}
    if evidence_a["text"] is None or evidence_b["text"] is None:
        return {"compared": False, "reason": NO_EVIDENCE_REFUSAL, "comparison": None, "generated_by": "deterministic_refusal"}

    prompt = (
        "You are the Scientific Comparison Agent for a spacecraft research platform. "
        f"{grounding_instructions()} Everything below labeled 'Document A' or 'Document B' is real "
        "evidence from two documents the operator uploaded — cite which one (A or B) each claim comes from.\n\n"
        f"Document A: {evidence_a['filename']}\n"
        f"Evidence A{' (truncated)' if evidence_a['truncated'] else ''}:\n{evidence_a['text']}\n\n"
        f"Document B: {evidence_b['filename']}\n"
        f"Evidence B{' (truncated)' if evidence_b['truncated'] else ''}:\n{evidence_b['text']}\n\n"
        "Produce a structured comparison with these fields: similarities, differences, "
        f"assumptions_comparison, conflicts (places where A and B disagree or contradict — use "
        f"\"{NOT_STATED}\" if none found), future_work_comparison."
    )
    try:
        comparison = call_grounded(prompt, COMPARISON_SCHEMA)
        return {"compared": True, "reason": None, "comparison": comparison, "generated_by": "claude",
                "document_a": {"id": document_id_a, "filename": evidence_a["filename"]},
                "document_b": {"id": document_id_b, "filename": evidence_b["filename"]}}
    except Exception as exc:
        return {"compared": False, "reason": f"Claude was unavailable: {exc}", "comparison": None,
                "generated_by": "deterministic_fallback",
                "document_a": {"id": document_id_a, "filename": evidence_a["filename"]},
                "document_b": {"id": document_id_b, "filename": evidence_b["filename"]}}
