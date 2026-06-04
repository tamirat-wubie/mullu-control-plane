"""External dependency health probes for promotion review.

Purpose: provide bounded, operator-invoked reachability checks for gateway,
worker, conformance, and deployment-evidence surfaces without exposing raw
network targets in the read model.
Governance scope: read-only promotion diagnostics.
Dependencies: standard-library HTTP client.
Invariants:
  - Never runs from /health or /ready.
  - Disabled-by-default network probing.
  - Raw endpoint values are not returned.
  - Per-probe failures are bounded and do not abort sibling probes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ExternalProbeSpec:
    """One external surface probe contract."""

    name: str
    env_name: str
    health_path: str


_EXTERNAL_PROBES: tuple[ExternalProbeSpec, ...] = (
    ExternalProbeSpec("gateway", "MULLU_GATEWAY_URL", "/health"),
    ExternalProbeSpec("runtime_conformance", "MULLU_GATEWAY_URL", "/runtime/conformance"),
    ExternalProbeSpec("deployment_witness", "MULLU_GATEWAY_URL", "/deployment/witness"),
    ExternalProbeSpec("capability_worker", "MULLU_CAPABILITY_WORKER_URL", "/health"),
    ExternalProbeSpec("browser_worker", "MULLU_BROWSER_WORKER_URL", "/health"),
    ExternalProbeSpec("document_worker", "MULLU_DOCUMENT_WORKER_URL", "/health"),
    ExternalProbeSpec("voice_worker", "MULLU_VOICE_WORKER_URL", "/health"),
    ExternalProbeSpec("email_calendar_worker", "MULLU_EMAIL_CALENDAR_WORKER_URL", "/health"),
)

_ENABLED_FLAG = "MULLU_HEALTH_EXTERNAL_PROBES_ENABLED"
_TIMEOUT_ENV = "MULLU_HEALTH_EXTERNAL_TIMEOUT_SECONDS"
_REQUIRE_FLAG = "MULLU_HEALTH_REQUIRE_EXTERNAL_DEPENDENCIES"


def external_probe_required(env: Mapping[str, str] | None = None) -> bool:
    """Whether promotion witness should fail when external probes fail."""
    return _env_flag(_REQUIRE_FLAG, env or os.environ)


def collect_external_dependency_health(
    env: Mapping[str, str] | None = None,
    *,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Collect bounded external dependency health.

    Network probing is disabled unless MULLU_HEALTH_EXTERNAL_PROBES_ENABLED is
    truthy. When disabled, configured URLs are reported as configured_unprobed
    rather than healthy/unhealthy. This prevents readiness/liveness checks from
    making remote calls while still exposing a promotion-safe operator surface.
    """
    env = env or os.environ
    enabled = _env_flag(_ENABLED_FLAG, env)
    timeout = _bounded_timeout(env.get(_TIMEOUT_ENV, ""))
    probes = [
        _probe_external(spec, env=env, enabled=enabled, timeout=timeout, opener=opener)
        for spec in _EXTERNAL_PROBES
    ]
    states = {probe["state"] for probe in probes}
    if "unhealthy" in states:
        overall = "unhealthy"
    elif "configured_unprobed" in states or "unconfigured" in states or "protected" in states:
        overall = "degraded"
    else:
        overall = "healthy"
    return {
        "governed": True,
        "enabled": enabled,
        "required_for_witness": external_probe_required(env),
        "overall": overall,
        "timeout_seconds": timeout,
        "probes": probes,
    }


def _probe_external(
    spec: ExternalProbeSpec,
    *,
    env: Mapping[str, str],
    enabled: bool,
    timeout: float,
    opener: Callable[..., Any],
) -> dict[str, Any]:
    configured_value = str(env.get(spec.env_name, "") or "").strip()
    target = _health_url(configured_value, spec.health_path)
    base = {
        "name": spec.name,
        "configured": bool(configured_value),
        "path": spec.health_path,
        "state": "unconfigured",
        "reachable": False,
    }
    if not configured_value:
        return base
    if not target:
        return {**base, "state": "unhealthy", "error_type": "invalid_url"}
    if not enabled:
        return {**base, "state": "configured_unprobed"}
    return {**base, **_http_probe(target, timeout=timeout, opener=opener)}


def _health_url(raw_url: str, path: str) -> str:
    """Return a health URL from a configured endpoint without leaking it."""
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    normalized_path = path if path.startswith("/") else f"/{path}"
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


def _http_probe(target: str, *, timeout: float, opener: Callable[..., Any]) -> dict[str, Any]:
    request = Request(target, method="GET", headers={"User-Agent": "mullu-health-probe"})
    try:
        with opener(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", response.getcode()))
        if 200 <= status_code < 400:
            return {"state": "healthy", "reachable": True, "status_code": status_code}
        return {"state": "unhealthy", "reachable": True, "status_code": status_code}
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return {"state": "protected", "reachable": True, "status_code": int(exc.code)}
        return {"state": "unhealthy", "reachable": True, "status_code": int(exc.code)}
    except (TimeoutError, URLError) as exc:
        return {"state": "unhealthy", "reachable": False, "error_type": type(exc).__name__}
    except Exception as exc:  # pragma: no cover - defensive boundary
        return {"state": "unhealthy", "reachable": False, "error_type": type(exc).__name__}


def _env_flag(name: str, env: Mapping[str, str]) -> bool:
    return str(env.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_timeout(raw: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 2.0
    return max(0.1, min(value, 5.0))
