"""Mission Timeline, Analytics, Compare, Export, Reports — every value computed from real
DB rows scoped to one mission_id. No new metrics invented here: analytics reuses the same
aggregation shape as backend/routers/evaluation.py (the global evaluation report), just
filtered per mission. Reports are generated deterministically from those aggregates —
generated_by is always an honest, literal label, never implying more than was computed."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from backend.audit_chain import verify_chain
from backend.db import engine
from backend.logs import log_event
from backend.models import commands, mission_imports, mission_profiles, mission_reports, missions, security_events
from backend.routers.replay import build_command_history

router = APIRouter(prefix="/api/missions/{mission_id}", tags=["mission-analytics"])


def _require_mission(conn, mission_id: int) -> None:
    if conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone() is None:
        raise HTTPException(404, f"Mission {mission_id} not found")


@router.get("/timeline")
def timeline(mission_id: int, limit: int = 100):
    """Every command proposal/verification and every import for this mission, merged into
    one chronological feed. Nothing here is synthesized — each entry is a real row."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        cmd_rows = conn.execute(
            select(commands).where(commands.c.mission_id == mission_id)
            .order_by(commands.c.id.desc()).limit(limit)
        ).fetchall()
        import_rows = conn.execute(
            select(mission_imports).where(mission_imports.c.mission_id == mission_id)
            .order_by(mission_imports.c.id.desc()).limit(limit)
        ).fetchall()

    events = []
    for row in cmd_rows:
        r = dict(row._mapping)
        events.append({
            "kind": "command", "at": r["submitted_at"], "verdict": r["verdict"],
            "command_id": r["command_id"], "detail": r,
        })
    for row in import_rows:
        r = dict(row._mapping)
        events.append({
            "kind": "import", "at": r["imported_at"], "import_type": r["import_type"],
            "filename": r["filename"], "detail": r,
        })
    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events[:limit]


def _compute_mission_analytics(conn, mission_id: int) -> dict:
    total = conn.execute(select(func.count()).select_from(commands).where(commands.c.mission_id == mission_id)).scalar() or 0
    verified = conn.execute(
        select(func.count()).select_from(commands)
        .where(commands.c.mission_id == mission_id, commands.c.verdict == "VERIFIED")
    ).scalar() or 0
    rejected = conn.execute(
        select(func.count()).select_from(commands)
        .where(commands.c.mission_id == mission_id, commands.c.verdict == "REJECTED")
    ).scalar() or 0
    avg_producer = conn.execute(
        select(func.avg(commands.c.producer_time_ms)).where(commands.c.mission_id == mission_id)
    ).scalar() or 0.0
    avg_verifier = conn.execute(
        select(func.avg(commands.c.verifier_time_ms)).where(commands.c.mission_id == mission_id)
    ).scalar() or 0.0
    attacks_total = conn.execute(
        select(func.count()).select_from(security_events).join(commands, security_events.c.command_id == commands.c.id)
        .where(commands.c.mission_id == mission_id)
    ).scalar() or 0
    attacks_detected = conn.execute(
        select(func.count()).select_from(security_events).join(commands, security_events.c.command_id == commands.c.id)
        .where(commands.c.mission_id == mission_id, security_events.c.detected == 1)
    ).scalar() or 0
    import_count = conn.execute(
        select(func.count()).select_from(mission_imports).where(mission_imports.c.mission_id == mission_id)
    ).scalar() or 0

    return {
        "mission_id": mission_id,
        "total_commands": total,
        "acceptance_rate": (verified / total) if total else None,
        "rejection_rate": (rejected / total) if total else None,
        "avg_producer_latency_ms": round(avg_producer, 4),
        "avg_verifier_latency_ms": round(avg_verifier, 4),
        "attacks_simulated": attacks_total,
        "attacks_detected": attacks_detected,
        "attack_detection_rate": (attacks_detected / attacks_total) if attacks_total else None,
        "imports_recorded": import_count,
    }


