# First Light — UI Redesign Brief (for generating a new design prompt)

Give this to whatever tool generates the new UI/UX design, alongside the reference
screenshots. It describes what actually exists on the backend so the new design can be
built to real data instead of decorative placeholders.

## What this system actually is (do not change)

Proof-Carrying Commands (PCC) for NASA cFS: an AI agent proposes a spacecraft RCS
attitude-control command; a Z3-derived Farkas linear-infeasibility certificate proves the
post-maneuver angular rate stays within a safety bound; a cheap deterministic verifier
(hash + HMAC signature + sequence + model + Farkas arithmetic) checks the certificate
instead of re-solving anything. This is locked — no orbital mechanics, no zk-SNARKs, no
new safety property.

## Real backend endpoints (design screens around these, not around invented data)

- `POST /api/commands/propose` — runs the real 5-agent pipeline (Planner→Dynamics→
  Safety→Proof Generator→Reviewer), returns the certificate + per-agent step records
  (`{inputs, outputs, latency_ms, confidence, reasoning_summary, status}`)
- `POST /api/commands/verify` — runs the real 5-check verifier, returns `trust`
  (5 booleans + overall) and `explain` (constraint checked, expected vs actual, narrative)
- `GET /api/commands/feed` — real command history from SQLite
- `GET /api/profiles` — 4 real mission profiles (Earth Observation, Deep Space, Lunar
  Orbiter, Science Mission), each with a distinct `max_omega_rad_s` safety envelope
- `GET /api/pipeline/steps?run_id=` — the 5 agent-step records for one run
- `GET /api/missions/replay` — full history: command + certificate + verification + steps
- `GET /api/attacks/types` / `POST /api/attacks/run` — 7 real attack scenarios
  (tampered_command, replay, wrong_certificate, missing_proof, stale_telemetry,
  wrong_sequence, modified_payload), each genuinely mutates a valid certificate and
  submits it to the live verifier
- `GET /api/telemetry/latest` + WebSocket `/ws` (`digital_twin_tick` messages) — a real
  physics-based simulator (reuses the same rigid-body dynamics as the Proof Generator):
  omega (x/y/z), reaction wheel momentum, battery SOC, temperature, comm delay, sensor
  latency
- `GET /api/evaluation/report` — real aggregates: acceptance/rejection rate, avg
  producer/verifier latency, computational asymmetry, attack detection rate
- `GET /metrics` — Prometheus counters/histograms + live process CPU/memory

## Screens that map cleanly onto the mockup (safe to redesign visually, data already exists)

1. **Dashboard / Flight Digital Twin** — live telemetry from the WebSocket, mission
   profile selector, propose/verify buttons, trust score
2. **AI Agent Observatory / Multi-Agent Timeline** — the 5 real pipeline agents as nodes,
   each with real latency/confidence/reasoning (screenshot 2's layout is a great fit)
3. **Verification / Explainable AI** — real trust checklist + expected-vs-actual
   narrative (screenshot 3's "XAI: Conflict Resolution" concept is a great fit, **minus
   the "zk-SNARK Validated" label — rename to "Farkas Certificate Verified" or
   "HMAC-SHA256 Verified", the actual mechanism**)
4. **Attack Library** — 7 real attack cards, each runs a genuine attack and shows the
   real rejection reason
5. **Mission Replay** — real command/proof/verdict history from the database

## Screens/elements that need scoping before a designer assumes they're real

- Orbital telemetry (velocity, mission phase, orbit insertion) — not computed; either
  drop it or tell me to add it as a real feature
- Multiple safety-rule "constraint matrix" (thermal, power, pointing) — only angular-rate
  is implemented; others are named extension points in `producer/rules.py`, not real
  checks yet
- "Predicted vs Actual" state comparison — only one simulated state exists today; a real
  predicted/actual delta would be a new feature

## Design constraints

- Keep the mission-control dark aesthetic — that direction is good
- Every number on screen should trace to one of the endpoints above, or be explicitly
  scoped as a new feature before the design assumes it exists
- No cryptographic claims beyond what's real: SHA-256 command hash, HMAC-SHA256
  signature, Z3-derived Farkas certificate. Never zk-SNARK, never blockchain (unless we
  build the hash-chain feature — see the separate graph/crypto discussion)
