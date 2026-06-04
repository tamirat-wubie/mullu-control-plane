"""Readiness gate test lane — proves /ready is dependency-aware.

These tests fail if any of the readiness invariants regress:
  - /ready reports ready while a required dependency component is missing.
  - /ready reports ready while a dependency component is unhealthy.
  - DB unreachable / proof bridge uncallable / audit chain broken all surface as
    an ``unhealthy`` component via DeepHealthChecker.
  - pilot/production reports ready while the LLM backend is ``stub``.
  - pilot/production reports ready while field encryption is unavailable.
  - pilot/production reports ready while PII scanning is disabled.
  - dev/test is not incorrectly gated on stub LLM / encryption / PII posture.

The policy is verified as a pure function (``evaluate_readiness``); the real
``DeepHealthChecker`` is used to prove the throwing-dependency path; and a
TestClient integration test proves the probes are actually wired into the app.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from mcoi_runtime.app.routers.health import evaluate_readiness
from mcoi_runtime.core.deep_health import (
    ComponentHealth,
    DeepHealthChecker,
    HealthStatus,
    SystemHealth,
)

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    FASTAPI_AVAILABLE = False


_BASELINE_COMPONENTS = (
    "store",
    "llm",
    "proof_bridge",
    "audit",
    "rate_limiter",
    "tenant_budget",
    "tenant_gating",
    "content_safety",
)

_STRICT_COMPONENTS = ("field_encryption", "pii_scanner")


def _component(name: str, status: str, **detail: object) -> ComponentHealth:
    return ComponentHealth(
        name=name,
        status=HealthStatus(status),
        latency_ms=0.1,
        detail={"status": status, **detail},
    )


def _healthy_baseline_components() -> list[ComponentHealth]:
    return [
        _component("store", "healthy"),
        _component("llm", "healthy", provider="anthropic"),
        _component("proof_bridge", "healthy"),
        _component("audit", "healthy", chain_valid=True),
        _component("rate_limiter", "healthy"),
        _component("tenant_budget", "healthy"),
        _component("tenant_gating", "healthy"),
        _component("content_safety", "healthy", filters_configured=True),
    ]


def _healthy_strict_components() -> list[ComponentHealth]:
    return [
        _component("field_encryption", "healthy", aes_available=True),
        _component("pii_scanner", "healthy", enabled=True),
    ]


def _report(*components: ComponentHealth) -> SystemHealth:
    if any(c.status == HealthStatus.UNHEALTHY for c in components):
        overall = HealthStatus.UNHEALTHY
    elif any(c.status == HealthStatus.DEGRADED for c in components):
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.HEALTHY
    return SystemHealth(
        overall=overall,
        components=tuple(components),
        total_latency_ms=1.0,
        checked_at="2026-01-01T00:00:00Z",
    )


# ── Pure policy: the healthy baseline ─────────────────────────────────────


def test_all_healthy_is_ready() -> None:
    report = _report(*_healthy_baseline_components(), *_healthy_strict_components())
    verdict = evaluate_readiness(report, "production")
    assert verdict["ready"] is True
    assert verdict["status"] == "healthy"
    assert verdict["missing"] == []
    assert verdict["blocking"] == []


def test_degraded_advisory_component_does_not_block() -> None:
    report = _report(
        *_healthy_baseline_components(),
        _component("metrics", "degraded"),
    )
    verdict = evaluate_readiness(report, "development")
    assert verdict["ready"] is True
    assert verdict["status"] == "degraded"


# ── Pure policy: missing / unhealthy dependencies block readiness ─────────


@pytest.mark.parametrize("missing", _BASELINE_COMPONENTS)
def test_missing_required_component_blocks_readiness(missing: str) -> None:
    components = [component for component in _healthy_baseline_components() if component.name != missing]
    verdict = evaluate_readiness(_report(*components), "development")
    assert verdict["ready"] is False
    assert missing in verdict["missing"]
    assert f"{missing}:missing" in verdict["blocking"]


@pytest.mark.parametrize("failed", ["store", "proof_bridge", "audit", "content_safety"])
def test_unhealthy_dependency_blocks_readiness(failed: str) -> None:
    """A dead DB, an uncallable proof bridge, a broken audit chain, or a
    disabled first-line content-safety chain must make the service not-ready."""
    components = [
        _component(c.name, "unhealthy") if c.name == failed else c
        for c in _healthy_baseline_components()
    ]
    verdict = evaluate_readiness(_report(*components), "production")
    assert verdict["ready"] is False
    assert failed in verdict["blocking"]


def test_real_checker_throwing_probe_is_not_ready() -> None:
    """End-to-end through the real DeepHealthChecker: a probe that raises
    (e.g. ``store.ledger_count()`` against a dead Postgres) becomes an
    unhealthy component, and /ready must refuse."""
    checker = DeepHealthChecker(clock=lambda: "2026-01-01T00:00:00Z")

    def _dead_store() -> dict[str, object]:
        raise ConnectionError("database unavailable")

    checker.register("store", _dead_store)
    for component in _healthy_baseline_components():
        if component.name != "store":
            checker.register(component.name, lambda component=component: component.detail)

    verdict = evaluate_readiness(checker.run(), "production")
    assert verdict["ready"] is False
    assert "store" in verdict["blocking"]


# ── Pure policy: promotion-grade gates are env-aware ──────────────────────


def test_dev_allows_stub_llm_encryption_and_pii_advisory_posture() -> None:
    report = _report(
        *[
            _component("llm", "healthy", provider="stub") if c.name == "llm" else c
            for c in _healthy_baseline_components()
        ],
        _component("field_encryption", "healthy", aes_available=False),
        _component("pii_scanner", "degraded", enabled=False),
    )
    verdict = evaluate_readiness(report, "development")
    assert verdict["ready"] is True
    assert verdict["blocking"] == []


@pytest.mark.parametrize("env", ["pilot", "production"])
def test_production_blocks_stub_llm(env: str) -> None:
    report = _report(
        *[
            _component("llm", "healthy", provider="stub") if c.name == "llm" else c
            for c in _healthy_baseline_components()
        ],
        *_healthy_strict_components(),
    )
    verdict = evaluate_readiness(report, env)
    assert verdict["ready"] is False
    assert "llm:stub_backend_forbidden" in verdict["blocking"]


@pytest.mark.parametrize("env", ["pilot", "production"])
def test_production_requires_field_encryption(env: str) -> None:
    report = _report(
        *_healthy_baseline_components(),
        _component("field_encryption", "healthy", aes_available=False),
        _component("pii_scanner", "healthy", enabled=True),
    )
    verdict = evaluate_readiness(report, env)
    assert verdict["ready"] is False
    assert "field_encryption:unavailable" in verdict["blocking"]


@pytest.mark.parametrize("env", ["pilot", "production"])
def test_production_requires_pii_scanner(env: str) -> None:
    report = _report(
        *_healthy_baseline_components(),
        _component("field_encryption", "healthy", aes_available=True),
        _component("pii_scanner", "degraded", enabled=False),
    )
    verdict = evaluate_readiness(report, env)
    assert verdict["ready"] is False
    assert "pii_scanner:disabled" in verdict["blocking"]


@pytest.mark.parametrize("env", ["pilot", "production"])
def test_production_missing_strict_component_blocks(env: str) -> None:
    report = _report(*_healthy_baseline_components())
    verdict = evaluate_readiness(report, env)
    assert verdict["ready"] is False
    assert "field_encryption:missing" in verdict["blocking"]
    assert "pii_scanner:missing" in verdict["blocking"]


def test_production_ready_with_real_provider_encryption_and_pii() -> None:
    report = _report(*_healthy_baseline_components(), *_healthy_strict_components())
    verdict = evaluate_readiness(report, "production")
    assert verdict["ready"] is True
    assert verdict["blocking"] == []


def test_no_default_llm_backend_is_unhealthy_everywhere() -> None:
    """An unconfigured LLM bridge is unhealthy regardless of environment."""
    components = [
        _component("llm", "unhealthy") if c.name == "llm" else c
        for c in _healthy_baseline_components()
    ]
    assert evaluate_readiness(_report(*components), "development")["ready"] is False
    assert evaluate_readiness(_report(*components, *_healthy_strict_components()), "production")["ready"] is False


# ── Integration: probes are actually wired into the app ───────────────────


@pytest.fixture
def client() -> Iterator[TestClient]:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    yield TestClient(app)


def test_ready_endpoint_is_ready_in_dev(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["governed"] is True
    assert body["blocking"] == []
    for name in (*_BASELINE_COMPONENTS, *_STRICT_COMPONENTS):
        assert name in body["checks"]


def test_deep_health_includes_required_components(client: TestClient) -> None:
    resp = client.get("/api/v1/health/deep")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()["components"]}
    assert set(_BASELINE_COMPONENTS) <= names
    assert set(_STRICT_COMPONENTS) <= names


def test_dependency_health_route_is_deep_health_derived(client: TestClient) -> None:
    resp = client.get("/api/v1/health/dependencies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["governed"] is True
    assert body["dependencies"]
    names = {component["name"] for component in body["dependencies"]}
    assert set(_BASELINE_COMPONENTS) <= names
