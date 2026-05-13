"""Shared response shape and helpers for /domains/* endpoints."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import MusiaAuthContext
from mcoi_runtime.app.routers.musia_governance_bridge import gate_domain_run
from mcoi_runtime.substrate.registry_store import STORE


class DomainOutcome(BaseModel):
    """Common envelope returned by every /domains/* endpoint."""

    domain: str
    governance_status: str
    audit_trail_id: str
    risk_flags: list[str]
    plan: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str
    run_id: str | None = None  # populated when persist_run=true and merge succeeds


def _gate_or_blocked_outcome(
    *,
    domain: str,
    tenant_id: str,
    summary: str,
) -> DomainOutcome | None:
    """Run the domain-level chain gate. Returns None on pass, a blocked
    DomainOutcome on rejection. The caller short-circuits when this
    returns non-None, skipping the cycle entirely.

    v4.16.0+. The audit_trail_id is a fresh UUID identifying this gate
    decision so operators correlating chain logs with domain responses
    have a stable handle.
    """
    ok, reason = gate_domain_run(
        domain=domain,
        tenant_id=tenant_id,
        summary=summary,
    )
    if ok:
        return None
    return DomainOutcome(
        domain=domain,
        governance_status=f"blocked: chain_rejected ({reason})",
        audit_trail_id=str(uuid4()),
        risk_flags=[f"chain_gate_rejected: {reason}"],
        plan=[],
        metadata={"chain_gate": "rejected", "reason": reason},
        tenant_id=tenant_id,
        run_id=None,
    )


def _resolve_domain_auth(
    persist_run: bool,
    auth: MusiaAuthContext,
) -> str:
    """v4.26.0 (audit F13 fix): scope check matched to actual side-effect.

    When ``persist_run=False`` the endpoint is read-only (cycle output
    returned, nothing written). ``musia.read`` is sufficient.

    When ``persist_run=True`` the endpoint calls ``state.merge_run(...)``
    which writes captured constructs into the tenant's persistent registry.
    ``musia.write`` is required. Pre-v4.26 the same ``Depends(require_read)``
    gated both paths — read-scope credential could persist constructs by
    setting one query parameter. Audit P3 F13.

    Returns the validated tenant_id; raises 403 on insufficient scope.
    """
    required = "musia.write" if persist_run else "musia.read"
    granted = auth.scopes
    if "*" not in granted and required not in granted:
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"missing scope: {required}",
                "subject": auth.subject,
                "granted_scopes": sorted(granted),
            },
        )
    return auth.tenant_id


def _maybe_persist_run(
    tenant_id: str,
    persist_run: bool,
    captured: list,
    risk_flags: list[str],
    *,
    domain: str | None = None,
    summary: str | None = None,
) -> str | None:
    """If persist_run is set, merge captured constructs into the tenant registry.

    v4.12.0: ``domain`` and ``summary`` are stamped on each construct's
    metadata as ``run_domain`` / ``run_summary``, joining ``run_id`` and
    ``run_timestamp``. This makes a persisted run self-describing without
    requiring the caller to query the registry by run_id and reconstruct.

    Returns the run_id when merge succeeds. On quota rejection, appends
    a risk flag to risk_flags (mutates) and returns None — the cycle
    result is still returned to the caller, just without persistence.
    """
    if not persist_run or not captured:
        return None
    state = STORE.get_or_create(tenant_id)
    run_id = f"run-{uuid4().hex[:12]}"
    ok, reason = state.merge_run(
        run_id,
        captured,
        domain=domain,
        summary=summary,
    )
    if not ok:
        risk_flags.append(f"persist_run_rejected: {reason}")
        return None
    return run_id


def _kind_or_400(enum_cls, value: str):
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_kind",
                "value": value,
                "valid": [e.value for e in enum_cls],
            },
        )
