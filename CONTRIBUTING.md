# Contributing to First Light

Thanks for considering a contribution. This document covers real, verified setup
steps and conventions — nothing here is aspirational.

## Before you start: what's locked

The research contribution is frozen and out of scope for redesign:

- Proof-Carrying Commands (producer/verifier asymmetry)
- Z3 / Farkas certificate construction (`producer/certificate.py`)
- The deterministic verifier (`backend/verifier.py`)
- Replay protection (`backend/verifier.py`'s atomic sequence upsert)
- The tamper-evident audit chain (`backend/audit_chain.py`)
- The angular-rate safety property itself

See [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`VERIFICATION_PIPELINE.md`](VERIFICATION_PIPELINE.md)
for what these are and why they're locked. Contributions that extend the
surrounding platform (imports, engines, agents, UI) without touching this core
are welcome; PRs that modify it will need a clear justification and should
start as an issue/discussion first.

## Setup

```bash
git clone <this-repo>
cd first-light
pip install -r requirements.txt
python3 -m db.seed              # creates first_light.db, seeds mission profiles
uvicorn backend.main:app --reload
# open http://localhost:8000
```

Copy `.env.example` to `.env` if you want a real `ANTHROPIC_API_KEY` for the
Mission Planner Agent / Mission Assistant / Knowledge / Paper / Algorithm
Review agents' live Claude calls — every one of them has a deterministic
fallback and runs (and is tested) without a key.

## Running tests

```bash
pytest eval/ -v
```

157 tests as of this writing, all against the real, live FastAPI backend via
`TestClient` — no reimplementation of the logic under test. `eval/conftest.py`
isolates the test suite from your real `first_light.db` and uploaded-document
storage (temp DB, temp directory, cleared `ANTHROPIC_API_KEY` so LLM-backed
agents exercise their real deterministic-fallback path).

If you add a feature, add a test that exercises the real endpoint — see any
file in `eval/` for the established pattern (a `client` fixture, real HTTP
calls, assertions on the actual response, not a mocked one).

## Code conventions

- **No enforced formatter or linter is configured yet** (no `pyproject.toml`,
  `.flake8`, or pre-commit hook exists in this repo) — match the surrounding
  file's style rather than reformatting wholesale in an unrelated PR.
- Docstrings explain *why*, not *what* — see any file under `backend/` for the
  established tone: state the real constraint or decision behind a piece of
  code, not a restatement of its name.
- **Never fabricate.** This project's central discipline is that every number,
  citation, and claim traces to a real computation or a real uploaded
  document. If you add a feature that can't honestly back a value, label it
  clearly (see `backend/documents/search.py`'s `"search_type": "keyword"`
  labeling, or the `"Not stated in the uploaded document."` sentinel in
  `backend/agents/_grounded_review.py`, for the pattern).
- New engineering agents should use `backend/agents/base.py::run_agent` for
  execution history/latency/version tracking — don't hand-roll a new pattern.
- New routers should follow the existing `mission_id` path-prefix convention
  (`/api/missions/{mission_id}/...`) unless the resource is genuinely global.

## Filing issues

Real bug reports and scoped feature proposals are welcome. For anything that
touches the locked research surface, please open a discussion first — see
[`ROADMAP.md`](ROADMAP.md) for what's already planned/deferred so you're not
duplicating known work.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
