"""Mission Status — orbit context, mission health, verification state, and telemetry
freshness, each DERIVED from real data (a mission's TLE + real SGP4 propagation, the most
recent real telemetry row, the most recent real command verdict). Nothing here is
invented: fields are explicitly labeled UNKNOWN/insufficient data when there's nothing
real to derive from, rather than fabricating a plausible-looking value.

mission_health is a simple, honestly-documented heuristic (thresholds against the
mission's real mission_profiles envelope) — not a certified flight-health model. It never
feeds back into the verifier; it's operator-facing context only, same boundary as
producer/orbit.py's mission-context-only role."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select

from backend.db import engine
from backend.models import commands, missions, mission_profiles, telemetry
from producer.orbit import orbital_period_minutes, propagate

router = APIRouter(prefix="/api/missions/{mission_id}", tags=["mission-status"])

BATTERY_CAUTION_PCT = 20.0
BATTERY_CRITICAL_PCT = 10.0
OMEGA_CAUTION_FRACTION = 0.8


def _require_mission_row(conn, mission_id: int):
    row = conn.execute(
        select(missions, mission_profiles).join(mission_profiles, missions.c.mission_profile_id == mission_profiles.c.id)
        .where(missions.c.id == mission_id)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return dict(row._mapping)


@router.get("/orbit-context")
def orbit_context(mission_id: int):
    """Real SGP4 propagation (producer/orbit.py, unchanged) using the mission's imported
    TLE and the actual current time — not a cached or precomputed position."""
    with engine.connect() as conn:
        mission = _require_mission_row(conn, mission_id)
    if not mission["tle_line1"] or not mission["tle_line2"]:
        raise HTTPException(409, "No TLE imported for this mission — orbit context requires a real TLE")

    epoch_yy = int(mission["tle_line1"][18:20])
    epoch_day = float(mission["tle_line1"][20:32])
    epoch_year = 2000 + epoch_yy if epoch_yy < 57 else 1900 + epoch_yy
    epoch = datetime(epoch_year, 1, 1, tzinfo=timezone.utc) + timedelta(days=epoch_day - 1)
    minutes_from_epoch = (datetime.now(timezone.utc) - epoch).total_seconds() / 60.0

    try:
        state = propagate(mission["tle_line1"], mission["tle_line2"], minutes_from_epoch)
        period = orbital_period_minutes(mission["tle_line1"], mission["tle_line2"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "mission_id": mission_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "minutes_from_tle_epoch": round(minutes_from_epoch, 3),
        "lat_deg": state.lat_deg, "lon_deg": state.lon_deg, "altitude_km": state.altitude_km,
        "orbital_period_minutes": period,
    }


def _seconds_since(iso_ts: str) -> float:
    ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _assess_health(tick: dict, profile: dict) -> dict:
    omega_mag = (tick["omega_x"] ** 2 + tick["omega_y"] ** 2 + tick["omega_z"] ** 2) ** 0.5
    max_omega = profile["max_omega_rad_s"]
    flags = []

    if omega_mag > max_omega:
        flags.append(("CRITICAL", f"angular rate {omega_mag:.4f} rad/s exceeds envelope {max_omega:.4f} rad/s"))
    elif omega_mag > max_omega * OMEGA_CAUTION_FRACTION:
        flags.append(("CAUTION", f"angular rate {omega_mag:.4f} rad/s is within {int((1-OMEGA_CAUTION_FRACTION)*100)}% of envelope {max_omega:.4f} rad/s"))

    if tick["temperature_c"] > profile["thermal_max_c"] or tick["temperature_c"] < profile["thermal_min_c"]:
        flags.append(("CRITICAL", f"temperature {tick['temperature_c']:.1f}°C outside envelope "
                                   f"[{profile['thermal_min_c']:.1f}, {profile['thermal_max_c']:.1f}]°C"))

    if tick["battery_soc_pct"] < BATTERY_CRITICAL_PCT:
        flags.append(("CRITICAL", f"battery {tick['battery_soc_pct']:.1f}% below {BATTERY_CRITICAL_PCT}%"))
    elif tick["battery_soc_pct"] < BATTERY_CAUTION_PCT:
        flags.append(("CAUTION", f"battery {tick['battery_soc_pct']:.1f}% below {BATTERY_CAUTION_PCT}%"))

    if any(sev == "CRITICAL" for sev, _ in flags):
        overall = "CRITICAL"
    elif flags:
        overall = "CAUTION"
    else:
        overall = "NOMINAL"
    return {"overall": overall, "reasons": [msg for _, msg in flags]}


@router.get("/status")
def mission_status(mission_id: int):
    """Composes: mission_health (heuristic against the real mission_profiles envelope),
    verification_state (the real most-recent command verdict), and telemetry_freshness_seconds
    (real wall-clock age of the most recent real telemetry row) — all UNKNOWN/null when
    there's no real data to derive from, never fabricated."""
    with engine.connect() as conn:
        mission = _require_mission_row(conn, mission_id)

        tick_row = conn.execute(
            select(telemetry).where(telemetry.c.mission_id == mission_id).order_by(desc(telemetry.c.id)).limit(1)
        ).fetchone()
        cmd_row = conn.execute(
            select(commands.c.command_id, commands.c.verdict, commands.c.submitted_at)
            .where(commands.c.mission_id == mission_id).order_by(desc(commands.c.id)).limit(1)
        ).fetchone()

    if tick_row is None:
        health = {"overall": "UNKNOWN", "reasons": ["no telemetry recorded for this mission yet"]}
        freshness_seconds = None
    else:
        tick = dict(tick_row._mapping)
        health = _assess_health(tick, mission)
        freshness_seconds = round(_seconds_since(tick["ts"]), 2)

    if cmd_row is None:
        verification_state = {"state": "NO_COMMANDS", "command_id": None, "verdict": None}
    else:
        verification_state = {"state": cmd_row.verdict, "command_id": cmd_row.command_id, "verdict": cmd_row.verdict}

    return {
        "mission_id": mission_id,
        "mission_health": health,
        "verification_state": verification_state,
        "telemetry_freshness_seconds": freshness_seconds,
    }
