"""Mission Files — unstructured/reference document upload, extraction, keyword search,
and the Mission Intake Agent. Distinct from backend/routers/imports.py (structured
operational data with its own real parsers). See backend/documents/*.py and
backend/agents/mission_intake.py for the real implementations behind these endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.agents.base import run_agent
from backend.agents.mission_intake import run_mission_intake
from backend.agents.mission_knowledge import answer_question
from backend.db import engine
from backend.documents.extraction import extract
from backend.documents.persistence import persist_sections
from backend.documents.search import search_documents, search_sections
from backend.documents.storage import MAX_DOCUMENT_BYTES, checksum, save
from backend.logs import log_event
from backend.models import agent_runs, document_sections, missions, mission_documents

router = APIRouter(prefix="/api/missions/{mission_id}", tags=["mission-documents"])

VALID_DOC_TYPES = {
    "ENGINEERING_PDF", "RESEARCH_PAPER", "ALGORITHM_DESCRIPTION", "NOTEBOOK", "MATLAB_SCRIPT",
    "CONFIGURATION_FILE", "FLIGHT_RULES", "SAFETY_DOCUMENT", "IMAGE", "ENGINEERING_NOTES", "OTHER",
}


def _require_mission(conn, mission_id: int) -> None:
    if conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone() is None:
        raise HTTPException(404, f"Mission {mission_id} not found")


@router.post("/documents")
async def upload_document(mission_id: int, file: UploadFile, doc_type: str = "OTHER"):
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(400, f"Unknown doc_type '{doc_type}', must be one of {sorted(VALID_DOC_TYPES)}")

    raw = await file.read()
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_DOCUMENT_BYTES // (1024*1024)}MB limit")

    result = extract(file.filename, raw)
    digest = checksum(raw)

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        prior_versions = conn.execute(
            select(mission_documents.c.version_no).where(
                mission_documents.c.mission_id == mission_id, mission_documents.c.filename == file.filename,
            ).order_by(mission_documents.c.version_no.desc()).limit(1)
        ).fetchone()
        version_no = (prior_versions[0] + 1) if prior_versions else 1

        insert_result = conn.execute(mission_documents.insert().values(
            mission_id=mission_id, doc_type=doc_type, filename=file.filename, version_no=version_no,
            content_type=file.content_type, size_bytes=len(raw), checksum=digest,
            storage_path="",  # filled in below once we have the row id
            extraction_status=result["status"], extracted_text=result["text"],
            extracted_metadata_json=json.dumps(result["metadata"]),
        ))
        doc_id = insert_result.inserted_primary_key[0]
        storage_path = save(mission_id, file.filename, raw)
        conn.execute(mission_documents.update().where(mission_documents.c.id == doc_id).values(storage_path=storage_path))

        section_count = persist_sections(conn, doc_id, mission_id, result["structure"])

        intake = run_agent(conn, mission_id, "mission_intake", lambda: run_mission_intake(conn, mission_id),
                            input_summary=f"triggered by upload of '{file.filename}' (doc_id={doc_id})")

    log_event("mission.document.uploaded", mission_id=mission_id, document_id=doc_id, doc_type=doc_type,
              filename=file.filename, extraction_status=result["status"], version_no=version_no,
              section_count=section_count)

    return {
        "document_id": doc_id, "filename": file.filename, "doc_type": doc_type, "version_no": version_no,
        "size_bytes": len(raw), "checksum": digest, "extraction_status": result["status"],
        "extraction_metadata": result["metadata"], "structure_summary": {
            "title": result["structure"].get("title"), "has_abstract": bool(result["structure"].get("abstract")),
            "heading_count": len(result["structure"].get("headings", [])),
            "table_count": len(result["structure"].get("tables", [])),
            "reference_count": len(result["structure"].get("references", [])),
            "equations_note": result["structure"].get("equations_note"),
        },
        "mission_intake": intake,
    }


@router.get("/documents")
def list_documents(mission_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(mission_documents.c.id, mission_documents.c.doc_type, mission_documents.c.filename,
                   mission_documents.c.version_no, mission_documents.c.content_type, mission_documents.c.size_bytes,
                   mission_documents.c.checksum, mission_documents.c.extraction_status, mission_documents.c.uploaded_at)
            .where(mission_documents.c.mission_id == mission_id).order_by(mission_documents.c.id.desc())
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/documents/search")
def search(mission_id: int, q: str, limit: int = 10):
    """Real keyword (term-frequency) search — see backend/documents/search.py for why
    this is explicitly not called 'semantic search'. Registered before /documents/{document_id}
    so 'search' is never parsed as a document_id path parameter (route-matching order matters)."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(mission_documents.c.id, mission_documents.c.filename, mission_documents.c.doc_type,
                   mission_documents.c.extracted_text)
            .where(mission_documents.c.mission_id == mission_id, mission_documents.c.extraction_status == "OK")
        ).fetchall()
    documents = [dict(r._mapping) for r in rows]
    return {"query": q, "search_type": "keyword", "results": search_documents(documents, q, limit)}


