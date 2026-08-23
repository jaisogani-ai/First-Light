"""Mission Planning orbit support — real SGP4 propagation (via the `sgp4` package, the
standard Vallado/NORAD implementation used to process real TLEs), not a hand-rolled
approximation. This supplies mission CONTEXT only (position, ground track, visibility
windows, orbital period) to inform when/how a maneuver might be planned — it does not
feed into, alter, or weaken the locked Farkas/Z3 safety verification in any way. The
research contribution stays command verification; this is context the Mission Planner
Agent can use, nothing more.

Ground-track and visibility geometry use a spherical-Earth approximation (mean radius
6378.137 km), not the full WGS84 ellipsoid — honestly documented here rather than
silently passed off as full geodetic precision. Error from this approximation is at most
~0.3% of Earth's radius (~21 km, the equatorial/polar difference), immaterial for mission
context display but explicitly not survey-grade.
"""

import math
from dataclasses import dataclass

from sgp4.api import SGP4_ERRORS, Satrec

EARTH_RADIUS_KM = 6378.137
EARTH_ROTATION_RAD_PER_MIN = 2 * math.pi / 1436.0682  # sidereal day, minutes


@dataclass(frozen=True)
class OrbitState:
    minutes_from_epoch: float
    position_km: tuple
    velocity_km_s: tuple
    altitude_km: float
    lat_deg: float
    lon_deg: float


def _load(line1: str, line2: str) -> Satrec:
    sat = Satrec.twoline2rv(line1, line2)
    if sat.error != 0:
        raise ValueError(f"Invalid TLE (sgp4 error {sat.error}): {SGP4_ERRORS.get(sat.error, 'unknown error')}")
    return sat


def orbital_period_minutes(line1: str, line2: str) -> float:
    """Real value derived from the TLE's mean motion field (revolutions/day)."""
    sat = _load(line1, line2)
    mean_motion_rev_per_day = sat.no_kozai * 1440.0 / (2 * math.pi)
    return 1440.0 / mean_motion_rev_per_day


def _eci_to_geodetic(position_km: tuple, minutes_from_epoch: float) -> tuple:
    """Spherical-Earth ECI -> lat/lon, rotating for Earth's spin since TLE epoch."""
    x, y, z = position_km
    r = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / r))
    lon_inertial = math.degrees(math.atan2(y, x))
    lon = ((lon_inertial - math.degrees(EARTH_ROTATION_RAD_PER_MIN * minutes_from_epoch)) + 180) % 360 - 180
    return lat, lon, r - EARTH_RADIUS_KM


def propagate(line1: str, line2: str, minutes_from_epoch: float = 0.0) -> OrbitState:
    sat = _load(line1, line2)
    error, position, velocity = sat.sgp4_tsince(minutes_from_epoch)
    if error != 0:
        raise ValueError(f"SGP4 propagation error {error} at t={minutes_from_epoch} min")
    lat, lon, alt = _eci_to_geodetic(position, minutes_from_epoch)
    return OrbitState(minutes_from_epoch, position, velocity, alt, lat, lon)


def ground_track(line1: str, line2: str, duration_minutes: float = 100.0, step_minutes: float = 2.0) -> list:
    points = []
    t = 0.0
    while t <= duration_minutes:
        s = propagate(line1, line2, t)
        points.append({"t_minutes": t, "lat_deg": s.lat_deg, "lon_deg": s.lon_deg, "altitude_km": s.altitude_km})
        t += step_minutes
    return points


def visibility_windows(line1: str, line2: str, station_lat_deg: float, station_lon_deg: float,
                        station_alt_km: float = 0.0, duration_minutes: float = 1440.0,
                        step_minutes: float = 1.0, min_elevation_deg: float = 10.0) -> list:
    """Real topocentric elevation-angle line-of-sight computation (spherical Earth,
    ENU local frame at the ground station) — not a lookup table."""
    lat_r = math.radians(station_lat_deg)
    lon_r = math.radians(station_lon_deg)
    station_r = EARTH_RADIUS_KM + station_alt_km
    station_ecef = (
        station_r * math.cos(lat_r) * math.cos(lon_r),
        station_r * math.cos(lat_r) * math.sin(lon_r),
        station_r * math.sin(lat_r),
    )

    windows = []
    in_pass = False
    pass_start = None
    max_elev = -90.0
    t = 0.0
    while t <= duration_minutes:
        s = propagate(line1, line2, t)
        earth_rot = EARTH_ROTATION_RAD_PER_MIN * t
        cos_r, sin_r = math.cos(earth_rot), math.sin(earth_rot)
        x, y, z = s.position_km
        sat_ecef = (x * cos_r + y * sin_r, -x * sin_r + y * cos_r, z)

        rng = (sat_ecef[0] - station_ecef[0], sat_ecef[1] - station_ecef[1], sat_ecef[2] - station_ecef[2])
        rng_mag = math.sqrt(sum(c * c for c in rng))
        up = (math.cos(lat_r) * math.cos(lon_r), math.cos(lat_r) * math.sin(lon_r), math.sin(lat_r))
        up_component = sum(rng[i] * up[i] for i in range(3))
        elevation_deg = math.degrees(math.asin(max(-1.0, min(1.0, up_component / rng_mag))))

        visible = elevation_deg >= min_elevation_deg
        if visible and not in_pass:
            in_pass, pass_start, max_elev = True, t, elevation_deg
        elif visible and in_pass:
            max_elev = max(max_elev, elevation_deg)
        elif not visible and in_pass:
            windows.append({"aos_minutes": pass_start, "los_minutes": t, "max_elevation_deg": max_elev})
            in_pass = False
        t += step_minutes

    if in_pass:
        windows.append({"aos_minutes": pass_start, "los_minutes": duration_minutes, "max_elevation_deg": max_elev})
    return windows
