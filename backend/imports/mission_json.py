"""Mission JSON manifest import validation — an alternate, file-based way to set the same
mission metadata POST /api/missions accepts inline (mission_name, objective, TLE pair)."""

OPTIONAL_STRING_FIELDS = ["mission_name", "objective", "tle_line1", "tle_line2"]


def validate_mission_json(data: dict) -> dict:
    errors = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Mission manifest must be a JSON object"]}

    if not any(f in data for f in OPTIONAL_STRING_FIELDS):
        errors.append(f"Manifest must set at least one of: {OPTIONAL_STRING_FIELDS}")

    for field in OPTIONAL_STRING_FIELDS:
        if field in data and data[field] is not None and not isinstance(data[field], str):
            errors.append(f"'{field}' must be a string")

    unknown = [k for k in data.keys() if k not in OPTIONAL_STRING_FIELDS]
    if unknown:
        errors.append(f"Unknown fields (not part of the mission manifest schema): {unknown}")

    return {"valid": not errors, "errors": errors}
