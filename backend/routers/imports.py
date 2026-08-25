"""Mission Import Pipeline. Every import is validated first (errors reported, nothing
persisted on failure), previewable via dry_run (validate without writing), and recorded
in mission_imports with real provenance: what was imported, when, how many records, and
(for TLE) how fresh the data is. Nothing here is silently accepted."""

import hashlib
import json

from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select

from backend.db import engine
from backend.imports.constraint_profile import validate_constraint_profile
from backend.imports.csv_telemetry import validate_csv_telemetry
from backend.imports.mission_json import validate_mission_json
from backend.imports.omm import validate_omm
from backend.imports.spacecraft_profile import validate_spacecraft_profile
from backend.imports.tle import validate_tle
from backend.logs import log_event
from backend.models import missions, mission_imports, spacecraft, telemetry

router = APIRouter(prefix="/api/missions/{mission_id}/imports", tags=["imports"])

MAX_CSV_TELEMETRY_BYTES = 5 * 1024 * 1024  # 5MB — a real cap; a bare UploadFile.read() had none
MAX_CSV_TELEMETRY_ROWS = 20_000

SCHEMA_VERSIONS = {
    "TLE": "1.0", "CSV_TELEMETRY": "1.0", "MISSION_JSON": "1.0",
    "SPACECRAFT_PROFILE": "1.0", "CONSTRAINT_PROFILE": "1.0", "OMM": "CCSDS-502.0-B-2",
}


def _checksum(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_mission(conn, mission_id: int) -> None:
    row = conn.execute(select(missions.c.id).where(missions.c.id == mission_id)).fetchone()
    if not row:
        raise HTTPException(404, f"Mission {mission_id} not found")


def _record_import(conn, mission_id: int, import_type: str, filename: str | None, record_count: int,
                    detail: dict, raw_content: str, source: str = "operator_upload",
                    freshness_days: float | None = None) -> int:
    result = conn.execute(mission_imports.insert().values(
        mission_id=mission_id,
        import_type=import_type,
        filename=filename,
        record_count=record_count,
        detail_json=json.dumps(detail),
        checksum=_checksum(raw_content),
        source=source,
        schema_version=SCHEMA_VERSIONS[import_type],
        freshness_days=freshness_days,
    ))
    return result.inserted_primary_key[0]


@router.get("")
def list_imports(mission_id: int):
    with engine.connect() as conn:
        _require_mission(conn, mission_id)
        rows = conn.execute(
            select(mission_imports).where(mission_imports.c.mission_id == mission_id)
            .order_by(mission_imports.c.id.desc())
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/omm")
def import_omm(mission_id: int, body: dict, dry_run: bool = False):
    """CCSDS OMM (Orbit Mean-Elements Message) — validated via the real sgp4.omm module
    (backend/imports/omm.py). Recorded for provenance; does not yet feed Mission Status's
    orbit-context propagation, which still reads a mission's imported TLE only — see
    backend/imports/omm.py's docstring for the honest scope boundary."""
    validation = validate_omm(body)
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="OMM", errors=validation["errors"])
        return {"dry_run": dry_run, **validation}
    if dry_run:
        return {"dry_run": True, **validation}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        import_id = _record_import(
            conn, mission_id, "OMM", body.get("filename"), 1,
            {"object_id": body.get("OBJECT_ID"), "norad_cat_id": body.get("NORAD_CAT_ID"), "epoch": validation["epoch"]},
            raw_content=json.dumps(body, sort_keys=True), source=body.get("source", "operator_upload"),
            freshness_days=validation["freshness_days"],
        )
    log_event("mission.import.omm", mission_id=mission_id, import_id=import_id, freshness_days=validation["freshness_days"])
    return {"dry_run": False, "import_id": import_id, **validation}


@router.post("/tle")
def import_tle(mission_id: int, body: dict, dry_run: bool = False):
    line1, line2 = body.get("line1", ""), body.get("line2", "")
    validation = validate_tle(line1, line2)
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="TLE", errors=validation["errors"])
        return {"dry_run": dry_run, **validation}
    if dry_run:
        return {"dry_run": True, **validation}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        conn.execute(missions.update().where(missions.c.id == mission_id).values(
            tle_line1=line1, tle_line2=line2,
        ))
        import_id = _record_import(
            conn, mission_id, "TLE", body.get("filename"), 1,
            {"epoch": validation["epoch"]}, raw_content=f"{line1}\n{line2}",
            source=body.get("source", "operator_upload"), freshness_days=validation["freshness_days"],
        )
    log_event("mission.import.tle", mission_id=mission_id, import_id=import_id,
              freshness_days=validation["freshness_days"])
    return {"dry_run": False, "import_id": import_id, **validation}


