"""Test fixtures. Sets a temp SQLite DB before any backend import, so the suite never touches
first_light.db, then exposes a TestClient wired to the real FastAPI app."""

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["FIRST_LIGHT_DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["FIRST_LIGHT_HMAC_SECRET_KEY"] = "test_only_secret_key_do_not_use_in_prod"

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
