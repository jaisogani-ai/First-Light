# Security Policy

## Reporting a vulnerability

This is a research prototype, not flight-qualified or production-deployed
software (see [`docs/SAFETY_DISCLAIMER.md`](docs/SAFETY_DISCLAIMER.md)). If
you find a real security issue — something that would let an attacker forge a
proof, bypass replay protection, corrupt the audit chain, or exfiltrate data
it shouldn't have access to — please open a GitHub issue. There is no bug
bounty; this is an unfunded research project.

## What's actually verified here

Full detail lives in [`README.md` §5](README.md#5-security-properties) and
§9 (Security Review, in the Self-Review section) — this file summarizes and
points there rather than duplicating it.

**Real, tested security properties:**
- SHA-256 command hashing + HMAC-SHA256 signing, RFC-vector tested in both
  the Python (`backend/security.py`) and C (`apps/gate/fsw/src/pcc_crypto.c`)
  implementations.
- Replay protection via a single atomic SQL upsert
  (`INSERT ... ON CONFLICT DO UPDATE ... WHERE last_accepted_sequence < ?`,
  `backend/verifier.py`) — a genuine compare-and-swap, not a read-then-write
  race. Concurrency-tested (`eval/test_sequence_race.py`).
- Sequence streams are scoped per **mission**, not per profile — two missions
  sharing a safety envelope cannot cross-pollinate each other's replay
  counters (`backend/stream_id.py`, regression-tested).
- Tamper-evident hash-chain audit log (`backend/audit_chain.py`) — each
  link's `chain_hash` is independently recomputed from the command's actual
  current hash/signature at verify time, not trusted from storage.
- Rate limiting (`backend/security.py`) — thread-safe (a real lock, not just
  a `dict`, since FastAPI's sync routes run in a real threadpool), with
  periodic pruning to bound memory.
- SQLite runs in WAL mode with a 5s `busy_timeout` (`backend/db.py`) —
  concurrent writers wait and retry instead of raising "database is locked."
- Document/CSV uploads are size-capped (25MB documents, 5MB/20,000-row CSV
  telemetry) — found and fixed as a real gap during review, not designed in
  from the start.
- Import content is checksummed (SHA-256) at ingestion.

## Known, disclosed weaknesses (not hidden)

- **No authentication or authorization** anywhere in the API. This is an
  explicit, disclosed scope decision for a single-operator research
  prototype — see `README.md` §9 ("Scope Decisions"). Do not deploy this
  publicly reachable without adding auth first.
- **SQLite, single-process.** Rate limiting and the Digital Twin's active-
  mission tag are in-memory, per-process globals — they do not survive a
  restart or scale across multiple worker processes.
- **The C reference verifier's HMAC key is a compiled-in demo constant**
  (`apps/gate/fsw/src/gate_verify.c`) — explicitly not suitable for flight
  use; the comment in that file says so.
- **A benign TOCTOU** exists in the propose-time sequence-number read
  (`backend/routers/commands.py`): two concurrent proposals for the same
  mission can be assigned the same tentative sequence number. This is
  provably benign — `backend/verifier.py`'s atomic upsert is the actual
  safety boundary and correctly lets only one verify; the effect under load
  is a spurious rejection, never a double-accept.
- **No rate limiting on read-only GET endpoints** — only mutating endpoints
  (`propose`, `verify`, mission/document creation) are rate-limited.

## Out of scope for this repository

Authentication, production deployment hardening, and infrastructure security
(TLS termination, secrets management beyond the local `.pcc_secret_key` file,
network policy) are explicitly out of scope — see [`ROADMAP.md`](ROADMAP.md).
