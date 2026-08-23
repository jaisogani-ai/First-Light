"""Per-agent-step data backing the AI Agent Observatory and Multi-Agent Timeline."""

import json

from fastapi import APIRouter
from sqlalchemy import select

from backend.db import engine
from backend.models import pipeline_steps
from backend.pipeline_graph import build_pipeline_graph

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/steps")
def steps_for_run(run_id: str):
    with engine.connect() as conn:
        rows = conn.execute(
            select(pipeline_steps).where(pipeline_steps.c.run_id == run_id).order_by(pipeline_steps.c.step_order)
        ).fetchall()
    steps = []
    for r in rows:
        d = dict(r._mapping)
        d["dependencies"] = json.loads(d.pop("dependencies_json") or "[]")
        steps.append(d)
    return steps


@router.get("/graph")
def graph_for_run(run_id: str):
    with engine.connect() as conn:
        rows = conn.execute(
            select(pipeline_steps).where(pipeline_steps.c.run_id == run_id).order_by(pipeline_steps.c.step_order)
        ).fetchall()
    steps = []
    for r in rows:
        d = dict(r._mapping)
        d["inputs"] = json.loads(d.pop("inputs_json"))
        d["outputs"] = json.loads(d.pop("outputs_json"))
        steps.append(d)
    return build_pipeline_graph(steps)


@router.get("/recent")
def recent_runs(limit: int = 20):
    with engine.connect() as conn:
        rows = conn.execute(
            select(pipeline_steps.c.run_id, pipeline_steps.c.created_at)
            .order_by(pipeline_steps.c.id.desc()).limit(limit)
        ).fetchall()
    seen, run_ids = set(), []
    for r in rows:
        if r.run_id not in seen:
            seen.add(r.run_id)
            run_ids.append(r.run_id)
    return run_ids
