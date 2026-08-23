"""Evaluation report — every number computed from real DB aggregates, exportable as JSON/CSV."""

import csv
import io

import psutil
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from backend.db import engine
from backend.models import commands, security_events

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def _compute_report() -> dict:
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(commands)).scalar() or 0
        verified = conn.execute(select(func.count()).select_from(commands).where(commands.c.verdict == "VERIFIED")).scalar() or 0
        rejected = conn.execute(select(func.count()).select_from(commands).where(commands.c.verdict == "REJECTED")).scalar() or 0
        avg_producer = conn.execute(select(func.avg(commands.c.producer_time_ms))).scalar() or 0.0
        avg_verifier = conn.execute(select(func.avg(commands.c.verifier_time_ms))).scalar() or 0.0
        attacks_total = conn.execute(select(func.count()).select_from(security_events)).scalar() or 0
        attacks_detected = conn.execute(
            select(func.count()).select_from(security_events).where(security_events.c.detected == 1)
        ).scalar() or 0

    proc = psutil.Process()
    return {
        "total_commands": total,
        "acceptance_rate": (verified / total) if total else 0.0,
        "rejection_rate": (rejected / total) if total else 0.0,
        "avg_producer_latency_ms": round(avg_producer, 4),
        "avg_verifier_latency_ms": round(avg_verifier, 4),
        "computational_asymmetry": round(avg_producer / avg_verifier, 1) if avg_verifier else None,
        "attack_detection_rate": (attacks_detected / attacks_total) if attacks_total else None,
        "attacks_simulated": attacks_total,
        "attacks_detected": attacks_detected,
        "process_cpu_percent": proc.cpu_percent(interval=0.05),
        "process_memory_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
    }


@router.get("/report")
def report():
    return _compute_report()


@router.get("/export")
def export(fmt: str = "json"):
    data = _compute_report()
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(data.keys())
        writer.writerow(data.values())
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                  headers={"Content-Disposition": "attachment; filename=evaluation_report.csv"})
    return data
