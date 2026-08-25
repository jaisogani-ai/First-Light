# System Design

Where [`ARCHITECTURE.md`](ARCHITECTURE.md) maps *what* exists, this document
explains *why* — the real trade-offs behind decisions a reviewer might
otherwise assume were oversights.

## Why SQLite, not a client-server database

This is a single-operator research prototype, not a multi-tenant service.
SQLite in WAL mode with a `busy_timeout` (`backend/db.py`) handles real
concurrent writers correctly (verified: `eval/test_sequence_race.py`,
`eval/test_db_pragmas.py`) at the scale one researcher or one CubeSat team
actually generates. A PostgreSQL migration would add real operational
overhead (a server to run, connection pooling, migrations tooling) for a
scale problem this project doesn't have. Explicitly deferred, not
overlooked — see [`ROADMAP.md`](ROADMAP.md).

## Why the producer/verifier split (the core research decision)

The central insight Proof-Carrying Commands demonstrates: an AI-driven
producer can be arbitrarily complex, slow, and even untrusted, as long as
the **verifier** — the code that actually gates whether a command reaches
the spacecraft — stays simple, fast, and independently auditable. Z3's
solve happens on the ground (milliseconds to tens of milliseconds); the
verifier's recheck is pure arithmetic (sub-millisecond). This asymmetry is
measured, not asserted — see `eval/test_positive.py`'s latency assertions
and `GET /api/evaluation/report`'s real `computational_asymmetry` field.

## Why every LLM-backed feature has a deterministic fallback

Seven different places call the Anthropic API (Mission Planner, Mission
Assistant, Knowledge, Paper Review, Algorithm Review, Comparison). Every one
of them:
1. Never lets an LLM call gate a safety decision — the Mission Planner's
   proposal is just a proposal; the deterministic verifier decides.
2. Degrades to a real, honestly-labeled fallback (`generated_by:
   "deterministic_fallback"`) rather than failing the whole request when
   Claude is unavailable, rate-limited, or no API key is configured.
3. Is tested with `ANTHROPIC_API_KEY` cleared (`eval/conftest.py`) so the
   fallback path is exercised for real in CI, not just hoped to work.

This is a deliberate consistency, not an accident of seven independent
implementations — see `backend/agents/_grounded_review.py` and
`backend/mission_assistant.py` for the shared pattern.

## Why grounding happens before generation, not as a prompt instruction

Early in this project's iteration, a live test revealed a real bug: the
Knowledge Agent answered an unrelated question because keyword-search
stopwords inflated a match score, and the "only answer from evidence"
instruction lived entirely in the prompt — nothing in the code actually
prevented Claude from seeing an irrelevant document and trying anyway. The
fix was architectural, not just a better prompt: retrieval
(`backend/documents/grounding.py`) runs *before* any Claude call, and if it
finds nothing, the refusal is a deterministic code path that never touches
the network. The lesson generalizes to why every grounded agent in this
project works this way — see [`AGENTS.md`](AGENTS.md).

## Why engineering agents are a separate framework from the PCC pipeline

`producer/pipeline.py`'s 5 agents and `backend/agents/*.py`'s engineering
agents look superficially similar (both produce structured, timed,
evidence-carrying output). They're kept structurally separate because they
have fundamentally different trust requirements: the PCC pipeline's output
feeds a safety decision and must be independently re-verifiable by
deterministic arithmetic; engineering agents' output is operator-facing
context (a document summary, a telemetry statistic) that never reaches the
verifier. Merging them into one framework would blur that boundary — see
[`AGENTS.md`](AGENTS.md) for why that boundary matters.

## Why mission-scoping happened after an initial global design

The earliest version of this platform had no Mission Workspace concept —
commands and telemetry were global. Retrofitting `mission_id` scoping
surfaced a real bug: the replay-protection sequence counter
(`sequence_state`) was keyed by `mission_profile_key`, so two missions
sharing a safety envelope could cross-pollinate each other's replay
counters. Fixed by rescoping the stream identity to `mission_id`
(`backend/stream_id.py`) — a schema-level fix, not a UI patch, because the
bug was in what identified a "stream" for the locked replay-protection
mechanism, not in application logic layered on top of it.

## Why the frontend has no build step or framework

`index.html`/`app.js`/`styles.css` are plain files, served directly by
FastAPI — no bundler, no npm, no framework. For a research prototype whose
value is in the backend's correctness (verifier, certificates, audit chain,
grounding), a build pipeline adds real friction (a second toolchain to
install, version, and debug) without a corresponding benefit at this
project's UI complexity. This is a real trade-off, not free — a framework
would make some of the 13-screen UI's shared state (active mission, active
profile) more ergonomic to manage than the current module-scoped globals in
`app.js`. Revisit if the UI's complexity grows materially past its current
scope.

## Why component-based normalization for spacecraft configuration

`spacecraft_components` is one table with a `component_type` discriminator
and a `parameters_json` blob, rather than dozens of mostly-NULL columns on
`spacecraft` for every possible subsystem's parameters. Reaction wheels need
`max_torque_nm`/`max_momentum_nms`; batteries need `capacity_wh`/
`nominal_voltage_v`; these don't share a schema. A discriminated-union table
matches the actual shape of the data — see `backend/engines/spacecraft_config.py`'s
`REQUIRED_PARAMETERS` dict for the real per-type validation rules this
enables.
