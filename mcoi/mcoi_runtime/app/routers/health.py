"""Health-related endpoints extracted from server.py.

Provides liveness (/health), dependency-aware readiness (/ready),
deep-health, scored-health, and versioned health-check routes.

Liveness vs readiness:
  - /health is a shallow liveness signal (is the process up). It is what the
    container HEALTHCHECK probes and must stay cheap and dependency-free.
  - /ready is a readiness gate: it consults the deep-health probes and fails
    closed (HTTP 503) when a dependency is unhealthy, plus enforces
    promotion-grade policy in pilot/production.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.deep_health import SystemHealth

router = APIRouter()


# ── Basic health & readiness ──────────────────────────────────────────────


@router.get("/health")
def health():
    surface_health = deps.surface.health()
    return {
        "status": surface_health.get("status", "unknown"),
        "governed": bool(surface_health.get("governed", True)),
    }


# Environments where readiness applies strict promotion-grade gates.
_STRICT_ENVIRONMENTS = ("pilot", "production")


def _environment() -> str:
    """Best-effort deployment environment name (never raises)."""
    try:
        return str(deps.surface.manifest.environment)
    except Exception:  # pragma: no cover - defensive; surface is always wired
        return "unknown"


def evaluate_readiness(health_report: SystemHealth, environment: str) -> dict[str, Any]:
    """Pure readiness verdict over a deep-health report + environment.

    Ready iff no component is ``unhealthy``. ``degraded`` does not block. In
    pilot/production two promotion-grade gates also apply (defense in depth —
    the LLM bootstrap already fails closed on a stub backend): the LLM backend
    must not be ``stub`` and field encryption must be available.
    """
    components = {c.name: c for c in health_report.components}
    checks = {name: component.status.value for name, component in components.items()}
    blocking = [
        name for name, component in components.items()
        if component.status.value == "unhealthy"
    ]

    if environment in _STRICT_ENVIRONMENTS:
        llm = components.get("llm")
        if llm is not None and llm.detail.get("provider") == "stub":
            blocking.append("llm:stub_backend_forbidden")
        field_encryption = components.get("field_encryption")
        if field_encryption is not None and not field_encryption.detail.get("aes_available", False):
            blocking.append("field_encryption:unavailable")

    return {
        "ready": not blocking,
        "status": health_report.overall.value,
        "governed": True,
        "environment": environment,
        "checks": checks,
        "blocking": blocking,
    }


@router.get("/ready")
def ready(response: Response):
    """Dependency-aware readiness gate; returns HTTP 503 when not ready."""
    report = evaluate_readiness(deps.deep_health.run(), _environment())
    if not report["ready"]:
        response.status_code = 503
    return report


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


# ── Promotion witness ────────────────────────────────────────────────────
#
# A deliberate, operator-invoked promotion-grade proof that the governed
# receipt chain works end-to-end at runtime. Unlike /health and /ready it
# MUTATES state (persists one synthetic proof + audit receipt per call), so it
# is disabled by default and must be explicitly enabled in the promotion
# environment. It is POST (an action, not a probe) and is never invoked by the
# liveness/readiness probes.

_WITNESS_FLAG = "MULLU_HEALTH_WITNESS_ENABLED"
_WITNESS_TENANT = "system"
_WITNESS_ACTOR = "health-witness"


def _witness_enabled() -> bool:
    """Whether the promotion-witness endpoint is enabled (default off)."""
    return os.environ.get(_WITNESS_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


@router.post("/api/v1/health/witness")
def promotion_witness(response: Response):
    """Prove the governed proof + audit chain at runtime (promotion gate).

    Disabled by default — set ``MULLU_HEALTH_WITNESS_ENABLED=true`` in the
    promotion environment. Each call issues ONE bounded synthetic governed
    decision (tenant ``system``, actor ``health-witness``), persists its proof
    and audit receipts, then verifies both. Returns HTTP 503 when the witness
    cannot be produced or verified.
    """
    if not _witness_enabled():
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "error_code": "not_found"},
        )

    errors: list[str] = []

    # 1. Synthetic governed decision -> proof receipt (real wired bridge).
    proof = deps.proof_bridge.certify_governance_decision(
        tenant_id=_WITNESS_TENANT,
        endpoint="/api/v1/health/witness",
        guard_results=[
            {
                "guard_name": "health_witness",
                "allowed": True,
                "reason": "synthetic promotion witness",
            }
        ],
        decision="allowed",
        actor_id=_WITNESS_ACTOR,
        reason="promotion witness",
    )
    receipt = proof.capsule.receipt
    proof_verified = bool(deps.proof_bridge.verify_receipt(receipt))
    if not proof_verified:
        errors.append("proof_receipt_unverified")

    # 2. Audit receipt + hash-chain verification (real wired trail).
    entry = deps.audit_trail.record(
        action="health.witness",
        actor_id=_WITNESS_ACTOR,
        tenant_id=_WITNESS_TENANT,
        target="control-plane",
        outcome="success",
        detail={"proof_receipt_id": receipt.receipt_id},
    )
    chain_valid, chain_length = deps.audit_trail.verify_chain()
    if not chain_valid:
        errors.append("audit_chain_invalid")

    if errors:
        response.status_code = 503
    return {
        "witness_id": f"health-witness-{receipt.receipt_id}",
        "outcome": "verified" if not errors else "failed",
        "governed": True,
        "environment": _environment(),
        "proof": {
            "receipt_id": receipt.receipt_id,
            "receipt_hash": proof.receipt_hash,
            "verified": proof_verified,
        },
        "audit": {
            "entry_id": entry.entry_id,
            "chain_valid": chain_valid,
            "chain_length": chain_length,
        },
        "errors": errors,
    }
