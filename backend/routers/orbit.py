"""Mission Planning orbit support — real SGP4 propagation, supplies mission CONTEXT to
the operator/Planner Agent only. Does not touch the locked Farkas/Z3 safety verification
in any way; see producer/orbit.py for the honesty notes on the spherical-Earth
approximation used for ground-track/visibility geometry."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from producer.orbit import ground_track, orbital_period_minutes, propagate, visibility_windows

router = APIRouter(prefix="/api/orbit", tags=["orbit"])


class TLERequest(BaseModel):
    line1: str
    line2: str


class PropagateRequest(TLERequest):
    minutes_from_epoch: float = 0.0


class GroundTrackRequest(TLERequest):
    duration_minutes: float | None = None
    step_minutes: float = 2.0


class VisibilityRequest(TLERequest):
    station_lat_deg: float
    station_lon_deg: float
    station_alt_km: float = 0.0
    duration_minutes: float = 1440.0
    step_minutes: float = 1.0
    min_elevation_deg: float = 10.0


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as err:
        raise HTTPException(400, str(err))


@router.post("/propagate")
def propagate_endpoint(req: PropagateRequest):
    s = _safe_call(propagate, req.line1, req.line2, req.minutes_from_epoch)
    return {"minutes_from_epoch": s.minutes_from_epoch, "position_km": s.position_km,
            "velocity_km_s": s.velocity_km_s, "altitude_km": s.altitude_km,
            "lat_deg": s.lat_deg, "lon_deg": s.lon_deg}


@router.post("/period")
def period_endpoint(req: TLERequest):
    minutes = _safe_call(orbital_period_minutes, req.line1, req.line2)
    return {"orbital_period_minutes": minutes}


@router.post("/ground-track")
def ground_track_endpoint(req: GroundTrackRequest):
    duration = req.duration_minutes or _safe_call(orbital_period_minutes, req.line1, req.line2)
    return {"points": _safe_call(ground_track, req.line1, req.line2, duration, req.step_minutes)}


@router.post("/visibility")
def visibility_endpoint(req: VisibilityRequest):
    windows = _safe_call(
        visibility_windows, req.line1, req.line2, req.station_lat_deg, req.station_lon_deg,
        req.station_alt_km, req.duration_minutes, req.step_minutes, req.min_elevation_deg,
    )
    return {"windows": windows}
