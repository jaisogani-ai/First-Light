# Changelog

All notable changes to this project are documented here, in the spirit of
[Keep a Changelog](https://keepachangelog.com/). This project does not yet
follow formal version numbers — entries are grouped by real git history and,
for work not yet committed, an honest "Unreleased" section.

## [Unreleased]

Extensive work has been done in the working tree since the last commit
(`4b079ca`) that is **not yet committed** as of this writing — `git status`
shows ~50 modified/new files. Summarized here so the scope is visible even
before it lands as commits:

### Added
- **Mission Workspace** — full CRUD (`backend/routers/missions.py`), with
  `commands`/`telemetry` scoped by `mission_id`, and replay-protection
  sequence streams rescoped from profile-key to mission-id (closing a real
  cross-mission collision).
- **Mission Import Pipeline** — TLE (real NORAD checksum), OMM (real
  `sgp4.omm` validation), CSV telemetry, Mission JSON, Spacecraft Profile,
  Constraint Profile — each with real provenance (checksum, source, schema
  version, freshness).
- **Mission Files + document grounding** — real PDF (PyMuPDF)/DOCX
  (`python-docx`)/notebook/Markdown/LaTeX/plain-text extraction, structural
  extraction (title/abstract/headings/tables/references), keyword search,
  and the retrieve-before-answer grounding pipeline
  (`backend/documents/grounding.py`) that makes the Knowledge/Paper
  Review/Algorithm Review/Comparison agents refuse rather than hallucinate.
- **Five engineering agents**: Mission Intake, Spacecraft Configuration
  Engine, Telemetry Analysis Engine (all deterministic, no LLM), Mission
  Knowledge Agent, Paper Review / Algorithm Review / Scientific Comparison
  (Claude-backed, grounded, refuse on missing evidence) — all sharing a real
  execution-audit framework (`backend/agents/base.py`, `agent_runs` table:
  status, latency, version, input, output, errors).
- **Digital Twin realism** — mission health heuristic, verification state,
  telemetry freshness, and real SGP4 orbit context surfaced via
  `backend/routers/mission_status.py`; the WebSocket tick's
  reaction-wheel/battery/thermal/comm/sunlight fields (already computed,
  previously undisplayed) now shown live in the UI.
- **Evidence Package, Mission Analytics, Compare, Reports, Timeline** — pure
  composition of existing data, no duplicated queries.
- **13-screen frontend restructure** around a real operator workflow
  (Mission Overview → Planning → Files → Spacecraft Configuration →
  Telemetry → Digital Twin → Multi-Agent Pipeline → Verification → Replay →
  Knowledge → Reports → Evidence → Settings), replacing a single long
  "Mission Ops" page and three screens that were empty until a button click.
- A full flat, low-chroma design system (`styles.css`) replacing the
  original neon/glassmorphism theme.
- This GitHub documentation set (`ARCHITECTURE.md`, `SECURITY.md`,
  `CONTRIBUTING.md`, `ROADMAP.md`, `CHANGELOG.md`, `LICENSE`,
  `CODE_OF_CONDUCT.md`, `SYSTEM_DESIGN.md`, `AGENTS.md`,
  `MISSION_WORKFLOW.md`, `VERIFICATION_PIPELINE.md`).

### Fixed
- 7 genuinely unused imports (AST-verified) and one orphaned, untested,
  never-called API endpoint (`GET /api/commands/export`) removed.
- SQLite now runs in WAL mode with a `busy_timeout` (previously neither was
  configured — concurrent writers could raise "database is locked").
- CSV telemetry / document uploads are now size-capped (previously
  unbounded).
- A stopword-inflation bug in keyword search that let the Knowledge Agent
  answer an unrelated question instead of refusing — found via live testing,
  fixed, regression-tested.

Test suite: 157 tests (`pytest eval/ -v`), all passing against the live
backend.

## [Committed history]

- `4b079ca` — fix: eliminate critical TOCTOU replay race, add real orbit
  propagation, enrich agent metadata
- `7debce3` — feat: add tamper-evident hash-chain audit log and real
  pipeline dependency graph
- `7d68d8c` — docs: add UI redesign brief mapping real endpoints to design
  mockup screens
- `e4dc817` — fix: switch Mission Planner LLM to Haiku 4.5, fix
  pydantic-settings crash on unrelated `.env` vars, force deterministic
  fallback in tests
- `13ffdbe` — docs: add Related Work section citing real prior research and
  a named real attack-traffic dataset as an honest future-work item
- `67ce46a` — feat: wire a real Claude API call into the Mission Planner
  Agent
- `0bd41bc` — fix: eliminate remaining fake/dead code found in audit
- `b0e82ee` — docs: rewrite README to describe only what was actually
  implemented; add Docker packaging and `requirements.txt`
- `6ed29a0` — fix(apps/gate): replace mock XOR hash / marker signature with
  real SHA-256 and HMAC-SHA256 (RFC test vectors passing), honestly labeled
  as a reference implementation not wired to a live NASA cFE build
- `d897e6d` — feat: rewire frontend to real backend — Agent Observatory,
  Multi-Agent Timeline, Attack Library, Trust Score, Explainable AI panel,
  Mission Replay; fix JSON int/float signature canonicalization bug
- `7249771` — feat: real Z3 Farkas certificates, multi-agent pipeline,
  FastAPI backend with SQLite persistence, and adversarial test suite
  against the live verifier
- `53faef1` — chore: snapshot of hackathon prototype before
  real-implementation rewrite
