-- First Light: Proof-Carrying Commands for NASA cFS
-- Schema is deliberately SQLite-first (see backend/config.py); DATABASE_URL can point at
-- any SQLAlchemy-supported backend without model changes, but no dual-backend testing is
-- performed for this hackathon build.

CREATE TABLE IF NOT EXISTS mission_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key         TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    description         TEXT NOT NULL,
    max_omega_rad_s     REAL NOT NULL,
    power_reserve_w     REAL NOT NULL,
    thermal_max_c       REAL NOT NULL,
    thermal_min_c       REAL NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- A Mission Workspace: the container an operator actually works in. Everything else
-- (commands, telemetry, imports, reports) belongs to a mission rather than floating
-- globally. mission_profile_id supplies the safety envelope; tle_line1/2 and spacecraft
-- are optional context an operator can import after creating the mission.
CREATE TABLE IF NOT EXISTS missions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name        TEXT NOT NULL,
    objective            TEXT,
    mission_profile_id  INTEGER NOT NULL REFERENCES mission_profiles(id),
    tle_line1             TEXT,
    tle_line2              TEXT,
    status                TEXT NOT NULL DEFAULT 'ACTIVE',
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS spacecraft (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    name                TEXT NOT NULL,
    inertia_ixx         REAL NOT NULL,
    inertia_iyy         REAL NOT NULL,
    inertia_izz         REAL NOT NULL
);