@router.post("/csv-telemetry")
async def import_csv_telemetry(mission_id: int, file: UploadFile, dry_run: bool = False):
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_CSV_TELEMETRY_BYTES:
        raise HTTPException(413, f"CSV telemetry file exceeds the {MAX_CSV_TELEMETRY_BYTES // (1024*1024)}MB limit")
    raw = raw_bytes.decode("utf-8", errors="replace")
    validation = validate_csv_telemetry(raw)
    if validation["valid"] and validation["row_count"] > MAX_CSV_TELEMETRY_ROWS:
        validation = {"valid": False, "errors": [
            f"{validation['row_count']} rows exceeds the {MAX_CSV_TELEMETRY_ROWS}-row limit per import"
        ], "rows": [], "row_count": validation["row_count"]}
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="CSV_TELEMETRY", errors=validation["errors"])
        return {"dry_run": dry_run, "filename": file.filename,
                "valid": False, "errors": validation["errors"], "row_count": validation["row_count"]}
    if dry_run:
        return {"dry_run": True, "filename": file.filename,
                "valid": True, "errors": [], "row_count": validation["row_count"]}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        for row in validation["rows"]:
            values = {k: v for k, v in row.items() if k != "ts"}
            values["mission_id"] = mission_id
            if row.get("ts"):
                values["ts"] = row["ts"]
            conn.execute(telemetry.insert().values(**values))
        import_id = _record_import(conn, mission_id, "CSV_TELEMETRY", file.filename,
                                    validation["row_count"], {}, raw_content=raw)
    log_event("mission.import.csv_telemetry", mission_id=mission_id, import_id=import_id,
              record_count=validation["row_count"])
    return {"dry_run": False, "import_id": import_id, "filename": file.filename,
            "valid": True, "errors": [], "row_count": validation["row_count"]}


@router.post("/mission-json")
def import_mission_json(mission_id: int, body: dict, dry_run: bool = False):
    validation = validate_mission_json(body)
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="MISSION_JSON", errors=validation["errors"])
        return {"dry_run": dry_run, **validation}
    if dry_run:
        return {"dry_run": True, **validation}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        update_values = {k: v for k, v in body.items() if v is not None}
        if update_values:
            conn.execute(missions.update().where(missions.c.id == mission_id).values(**update_values))
        import_id = _record_import(conn, mission_id, "MISSION_JSON", body.get("filename"),
                                    1, {"fields_updated": list(update_values.keys())},
                                    raw_content=json.dumps(body, sort_keys=True))
    log_event("mission.import.mission_json", mission_id=mission_id, import_id=import_id)
    return {"dry_run": False, "import_id": import_id, **validation}


@router.post("/spacecraft-profile")
def import_spacecraft_profile(mission_id: int, body: dict, dry_run: bool = False):
    validation = validate_spacecraft_profile(body)
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="SPACECRAFT_PROFILE", errors=validation["errors"])
        return {"dry_run": dry_run, **validation}
    if dry_run:
        return {"dry_run": True, **validation}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        conn.execute(spacecraft.insert().values(
            mission_id=mission_id, name=body["name"],
            inertia_ixx=body["inertia_ixx"], inertia_iyy=body["inertia_iyy"], inertia_izz=body["inertia_izz"],
        ))
        import_id = _record_import(conn, mission_id, "SPACECRAFT_PROFILE", body.get("filename"),
                                    1, {"name": body["name"]}, raw_content=json.dumps(body, sort_keys=True))
    log_event("mission.import.spacecraft_profile", mission_id=mission_id, import_id=import_id)
    return {"dry_run": False, "import_id": import_id, **validation}


@router.post("/constraint-profile")
def import_constraint_profile(mission_id: int, body: dict, dry_run: bool = False):
    """Validates and records a proposed constraint profile for reference only — it is never
    written into the live mission_profiles table the verifier enforces. See
    backend/imports/constraint_profile.py for why."""
    validation = validate_constraint_profile(body)
    if not validation["valid"]:
        if not dry_run:
            log_event("mission.import.failed", mission_id=mission_id, import_type="CONSTRAINT_PROFILE", errors=validation["errors"])
        return {"dry_run": dry_run, **validation}
    if dry_run:
        return {"dry_run": True, **validation}

    with engine.begin() as conn:
        _require_mission(conn, mission_id)
        import_id = _record_import(conn, mission_id, "CONSTRAINT_PROFILE", body.get("filename"), 1, {
            "proposed_envelope": {k: body[k] for k in
                                   ["max_omega_rad_s", "power_reserve_w", "thermal_max_c", "thermal_min_c"]},
            "applied_to_verifier": False,
            "note": "Recorded for reference only; the live safety envelope stays the curated mission_profiles row.",
        }, raw_content=json.dumps(body, sort_keys=True))
    log_event("mission.import.constraint_profile", mission_id=mission_id, import_id=import_id)
    return {"dry_run": False, "import_id": import_id, **validation,
            "applied_to_verifier": False}
