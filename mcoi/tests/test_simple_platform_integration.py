"""Tests for simple platform app integration.

Purpose: verify host apps can mount simple task routes through an environment
gate without importing FastAPI when disabled.
Governance scope: integration helper only; simple platform runtime and router
factory retain validation and route authority.
Dependencies: simple platform integration helper and runtime API.
Invariants: disabled integration does not mount routes, enabled integration
uses the router factory, and mount results are explicit.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.simple_platform_integration import (
    SimplePlatformMountResult,
    mount_simple_platform_router_from_env,
)
from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime
from mcoi_runtime.core.simple_platform_fastapi_router import SimplePlatformFastAPIAdapter


class FakeApp:
    """Minimal app test double with include_router support."""

    def __init__(self) -> None:
        self.routers: list[Any] = []

    def include_router(self, router: Any) -> None:
        self.routers.append(router)


def test_simple_platform_integration_mounts_when_enabled() -> None:
    app = FakeApp()
    runtime_seen: list[SimplePlatformRuntime] = []
    prefix_seen: list[str] = []

    def router_factory(runtime: SimplePlatformRuntime, prefix: str) -> dict[str, object]:
        runtime_seen.append(runtime)
        prefix_seen.append(prefix)
        return {"router": "simple-platform", "prefix": prefix}

    result = mount_simple_platform_router_from_env(
        app,
        {"MULLU_SIMPLE_PLATFORM_ENABLED": "1", "MULLU_SIMPLE_PLATFORM_PREFIX": "/simple"},
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is True
    assert result.prefix == "/simple"
    assert result.reason == "mounted"
    assert result.to_dict()["mounted"] is True
    assert app.routers == [{"router": "simple-platform", "prefix": "/simple"}]
    assert isinstance(runtime_seen[0], SimplePlatformRuntime)
    assert prefix_seen == ["/simple"]


def test_simple_platform_integration_does_not_mount_when_disabled() -> None:
    app = FakeApp()

    def router_factory(runtime: SimplePlatformRuntime, prefix: str) -> object:
        raise AssertionError("router factory must not be called while disabled")

    result = mount_simple_platform_router_from_env(
        app,
        {"MULLU_SIMPLE_PLATFORM_ENABLED": "0", "MULLU_SIMPLE_PLATFORM_PREFIX": "/simple"},
        router_factory=router_factory,
    )

    assert result == SimplePlatformMountResult(
        enabled=False,
        mounted=False,
        prefix="/simple",
        reason="disabled_by_env",
    )
    assert app.routers == []


def test_simple_platform_integration_defaults_to_disabled_without_env_flag(monkeypatch) -> None:
    app = FakeApp()
    monkeypatch.setenv("MULLU_SIMPLE_PLATFORM_ENABLED", "1")

    def router_factory(runtime: SimplePlatformRuntime, prefix: str) -> object:
        raise AssertionError("explicit env mapping must not fall back to process env")

    result = mount_simple_platform_router_from_env(app, {}, router_factory=router_factory)

    assert result.enabled is False
    assert result.mounted is False
    assert result.prefix == "/api/v1/simple"
    assert result.reason == "disabled_by_env"
    assert app.routers == []


def test_simple_platform_integration_uses_default_prefix() -> None:
    app = FakeApp()

    def router_factory(runtime: SimplePlatformRuntime, prefix: str) -> dict[str, str]:
        return {"prefix": prefix}

    result = mount_simple_platform_router_from_env(
        app,
        {"MULLU_SIMPLE_PLATFORM_ENABLED": "true"},
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is True
    assert result.prefix == "/api/v1/simple"
    assert app.routers == [{"prefix": "/api/v1/simple"}]


def test_simple_platform_start_route_contract_returns_non_executing_guide() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    route_specs = SimplePlatformFastAPIAdapter.route_specs("/simple")
    route_by_handler = {route.handler_name: route for route in route_specs}
    payload = adapter.start_guide()
    guide = payload["payload"]["guide"]

    assert route_by_handler["start_guide"].method == "GET"
    assert route_by_handler["start_guide"].path == "/simple/start"
    assert payload["governed"] is True
    assert payload["status"] == "listed"
    assert guide["execution_allowed"] is False
    assert guide["recommended_path"][0]["command"] == "mullu workflows"
