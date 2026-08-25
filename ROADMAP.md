# Roadmap

Every item here is real, scoped future work — not a feature this repository
claims to already have. Nothing here is committed to a timeline; this is a
research prototype maintained as time allows. See `README.md`'s per-section
"Limitations" and "Future work" notes for the reasoning behind each item.

## Verification research (the locked core — extended, never redesigned)

- Extend the atomic-upsert replay-protection pattern from sequence freshness
  to `audit_chain` appends.
- Implement the flight rules named-but-missing beyond angular rate — for any
  non-box-constraint rule, first generalize multiplier derivation beyond the
  one-hot construction used today (real LP-dual or Z3 `unsat_core`-based
  extraction).
- Feed real orbit-derived context (next visibility window, ground track)
  into the Mission Planner Agent's LLM prompt — the orbit module and the
  pipeline are wired to the same API today but not to each other.
- Replace the Attack Library's seven synthetic scenarios with (or supplement
  using) real recorded attack traffic — a named real dataset is cited in
  `README.md` §1 as a candidate.
- A real Linux/CYGWIN native cFS build so `apps/gate`/`apps/target` run
  against real cFE/OSAL/PSP over the Software Bus.

## Platform

- **OMM → orbit-context propagation.** OMM (CCSDS) import is validated today
  via the real `sgp4.omm` library and recorded for provenance, but
  `GET /api/missions/{id}/orbit-context` still only propagates from an
  imported TLE. Extending it to accept OMM-sourced elements needs its own
  schema decision, not a quick patch.
- **PDF/CSV evidence export.** The Evidence Package is JSON only today; no
  PDF-generation library is a dependency yet.
- **Semantic document search.** Current search is real term-frequency keyword
  matching (`backend/documents/search.py`), explicitly labeled as such. Real
  semantic search needs an embeddings provider (e.g. Voyage AI) — not
  configured in this deployment, and not something to fake with a
  differently-labeled keyword score.
- **Automated citation verification** for the Paper Review / Algorithm Review
  / Scientific Comparison agents — they cite `[filename, page/section]`
  today, but nothing automatically checks that a citation's claimed page
  actually contains the claimed text. Manual spot-checking works; automated
  verification would close the loop.
- **A first real `SafetyPropertyPlugin` implementation.** The interface
  (`backend/plugins/base.py`) is real and documented; zero plugins exist.
  A real implementation (power, thermal, or momentum) would need its own
  Farkas/Z3 certificate construction to be cheaply rechecked by the
  verifier — the interface alone doesn't provide that proof machinery.
- **Multi-user identity.** No operator/user concept exists anywhere — every
  import, document, and agent run is anonymous. This is a materially bigger
  change (real auth, real accounts) than anything else on this list, and is
  explicitly out of scope for a single-operator research prototype.

## Explicitly not planned

Kubernetes, a microservices split, PostgreSQL migration, cloud deployment,
enterprise DevOps infrastructure — see `README.md` §9 for why these were
traded for research-facing features instead.
