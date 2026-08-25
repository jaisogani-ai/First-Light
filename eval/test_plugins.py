"""Plugin architecture interface — verifies it's honestly empty (no plugin implements the
interface, nothing is wired to the verifier) and that the registry itself works correctly
for whenever a real plugin is added."""

import pytest

from backend.plugins.base import PluginRegistry, SafetyPropertyPlugin


class _StubPowerPlugin(SafetyPropertyPlugin):
    property_key = "power"

    def describe(self) -> str:
        return "stub power constraint, for registry testing only"

    def check(self, state: dict, bound: dict) -> bool:
        return state.get("power_draw_w", 0) <= bound.get("power_reserve_w", 0)


def test_live_plugin_registry_is_empty():
    """The app-wide registry (backend.plugins.base.registry) must have nothing registered —
    this interface is not wired to the verifier yet, and the API should say so honestly."""
    from backend.plugins.base import registry
    assert registry.list_keys() == []


def test_plugins_endpoint_reports_empty_and_explains_why(client):
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    body = resp.json()
    assert body["registered"] == []
    assert "no safety-property plugins are implemented" in body["note"].lower()


def test_registry_register_and_get():
    reg = PluginRegistry()
    plugin = _StubPowerPlugin()
    reg.register(plugin)
    assert reg.get("power") is plugin
    assert reg.list_keys() == ["power"]


def test_registry_rejects_duplicate_registration():
    reg = PluginRegistry()
    reg.register(_StubPowerPlugin())
    with pytest.raises(ValueError):
        reg.register(_StubPowerPlugin())


def test_registry_get_missing_returns_none():
    reg = PluginRegistry()
    assert reg.get("thermal") is None


def test_stub_plugin_check_is_a_cheap_deterministic_call():
    plugin = _StubPowerPlugin()
    assert plugin.check({"power_draw_w": 5.0}, {"power_reserve_w": 8.0}) is True
    assert plugin.check({"power_draw_w": 10.0}, {"power_reserve_w": 8.0}) is False
