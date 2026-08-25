"""Test fixtures. Sets a temp SQLite DB before any backend import, so the suite never touches
first_light.db, then exposes a TestClient wired to the real FastAPI app."""

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["FIRST_LIGHT_DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["FIRST_LIGHT_HMAC_SECRET_KEY"] = "test_only_secret_key_do_not_use_in_prod"
# Isolate uploaded Mission Files the same way as the DB — never write into the real
# repo-local data/mission_documents/ directory from the test suite.
os.environ["FIRST_LIGHT_MISSION_DOCUMENTS_DIR"] = tempfile.mkdtemp(prefix="first_light_docs_")
# The full suite issues far more than 60 req/min from one shared session-scoped TestClient
# (same "testclient" host on every request) — that's a test-harness artifact, not something
# the production per-minute limit is meant to gate. Raise it here so eval/ tests real business
# logic, not the rate limiter itself (which has no dedicated test — see README known limitations).
os.environ["FIRST_LIGHT_RATE_LIMIT_PER_MINUTE"] = "100000"

import pytest
from fastapi.testclient import TestClient

from backend.main import app  # triggers backend.config's load_dotenv()

# Force the Mission Planner Agent's deterministic fallback path: tests must stay fast,
# free, offline, and deterministic — not dependent on a real (paid, networked, and
# non-deterministic) LLM call. backend.config's load_dotenv() may have just populated
# this from .env; clear it before any test calls propose_torque_llm.
os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_command(client):
    """Proposes a genuinely safe command through the real pipeline and returns its payload."""
    resp = client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
    })
    assert resp.status_code == 200
    return resp.json()
