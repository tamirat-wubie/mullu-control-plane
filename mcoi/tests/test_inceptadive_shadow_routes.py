"""Focused tests for read-only InceptaDive Shadow Pass posture routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.shadow import router


class _Metrics:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def inc(self, name: str, val: int = 1) -> None:
        del val
        self.calls.append(name)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_shadow_health_route_returns_redacted_read_model() -> None:
    previous_store = dict(deps._store)
    metrics = _Metrics()
    deps._store.clear()
    deps.set("metrics", metrics)
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().get("/api/v1/health/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    shadow = payload["shadow"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert shadow["status"] == "ready"
    assert shadow["execution_authority"] is False
    assert shadow["raw_request_text_exposed"] is False
    assert shadow["private_memory_exposed"] is False
    assert "requests_governed" in metrics.calls


def test_shadow_console_route_returns_counts_without_raw_text() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    summary = payload["summary"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["status"] == "ready"
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert summary["recent_result_count"] == 0
    assert summary["receipt_count"] == 0
    assert summary["execution_authority"] is False
    assert summary["raw_request_text_exposed"] is False
    assert summary["private_memory_exposed"] is False
    assert "deploy it" not in str(payload)
    assert "delete production logs" not in str(payload)


def test_shadow_routes_fallback_when_runtime_unregistered() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    try:
        health_response = _client().get("/api/v1/health/shadow")
        console_response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    health_payload = health_response.json()
    console_payload = console_response.json()
    assert health_response.status_code == 200
    assert console_response.status_code == 200
    assert health_payload["registered"] is False
    assert console_payload["registered"] is False
    assert health_payload["shadow"]["execution_authority"] is False
    assert console_payload["summary"]["execution_authority"] is False


def test_shadow_routes_respect_disabled_runtime_posture() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"}),
    )
    try:
        health_response = _client().get("/api/v1/health/shadow")
        console_response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    health_payload = health_response.json()
    console_payload = console_response.json()
    assert health_payload["shadow"]["status"] == "disabled"
    assert health_payload["shadow"]["enabled"] is False
    assert console_payload["status"] == "disabled"
    assert console_payload["summary"]["enabled"] is False
    assert health_payload["execution_authority"] is False
    assert console_payload["execution_authority"] is False
