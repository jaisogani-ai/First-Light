"""Test fixtures. Sets a temp SQLite DB before any backend import, so the suite never touches
first_light.db, then exposes a TestClient wired to the real FastAPI app."""

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["FIRST_LIGHT_DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["FIRST_LIGHT_HMAC_SECRET_KEY"] = "test_only_secret_key_do_not_use_in_prod"

import pytest
from fastapi.testclient import TestClient

from backend.main import app


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
