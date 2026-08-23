"""Seeds mission_profiles with real, distinct safety envelopes. Idempotent (skips existing keys)."""

from sqlalchemy import select

from backend.db import engine, init_db
from backend.models import mission_profiles

PROFILES = [
    dict(
        profile_key="earth_observation",
        display_name="Earth Observation",
        description="LEO pushbroom imaging platform; tight pointing, frequent slews.",
        max_omega_rad_s=0.05,
        power_reserve_w=8.0,
        thermal_max_c=45.0,
        thermal_min_c=-15.0,
    ),
    dict(
        profile_key="deep_space",
        display_name="Deep Space",
        description="Deep-space cruise vehicle; infrequent slow maneuvers, long comm delay.",
        max_omega_rad_s=0.02,
        power_reserve_w=15.0,
        thermal_max_c=60.0,
        thermal_min_c=-40.0,
    ),
    dict(
        profile_key="lunar_orbiter",
        display_name="Lunar Orbiter",
        description="Lunar science orbiter; moderate rate tolerance, thermal cycling near terminator.",
        max_omega_rad_s=0.08,
        power_reserve_w=10.0,
        thermal_max_c=55.0,
        thermal_min_c=-35.0,
    ),
    dict(
        profile_key="science_mission",
        display_name="Science Mission",
        description="High-agility science platform; larger rate envelope for rapid target reacquisition.",
        max_omega_rad_s=0.12,
        power_reserve_w=12.0,
        thermal_max_c=50.0,
        thermal_min_c=-20.0,
    ),
]


def seed() -> None:
    init_db()
    with engine.begin() as conn:
        existing = {row.profile_key for row in conn.execute(select(mission_profiles.c.profile_key))}
        to_insert = [p for p in PROFILES if p["profile_key"] not in existing]
        if to_insert:
            conn.execute(mission_profiles.insert(), to_insert)


if __name__ == "__main__":
    seed()
    print("Seeded mission profiles.")
