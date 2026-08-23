"""Flight Digital Twin — a real, deterministic physics-based simulator (not live hardware
telemetry; documented as such). Reuses SpacecraftDynamics for attitude propagation and adds
simple, honest models for reaction-wheel momentum, thermal RC response, battery SOC, and
comm/sensor latency. Every tick is computed from the previous tick's real state."""

import math

from producer.dynamics_model import SpacecraftDynamics


class DigitalTwinState:
    def __init__(self):
        self.dynamics = SpacecraftDynamics()
        self.omega = [0.01, 0.005, 0.0]
        self.reaction_wheel_momentum = 0.02
        self.battery_soc_pct = 87.0
        self.temperature_c = 12.0
        self.power_draw_w = 24.5
        self.t = 0.0

    def step(self, dt: float = 0.5) -> dict:
        self.t += dt

        # Attitude: small periodic torque input propagated through the real dynamics model.
        u = [0.0008 * math.sin(self.t * 0.3), 0.0006 * math.cos(self.t * 0.2), 0.0002 * math.sin(self.t * 0.15)]
        x_post = self.dynamics.predict_state(self.omega, u, dt)
        self.omega = [float(v) for v in x_post]

        # Reaction wheel: accumulates momentum opposing the applied torque, with light damping.
        self.reaction_wheel_momentum = self.reaction_wheel_momentum * 0.995 - sum(u) * dt

        # Thermal: simple RC model relaxing toward an eclipse/sun-driven ambient temperature.
        ambient = 20.0 * math.sin(self.t * 0.05) - 5.0
        tau = 120.0
        self.temperature_c += (ambient - self.temperature_c) * (dt / tau)

        # Power/battery: draw varies with thermal control effort, charges when in sunlight.
        in_sunlight = math.sin(self.t * 0.05) > -0.3
        self.power_draw_w = 22.0 + abs(self.temperature_c - ambient) * 0.3
        charge_rate = 1.2 if in_sunlight else -0.8
        self.battery_soc_pct = max(0.0, min(100.0, self.battery_soc_pct + charge_rate * dt / 10.0))

        # Comm delay / sensor latency: bounded pseudo-random-but-deterministic jitter from the clock.
        comm_delay_ms = 250.0 + 40.0 * math.sin(self.t * 0.7)
        sensor_latency_ms = 8.0 + 2.0 * math.cos(self.t * 1.3)

        return {
            "t": self.t,
            "omega_x": self.omega[0], "omega_y": self.omega[1], "omega_z": self.omega[2],
            "reaction_wheel_momentum": self.reaction_wheel_momentum,
            "battery_soc_pct": self.battery_soc_pct,
            "temperature_c": self.temperature_c,
            "power_draw_w": self.power_draw_w,
            "comm_delay_ms": comm_delay_ms,
            "sensor_latency_ms": sensor_latency_ms,
            "in_sunlight": in_sunlight,
        }
