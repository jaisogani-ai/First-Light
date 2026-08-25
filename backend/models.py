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

missions = Table(
    "missions", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_name", String),
    Column("objective", Text),
    Column("mission_profile_id", Integer, ForeignKey("mission_profiles.id")),
    Column("tle_line1", Text),
    Column("tle_line2", Text),
    Column("status", String),
    Column("active", Integer),
    Column("created_at", String),
)

spacecraft = Table(
    "spacecraft", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("name", String),
    Column("inertia_ixx", Float),
    Column("inertia_iyy", Float),
    Column("inertia_izz", Float),
)

spacecraft_components = Table(
    "spacecraft_components", metadata,
    Column("id", Integer, primary_key=True),
    Column("spacecraft_id", Integer, ForeignKey("spacecraft.id")),
    Column("component_type", String),
    Column("name", String),
    Column("parameters_json", Text),
    Column("created_at", String),
)

mission_imports = Table(
    "mission_imports", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("import_type", String),
    Column("filename", String),
    Column("record_count", Integer),
    Column("detail_json", Text),
    Column("checksum", String),
    Column("source", String),
    Column("schema_version", String),
    Column("freshness_days", Float),
    Column("imported_at", String),
)

mission_reports = Table(
    "mission_reports", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("report_type", String),
    Column("generated_by", String),
    Column("content_json", Text),
    Column("created_at", String),
)

commands = Table(
    "commands", metadata,
    Column("id", Integer, primary_key=True),
    Column("command_id", String, unique=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
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
    Column("mission_id", Integer, ForeignKey("missions.id")),
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

mission_documents = Table(
    "mission_documents", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("doc_type", String),
    Column("filename", String),
    Column("version_no", Integer),
    Column("content_type", String),
    Column("size_bytes", Integer),
    Column("checksum", String),
    Column("storage_path", String),
    Column("extraction_status", String),
    Column("extracted_text", Text),
    Column("extracted_metadata_json", Text),
    Column("uploaded_at", String),
)

document_sections = Table(
    "document_sections", metadata,
    Column("id", Integer, primary_key=True),
    Column("document_id", Integer, ForeignKey("mission_documents.id")),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("section_type", String),
    Column("page_number", Integer),
    Column("content_text", Text),
    Column("order_index", Integer),
    Column("created_at", String),
)

agent_runs = Table(
    "agent_runs", metadata,
    Column("id", Integer, primary_key=True),
    Column("mission_id", Integer, ForeignKey("missions.id")),
    Column("agent_name", String),
    Column("status", String),
    Column("input_summary", Text),
    Column("output_json", Text),
    Column("error_message", Text),
    Column("latency_ms", Float),
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
