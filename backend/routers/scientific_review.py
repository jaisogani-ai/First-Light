"""Scientific Review endpoints — Paper Review, Algorithm Review, Scientific Comparison.
All three ground on real uploaded Mission Files (backend/documents/grounding.py) and run
through the shared agent_runs execution-audit framework (real status, latency, output,
error message, mission association — Phase 6's engineering requirements)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.agents.algorithm_review import review_algorithm
from backend.agents.base import run_agent
from backend.agents.paper_review import review_paper
from backend.agents.scientific_comparison import compare_documents
from backend.db import engine
from backend.models import missions

router = APIRouter(prefix="/api/missions/{mission_id}", tags=["scientific-review"])


def _require_mission(conn, mission_id: int) -> None:
    if conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone() is None:
        raise HTTPException(404, f"Mission {mission_id} not found")


@router.post("/documents/{document_id}/review/paper")
def run_paper_review(mission_id: int, document_id: int):
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        return run_agent(conn, mission_id, "paper_review_agent",
                          lambda: review_paper(conn, mission_id, document_id),
                          input_summary=f"document_id={document_id}")


@router.post("/documents/{document_id}/review/algorithm")
def run_algorithm_review(mission_id: int, document_id: int):
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        return run_agent(conn, mission_id, "algorithm_review_agent",
                          lambda: review_algorithm(conn, mission_id, document_id),
                          input_summary=f"document_id={document_id}")


@router.post("/documents/compare")
def run_document_comparison(mission_id: int, body: dict):
    document_id_a = body.get("document_id_a")
    document_id_b = body.get("document_id_b")
    if document_id_a is None or document_id_b is None:
        raise HTTPException(400, "'document_id_a' and 'document_id_b' are both required")

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        return run_agent(conn, mission_id, "scientific_comparison_agent",
                          lambda: compare_documents(conn, mission_id, document_id_a, document_id_b),
                          input_summary=f"document_id_a={document_id_a}, document_id_b={document_id_b}")
