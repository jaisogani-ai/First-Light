"""Single source of truth for the replay-protection stream identity.

Previously, backend/verifier.py's sequence_state was keyed by mission_profile_key, so two
different Mission Workspaces sharing a profile (e.g. two "earth_observation" missions) shared
one sequence counter — a real cross-mission collision. The atomic-upsert monotonicity check
itself (backend/verifier.py) is the locked replay-protection mechanism and is unchanged here;
only what identifies a "stream" changes, from profile_key to mission_id."""


def mission_stream_id(mission_id: int) -> str:
    return f"mission:{mission_id}"
