# Mission Workflow

The real operator workflow this platform supports, mapped to actual UI
screens and API endpoints — not an aspirational description.

```mermaid
flowchart TD
    A["Create Mission<br/>POST /api/missions<br/>Header '+ Mission'"] --> B["Configure Spacecraft<br/>POST /spacecraft/configure<br/>Spacecraft Configuration screen"]
    B --> C["Upload Documents<br/>POST /documents<br/>Mission Files screen<br/>(papers, algorithms, notebooks, MATLAB, notes)"]
    C --> D["Import Structured Data<br/>TLE / OMM / CSV telemetry /<br/>Mission JSON / Constraint Profile"]
    D --> E["Digital Twin<br/>real SGP4 orbit context +<br/>live WebSocket telemetry"]
    E --> F["Mission Planning<br/>POST /api/commands/propose<br/>real 5-agent pipeline"]
    F --> G["Verification<br/>POST /api/commands/verify<br/>real deterministic 5-step check"]
    G --> H["Inspect Proof<br/>full Farkas certificate,<br/>hashes, audit chain — Verification screen"]
    H --> I["Replay<br/>GET /api/missions/replay<br/>mission-scoped history"]
    I --> J["Reports<br/>deterministic + Claude-narrated,<br/>Mission Compare, Analytics"]
    J --> K["Evidence Export<br/>GET /evidence-package<br/>composed, not recomputed"]
```

## Step-by-step, with real endpoints

| Step | Screen | Real endpoint(s) |
|---|---|---|
| Create mission | Header, any screen | `POST /api/missions` |
| Configure spacecraft | Spacecraft Configuration | `POST /api/missions/{id}/spacecraft/configure` |
| Upload documents | Mission Files | `POST /api/missions/{id}/documents` |
| Import TLE/OMM/CSV/JSON/profiles | Digital Twin, Telemetry, Settings | `POST /api/missions/{id}/imports/{type}` |
| Orbit context | Digital Twin | `GET /api/missions/{id}/orbit-context` |
| Digital Twin telemetry | Digital Twin | WebSocket `/ws`, `GET /api/telemetry/latest` |
| Propose a maneuver | Mission Planning | `POST /api/commands/propose` |
| Verify | (automatic after propose) | `POST /api/commands/verify` |
| Inspect proof | Verification | proof detail rendered from the propose/verify response; `GET /api/audit/chain`, `GET /api/audit/verify` |
| Run engineering agents | Mission Files, Telemetry, Multi-Agent Pipeline | `POST /intake/run`, `POST /telemetry-analysis/run`, `POST /knowledge/ask`, `POST /documents/{id}/review/{paper|algorithm}`, `POST /documents/compare` |
| Replay | Replay | `GET /api/missions/replay?mission_id=` |
| Reports | Reports | `GET /analytics`, `GET /api/missions/compare`, `POST /reports/generate`, `POST /assistant/explain` |
| Evidence export | Evidence | `GET /api/missions/{id}/evidence-package` |

## Mission Import Pipeline (structured data)

```mermaid
flowchart LR
    Upload["Operator uploads<br/>TLE / OMM / CSV / JSON / profile"] --> Validate["Real validator per type<br/>backend/imports/*.py"]
    Validate -->|invalid| Reject["Rejected — specific error<br/>returned, nothing persisted"]
    Validate -->|valid, dry_run=true| Preview["Preview only —<br/>nothing persisted"]
    Validate -->|valid| Checksum["sha256 checksum computed"]
    Checksum --> Persist["mission_imports row:<br/>checksum, source, schema_version,<br/>freshness_days, record_count"]
    Persist --> Structured["Structured data lands in its<br/>own table (missions.tle_line1,<br/>telemetry, spacecraft, ...)"]
```

Validators, real and specific per type: NORAD mod-10 checksum (TLE), the
real `sgp4.omm` library's own construction check (OMM), full-row numeric
validation against the `telemetry` table's actual `NOT NULL` columns (CSV —
all-or-nothing, no partial import), JSON schema checks (Mission
JSON/Spacecraft/Constraint Profile). See `backend/imports/*.py`.

**A deliberate safety boundary:** Constraint Profile imports are validated
and recorded for provenance, but **never written into the `mission_profiles`
table the verifier actually enforces** — see `backend/imports/constraint_profile.py`
for why, and `eval/test_imports.py`'s
`test_constraint_profile_import_never_touches_live_verifier_envelope` for the
regression test proving it.

## What happens when something is unsupported

Every stage in this workflow refuses honestly rather than guessing:
- An unrecognized document extension → `extraction_status: "UNSUPPORTED"`,
  file still stored, no fabricated text.
- A corrupt PDF/notebook → `extraction_status: "CORRUPT"`, real parse error
  surfaced.
- An image → `extraction_status: "NOT_APPLICABLE"` (OCR/vision not
  implemented — see `ROADMAP.md`), never silently skipped without saying so.
- A Knowledge/Paper/Algorithm/Comparison question with no matching evidence →
  a deterministic refusal, no Claude call.
- An invalid import (bad TLE checksum, missing CSV column, malformed OMM) →
  a specific real validation error, nothing persisted.
