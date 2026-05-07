"""Tests for optional governed swarm control-plane integration.

Purpose: verify the governed swarm router mounts only behind an explicit flag
and fails closed when configuration or optional runtime dependencies are absent.
Governance scope: feature flag, audit-store path, and router mount boundary.
Dependencies: governed_swarm_integration helper.
Invariants: disabled startup mounts nothing, enabled startup requires explicit
audit persistence, and mounted state is recorded.
"""

from __future__ import annotations

import sys
from types import ModuleType
from pathlib import Path

import pytest

from mcoi_runtime.app.governed_swarm_integration import (
    GovernedSwarmBootstrap,
    env_flag,
    extend_runtime_package_path,
    mount_governed_swarm_router_from_env,
)


class FakeApp:
    """Minimal app object with router collection."""

    def __init__(self) -> None:
        self.routers: list[object] = []

    def include_router(self, router: object) -> None:
        self.routers.append(router)


class FakeRuntime:
    """Runtime marker for router factory tests."""

    def __init__(self, path: Path) -> None:
        self.path = path


class FakeAPIRouter:
    """Minimal APIRouter compatible with the governed swarm router factory."""

    def __init__(self, *, prefix: str = "", tags: list[str] | None = None) -> None:
        self.prefix = prefix
        self.tags = tags or []
        self.routes: list[tuple[str, str, object]] = []

    def post(self, path: str):
        def _decorator(handler):
            self.routes.append(("POST", f"{self.prefix}{path}", handler))
            return handler

        return _decorator

    def get(self, path: str):
        def _decorator(handler):
            self.routes.append(("GET", f"{self.prefix}{path}", handler))
            return handler

        return _decorator


def test_env_flag_accepts_explicit_truthy_values_only() -> None:
    assert env_flag("true") is True
    assert env_flag("enabled") is True
    assert env_flag("1") is True
    assert env_flag("") is False
    assert env_flag("false") is False
    assert env_flag(None) is False


def test_governed_swarm_integration_stays_disabled_without_flag() -> None:
    app = FakeApp()

    bootstrap = mount_governed_swarm_router_from_env(app=app, runtime_env={})

    assert isinstance(bootstrap, GovernedSwarmBootstrap)
    assert bootstrap.enabled is False
    assert bootstrap.mounted is False
    assert bootstrap.reason == "disabled"
    assert app.routers == []


def test_governed_swarm_integration_requires_audit_store_when_enabled() -> None:
    app = FakeApp()

    with pytest.raises(RuntimeError, match="AUDIT_STORE_PATH"):
        mount_governed_swarm_router_from_env(
            app=app,
            runtime_env={"MULLU_GOVERNED_SWARM_ENABLED": "true"},
        )

    assert app.routers == []


def test_governed_swarm_integration_mounts_supplied_router_factory(tmp_path: Path) -> None:
    app = FakeApp()
    mounted_runtime: dict[str, FakeRuntime] = {}

    def runtime_factory(path: str | Path) -> FakeRuntime:
        runtime = FakeRuntime(Path(path))
        mounted_runtime["runtime"] = runtime
        return runtime

    def router_factory(runtime: FakeRuntime) -> dict[str, object]:
        return {"runtime_path": runtime.path}

    bootstrap = mount_governed_swarm_router_from_env(
        app=app,
        runtime_env={
            "MULLU_GOVERNED_SWARM_ENABLED": "true",
            "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH": str(tmp_path / "swarm-runs.jsonl"),
        },
        runtime_factory=runtime_factory,
        router_factory=router_factory,
    )

    assert bootstrap.enabled is True
    assert bootstrap.mounted is True
    assert bootstrap.reason == "mounted"
    assert bootstrap.audit_store_path.endswith("swarm-runs.jsonl")
    assert app.routers == [{"runtime_path": mounted_runtime["runtime"].path}]


def test_governed_swarm_integration_reports_missing_runtime_dependency(tmp_path: Path) -> None:
    app = FakeApp()

    with pytest.raises(RuntimeError, match="governed swarm package is required"):
        mount_governed_swarm_router_from_env(
            app=app,
            runtime_env={
                "MULLU_GOVERNED_SWARM_ENABLED": "true",
                "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH": str(tmp_path / "swarm-runs.jsonl"),
            },
        )

    assert app.routers == []


def test_runtime_path_extension_requires_swarm_package(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="must contain mcoi_runtime/swarm"):
        extend_runtime_package_path(tmp_path)

    assert not (tmp_path / "mcoi_runtime" / "swarm").exists()
    assert tmp_path.exists()


def test_runtime_path_extension_adds_external_swarm_package(tmp_path: Path) -> None:
    package_path = tmp_path / "mcoi_runtime"
    swarm_path = package_path / "swarm"
    swarm_path.mkdir(parents=True)

    extended = extend_runtime_package_path(tmp_path)

    assert extended == package_path
    import mcoi_runtime

    assert str(package_path) in mcoi_runtime.__path__
    assert str(tmp_path) in __import__("sys").path


def test_enabled_integration_mounts_external_swarm_router_with_fake_fastapi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_fastapi = ModuleType("fastapi")
    fake_fastapi.APIRouter = FakeAPIRouter
    fake_fastapi.Body = lambda default: default
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    app = FakeApp()
    runtime_root = Path(__file__).resolve().parents[1].parent / "mcoi"

    bootstrap = mount_governed_swarm_router_from_env(
        app=app,
        runtime_env={
            "MULLU_GOVERNED_SWARM_ENABLED": "true",
            "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH": str(tmp_path / "swarm-runs.jsonl"),
            "MULLU_GOVERNED_SWARM_RUNTIME_PATH": str(runtime_root),
        },
    )

    assert bootstrap.enabled is True
    assert bootstrap.mounted is True
    assert len(app.routers) == 1
    router = app.routers[0]
    assert router.prefix == "/api/v1/swarm"
    assert [(method, path) for method, path, _handler in router.routes] == [
        ("POST", "/api/v1/swarm/invoice-runs"),
        ("GET", "/api/v1/swarm/runs/{run_id}"),
        ("GET", "/api/v1/swarm/runs"),
    ]
