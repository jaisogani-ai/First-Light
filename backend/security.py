"""Real cryptographic checks and a light in-memory rate limiter (no Redis, no auth system)."""

import hashlib
import hmac
import json
import time
from collections import defaultdict

from backend.config import settings


def sha256_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def verify_command_hash(cmd_bytes: bytes, claimed_hash: str) -> bool:
    return hmac.compare_digest(sha256_hash(cmd_bytes), claimed_hash)


def _canonicalize(value):
    """Coerce every non-bool int to float so an integral-valued float (e.g. multiplier 1.0)
    hashes identically whether it arrived as a Python float or round-tripped through JSON —
    JSON (and JS's JSON.stringify) does not distinguish 1 from 1.0, so without this the same
    certificate would sign differently before and after a network hop."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


def compute_hmac_signature(payload_without_signature: dict) -> str:
    canonical = _canonicalize(payload_without_signature)
    payload_str = json.dumps(canonical, sort_keys=True)
    sig = hmac.new(settings.hmac_secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac_sha256:{sig}"


def verify_signature(proof: dict) -> bool:
    claimed = proof.get("signature", "")
    payload_without_signature = {k: v for k, v in proof.items() if k != "signature"}
    expected = compute_hmac_signature(payload_without_signature)
    return hmac.compare_digest(expected, claimed)


class RateLimiter:
    """Fixed-window in-memory limiter, per client key. No external dependency."""

    def __init__(self, limit_per_minute: int = 60):
        self.limit = limit_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        hits = [t for t in self._hits[key] if t > window_start]
        hits.append(now)
        self._hits[key] = hits
        return len(hits) <= self.limit


rate_limiter = RateLimiter(settings.rate_limit_per_minute)
