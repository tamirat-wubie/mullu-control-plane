"""Tests for optional remote health diagnostics."""
from __future__ import annotations

from urllib.error import HTTPError, URLError

from mcoi_runtime.app.health_external import collect_external_dependency_health


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self) -> int:
        return self.status


def test_remote_probe_disabled_does_not_call_network() -> None:
    called = False

    def opener(*args, **kwargs):
        nonlocal called
        called = True
        return _FakeResponse(200)

    report = collect_external_dependency_health(
        {"MULLU_GATEWAY_URL": "https://example.invalid"},
        opener=opener,
    )

    assert called is False
    assert report["enabled"] is False
    assert report["overall"] == "degraded"
    gateway = next(item for item in report["probes"] if item["name"] == "gateway")
    assert gateway["configured"] is True
    assert gateway["state"] == "configured_unprobed"
    assert "example.invalid" not in str(report)


def test_remote_probe_success_when_enabled() -> None:
    requested = []

    def opener(request, *, timeout):
        requested.append((request.full_url, timeout))
        return _FakeResponse(200)

    report = collect_external_dependency_health(
        {
            "MULLU_HEALTH_EXTERNAL_PROBES_ENABLED": "true",
            "MULLU_GATEWAY_URL": "https://gateway.example/base",
            "MULLU_HEALTH_EXTERNAL_TIMEOUT_SECONDS": "0.2",
        },
        opener=opener,
    )

    assert report["enabled"] is True
    assert report["timeout_seconds"] == 0.2
    assert requested
    assert all(url.startswith("https://gateway.example/") for url, _ in requested)
    gateway = next(item for item in report["probes"] if item["name"] == "gateway")
    assert gateway["state"] == "healthy"
    assert gateway["reachable"] is True


def test_remote_probe_protected_is_bounded() -> None:
    def opener(request, *, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", hdrs=None, fp=None)

    report = collect_external_dependency_health(
        {
            "MULLU_HEALTH_EXTERNAL_PROBES_ENABLED": "true",
            "MULLU_GATEWAY_URL": "https://gateway.example",
        },
        opener=opener,
    )

    gateway = next(item for item in report["probes"] if item["name"] == "gateway")
    assert gateway["state"] == "protected"
    assert gateway["reachable"] is True
    assert gateway["status_code"] == 403
    assert report["overall"] == "degraded"


def test_remote_probe_unreachable_is_unhealthy_and_sanitized() -> None:
    def opener(request, *, timeout):
        raise URLError("network-path-secret-value")

    report = collect_external_dependency_health(
        {
            "MULLU_HEALTH_EXTERNAL_PROBES_ENABLED": "true",
            "MULLU_GATEWAY_URL": "https://gateway.example",
        },
        opener=opener,
    )

    gateway = next(item for item in report["probes"] if item["name"] == "gateway")
    assert gateway["state"] == "unhealthy"
    assert gateway["reachable"] is False
    assert gateway["error_type"] == "URLError"
    assert "network-path-secret-value" not in str(report)


def test_remote_probe_invalid_url_is_unhealthy_without_leaking_target() -> None:
    report = collect_external_dependency_health(
        {
            "MULLU_HEALTH_EXTERNAL_PROBES_ENABLED": "true",
            "MULLU_GATEWAY_URL": "not-a-url",
        },
    )

    gateway = next(item for item in report["probes"] if item["name"] == "gateway")
    assert gateway["state"] == "unhealthy"
    assert gateway["error_type"] == "invalid_url"
    assert "not-a-url" not in str(report)
