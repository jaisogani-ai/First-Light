"""The hash-chain audit log must actually catch tampering — proposing/verifying several
commands builds a real chain, and directly corrupting one row's command_hash in the
database (bypassing the API entirely) must be detected by recomputation, not just
trusted from the stored chain_hash."""

from sqlalchemy import text

from backend.db import engine


def _propose_and_verify(client, n=1):
    for _ in range(n):
        proposal = client.post("/api/commands/propose", json={
            "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        }).json()
        assert not proposal["refused"]
        client.post("/api/commands/verify", json={
            "command_row_id": proposal["command_row_id"],
            "proof": proposal["proof"],
            "submitted_command_id": proposal["command_id"],
            "submitted_u_cmd": proposal["u_cmd"],
            "mission_profile_key": "earth_observation",
        })


def test_chain_valid_after_real_commands(client):
    _propose_and_verify(client, n=3)
    result = client.get("/api/audit/verify").json()
    assert result["valid"] is True
    assert result["total_links"] >= 3
    assert result["broken_at_index"] is None


def test_chain_detects_direct_db_tampering(client):
    _propose_and_verify(client, n=3)
    baseline = client.get("/api/audit/verify").json()
    assert baseline["valid"] is True

    # Bypass the API entirely and corrupt a command_hash directly in the database —
    # simulates an attacker (or a bug) editing historical records after the fact.
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, command_hash FROM commands ORDER BY id LIMIT 1")).fetchone()
        tampered_hash = "sha256:" + ("0" * 64)
        assert tampered_hash != row.command_hash
        conn.execute(text("UPDATE commands SET command_hash = :h WHERE id = :id"),
                     {"h": tampered_hash, "id": row.id})

    result = client.get("/api/audit/verify").json()
    assert result["valid"] is False
    assert result["broken_at_index"] == 1  # the tampered row was the first link in the chain
