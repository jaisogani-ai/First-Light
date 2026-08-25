"""Constraint Profile import validation. IMPORTANT SAFETY BOUNDARY: this validates and
records a proposed safety envelope for reference only. It never writes into the live
mission_profiles table the Farkas certificate/verifier actually enforce (backend/verifier.py,
producer/certificate.py) — those stay curated, seeded values (db/seed.py), not runtime/
user-supplied input. Letting an import silently redefine the angular-rate bound the verifier
checks against would undermine the entire Proof-Carrying Commands property this repo
demonstrates. If this ever needs to feed real profile creation, that's a deliberate,
separately-reviewed decision, not a side effect of an import parser."""

REQUIRED_FIELDS = ["max_omega_rad_s", "power_reserve_w", "thermal_max_c", "thermal_min_c"]


def validate_constraint_profile(data: dict) -> dict:
    errors = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Constraint profile must be a JSON object"]}

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field '{field}'")

    for field in REQUIRED_FIELDS:
        if field in data and (not isinstance(data[field], (int, float)) or isinstance(data[field], bool)):
            errors.append(f"'{field}' must be a number")

    if not errors:
        if data["max_omega_rad_s"] <= 0:
            errors.append("'max_omega_rad_s' must be positive")
        if data["power_reserve_w"] <= 0:
            errors.append("'power_reserve_w' must be positive")
        if data["thermal_min_c"] >= data["thermal_max_c"]:
            errors.append("'thermal_min_c' must be less than 'thermal_max_c'")

    return {"valid": not errors, "errors": errors}
