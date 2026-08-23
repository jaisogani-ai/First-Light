"""Flight Rules Engine.

Each rule implements the same interface (`evaluate(state, profile) -> RuleResult`) so the
Safety Agent can run one or many rules uniformly. Only Rule 1 (angular rate) is wired into
this build; the registry exists so Battery Reserve, Thermal Envelope, Comm Window, Wheel
Saturation, Power Reserve, and Sun-Pointing rules are a matter of adding a class here and
registering it — not restructuring the pipeline.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RuleResult:
    rule_key: str
    satisfied: bool
    constraints: list[float]
    binding_index: int
    binding_value: float
    detail: str


class FlightRule(Protocol):
    key: str

    def evaluate(self, state: dict, profile: dict) -> RuleResult: ...


class AngularRateRule:
    """Rule 1: |omega_i| <= max_omega_rad_s on every axis (post-maneuver angular rate bound).

    Encoded as 6 signed half-space constraints (upper/lower per axis), each negative when
    satisfied. The binding (max) constraint is the axis/direction closest to violating the
    bound; its value is the single number that must be < 0 for the whole box to be safe.
    """

    key = "angular_rate"

    def evaluate(self, state: dict, profile: dict) -> RuleResult:
        max_omega = profile["max_omega_rad_s"]
        omega = state["omega"]

        constraints: list[float] = []
        for w in omega:
            constraints.append(float(w) - max_omega)   # upper bound: w - max <= 0 when satisfied
            constraints.append(-float(w) - max_omega)  # lower bound: -w - max <= 0 when satisfied

        binding_index = max(range(len(constraints)), key=lambda i: constraints[i])
        binding_value = constraints[binding_index]
        satisfied = binding_value < 0.0

        axis = binding_index // 2
        direction = "upper" if binding_index % 2 == 0 else "lower"
        detail = (
            f"Binding constraint: axis {axis} {direction} bound, margin {binding_value:.5f} "
            f"({'within' if satisfied else 'exceeds'} {max_omega:.5f} rad/s envelope)."
        )
        return RuleResult(self.key, satisfied, constraints, binding_index, binding_value, detail)


RULE_REGISTRY: dict[str, FlightRule] = {
    "angular_rate": AngularRateRule(),
    # Not yet implemented for this build, but the interface above supports adding:
    # "battery_reserve", "thermal_envelope", "comm_window", "wheel_saturation",
    # "power_reserve", "sun_pointing" — each just needs a RuleResult-returning evaluate().
}
