"""Parses the real cFE ES startup script (apps/cfe_es_startup.scr) and confirms
PCC_GATE_APP is ordered before TARGET_APP — not a hardcoded list duplicated inside the test."""

from pathlib import Path

STARTUP_SCRIPT = Path(__file__).resolve().parent.parent / "apps" / "cfe_es_startup.scr"


def test_gate_app_starts_before_target_app():
    assert STARTUP_SCRIPT.exists(), f"missing {STARTUP_SCRIPT}"
    lines = [
        line for line in STARTUP_SCRIPT.read_text().splitlines()
        if line.strip().startswith("CFE_APP,")
    ]
    assert len(lines) >= 2, "expected at least PCC_GATE_APP and TARGET_APP entries"

    gate_index = next(i for i, line in enumerate(lines) if "PCC_GATE_APP" in line)
    target_index = next(i for i, line in enumerate(lines) if "TARGET_APP" in line)

    assert gate_index < target_index, "PCC_GATE_APP must start BEFORE TARGET_APP to prevent boot race"
