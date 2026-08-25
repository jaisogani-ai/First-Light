# Architecture

This document maps the real module structure and request flow. For *why*
specific decisions were made (SQLite vs. a client-server DB, the
producer/verifier split, etc.), see [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md).
For the locked verification research specifically, see
[`VERIFICATION_PIPELINE.md`](VERIFICATION_PIPELINE.md).

## Component map

```mermaid
graph TD
    subgraph Client["Browser (index.html / app.js)"]
        UI["13-screen Mission Operations UI"]
    end

    subgraph API["backend/ — FastAPI application"]
        Routers["backend/routers/*.py<br/>(missions, commands, imports, documents,<br/>spacecraft, telemetry_analysis, scientific_review, ...)"]
        Verifier["backend/verifier.py<br/>LOCKED — deterministic 5-step check"]
        AuditChain["backend/audit_chain.py<br/>LOCKED — hash-chain"]
        Agents["backend/agents/*.py<br/>engineering agents + run_agent framework"]
        Engines["backend/engines/*.py<br/>deterministic — no LLM"]
        Documents["backend/documents/*.py<br/>extraction, structure, search, grounding"]
    end

    subgraph Producer["producer/ — ground-side pipeline (LOCKED)"]
        Pipeline["producer/pipeline.py<br/>Planner → Dynamics → Safety → Proof Gen → Reviewer"]
        Cert["producer/certificate.py<br/>real Z3 + Farkas derivation"]
        Orbit["producer/orbit.py<br/>real SGP4 propagation"]
    end

    subgraph External["External"]
        Claude["Anthropic Claude API<br/>(Planner, Assistant, Knowledge,<br/>Paper/Algorithm Review, Comparison)"]
        Z3["Z3 SMT Solver"]
    end

    subgraph Data["Persistence"]
        SQLite[("SQLite — db/schema.sql<br/>WAL mode")]
        Files["data/mission_documents/<br/>original uploaded files"]
    end

    UI -->|REST + WebSocket| Routers
    Routers --> Verifier
    Routers --> AuditChain
    Routers --> Agents
    Routers --> Engines
    Routers --> Documents
    Routers --> Pipeline
    Pipeline --> Cert
    Cert --> Z3
    Pipeline -.->|Mission Planner Agent only| Claude
    Agents -.->|Knowledge/Paper/Algorithm/Comparison| Claude
    Orbit --> Routers
    Verifier --> SQLite
    AuditChain --> SQLite
    Agents --> SQLite
    Engines --> SQLite
    Documents --> SQLite
    Documents --> Files
    Routers --> SQLite
```

**Locked, frozen research** (never modified by surrounding-platform work):
`backend/verifier.py`, `backend/audit_chain.py`, `producer/pipeline.py`,
`producer/certificate.py`. See [`VERIFICATION_PIPELINE.md`](VERIFICATION_PIPELINE.md).

## Directory layout

```
backend/
  routers/        REST + WebSocket API — one file per resource area
  agents/         Engineering-agent execution framework + 5 real agents
                   (NOT the locked producer/pipeline.py multi-agent chain)
  engines/        Deterministic engines (Spacecraft Config, Telemetry
                   Analysis) — explicitly no LLM call
  documents/       Mission Files: extraction, structure, search, grounding
  imports/          Structured-data import validators (TLE, OMM, CSV, ...)
  plugins/           SafetyPropertyPlugin interface (unimplemented, unwired)
  verifier.py          LOCKED — the 5-step deterministic verifier
  audit_chain.py        LOCKED — tamper-evident hash chain
  digital_twin.py        Deterministic physics simulator
  db.py, models.py         SQLAlchemy Core over db/schema.sql

producer/         Ground-side mission-planning pipeline — LOCKED
  agent.py, llm_planner.py    Mission Planner Agent (real Claude call)
  dynamics_model.py            Dynamics Agent
  rules.py                      Flight Rules Engine
  certificate.py                  Proof Generator Agent (real Z3/Farkas)
  pipeline.py                      Orchestrates all 5 agents
  orbit.py                          Real SGP4 propagation

apps/gate, apps/target   cFS-pattern C reference verifier (not a live cFE build)
db/schema.sql            Source-of-truth SQLite schema
eval/                     pytest suite against the live backend (157 tests)
index.html / app.js / styles.css   Mission Operations dashboard
```

## API flow (a single propose → verify request)

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as backend/routers/commands.py
    participant Pipe as producer/pipeline.py (LOCKED)
    participant Claude as Claude API
    participant Z3 as Z3 Solver
    participant DB as SQLite

    UI->>API: POST /api/commands/propose
    API->>Pipe: pipeline.run(cmd_id, maneuver_type, x0, profile)
    Pipe->>Claude: Mission Planner Agent proposes u_cmd
    Claude-->>Pipe: torque proposal
    Pipe->>Pipe: Dynamics Agent propagates state
    Pipe->>Pipe: Safety Agent checks envelope
    Pipe->>Z3: Proof Generator derives Farkas certificate
    Z3-->>Pipe: UNSAT certificate
    Pipe->>Pipe: Reviewer Agent final gate
    Pipe-->>API: {proof, u_cmd, pipeline_steps, refused}
    API->>DB: persist_command() + audit_chain append
    API-->>UI: propose response
    UI->>API: POST /api/commands/verify
    API->>API: verifier.py: 5-step deterministic recheck
    API->>DB: atomic sequence upsert (replay protection)
    API-->>UI: {verdict, trust, explain}
```

## Database schema (real tables, `db/schema.sql`)

```mermaid
erDiagram
    missions ||--o{ commands : "mission_id"
    missions ||--o{ telemetry : "mission_id"
    missions ||--o{ mission_imports : "mission_id"
    missions ||--o{ mission_documents : "mission_id"
    missions ||--o{ mission_reports : "mission_id"
    missions ||--o{ agent_runs : "mission_id"
    missions ||--o{ spacecraft : "mission_id"
    missions }o--|| mission_profiles : "mission_profile_id"

    commands ||--o| proof_certificates : "command_id"
    commands ||--o| verification_results : "command_id"
    commands ||--o{ pipeline_steps : "command_id"
    commands ||--o| audit_chain : "command_id"
    commands ||--o{ security_events : "command_id"

    spacecraft ||--o{ spacecraft_components : "spacecraft_id"
    mission_documents ||--o{ document_sections : "document_id"

    missions {
        int id PK
        string mission_name
        string tle_line1
        string tle_line2
        string status
    }
    commands {
        int id PK
        int mission_id FK
        string command_hash
        int sequence_no
        string verdict
    }
    mission_documents {
        int id PK
        int mission_id FK
        string doc_type
        string checksum
        string extraction_status
        text extracted_text
    }
    agent_runs {
        int id PK
        int mission_id FK
        string agent_name
        string status
        float latency_ms
        text output_json
    }
```

See `db/schema.sql` for the complete, authoritative DDL — this diagram covers
the tables most relevant to understanding the platform, not every index.

## Related documents

- [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) — design decisions and trade-offs
- [`VERIFICATION_PIPELINE.md`](VERIFICATION_PIPELINE.md) — the locked PCC research
- [`AGENTS.md`](AGENTS.md) — every AI agent, real vs. simulated vs. deterministic
- [`MISSION_WORKFLOW.md`](MISSION_WORKFLOW.md) — the real operator workflow
- [`README.md`](README.md) — the full narrative writeup with honesty notes throughout
