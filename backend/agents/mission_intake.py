"""Mission Intake Agent — deterministic, rule-based (no LLM call; nothing here needs one).
Reads a mission's real uploaded documents and real structured imports, and reports real
problems: duplicate uploads (by sha256 checksum), corrupt/unsupported files (by real
extraction status), and missing fields (by checking what's actually absent from the
mission/spacecraft/telemetry tables). Every finding traces to a real row; nothing is
inferred or guessed."""

from sqlalchemy import select

from backend.models import mission_documents, missions, spacecraft, telemetry


def run_mission_intake(conn, mission_id: int) -> dict:
    doc_rows = conn.execute(
        select(mission_documents).where(mission_documents.c.mission_id == mission_id)
    ).fetchall()
    docs = [dict(r._mapping) for r in doc_rows]

    duplicates = []
    by_checksum: dict[str, list[dict]] = {}
    for d in docs:
        by_checksum.setdefault(d["checksum"], []).append(d)
    for checksum, group in by_checksum.items():
        if len(group) > 1:
            duplicates.append({
                "checksum": checksum,
                "document_ids": [d["id"] for d in group],
                "filenames": [d["filename"] for d in group],
            })

    corrupt = [{"document_id": d["id"], "filename": d["filename"]} for d in docs if d["extraction_status"] == "CORRUPT"]
    unsupported = [{"document_id": d["id"], "filename": d["filename"]} for d in docs if d["extraction_status"] == "UNSUPPORTED"]

    mission_row = conn.execute(select(missions).where(missions.c.id == mission_id)).fetchone()
    mission = dict(mission_row._mapping) if mission_row else {}

    missing_fields = []
    if not mission.get("tle_line1") or not mission.get("tle_line2"):
        missing_fields.append("No TLE imported for this mission — orbit context is unavailable")
    has_spacecraft = conn.execute(select(spacecraft.c.id).where(spacecraft.c.mission_id == mission_id).limit(1)).fetchone()
    if not has_spacecraft:
        missing_fields.append("No spacecraft profile imported for this mission")
    has_telemetry = conn.execute(select(telemetry.c.id).where(telemetry.c.mission_id == mission_id).limit(1)).fetchone()
    if not has_telemetry:
        missing_fields.append("No telemetry recorded for this mission yet")

    return {
        "document_count": len(docs),
        "duplicate_uploads": duplicates,
        "corrupt_files": corrupt,
        "unsupported_files": unsupported,
        "missing_fields": missing_fields,
        "clean": not duplicates and not corrupt and not unsupported and not missing_fields,
    }
