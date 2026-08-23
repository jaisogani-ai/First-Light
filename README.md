# First Light — Proof-Carrying Commands for NASA Core Flight System (cFS)

**Track:** Aerotech & Aerospace Innovation
**Event:** International Innovation Challenge 3.0 (IIC 3.0), Manipal University Jaipur

---

## 1. Problem and Research Gap

AI mission-planning agents are increasingly proposed for spacecraft autonomy, but they cannot be trusted to execute commands without independent safety verification, and re-running a full safety solve on board is too expensive for flight computers. Existing approaches are either **reactive runtime monitors** (catch violations after they start) or **ground-side rule engines** (slow, human-in-the-loop). Neither gives a flight computer a way to *cheaply and independently* verify that an AI-proposed command is safe before executing it.

**Proof-Carrying Commands (PCC)** is the response: the ground-side AI agent does the expensive work (an SMT/Z3 solve deriving a mathematical certificate of safety) and attaches that certificate to the command. The spacecraft-side verifier does not re-solve anything — it recomputes a small, deterministic arithmetic check over the certificate's own stated numbers. This is the **locked research contribution** of this project: the mechanism, the Farkas-style certificate family, the angular-rate safety property, and the producer/verifier computational asymmetry are unchanged from the original design.

## 2. What Changed in This Build

The original hackathon prototype demonstrated the *idea* with fabricated data: hardcoded Farkas multipliers, a verifier that checked string prefixes instead of cryptographic hashes/signatures, a magic sequence-number constant instead of persisted state, and a frontend that pushed `Math.random()` rows into a JS array. None of that is defensible under inspection — a hash check that isn't a hash check is not a security property.

