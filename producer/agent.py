"""Mission Planner Agent entry point — thin convenience wrapper around the full producer
pipeline (see producer/pipeline.py for the Planner/Dynamics/Safety/Proof/Reviewer chain)."""

from producer.pipeline import MissionPipeline

MANEUVER_PRESETS = {
    "SAFE_RCS_PULSE": {"x0": [0.01, 0.01, 0.00], "u_cmd": [0.001, -0.002, 0.001]},
    "UNSAFE_RCS_PULSE": {"x0": [0.04, 0.03, 0.02], "u_cmd": [0.100, 0.200, 0.150]},
}


class MissionPlanningAgent:
    def __init__(self, sequence_allocator, mission_profile: dict):
        self.pipeline = MissionPipeline(sequence_allocator)
        self.mission_profile = mission_profile
        self._counter = 0

    def propose_maneuver(self, maneuver_type: str = "SAFE_RCS_PULSE") -> dict:
        self._counter += 1
        cmd_id = f"RCS_PULSE_{self._counter:04d}"
        preset = MANEUVER_PRESETS.get(maneuver_type, {"x0": [0.0, 0.0, 0.0], "u_cmd": [0.0, 0.0, 0.0]})
        return self.pipeline.run(cmd_id, maneuver_type, preset["x0"], preset["u_cmd"], self.mission_profile)


if __name__ == "__main__":
    counter = {"n": 1042}

    def _seq():
        counter["n"] += 1
        return counter["n"]

    profile = {"profile_key": "earth_observation", "display_name": "Earth Observation", "max_omega_rad_s": 0.05}
    agent = MissionPlanningAgent(_seq, profile)
    result = agent.propose_maneuver("SAFE_RCS_PULSE")
    for step in result["steps"]:
        print(f"[{step['agent_name']}] {step['reasoning_summary']} ({step['latency_ms']:.3f} ms)")
    if result["proof"]:
        print("Proof generated successfully.")
