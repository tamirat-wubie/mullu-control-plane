"""Health-related endpoints extracted from server.py.

Provides liveness, readiness, deep-health, scored-health, and versioned
health-check routes.
"""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Basic health & readiness ──────────────────────────────────────────────


@router.get("/health")
def health():
    surface_health = deps.surface.health()
    return {
        "status": surface_health.get("status", "unknown"),
        "governed": bool(surface_health.get("governed", True)),
    }


@router.get("/ready")
def ready():
    h = health()
    return {"ready": h["status"] == "healthy", **h}


# ── Deep & scored health ─────────────────────────────────────────────────


@router.get("/api/v1/health/deep")
def deep_health_check():
    """System-wide deep health diagnostic."""
    result = deps.deep_health.run()
    return {
        "overall": result.overall.value,
        "components": [
            {"name": c.name, "status": c.status.value, "latency_ms": c.latency_ms, "detail": c.detail}
            for c in result.components
        ],
        "total_latency_ms": result.total_latency_ms,
        "checked_at": result.checked_at,
    }


@router.get("/api/v1/health/score")
def health_score():
    """Unified system health score (0.0-1.0)."""
    result = deps.health_agg.compute()
    return {
        "score": result.overall_score,
        "status": result.status,
        "components": [
            {"name": c.name, "score": c.score, "weight": c.weight, "status": c.status}
            for c in result.components
        ],
        "checked_at": result.checked_at,
    }


# ── Optional extension health ────────────────────────────────────────────


def _extension_state(*, registered: bool, enabled: bool, mounted: bool) -> str:
    """Return the bounded startup state for an optional route extension."""

    if not registered:
        return "unregistered"
    if mounted:
        return "mounted"
    if enabled:
        return "enabled_unmounted"
    return "disabled"


def _extension_bootstrap_read_model(
    dependency_name: str,
    *,
    path_attribute: str,
    path_configured_key: str,
) -> dict[str, object]:
    """Return an operator-safe optional extension bootstrap read model."""

    try:
        bootstrap = deps.get(dependency_name)
    except RuntimeError:
        return {
            "registered": False,
            "enabled": False,
            "mounted": False,
            "state": _extension_state(registered=False, enabled=False, mounted=False),
            "reason": "dependency_not_registered",
            path_configured_key: False,
        }

    enabled = bool(getattr(bootstrap, "enabled", False))
    mounted = bool(getattr(bootstrap, "mounted", False))
    configured_path = str(getattr(bootstrap, path_attribute, "") or "").strip()
    return {
        "registered": True,
        "enabled": enabled,
        "mounted": mounted,
        "state": _extension_state(registered=True, enabled=enabled, mounted=mounted),
        "reason": str(getattr(bootstrap, "reason", "") or "unknown"),
        path_configured_key: bool(configured_path),
    }


def _nested_mind_connector_read_model() -> dict[str, object]:
    """Return nested-mind connector posture without exposing URL or token values."""

    try:
        bootstrap = deps.get("nested_mind_bootstrap")
    except RuntimeError:
        return {
            "registered": False,
            "enabled": False,
            "active": False,
            "state": "unregistered",
            "base_url_configured": False,
            "credential_configured": False,
        }

    enabled = bool(getattr(bootstrap, "enabled", False))
    active = getattr(bootstrap, "connector", None) is not None
    base_url_configured = bool(str(getattr(bootstrap, "base_url", "") or "").strip())
    return {
        "registered": True,
        "enabled": enabled,
        "active": active,
        "state": _optional_feature_state(registered=True, enabled=enabled, active=active),
        "base_url_configured": base_url_configured,
        "credential_configured": bool(getattr(bootstrap, "credential_configured", False)),
    }


def _nested_mind_observation_bridge_read_model() -> dict[str, object]:
    """Return nested-mind observation proposal planner posture."""

    try:
        bootstrap = deps.get("nested_mind_observation_bridge_bootstrap")
    except RuntimeError:
        return {
            "registered": False,
            "enabled": False,
            "active": False,
            "state": "unregistered",
            "planner_configured": False,
        }

    enabled = bool(getattr(bootstrap, "enabled", False))
    active = getattr(bootstrap, "planner", None) is not None
    return {
        "registered": True,
        "enabled": enabled,
        "active": active,
        "state": _optional_feature_state(registered=True, enabled=enabled, active=active),
        "planner_configured": active,
    }


def _nested_mind_observation_submitter_read_model() -> dict[str, object]:
    """Return nested-mind live observation submitter posture without secrets."""

    try:
        bootstrap = deps.get("nested_mind_observation_submitter_bootstrap")
    except RuntimeError:
        return {
            "registered": False,
            "enabled": False,
            "active": False,
            "state": "unregistered",
            "base_url_configured": False,
            "credential_configured": False,
        }

    enabled = bool(getattr(bootstrap, "enabled", False))
    active = getattr(bootstrap, "submitter", None) is not None
    base_url_configured = bool(str(getattr(bootstrap, "base_url", "") or "").strip())
    return {
        "registered": True,
        "enabled": enabled,
        "active": active,
        "state": _optional_feature_state(registered=True, enabled=enabled, active=active),
        "base_url_configured": base_url_configured,
        "credential_configured": bool(getattr(bootstrap, "credential_configured", False)),
    }


def _optional_feature_state(*, registered: bool, enabled: bool, active: bool) -> str:
    """Return a bounded state label for non-router optional features."""

    if not registered:
        return "unregistered"
    if active and enabled:
        return "active"
    if active:
        return "standby"
    if enabled:
        return "enabled_inactive"
    return "disabled"


@router.get("/api/v1/health/extensions")
def extension_health():
    """Optional extension posture without exposing host filesystem paths."""

    return {
        "governed": True,
        "extensions": {
            "governed_swarm": _extension_bootstrap_read_model(
                "governed_swarm_bootstrap",
                path_attribute="audit_store_path",
                path_configured_key="audit_store_configured",
            ),
            "note_memory": _extension_bootstrap_read_model(
                "note_memory_bootstrap",
                path_attribute="store_path",
                path_configured_key="store_configured",
            ),
            "nested_mind": _nested_mind_connector_read_model(),
            "nested_mind_observation_bridge": _nested_mind_observation_bridge_read_model(),
            "nested_mind_observation_submitter": _nested_mind_observation_submitter_read_model(),
        },
    }


# ── Versioned health checks ──────────────────────────────────────────────


@router.get("/api/v1/health/v2")
def health_check_v2():
    """Run health checks with degraded state support."""
    deps.metrics.inc("requests_governed")
    result = deps.health_agg_v2.run()
    return {"health": result.to_dict(), "governed": True}


@router.get("/api/v1/health/v3")
def get_health_v3():
    """Weighted health check with recovery tracking."""
    deps.metrics.inc("requests_governed")
    return deps.health_v3.check_all()
