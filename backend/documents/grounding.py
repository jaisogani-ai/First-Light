"""Document grounding — retrieves real evidence (document + page + section + confidence)
for a question BEFORE any AI call happens. This is what makes backend/agents/mission_knowledge.py
trustworthy: it never sees the question without also seeing exactly what real, uploaded
text backs any answer, and it's given no path to add anything else."""

from sqlalchemy import select

from backend.documents.search import search_sections
from backend.models import document_sections, mission_documents

MIN_EVIDENCE_ITEMS = 1  # at least one real match required, or the agent must refuse
MAX_DOCUMENT_GROUNDING_CHARS = 12000  # a real, disclosed cap — never silently truncated without saying so


def retrieve_evidence(conn, mission_id: int, question: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        select(document_sections.c.document_id, mission_documents.c.filename, document_sections.c.section_type,
               document_sections.c.page_number, document_sections.c.content_text, document_sections.c.order_index)
        .join(mission_documents, document_sections.c.document_id == mission_documents.c.id)
        .where(document_sections.c.mission_id == mission_id)
    ).fetchall()
    sections = [dict(r._mapping) for r in rows]
    return search_sections(sections, question, limit)


def has_sufficient_evidence(evidence: list[dict]) -> bool:
    return len(evidence) >= MIN_EVIDENCE_ITEMS


def retrieve_document_evidence(conn, mission_id: int, document_id: int) -> dict | None:
    """Full-document grounding for a single Mission File — used by the Paper Review,
    Algorithm Review, and Scientific Comparison agents, which review/compare one whole
    document rather than answering a query against the whole corpus (Mission Knowledge
    Agent's job). Returns None if the document doesn't exist for this mission, or if it
    has no real extracted text (extraction failed/unsupported/not applicable) — the
    caller must refuse in that case, there is nothing real to ground on."""
    doc_row = conn.execute(
        select(mission_documents).where(mission_documents.c.id == document_id, mission_documents.c.mission_id == mission_id)
    ).fetchone()
    if not doc_row:
        return None
    doc = dict(doc_row._mapping)
    if doc["extraction_status"] != "OK" or not doc["extracted_text"]:
        return {"document_id": document_id, "filename": doc["filename"], "text": None, "truncated": False, "sections": []}

    text = doc["extracted_text"]
    truncated = len(text) > MAX_DOCUMENT_GROUNDING_CHARS
    text = text[:MAX_DOCUMENT_GROUNDING_CHARS]

    section_rows = conn.execute(
        select(document_sections).where(document_sections.c.document_id == document_id).order_by(document_sections.c.order_index)
    ).fetchall()
    sections = [dict(r._mapping) for r in section_rows]

    return {"document_id": document_id, "filename": doc["filename"], "text": text, "truncated": truncated, "sections": sections}
