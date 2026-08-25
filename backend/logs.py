"""Structured engineering event log. Every call emits one real, machine-parseable log line
via the standard library's logging module (logger name 'first_light.events') — searchable
with any standard log tool (grep, jq if JSON-formatted, a log aggregator). This does not
replace Python's normal exception/traceback logging; it's an additional, deliberately
narrow channel for the operationally meaningful events an operator or reviewer would want
to search for (mission lifecycle, imports, verification outcomes) — not a general-purpose
logger, and not a fabricated 'AI observability' layer. Every field logged comes from a real
call site; nothing here is synthesized."""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("first_light.events")


def log_event(event: str, **fields) -> None:
    """event is a short, stable, dot-namespaced name (e.g. 'mission.created',
    'command.verified'). fields are the real, event-specific values a search would filter
    on (mission_id, command_id, verdict, ...) — always JSON-serializable."""
    record = {"event": event, "ts": datetime.now(timezone.utc).isoformat(), **fields}
    logger.info(json.dumps(record, default=str))
