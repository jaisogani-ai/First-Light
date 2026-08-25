"""Persists a document's extracted structure (backend/documents/structure.py's output)
into document_sections — one real row per title/abstract/heading/table/reference, each
tagged with its actual page number when known. This is the corpus search and grounding
query; nothing here is synthesized beyond what extraction actually found."""

import json

from backend.models import document_sections


def persist_sections(conn, document_id: int, mission_id: int, structure: dict) -> int:
    order = 0
    rows = []

    if structure.get("title"):
        rows.append(("TITLE", None, structure["title"]))
        order += 1
    if structure.get("abstract"):
        rows.append(("ABSTRACT", None, structure["abstract"]))
        order += 1
    for h in structure.get("headings", []):
        rows.append(("HEADING", h.get("page_number"), h["text"]))
    for t in structure.get("tables", []):
        rows.append(("TABLE", t.get("page_number"), json.dumps(t["rows"])))
    for r in structure.get("references", []):
        rows.append(("REFERENCE", None, r))

    for i, (section_type, page_number, content_text) in enumerate(rows):
        conn.execute(document_sections.insert().values(
            document_id=document_id, mission_id=mission_id, section_type=section_type,
            page_number=page_number, content_text=content_text, order_index=i,
        ))
    return len(rows)
