"""Plugin interface for future safety properties (power, thermal, radiation, momentum,
fuel, reaction wheels, communication windows).

STATUS: interface only. Nothing implements SafetyPropertyPlugin yet, and nothing in
backend/verifier.py or producer/certificate.py calls the registry below — the live
verifier still enforces exactly the one locked, real property (angular rate, via the
real Z3/Farkas construction). Wiring a plugin's check into the actual verified path is a
deliberate, separately-reviewed decision that would need its own Farkas/Z3 certificate
construction for that property (see README §4) — not something this interface alone
enables. This module exists so a future property has a defined shape to implement against,
not to claim those properties are checked today.
"""

from abc import ABC, abstractmethod


class SafetyPropertyPlugin(ABC):
    """One future safety property's interface. A real implementation would need to derive
    its own Farkas certificate (or equivalent formal proof) for backend/verifier.py to
    cheaply recheck — mirroring how the locked angular-rate property works today. This
    class only defines the shape; it does not provide that proof machinery."""

    #: Short, stable identifier, e.g. "power", "thermal", "radiation".
    property_key: str

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of what this property constrains."""
        raise NotImplementedError

    @abstractmethod
    def check(self, state: dict, bound: dict) -> bool:
        """Cheap, deterministic feasibility check — the verifier-side half of the
        producer/verifier asymmetry, analogous to backend/verifier.py's arithmetic
        recomputation for angular rate. Must not call an LLM or do expensive solving;
        that belongs on the producer side, mirroring producer/certificate.py."""
        raise NotImplementedError


class PluginRegistry:
    """A plain list-backed registry — no auto-discovery, no entry_points magic. Explicit
    registration only, so it's always clear from reading the code what's registered."""

    def __init__(self):
        self._plugins: dict[str, SafetyPropertyPlugin] = {}

    def register(self, plugin: SafetyPropertyPlugin) -> None:
        if plugin.property_key in self._plugins:
            raise ValueError(f"Plugin '{plugin.property_key}' is already registered")
        self._plugins[plugin.property_key] = plugin

    def get(self, property_key: str) -> SafetyPropertyPlugin | None:
        return self._plugins.get(property_key)

    def list_keys(self) -> list[str]:
        return sorted(self._plugins.keys())


registry = PluginRegistry()
