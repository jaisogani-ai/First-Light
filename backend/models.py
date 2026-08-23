"""SQLAlchemy Core table definitions mirroring db/schema.sql (the DDL is the source of truth;
these Table objects give typed query building without a duplicate ORM class hierarchy)."""

from sqlalchemy import Column, Float, ForeignKey, Integer, MetaData, String, Table, Text

metadata = MetaData()

mission_profiles = Table(
    "mission_profiles", metadata,
    Column("id", Integer, primary_key=True),
    Column("profile_key", String, unique=True),
    Column("display_name", String),
    Column("description", Text),
    Column("max_omega_rad_s", Float),
    Column("power_reserve_w", Float),
    Column("thermal_max_c", Float),
    Column("thermal_min_c", Float),
    Column("created_at", String),
)

commands = Table(
    "commands", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", String, unique=True),
    Column("mission_profile_id", Integer, ForeignKey("mission_profiles.id")),
    Column("command_hash", String),
    Column("sequence_no", Integer),
    Column("u_torque_x", Float),
    Column("u_torque_y", Float),
    Column("u_torque_z", Float),
    Column("submitted_at", String),
    Column("producer_time_ms", Float),
    Column("verifier_time_ms", Float),
    Column("verdict", String),
    Column("reject_reason", Text),
)

proof_certificates = Table(
    "proof_certificates", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("property", String),
    Column("bound_json", Text),
    Column("constraints_json", Text),
    Column("multipliers_json", Text),
    Column("derived_contradiction", Text),
    Column("model_id", String),
    Column("signature", Text),
)

verification_results = Table(
    "verification_results", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("sequence_ok", Integer),
    Column("hash_ok", Integer),
    Column("signature_ok", Integer),
    Column("model_ok", Integer),
    Column("farkas_ok", Integer),
    Column("overall_trusted", Integer),
    Column("explain_json", Text),
    Column("verified_at", String),
)

pipeline_steps = Table(
    "pipeline_steps", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("run_id", String),
    Column("step_order", Integer),
    Column("agent_name", String),
    Column("inputs_json", Text),
    Column("outputs_json", Text),
    Column("latency_ms", Float),
    Column("confidence", Float),
    Column("reasoning_summary", Text),
    Column("status", String),
    Column("dependencies_json", Text),
    Column("step_timestamp", String),
    Column("created_at", String),
)

sequence_state = Table(
    "sequence_state", metadata,
    Column("stream_id", String, primary_key=True),
    Column("last_accepted_sequence", Integer),
    Column("updated_at", String),
)

telemetry = Table(
    "telemetry", metadata,
    Column("id", Integer, primary_key=True),
    Column("spacecraft_id", Integer),
    Column("ts", String),
    Column("omega_x", Float),
    Column("omega_y", Float),
    Column("omega_z", Float),
    Column("reaction_wheel_momentum", Float),
    Column("battery_soc_pct", Float),
    Column("temperature_c", Float),
    Column("power_draw_w", Float),
    Column("comm_delay_ms", Float),
    Column("sensor_latency_ms", Float),
)

security_events = Table(
    "security_events", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("attack_type", String),
    Column("detected", Integer),
    Column("detail_json", Text),
    Column("created_at", String),
)

audit_logs = Table(
    "audit_logs", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("action", String),
    Column("detail_json", Text),
    Column("created_at", String),
)

audit_chain = Table(
    "audit_chain", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", Integer, ForeignKey("commands.id")),
    Column("sequence_index", Integer),
    Column("previous_chain_hash", String),
    Column("chain_hash", String),
    Column("created_at", String),
)
