"""Spacecraft Configuration Engine — deterministic, NOT an LLM. Parses an uploaded
spacecraft configuration (name + inertia + a list of subsystem components), validates
every component against its type's real required parameters, detects inconsistencies
(duplicate names, physically implausible values), reports missing subsystems, and
persists a normalized spacecraft_components row per component. Every finding is a plain
rule evaluated against the submitted numbers — nothing here calls Claude or infers
anything not explicitly present in the input."""

REQUIRED_PARAMETERS = {
    "REACTION_WHEEL": {"max_torque_nm": "positive", "max_momentum_nms": "positive"},
    "THRUSTER": {"thrust_n": "positive", "isp_s": "positive"},
    "BATTERY": {"capacity_wh": "positive", "nominal_voltage_v": "positive"},
    "SOLAR_ARRAY": {"area_m2": "positive", "efficiency_pct": "percent"},
    "PAYLOAD": {"power_draw_w": "non_negative", "mass_kg": "positive"},
    "THERMAL_SYSTEM": {"operating_range_min_c": "number", "operating_range_max_c": "number"},
    "COMM_SYSTEM": {"frequency_band": "string", "data_rate_kbps": "positive"},
    "SENSOR": {"sensor_type": "string", "accuracy": "positive"},
    "ATTITUDE_CONTROL": {"control_type": "string"},
    "FUEL_TANK": {"capacity_kg": "positive", "propellant_type": "string"},
}

# Loose, honestly-heuristic sanity bounds for a typical small satellite — flagged as a
# WARNING (not rejected), because a real mission might legitimately exceed them.
SANITY_BOUNDS = {
    "REACTION_WHEEL": {"max_torque_nm": (0, 5.0)},
    "THRUSTER": {"thrust_n": (0, 500.0)},
    "BATTERY": {"capacity_wh": (0, 20000.0)},
}

RECOMMENDED_TYPES = {
    "BATTERY": "No battery pack defined",
    "THERMAL_SYSTEM": "No thermal system defined",
}


def _check_value(value, kind: str) -> str | None:
    if kind == "string":
        return None if isinstance(value, str) and value.strip() else "must be a non-empty string"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "must be a number"
    if kind == "positive" and value <= 0:
        return "must be positive"
    if kind == "non_negative" and value < 0:
        return "must be non-negative"
    if kind == "percent" and not (0 <= value <= 100):
        return "must be between 0 and 100"
    return None


def validate_configuration(data: dict) -> dict:
    """Returns {'valid': bool, 'errors': [...], 'warnings': [...], 'components': [...]}.
    'components' (normalized, only present when valid) is what gets persisted."""
    errors, warnings = [], []

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Configuration must be a JSON object"], "warnings": [], "components": []}
    for field in ("name", "inertia_ixx", "inertia_iyy", "inertia_izz"):
        if field not in data:
            errors.append(f"Missing required field '{field}'")
    components = data.get("components", [])
    if not isinstance(components, list):
        errors.append("'components' must be a list")
        components = []

    normalized = []
    seen_names = set()
    for i, comp in enumerate(components):
        if not isinstance(comp, dict) or "component_type" not in comp or "name" not in comp:
            errors.append(f"components[{i}] must have 'component_type' and 'name'")
            continue
        ctype, cname = comp["component_type"], comp["name"]
        if ctype not in REQUIRED_PARAMETERS:
            errors.append(f"components[{i}]: unknown component_type '{ctype}' (known: {sorted(REQUIRED_PARAMETERS)})")
            continue
        if cname in seen_names:
            warnings.append(f"Duplicate component name '{cname}' — ensure this is intentional")
        seen_names.add(cname)

        params = comp.get("parameters", {})
        for pname, kind in REQUIRED_PARAMETERS[ctype].items():
            if pname not in params:
                errors.append(f"components[{i}] ('{cname}', {ctype}): missing required parameter '{pname}'")
                continue
            problem = _check_value(params[pname], kind)
            if problem:
                errors.append(f"components[{i}] ('{cname}', {ctype}): parameter '{pname}' {problem}")

        if ctype == "THERMAL_SYSTEM" and "operating_range_min_c" in params and "operating_range_max_c" in params:
            if params["operating_range_min_c"] >= params["operating_range_max_c"]:
                errors.append(f"components[{i}] ('{cname}'): operating_range_min_c must be less than operating_range_max_c")

        for pname, (lo, hi) in SANITY_BOUNDS.get(ctype, {}).items():
            if pname in params and isinstance(params[pname], (int, float)) and not (lo <= params[pname] <= hi):
                warnings.append(f"'{cname}' ({ctype}): {pname}={params[pname]} is outside the typical smallsat "
                                 f"range [{lo}, {hi}] — verify this is intentional")

        if not errors or all(not e.startswith(f"components[{i}]") for e in errors):
            normalized.append({"component_type": ctype, "name": cname, "parameters": params})

    if not errors:
        present_types = {c["component_type"] for c in normalized}
        for ctype, message in RECOMMENDED_TYPES.items():
            if ctype not in present_types:
                warnings.append(message)
        if not present_types & {"ATTITUDE_CONTROL", "REACTION_WHEEL"}:
            warnings.append("No attitude control components defined (no REACTION_WHEEL or ATTITUDE_CONTROL)")

    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "components": normalized if not errors else []}
