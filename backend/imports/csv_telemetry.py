"""CSV telemetry import validation. Required numeric columns mirror backend/models.py's
telemetry table (minus id/mission_id/spacecraft_id, which are assigned at persist time).
All-or-nothing: any row error rejects the whole file — a science/ops CSV either represents
a real, complete pass or it doesn't get persisted as if it did."""

import csv
import io

# Every telemetry column is NOT NULL in db/schema.sql except ts (which has a server-side
# default) — so every one of these must have a real value in the file. Silently defaulting
# a missing column to 0 or None would be inventing telemetry, which we don't do.
REQUIRED_COLUMNS = ["omega_x", "omega_y", "omega_z", "reaction_wheel_momentum", "battery_soc_pct",
                    "temperature_c", "power_draw_w", "comm_delay_ms", "sensor_latency_ms"]
OPTIONAL_COLUMNS = ["ts"]
NUMERIC_COLUMNS = REQUIRED_COLUMNS


def validate_csv_telemetry(text: str) -> dict:
    """Returns {'valid': bool, 'errors': [...], 'rows': [dict, ...], 'row_count': int}.
    'rows' is only populated (and only trustworthy) when 'valid' is True."""
    errors = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {"valid": False, "errors": ["File is empty or has no header row"], "rows": [], "row_count": 0}

    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return {"valid": False, "errors": errors, "rows": [], "row_count": 0}

    unknown = [c for c in reader.fieldnames if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if unknown:
        errors.append(f"Unknown columns (not part of the telemetry schema): {unknown}")

    rows = []
    row_count = 0
    for line_no, raw_row in enumerate(reader, start=2):  # header is line 1
        row_count += 1
        parsed = {}
        for col in NUMERIC_COLUMNS:
            raw_val = raw_row.get(col)
            if raw_val is None or raw_val == "":
                parsed[col] = None
                continue
            try:
                parsed[col] = float(raw_val)
            except ValueError:
                errors.append(f"Row {line_no}: column '{col}' value '{raw_val}' is not numeric")
        for col in REQUIRED_COLUMNS:
            if parsed.get(col) is None:
                errors.append(f"Row {line_no}: required column '{col}' is missing a value")
        parsed["ts"] = raw_row.get("ts") or None
        rows.append(parsed)

    if row_count == 0:
        errors.append("File has a header but no data rows")

    return {"valid": not errors, "errors": errors, "rows": rows if not errors else [], "row_count": row_count}
