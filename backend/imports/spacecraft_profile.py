"""Spacecraft Profile import validation — the physical inertia parameters a mission's
Digital Twin/dynamics model would use. Validated and recorded; NOT auto-wired into the
live dynamics model (producer/dynamics_model.py stays on its own fixed physical constants,
per the locked research scope) — see mission_reports/README for that explicit boundary."""

REQUIRED_FIELDS = ["name", "inertia_ixx", "inertia_iyy", "inertia_izz"]


def validate_spacecraft_profile(data: dict) -> dict:
    errors = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Spacecraft profile must be a JSON object"]}

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field '{field}'")

    if "name" in data and not isinstance(data["name"], str):
        errors.append("'name' must be a string")
    elif "name" in data and not data["name"].strip():
        errors.append("'name' must not be empty")

    for field in ("inertia_ixx", "inertia_iyy", "inertia_izz"):
        if field in data:
            value = data[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"'{field}' must be a number")
            elif value <= 0:
                errors.append(f"'{field}' must be positive (a moment of inertia cannot be zero or negative), got {value}")

    return {"valid": not errors, "errors": errors}
