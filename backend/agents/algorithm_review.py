"""Algorithm Review Agent — reviews ONE uploaded algorithm description, source file
(Python/MATLAB/notebook), or spec, grounded on its own real extracted text. Complexity is
explicitly instructed to come back "Not stated in the uploaded document." unless the text
itself states or clearly implies it (e.g. an explicit Big-O comment) — never computed or
guessed by Claude from the code's structure."""

from backend.agents._grounded_review import NO_EVIDENCE_REFUSAL, NOT_STATED, call_grounded, grounding_instructions
from backend.documents.grounding import retrieve_document_evidence

FIELDS = ["algorithm_summary", "inputs", "outputs", "complexity", "dependencies", "assumptions",
          "failure_modes", "potential_improvements", "implementation_checklist", "engineering_risks"]

ALGORITHM_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "string"} for f in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def review_algorithm(conn, mission_id: int, document_id: int) -> dict:
    evidence = retrieve_document_evidence(conn, mission_id, document_id)
    if evidence is None:
        return {"reviewed": False, "reason": f"Document {document_id} not found for this mission",
                "review": None, "generated_by": None}
    if evidence["text"] is None:
        return {"reviewed": False, "reason": NO_EVIDENCE_REFUSAL, "review": None, "generated_by": "deterministic_refusal"}

    prompt = (
        "You are the Algorithm Review Agent for a spacecraft research platform. "
        f"{grounding_instructions()}\n\n"
        f"Document: {evidence['filename']}\n"
        f"Evidence text{' (truncated — the full document is longer)' if evidence['truncated'] else ''}:\n"
        f"{evidence['text']}\n\n"
        "Produce a structured algorithm review with these fields: algorithm_summary, inputs, outputs, "
        f"complexity (report \"{NOT_STATED}\" unless the text itself states or clearly documents a "
        "complexity — never compute or estimate one yourself from the code's structure), dependencies, "
        "assumptions, failure_modes, potential_improvements, implementation_checklist, engineering_risks. "
        f"Use \"{NOT_STATED}\" for any other field the document doesn't address."
    )
    try:
        review = call_grounded(prompt, ALGORITHM_REVIEW_SCHEMA)
        return {"reviewed": True, "reason": None, "review": review, "generated_by": "claude",
                "document_id": document_id, "filename": evidence["filename"], "truncated": evidence["truncated"]}
    except Exception as exc:
        return {"reviewed": False, "reason": f"Claude was unavailable: {exc}", "review": None,
                "generated_by": "deterministic_fallback", "document_id": document_id, "filename": evidence["filename"]}
