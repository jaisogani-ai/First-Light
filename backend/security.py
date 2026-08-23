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


def compute_hmac_signature(payload_without_signature: dict) -> str:
    payload_str = json.dumps(payload_without_signature, sort_keys=True)
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
