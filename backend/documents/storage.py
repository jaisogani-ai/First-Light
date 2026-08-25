"""Original-file storage for Mission Files. Every upload gets its own path keyed by a
sha256 prefix + the DB row id — never overwritten, even across re-uploads of the same
filename (that's what version_no in mission_documents is for)."""

import hashlib
from pathlib import Path

from backend.config import settings

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024  # 25MB — a real cap; storage.py never buffers more than this


def checksum(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def save(mission_id: int, filename: str, raw: bytes) -> str:
    """Writes raw bytes to a unique path and returns it. Called after the DB row's id is
    known, so the path can include it (avoids any filename-collision logic)."""
    mission_dir = Path(settings.mission_documents_dir) / str(mission_id)
    mission_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()[:16]
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    path = mission_dir / f"{digest}_{safe_name}"
    # Two uploads of byte-identical content would otherwise collide on this path — append
    # a numeric suffix rather than silently reusing (and thus not actually re-storing) it.
    n = 1
    while path.exists():
        path = mission_dir / f"{digest}_{n}_{safe_name}"
        n += 1
    path.write_bytes(raw)
    return str(path)
