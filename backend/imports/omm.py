"""OMM (Orbit Mean-Elements Message, CCSDS 502.0-B-2) import validation. Uses the real
`sgp4.omm` module (the same first-party library backing producer/orbit.py's TLE
propagation, not a hand-rolled parser) to actually construct an SGP4 satellite record from
the submitted fields — if that construction fails, the OMM is invalid, not "probably fine."

SCOPE: this validates and records provenance for an OMM import. It does NOT yet feed the
Mission Status orbit-context endpoint (backend/routers/mission_status.py), which still
propagates from a mission's imported TLE only — extending propagation to accept OMM-sourced
elements is real, scoped future work, not implemented here to avoid rushing a schema change."""

from datetime import datetime, timezone

from sgp4 import omm
from sgp4.api import Satrec

REQUIRED_FIELDS = [
    "CLASSIFICATION_TYPE", "OBJECT_ID", "EPHEMERIS_TYPE", "ELEMENT_SET_NO", "REV_AT_EPOCH",
    "EPOCH", "ARG_OF_PERICENTER", "BSTAR", "ECCENTRICITY", "INCLINATION", "MEAN_ANOMALY",
    "MEAN_MOTION_DDOT", "MEAN_MOTION_DOT", "MEAN_MOTION", "RA_OF_ASC_NODE", "NORAD_CAT_ID",
]


def validate_omm(data: dict) -> dict:
    errors = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["OMM must be a JSON object"], "epoch": None, "freshness_days": None}

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        errors.append(f"Missing required CCSDS OMM fields: {missing}")
        return {"valid": False, "errors": errors, "epoch": None, "freshness_days": None}

    fields = {k: str(v) for k, v in data.items()}
    try:
        sat = Satrec()
        omm.initialize(sat, fields)
    except (KeyError, ValueError, TypeError) as exc:
        return {"valid": False, "errors": [f"sgp4.omm rejected this OMM: {exc}"], "epoch": None, "freshness_days": None}

    try:
        epoch = datetime.strptime(data["EPOCH"], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        return {"valid": False, "errors": [f"Invalid EPOCH format (expected ISO 8601 with microseconds): {exc}"],
                "epoch": None, "freshness_days": None}

    freshness_days = (datetime.now(timezone.utc) - epoch).total_seconds() / 86400.0
    return {"valid": True, "errors": [], "epoch": epoch.isoformat(), "freshness_days": freshness_days}