This build replaces every one of those with a real implementation, verified end-to-end (see [§7](#7-evaluation) and [§8](#8-testing)):

- Real Z3-derived Farkas certificates (`producer/certificate.py`, `producer/rules.py`)
- Real SHA-256 command-hash binding and HMAC-SHA256 signatures, independently recomputed on verify (`backend/security.py`, `backend/verifier.py`)
- Real, DB-backed monotonic sequence numbers — replay is caught by state, not a hardcoded threshold (`db/schema.sql`, `backend/verifier.py`)
- A real FastAPI backend and SQLite database backing every dashboard number (`backend/`)
- A real, five-agent producer pipeline (Planner → Dynamics → Safety → Proof Generator → Reviewer), each step's latency/confidence/reasoning genuinely computed (`producer/pipeline.py`)
- A real Attack Library — seven attack types that mutate a genuinely valid certificate and submit it to the live verifier (`backend/attack_mutations.py`, `backend/routers/attacks.py`)
- A pytest suite that exercises the live backend via `TestClient`, not a reimplementation of the checks under test (`eval/`)

## 3. Architecture

```
producer/                     Ground-side: AI mission-planning pipeline
  agent.py                     Mission Planner Agent (maneuver presets)
  dynamics_model.py             Dynamics Agent's rigid-body propagation engine
  rules.py                      Flight Rules Engine (interface + Rule 1: angular rate)
  certificate.py                 Proof Generator Agent — real Z3 SMT call + Farkas derivation
  pipeline.py                    Orchestrates all 5 agents, records per-step telemetry

backend/                      Spacecraft-side (reference) + application backend
  verifier.py                    The real 5-step verifier (hash/sig/sequence/model/Farkas)
  security.py                     SHA-256, HMAC-SHA256, canonicalization, rate limiting
  digital_twin.py                  Physics-based telemetry simulator (Flight Digital Twin)
  attack_mutations.py               Shared attack definitions (Attack Library + eval/ tests)
  routers/                          commands, pipeline, profiles, replay, attacks, telemetry,
                                     evaluation, metrics — the full REST + WebSocket API
  db.py, models.py                   SQLAlchemy Core over db/schema.sql

apps/gate, apps/target        cFS-pattern C reference verifier — see §6, not a live cFE build
db/schema.sql                 Source-of-truth SQLite schema (SQLite only, no ORM migrations)
eval/                         pytest adversarial suite against the live FastAPI backend
index.html / app.js / styles.css   Mission Control dashboard (design unchanged, data is real)
```

### Mission Knowledge Base and Flight Rules Engine

Safety limits are not hardcoded. `mission_profiles` (a real DB table, seeded in `db/seed.py`) holds four distinct envelopes — Earth Observation, Deep Space, Lunar Orbiter, Science Mission — each with its own `max_omega_rad_s`, power reserve, and thermal limits. The Mission Planner Agent reads the active profile and passes its limits down the pipeline; switching profiles changes the Farkas certificate's numbers, not just a label.

`producer/rules.py` defines a `FlightRule` interface (`evaluate(state, profile) -> RuleResult`) and a rule registry. Only **Rule 1 (Angular Rate)** is implemented and wired into the Safety Agent — Battery Reserve, Thermal Envelope, Comm Window, Wheel Saturation, Power Reserve, and Sun-Pointing are named as the registry's intended extension points, not implemented. Adding one is a matter of implementing the interface, not restructuring the pipeline.

### AI Agent Observatory and Multi-Agent Timeline

The producer is not one opaque function call. `producer/pipeline.py` runs five distinct steps — Mission Planner, Dynamics, Safety, Proof Generator, Reviewer — each producing a `{inputs, outputs, latency_ms, confidence, reasoning_summary, status}` record from real numbers (latency via `time.perf_counter()`, confidence as a genuine margin-to-bound ratio). These are persisted to `pipeline_steps` and rendered live in the dashboard's AI Agent Observatory / Multi-Agent Timeline screen.

The Reviewer Agent is a genuine second opinion: it independently recomputes `Σ(λᵢ·cᵢ)` from the certificate the Proof Generator just produced and refuses to let it be signed if the recheck fails — this is a real internal check, not decoration.

### Explainable AI and Trust Score

Every verification result carries structured explain data (`backend/schemas.py: ExplainData`) — which constraint was checked, the expected bound vs. the actual binding-axis rate, and which of the five checks failed. The five underlying booleans are also surfaced directly as a `TrustAssessment` rather than collapsed into a single pass/fail flag, so a rejection is legible ("Sequence Freshness failed" vs. "Signature Valid failed") instead of an opaque `REJECTED`.

### Mission Replay

`GET /api/missions/replay` returns the full persisted history — every command, its certificate, its verification result, and its pipeline trace — straight from the database. The dashboard's Mission Replay screen renders exactly that; there is no synthesized replay data.

### Flight Digital Twin

`backend/digital_twin.py` is a real, deterministic physics-based simulator: it reuses `SpacecraftDynamics` (the same rigid-body model the Proof Generator uses) to propagate attitude, and adds simple, honestly-labeled models for reaction-wheel momentum, thermal RC response, battery state-of-charge, and comm/sensor latency. It is **not live spacecraft telemetry** — it is a simulation, and is described as such everywhere it appears.

## 4. Real Farkas Certificate Construction

The safety property is `post_maneuver_omega_bound`: after a maneuver, `|ω_i| ≤ ω_max` on every axis. This is encoded as six signed half-space constraints (`producer/rules.py: AngularRateRule`):

```
c_upper_i = ω_i − ω_max        (negative when axis i's upper bound is satisfied)
c_lower_i = −ω_i − ω_max       (negative when axis i's lower bound is satisfied)
```

The **binding constraint** is `max(c_0..c_5)` — the axis/direction closest to violating the bound. The certificate's Farkas multiplier vector is one-hot on the binding constraint's index; every other multiplier is `0`. This is not an arbitrary choice: a convex combination of values that are all `≤ max(c)` can only equal `max(c)` if all weight sits on the maximal constraint(s) — so `Σ(λᵢ·cᵢ) = max(c) < 0` is both the correct safety condition and the only combination of non-negative multipliers that can honestly reproduce it. The verifier (`backend/verifier.py`) enforces exactly this: it rejects any multiplier vector that doesn't reproduce `max(constraints)` exactly, not merely one that happens to sum to something negative — an earlier version of this check only required a negative sum, which would have let a forged multiplier vector cherry-pick a comfortable constraint while hiding a violated one (caught and fixed during this build; see `eval/test_adversarial_forged.py`).

Independently of the closed-form derivation, `producer/certificate.py` makes a **real Z3 SMT call**: it encodes the propagated state as `z3.Real` constants, asserts the negation of the safety property as a disjunctive formula, and requires `Solver().check() == unsat` before a certificate is ever generated. If Z3 finds the negation satisfiable (i.e., the state is actually unsafe), the producer refuses — this is real solver-backed refusal, not a `Math.random()` fake alert.

## 5. Security Properties

| Check | Mechanism | What it actually catches |
|---|---|---|
| Sequence freshness | `sequence_state` table, transactional read/write | Replay of a previously-accepted certificate |
| Command hash match | Real SHA-256 over canonical command bytes | Attaching a valid certificate to a different (tampered) command |
| Signature valid | Real HMAC-SHA256 over the canonical certificate payload | Forged or corrupted certificates |
| Model version match | Registry of accepted `model_id` values | A certificate generated against an unrecognized dynamics model |
| Farkas inequality | Exact recomputation of `Σ(λᵢ·cᵢ)`, requires equality with `max(constraints)` | A certificate whose stated multipliers don't actually prove the stated conclusion |

`SECRET_KEY` (now `FIRST_LIGHT_HMAC_SECRET_KEY`) lives in `.env`, not source (see `.env.example`); it is no longer the hardcoded literal the original `certificate.py` shipped with. Rate limiting is a light in-memory fixed-window limiter (`backend/security.py: RateLimiter`) — deliberately not backed by Redis, per the scope decision in §9.

## 6. NASA cFS Integration — Honest Status

**What this build attempted:** a real NASA cFS Bundle build. `git clone --recursive https://github.com/nasa/cFS.git` succeeded (328MB, all submodules), and `gcc`/`cmake`/`git` were all available. The build reached CMake configuration and failed with:

```
CMake Error at cmake/arch_build.cmake:706 (message):
  Do not know how to set CFE_SYSTEM_PSPNAME on Darwin system
```

The open-source cFS native/host Platform Support Package is implemented only for Linux and CYGWIN (`cfe/cmake/arch_build.cmake:700-706`); porting OSAL's POSIX BSP to macOS is itself a nontrivial subproject, not a build-flag fix, and was out of scope for this session. **This build was not completed under a live NASA cFE/Software Bus instance.**

**What exists instead:** `apps/gate/fsw/src/` contains a **C reference implementation** of the same 5-step verifier logic as `backend/verifier.py`, including a from-scratch SHA-256 and HMAC-SHA256 (`pcc_crypto.c`) — verified independently against RFC 6234/4231 test vectors (`test_pcc_crypto.c`, all 3 vectors pass). This replaces the original mock (`Mock_SHA256` XORed bytes; `Mock_VerifySig` checked for a two-byte marker). It compiles and runs standalone with plain `gcc`, and demonstrates the same verification logic in C — but it has not been built or exercised inside an actual cFE application, has not subscribed to a real Software Bus message ID, and has not been tested on target hardware or in QEMU.

**Honest next step:** running this on a Linux host (native cFS bundle target is Linux/CYGWIN-only) would let the existing `apps/gate`/`apps/target` structure build against real cFE/OSAL/PSP and communicate over the actual Software Bus — the C verifier logic itself would not need to change, since it already doesn't depend on cFS headers beyond `gate_app.h`'s structs.

## 7. Evaluation

`GET /api/evaluation/report` computes, from real DB aggregates (not hardcoded): total commands, acceptance/rejection rate, average producer/verifier latency, the computational asymmetry ratio, and attack detection rate. `GET /api/evaluation/export?fmt=csv` streams the same report as CSV. `GET /metrics` exposes Prometheus counters/histograms (`first_light_commands_verified_total`, `first_light_verifier_latency_ms`, etc.) plus live process CPU/memory via `psutil`.

Representative numbers from a local run: producer (Z3 solve + pipeline) ≈ 4–30 ms; verifier (arithmetic recomputation) ≈ 0.5–1 ms — a genuine multi-x computational asymmetry, not the fabricated "1,990x" the original dashboard displayed.

## 8. Testing

`eval/` is a pytest suite (migrated from `unittest`) that spins up the real FastAPI app via `TestClient` against a temporary SQLite database and exercises the actual `/api/commands/*` endpoints — not a reimplementation of the checks under test, which is what the original suite did (each old test reimplemented the same broken inline logic it was supposedly testing, so it would have passed against any input).

```
pytest eval/ -v
```

Covers: a genuinely safe maneuver end-to-end (`test_positive.py`); a valid certificate attached to a different command, rejected on hash mismatch (`test_adversarial_mismatch.py`); hand-corrupted Farkas multipliers, rejected on the arithmetic check — re-signed to specifically isolate the Farkas layer from the signature layer, which would otherwise catch the tampering first (`test_adversarial_forged.py`); replay of an already-accepted certificate (`test_replay.py`); a single flipped signature byte and the exact `startswith("hmac_sha256:")` bug the original code had (`test_tampered_signature.py`); every pipeline step's data and all 7 Attack Library scenarios (`test_pipeline_and_attacks.py`); and cFS startup ordering (`test_boot_order.py`). 17 tests, all passing against the live backend.

## 9. Scope Decisions

Explicitly **not** built, by decision rather than oversight: Kubernetes, a microservices split, PostgreSQL-specific work (SQLite only — `DATABASE_URL` is a plain env var, no dual-backend testing), OAuth/JWT, multi-user accounts, enterprise authentication, Redis, Kafka, and Alembic migrations (a single `db/schema.sql` with idempotent `CREATE TABLE IF NOT EXISTS` is the whole migration story). These were traded for the AI Agent Observatory, Multi-Agent Timeline, Flight Digital Twin, Explainable AI panel, Attack Library, and Mission Replay — judged more valuable for a hackathon research prototype than infrastructure sprawl a single mission profile doesn't need yet.

## 10. Quick Start

```bash
pip install -r requirements.txt
python3 -m db.seed              # creates first_light.db, seeds 4 mission profiles
uvicorn backend.main:app --reload
# open http://localhost:8000
```

```bash
pytest eval/ -v                 # full adversarial suite against the live backend
```

```bash
cd docker && docker compose up --build
```

## 11. Limitations

- Not flight-qualified software; not certified under any space agency safety standard (NASA-STD-8719.13, DO-178C, ECSS-E-ST-40C). See `docs/SAFETY_DISCLAIMER.md`.
- No live NASA cFE/Software Bus build in this repository — see §6.
- Only one Flight Rule (angular rate) is implemented; the registry supports more but they don't exist yet.
- The Digital Twin is a deterministic simulation, not live spacecraft telemetry.
- Rate limiting is in-memory and per-process — it does not survive a restart or scale across processes.
- The C reference verifier's HMAC key is a compiled-in demo constant, explicitly not suitable for flight use (see the comment in `apps/gate/fsw/src/gate_verify.c`).

## License

NASA cFS core components are subject to the **NASA Open Source Agreement (NOSA)**. Custom PCC gateway logic, producer engine, schema, backend, and UI dashboard are licensed under the **Apache 2.0 License**.