@router.get("/analytics")
def analytics(mission_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        return _compute_mission_analytics(conn, mission_id)


@router.get("/export")
def export_mission(mission_id: int):
    """Full real record for this mission: metadata, every command+certificate+verdict,
    every import. Suitable as an evidence package — nothing summarized or omitted."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        mission_row = conn.execute(select(missions).where(missions.c.id == mission_id)).fetchone()
        cmd_rows = conn.execute(
            select(commands).where(commands.c.mission_id == mission_id).order_by(commands.c.id)
        ).fetchall()
        import_rows = conn.execute(
            select(mission_imports).where(mission_imports.c.mission_id == mission_id).order_by(mission_imports.c.id)
        ).fetchall()
    return {
        "mission": dict(mission_row._mapping),
        "commands": [dict(r._mapping) for r in cmd_rows],
        "imports": [dict(r._mapping) for r in import_rows],
    }


@router.post("/reports/generate")
def generate_report(mission_id: int, report_type: str = "analytics_summary"):
    """Deterministically generates a report from real DB aggregates (backend.mission_assistant
    covers the separate, explicitly-labeled Claude-narrated variant). Stored in mission_reports
    with generated_by='deterministic' — never claims AI involvement it didn't have."""
    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        content = _compute_mission_analytics(conn, mission_id)
        result = conn.execute(mission_reports.insert().values(
            mission_id=mission_id, report_type=report_type, generated_by="deterministic",
            content_json=json.dumps(content),
        ))
        report_id = result.inserted_primary_key[0]
    log_event("mission.report.generated", mission_id=mission_id, report_id=report_id, report_type=report_type,
              generated_by="deterministic")
    return {"report_id": report_id, "report_type": report_type, "generated_by": "deterministic", "content": content}


@router.get("/reports", tags=["mission-analytics"])
def list_reports(mission_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(mission_reports).where(mission_reports.c.mission_id == mission_id)
            .order_by(mission_reports.c.id.desc())
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["content"] = json.loads(d.pop("content_json"))
        out.append(d)
    return out


@router.get("/reports/{report_id}/export/json")
def export_report_json(mission_id: int, report_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_reports).where(mission_reports.c.id == report_id, mission_reports.c.mission_id == mission_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Report {report_id} not found")
    d = dict(row._mapping)
    d["content"] = json.loads(d.pop("content_json"))
    return d


@router.get("/reports/{report_id}/export/csv")
def export_report_csv(mission_id: int, report_id: int):
    from fastapi.responses import Response
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_reports).where(mission_reports.c.id == report_id, mission_reports.c.mission_id == mission_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Report {report_id} not found")
    content = json.loads(row.content_json)
    lines = ["Metric,Value"]
    if isinstance(content, dict):
        for k, v in content.items():
            lines.append(f'"{k}","{v}"')
    csv_text = "\n".join(lines)
    return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=mission-{mission_id}-report-{report_id}.csv"})


@router.get("/reports/{report_id}/export/pdf")
def export_report_pdf(mission_id: int, report_id: int):
    """Generates a plain-text/PDF formatted operational report document."""
    from fastapi.responses import Response
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        row = conn.execute(
            select(mission_reports).where(mission_reports.c.id == report_id, mission_reports.c.mission_id == mission_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Report {report_id} not found")
    content = json.loads(row.content_json)
    
    # Clean text report summary formatted as an operational mission artifact
    pdf_text = f"FIRST LIGHT MISSION REPORT\n"
    pdf_text += f"========================\n"
    pdf_text += f"Mission ID: {mission_id}\n"
    pdf_text += f"Report ID: {report_id}\n"
    pdf_text += f"Report Type: {row.report_type}\n"
    pdf_text += f"Generated By: {row.generated_by}\n"
    pdf_text += f"Timestamp: {row.created_at}\n\n"
    pdf_text += f"METRICS & AGGREGATES:\n"
    pdf_text += f"---------------------\n"
    if isinstance(content, dict):
        for k, v in content.items():
            pdf_text += f"{k.replace('_', ' ').title()}: {v}\n"
            
    return Response(content=pdf_text.encode('utf-8'), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=mission-{mission_id}-report-{report_id}.txt"})



@router.get("/evidence-package")
def evidence_package(mission_id: int):
    """A single real 'flight recorder' bundle for this mission — pure composition of
    existing, already-tested logic (build_command_history from replay.py, the same
    analytics/timeline computation used by /analytics and /timeline, verify_chain from
    backend/audit_chain.py). Nothing here is recomputed or reimplemented; this endpoint
    only joins what already exists into one response so a caller doesn't need 5+ requests.

    audit_chain_verification is NOT mission-filtered — the hash chain (backend/audit_chain.py)
    links every command in the whole system, not per mission, so this reports the chain's
    global integrity, honestly labeled as such rather than pretending a mission-scoped chain
    exists."""
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        mission_row = conn.execute(select(missions).where(missions.c.id == mission_id)).fetchone()
        cmd_rows = conn.execute(
            select(commands, mission_profiles.c.display_name.label("mission_profile"))
            .join(mission_profiles, commands.c.mission_profile_id == mission_profiles.c.id)
            .where(commands.c.mission_id == mission_id).order_by(commands.c.id)
        ).fetchall()
        command_history = build_command_history(conn, cmd_rows)

        import_rows = conn.execute(
            select(mission_imports).where(mission_imports.c.mission_id == mission_id).order_by(mission_imports.c.id)
        ).fetchall()
        report_rows = conn.execute(
            select(mission_reports).where(mission_reports.c.mission_id == mission_id)
            .order_by(mission_reports.c.id.desc())
        ).fetchall()

        analytics_data = _compute_mission_analytics(conn, mission_id)
        audit_chain_verification = verify_chain(conn)

    reports = []
    for r in report_rows:
        d = dict(r._mapping)
        d["content"] = json.loads(d.pop("content_json"))
        reports.append(d)

    log_event("mission.evidence_package.generated", mission_id=mission_id, command_count=len(command_history))
    return {
        "mission": dict(mission_row._mapping),
        "analytics": analytics_data,
        "command_history": command_history,
        "imports": [dict(r._mapping) for r in import_rows],
        "reports": reports,
        "audit_chain_verification": audit_chain_verification,
        "audit_chain_scope": "global — not mission-filtered, see docstring",
    }


compare_router = APIRouter(prefix="/api/missions", tags=["mission-analytics"])


@compare_router.get("/compare")
def compare_missions(ids: str):
    """ids is a comma-separated list of mission_id, e.g. ?ids=1,2,3. Returns each mission's
    real analytics side by side — no cross-mission computation invented, just the same
    per-mission aggregate repeated for each id, so a caller can diff them."""
    try:
        mission_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "ids must be a comma-separated list of integers")
    if not mission_ids:
        raise HTTPException(400, "ids must contain at least one mission_id")

    with engine.connect() as conn:
        for mid in mission_ids:
            _require_mission(conn, mid)
        return [_compute_mission_analytics(conn, mid) for mid in mission_ids]
