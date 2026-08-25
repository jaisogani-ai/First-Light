"""Real TLE (Two-Line Element) validation: NORAD checksum + epoch extraction, per the
standard TLE fixed-column format. No orbit propagation here — producer/orbit.py (SGP4)
already owns that, unchanged; this module only validates and reports provenance/freshness
for the raw two lines an operator is importing."""

from datetime import datetime, timedelta, timezone


def _checksum(line: str) -> int:
    total = 0
    for c in line[:-1]:
        if c.isdigit():
            total += int(c)
        elif c == "-":
            total += 1
    return total % 10


def _parse_epoch(line1: str) -> datetime:
    yy = int(line1[18:20])
    day_of_year = float(line1[20:32])
    year = 2000 + yy if yy < 57 else 1900 + yy
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_of_year - 1)


def validate_tle(line1: str, line2: str) -> dict:
    """Returns {'valid': bool, 'errors': [...], 'epoch': iso str | None, 'freshness_days': float | None}.
    Never raises — callers decide whether to persist based on 'valid'."""
    errors = []
    line1 = line1.rstrip("\n")
    line2 = line2.rstrip("\n")

    if len(line1) != 69:
        errors.append(f"Line 1 must be 69 characters, got {len(line1)}")
    elif not line1.startswith("1 "):
        errors.append("Line 1 must start with '1 '")
    elif not line1[-1].isdigit():
        errors.append("Line 1 checksum digit missing/invalid")
    elif _checksum(line1) != int(line1[-1]):
        errors.append(f"Line 1 checksum mismatch: computed {_checksum(line1)}, found {line1[-1]}")

    if len(line2) != 69:
        errors.append(f"Line 2 must be 69 characters, got {len(line2)}")
    elif not line2.startswith("2 "):
        errors.append("Line 2 must start with '2 '")
    elif not line2[-1].isdigit():
        errors.append("Line 2 checksum digit missing/invalid")
    elif _checksum(line2) != int(line2[-1]):
        errors.append(f"Line 2 checksum mismatch: computed {_checksum(line2)}, found {line2[-1]}")

    if len(line1) == 69 and len(line2) == 69 and line1[2:7] != line2[2:7]:
        errors.append(f"NORAD catalog number mismatch between lines: '{line1[2:7]}' vs '{line2[2:7]}'")

    epoch_iso, freshness_days = None, None
    if not errors:
        try:
            epoch = _parse_epoch(line1)
            epoch_iso = epoch.isoformat()
            freshness_days = (datetime.now(timezone.utc) - epoch).total_seconds() / 86400.0
        except ValueError as exc:
            errors.append(f"Could not parse epoch from line 1: {exc}")

    return {"valid": not errors, "errors": errors, "epoch": epoch_iso, "freshness_days": freshness_days}
