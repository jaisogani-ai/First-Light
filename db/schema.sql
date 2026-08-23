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

CREATE TABLE IF NOT EXISTS missions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name        TEXT NOT NULL,
    mission_profile_id  INTEGER NOT NULL REFERENCES mission_profiles(id),
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

CREATE TABLE IF NOT EXISTS sequence_state (
    stream_id           TEXT PRIMARY KEY,
    last_accepted_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS commands (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id          TEXT NOT NULL UNIQUE,
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
    created_at                TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS telemetry (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE INDEX IF NOT EXISTS idx_commands_sequence ON commands(sequence_no);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run ON pipeline_steps(run_id, step_order);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(ts);