-- Normalized spacecraft subsystem components (reaction wheels, thrusters, solar arrays,
-- battery packs, payloads, thermal systems, comm systems, sensors, attitude control) —
-- one table with a component_type discriminator rather than dozens of mostly-NULL
-- columns on `spacecraft`, since each component type has genuinely different real
-- parameters. See backend/engines/spacecraft_config.py for the deterministic validator
-- that populates this table and the per-type required-parameter rules.
CREATE TABLE IF NOT EXISTS spacecraft_components (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    spacecraft_id       INTEGER NOT NULL REFERENCES spacecraft(id),
    component_type      TEXT NOT NULL,
    name                TEXT NOT NULL,
    parameters_json      TEXT NOT NULL DEFAULT '{}',
    created_at              TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Real, audited record of every imported file — what kind, how many records, when.
-- Never a claim of import without a row here to back it.
CREATE TABLE IF NOT EXISTS mission_imports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    import_type         TEXT NOT NULL,
    filename             TEXT,
    record_count          INTEGER NOT NULL,
    detail_json            TEXT NOT NULL DEFAULT '{}',
    checksum                TEXT,
    source                   TEXT,
    schema_version             TEXT,
    freshness_days               REAL,
    imported_at             TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Claude Mission Assistant output: explanations and summaries grounded in real stored
-- data. generated_by is always 'claude' or 'deterministic_fallback' — never silently
-- unlabeled — and this table never influences verification, which has already happened
-- deterministically before any report is generated.
CREATE TABLE IF NOT EXISTS mission_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    report_type         TEXT NOT NULL,
    generated_by         TEXT NOT NULL,
    content_json           TEXT NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sequence_state (
    stream_id           TEXT PRIMARY KEY,
    last_accepted_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS commands (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          TEXT NOT NULL UNIQUE,
    mission_id          INTEGER REFERENCES missions(id),
    mission_profile_id  INTEGER NOT NULL REFERENCES mission_profiles(id),
    command_hash        TEXT NOT NULL,
    sequence_no         INTEGER NOT NULL,
    u_torque_x          REAL NOT NULL,
    u_torque_y          REAL NOT NULL,
    u_torque_z          REAL NOT NULL,
    submitted_at         TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    producer_time_ms     REAL,
    verifier_time_ms      REAL,
    verdict              TEXT NOT NULL DEFAULT 'PENDING',
    reject_reason         TEXT
);

CREATE TABLE IF NOT EXISTS proof_certificates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          INTEGER NOT NULL REFERENCES commands(id),
    property             TEXT NOT NULL,
    bound_json            TEXT NOT NULL,
    constraints_json       TEXT NOT NULL,
    multipliers_json        TEXT NOT NULL,
    derived_contradiction     TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    signature              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          INTEGER NOT NULL REFERENCES commands(id),
    sequence_ok           INTEGER NOT NULL,
    hash_ok               INTEGER NOT NULL,
    signature_ok            INTEGER NOT NULL,
    model_ok               INTEGER NOT NULL,
    farkas_ok               INTEGER NOT NULL,
    overall_trusted           INTEGER NOT NULL,
    explain_json             TEXT NOT NULL,
    verified_at              TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          INTEGER REFERENCES commands(id),
    run_id                TEXT NOT NULL,
    step_order              INTEGER NOT NULL,
    agent_name              TEXT NOT NULL,
    inputs_json              TEXT NOT NULL,
    outputs_json              TEXT NOT NULL,
    latency_ms                REAL NOT NULL,
    confidence                REAL NOT NULL,
    reasoning_summary          TEXT NOT NULL,
    status                    TEXT NOT NULL,
    dependencies_json          TEXT NOT NULL DEFAULT '[]',
    step_timestamp               TEXT,
    created_at                TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS telemetry (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER REFERENCES missions(id),
    spacecraft_id        INTEGER REFERENCES spacecraft(id),
    ts                    TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    omega_x                REAL NOT NULL,
    omega_y                REAL NOT NULL,
    omega_z                REAL NOT NULL,
    reaction_wheel_momentum  REAL NOT NULL,
    battery_soc_pct           REAL NOT NULL,
    temperature_c              REAL NOT NULL,
    power_draw_w                 REAL NOT NULL,
    comm_delay_ms                  REAL NOT NULL,
    sensor_latency_ms                REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type            TEXT NOT NULL,
    payload_json            TEXT NOT NULL,
    created_at                TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id            INTEGER REFERENCES commands(id),
    action                  TEXT NOT NULL,
    detail_json                TEXT NOT NULL,
    created_at                TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS security_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id            INTEGER REFERENCES commands(id),
    attack_type              TEXT NOT NULL,
    detected                   INTEGER NOT NULL,
    detail_json                  TEXT NOT NULL,
    created_at                      TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Tamper-evident audit chain: each command's link hashes in the previous link's hash,
-- its own command_hash, signature, and sequence_no (Merkle/blockchain-style hash chaining).
-- Corrupting any past command_hash/signature breaks every chain_hash computed after it —
-- see backend/audit_chain.py for the real recomputation-and-compare verification.
CREATE TABLE IF NOT EXISTS audit_chain (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          INTEGER NOT NULL REFERENCES commands(id),
    sequence_index       INTEGER NOT NULL,
    previous_chain_hash    TEXT NOT NULL,
    chain_hash              TEXT NOT NULL,
    created_at                TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Mission Files: unstructured/reference documents (PDFs, papers, notebooks, MATLAB
-- scripts, configs, flight rules, safety docs, images, notes) attached to a mission.
-- Distinct from mission_imports (structured operational data: TLE/OMM/CSV telemetry/
-- Mission JSON/spacecraft/constraint profiles, which go through their own real parsers/
-- validators and land in their own tables). Every upload is a NEW row — originals are
-- never overwritten; version_no increments per (mission_id, filename) so history is
-- preserved. extracted_text is real, extracted at upload time (PyMuPDF for PDF, direct
-- UTF-8 decode for text/code/notebook formats) — NULL when extraction genuinely doesn't
-- apply (images) or failed (corrupt/unsupported), never a placeholder string.
CREATE TABLE IF NOT EXISTS mission_documents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    doc_type            TEXT NOT NULL,
    filename             TEXT NOT NULL,
    version_no            INTEGER NOT NULL DEFAULT 1,
    content_type           TEXT,
    size_bytes                INTEGER NOT NULL,
    checksum                    TEXT NOT NULL,
    storage_path                  TEXT NOT NULL,
    extraction_status               TEXT NOT NULL,
    extracted_text                    TEXT,
    extracted_metadata_json             TEXT NOT NULL DEFAULT '{}',
    uploaded_at                            TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Generic execution-history/audit-trail table every AI/engineering agent writes to —
-- real latency, real status, real output, never a decorative log line. agent_name is a
-- stable identifier (e.g. 'mission_intake', 'telemetry_analysis'); output_json is the
-- agent's actual structured result, not a summary of it.
CREATE TABLE IF NOT EXISTS agent_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    agent_name          TEXT NOT NULL,
    status               TEXT NOT NULL,
    input_summary          TEXT,
    output_json               TEXT NOT NULL DEFAULT '{}',
    error_message                TEXT,
    latency_ms                     REAL NOT NULL,
    created_at                       TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Structural pieces extracted from a document — one row per heading, table, reference,
-- title, or abstract. This is the real, page/section-cited corpus that search and AI
-- grounding (backend/documents/grounding.py) query — never the whole-document blob, so
-- every search/grounding result can honestly report a specific page and section.
CREATE TABLE IF NOT EXISTS document_sections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL REFERENCES mission_documents(id),
    mission_id          INTEGER NOT NULL REFERENCES missions(id),
    section_type        TEXT NOT NULL,
    page_number          INTEGER,
    content_text            TEXT NOT NULL,
    order_index                INTEGER NOT NULL,
    created_at                    TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mission_documents_mission ON mission_documents(mission_id);
CREATE INDEX IF NOT EXISTS idx_mission_documents_checksum ON mission_documents(checksum);
CREATE INDEX IF NOT EXISTS idx_agent_runs_mission ON agent_runs(mission_id, agent_name);
CREATE INDEX IF NOT EXISTS idx_document_sections_mission ON document_sections(mission_id);
CREATE INDEX IF NOT EXISTS idx_document_sections_document ON document_sections(document_id);

CREATE INDEX IF NOT EXISTS idx_commands_sequence ON commands(sequence_no);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run ON pipeline_steps(run_id, step_order);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_chain_command ON audit_chain(command_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_chain_sequence ON audit_chain(sequence_index);
CREATE INDEX IF NOT EXISTS idx_commands_mission ON commands(mission_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_mission ON telemetry(mission_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_spacecraft_components_spacecraft ON spacecraft_components(spacecraft_id);
