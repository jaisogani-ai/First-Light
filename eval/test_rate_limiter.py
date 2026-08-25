"""Unit tests for backend.security.RateLimiter — isolated from the shared app-level limiter
(which the rest of eval/ deliberately runs with a huge limit; see conftest.py) so these can
actually exercise the 429 boundary and the prune() memory-bound behavior."""

from backend.security import RateLimiter


def test_allows_requests_under_the_limit():
    limiter = RateLimiter(limit_per_minute=3)
    assert limiter.allow("client-a")
    assert limiter.allow("client-a")
    assert limiter.allow("client-a")


def test_rejects_requests_over_the_limit():
    limiter = RateLimiter(limit_per_minute=3)
    for _ in range(3):
        assert limiter.allow("client-b")
    assert limiter.allow("client-b") is False


def test_limit_is_scoped_per_key():
    limiter = RateLimiter(limit_per_minute=1)
    assert limiter.allow("client-c")
    assert limiter.allow("client-c") is False
    assert limiter.allow("client-d")  # different key, independent budget


def test_prune_drops_keys_with_no_hits_in_window():
    limiter = RateLimiter(limit_per_minute=5)
    limiter.allow("stale-client")
    limiter._hits["stale-client"] = [0.0]  # force it outside the 60s window
    dropped = limiter.prune()
    assert dropped == 1
    assert "stale-client" not in limiter._hits


def test_mission_creation_is_rate_limited(client, monkeypatch):
    """POST /api/missions was previously unprotected while /commands/propose and
    /commands/verify were both rate-limited — a real inconsistency found in review."""
    import backend.routers.missions as missions_router

    tiny_limiter = RateLimiter(limit_per_minute=1)
    monkeypatch.setattr(missions_router, "rate_limiter", tiny_limiter)

    ok = client.post("/api/missions", json={"mission_name": "RL Test 1", "mission_profile_key": "earth_observation"})
    assert ok.status_code == 200

    limited = client.post("/api/missions", json={"mission_name": "RL Test 2", "mission_profile_key": "earth_observation"})
    assert limited.status_code == 429