@router.get("/documents/sections/search")
def search_sections_endpoint(mission_id: int, q: str, limit: int = 10, section_type: str | None = None):
    """Section-level search (headings/tables/references/abstract/title), each result
    citing document + page + section + a real confidence score. This is the same query
    backend/documents/grounding.py uses for AI-answer grounding — see that module."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(document_sections.c.document_id, mission_documents.c.filename, document_sections.c.section_type,
                   document_sections.c.page_number, document_sections.c.content_text, document_sections.c.order_index)
            .join(mission_documents, document_sections.c.document_id == mission_documents.c.id)
            .where(document_sections.c.mission_id == mission_id)
        ).fetchall()
    sections = [dict(r._mapping) for r in rows]
    return {"query": q, "search_type": "keyword", "results": search_sections(sections, q, limit, section_type)}


@router.get("/documents/{document_id}/sections")
def get_document_sections(mission_id: int, document_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(document_sections).where(document_sections.c.document_id == document_id,
                                             document_sections.c.mission_id == mission_id)
            .order_by(document_sections.c.order_index)
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/documents/{document_id}")
def get_document(mission_id: int, document_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_documents).where(mission_documents.c.id == document_id, mission_documents.c.mission_id == mission_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Document {document_id} not found for mission {mission_id}")
    d = dict(row._mapping)
    d["extracted_metadata"] = json.loads(d.pop("extracted_metadata_json"))
    return d


@router.get("/documents/{document_id}/download")
def download_document(mission_id: int, document_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_documents.c.filename, mission_documents.c.storage_path, mission_documents.c.content_type)
            .where(mission_documents.c.id == document_id, mission_documents.c.mission_id == mission_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Document {document_id} not found for mission {mission_id}")
    path = row.storage_path
    if not path or not Path(path).exists():
        raise HTTPException(404, f"Storage file for document {document_id} missing on disk")
    return FileResponse(path, filename=row.filename, media_type=row.content_type or "application/octet-stream")


@router.delete("/documents/{document_id}")
def delete_document(mission_id: int, document_id: int):
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_documents.c.filename, mission_documents.c.storage_path)
            .where(mission_documents.c.id == document_id, mission_documents.c.mission_id == mission_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Document {document_id} not found for mission {mission_id}")

        conn.execute(document_sections.delete().where(document_sections.c.document_id == document_id))
        conn.execute(mission_documents.delete().where(mission_documents.c.id == document_id))

        if row.storage_path and Path(row.storage_path).exists():
            try:
                Path(row.storage_path).unlink()
            except Exception:
                pass

        intake = run_agent(conn, mission_id, "mission_intake", lambda: run_mission_intake(conn, mission_id),
                            input_summary=f"triggered by deletion of '{row.filename}' (doc_id={document_id})")

    log_event("mission.document.deleted", mission_id=mission_id, document_id=document_id, filename=row.filename)
    return {"deleted": True, "document_id": document_id, "filename": row.filename, "mission_intake": intake}


@router.post("/knowledge/ask")
def ask_knowledge_agent(mission_id: int, body: dict):
    """Mission Knowledge Agent: retrieves real evidence first, refuses deterministically
    (no Claude call) if none exists, otherwise answers citing only that evidence. See
    backend/agents/mission_knowledge.py."""
    question = body.get("question", "")
    if not question.strip():
        raise HTTPException(400, "'question' is required")

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        result = run_agent(conn, mission_id, "mission_knowledge_agent",
                            lambda: answer_question(conn, mission_id, question),
                            input_summary=question[:200])
    return result


@router.post("/intake/run")
def run_intake(mission_id: int):
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        result = run_agent(conn, mission_id, "mission_intake", lambda: run_mission_intake(conn, mission_id),
                            input_summary="manually triggered")
    return result


@router.get("/agent-runs")
def list_agent_runs(mission_id: int, agent_name: str | None = None, limit: int = 50):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        query = select(agent_runs).where(agent_runs.c.mission_id == mission_id)
        if agent_name:
            query = query.where(agent_runs.c.agent_name == agent_name)
        rows = conn.execute(query.order_by(agent_runs.c.id.desc()).limit(limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["output"] = json.loads(d.pop("output_json"))
        out.append(d)
    return out

