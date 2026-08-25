"""Engineering Paper Review Agent — reviews ONE uploaded document (a research paper,
engineering spec, or similar) grounded entirely on its own real extracted text. If the
document has no usable extracted text (extraction failed/unsupported/image), this refuses
deterministically without calling Claude — there is nothing real to review."""

from backend.agents._grounded_review import NO_EVIDENCE_REFUSAL, NOT_STATED, call_grounded, grounding_instructions
from backend.documents.grounding import retrieve_document_evidence

FIELDS = ["research_objective", "problem_statement", "methodology", "assumptions",
          "mathematical_models", "algorithms_discussed", "strengths", "limitations",
          "future_work", "datasets", "experimental_setup", "engineering_risks"]

PAPER_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "string"} for f in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def review_paper(conn, mission_id: int, document_id: int) -> dict:
    evidence = retrieve_document_evidence(conn, mission_id, document_id)
    if evidence is None:
        return {"reviewed": False, "reason": f"Document {document_id} not found for this mission",
                "review": None, "generated_by": None}
    if evidence["text"] is None:
        return {"reviewed": False, "reason": NO_EVIDENCE_REFUSAL, "review": None, "generated_by": "deterministic_refusal"}

    prompt = (
        "You are the Engineering Paper Review Agent for a spacecraft research platform. "
        f"{grounding_instructions()}\n\n"
        f"Document: {evidence['filename']}\n"
        f"Evidence text{' (truncated — the full document is longer)' if evidence['truncated'] else ''}:\n"
        f"{evidence['text']}\n\n"
        "Produce a structured engineering review with these fields: research_objective, "
        "problem_statement, methodology, assumptions, mathematical_models (named/described, not "
        "reproduced as equations — see equation policy), algorithms_discussed, strengths, "
        f"limitations, future_work, datasets, experimental_setup, engineering_risks. Use \"{NOT_STATED}\" "
        "for any field the document doesn't address."
    )
    try:
        review = call_grounded(prompt, PAPER_REVIEW_SCHEMA)
        return {"reviewed": True, "reason": None, "review": review, "generated_by": "claude",
                "document_id": document_id, "filename": evidence["filename"], "truncated": evidence["truncated"]}
    except Exception as exc:
        return {"reviewed": False, "reason": f"Claude was unavailable: {exc}", "review": None,
                "generated_by": "deterministic_fallback", "document_id": document_id, "filename": evidence["filename"]}
