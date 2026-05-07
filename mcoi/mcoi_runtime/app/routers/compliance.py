"""Compliance Proof Export — governed evidence packages for auditors and buyers.

Transforms internal audit trails, policy decisions, verification outcomes,
and coordination state into structured proof packages that external parties
can inspect without platform access.

Three export shapes:
- Audit Package: action history, policy decisions, verification outcomes
- Incident Package: failed/blocked actions, override history, affected entities
- Compliance Mapping: structured evidence mapped to governance frameworks
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Request Models ────────────────────────────────────────────────────


class AuditPackageRequest(BaseModel):
    tenant_id: str = ""
    from_date: str = ""
    to_date: str = ""
    limit: int = 1000
    include_chain_verification: bool = True


class IncidentPackageRequest(BaseModel):
    tenant_id: str = ""
    limit: int = 500


class ComplianceMappingRequest(BaseModel):
    tenant_id: str = ""
    framework: str = "generic"  # "generic", "soc2", "iso27001", "eu_ai_act"
    limit: int = 1000


# ── Package Builders ──────────────────────────────────────────────────


def _build_audit_package(
    tenant_id: str,
    limit: int,
    include_chain: bool,
) -> dict[str, Any]:
    """Build a self-contained audit evidence package."""
    entries = deps.audit_trail.query(
        tenant_id=tenant_id or None,
        limit=limit,
    )
    chain_valid = None
    if include_chain:
        chain_valid = deps.audit_trail.verify_chain()

    now = datetime.now(timezone.utc).isoformat()
    content = json.dumps({
        "entries": [dataclasses.asdict(e) for e in entries],
        "chain_valid": chain_valid,
    }, sort_keys=True, default=str)
    package_hash = sha256(content.encode()).hexdigest()

    return {
        "package_type": "audit",
        "generated_at": now,
        "package_hash": package_hash,
        "tenant_id": tenant_id or "all",
        "entry_count": len(entries),
        "chain_verification": chain_valid,
        "actions_summary": _summarize_actions(entries),
        "outcomes_summary": _summarize_outcomes(entries),
        "entries": [
            {
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "timestamp": e.recorded_at,
                "entry_hash": e.entry_hash,
            }
            for e in entries
        ],
    }


def _build_incident_package(
    tenant_id: str,
    limit: int,
) -> dict[str, Any]:
    """Build an incident evidence package — blocked/failed actions only."""
    all_entries = deps.audit_trail.query(
        tenant_id=tenant_id or None,
        limit=limit * 2,
    )
    incidents = [
        e for e in all_entries
        if e.outcome in ("denied", "error", "blocked", "failed")
    ][:limit]

    now = datetime.now(timezone.utc).isoformat()
    content = json.dumps({
        "incidents": [dataclasses.asdict(e) for e in incidents],
    }, sort_keys=True, default=str)
    package_hash = sha256(content.encode()).hexdigest()

    return {
        "package_type": "incident",
        "generated_at": now,
        "package_hash": package_hash,
        "tenant_id": tenant_id or "all",
        "incident_count": len(incidents),
        "blocked_count": sum(1 for e in incidents if e.outcome in ("denied", "blocked")),
        "error_count": sum(1 for e in incidents if e.outcome in ("error", "failed")),
        "incidents": [
            {
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "detail": e.detail,
                "timestamp": e.recorded_at,
                "entry_hash": e.entry_hash,
            }
            for e in incidents
        ],
    }


def _build_compliance_mapping(
    tenant_id: str,
    framework: str,
    limit: int,
) -> dict[str, Any]:
    """Build governance evidence mapped to compliance framework controls."""
    entries = deps.audit_trail.query(
        tenant_id=tenant_id or None,
        limit=limit,
    )
    now = datetime.now(timezone.utc).isoformat()

    # Map actions to generic compliance control categories
    controls = {
        "access_control": [],
        "audit_logging": [],
        "policy_enforcement": [],
        "change_management": [],
        "incident_response": [],
        "data_governance": [],
    }
    for e in entries:
        action = e.action
        entry_ref = {
            "action": action,
            "outcome": e.outcome,
            "timestamp": e.recorded_at,
            "entry_hash": e.entry_hash,
        }
        if "auth" in action or "key" in action or "session" in action:
            controls["access_control"].append(entry_ref)
        if "audit" in action or "trail" in action:
            controls["audit_logging"].append(entry_ref)
        if "policy" in action or "guard" in action or "budget" in action:
            controls["policy_enforcement"].append(entry_ref)
        if "config" in action or "deploy" in action or "checkpoint" in action:
            controls["change_management"].append(entry_ref)
        if "error" in (e.outcome or "") or "denied" in (e.outcome or ""):
            controls["incident_response"].append(entry_ref)
        if "data" in action or "export" in action or "ledger" in action:
            controls["data_governance"].append(entry_ref)

    content = json.dumps(controls, sort_keys=True, default=str)
    package_hash = sha256(content.encode()).hexdigest()

    return {
        "package_type": "compliance_mapping",
        "framework": framework,
        "generated_at": now,
        "package_hash": package_hash,
        "tenant_id": tenant_id or "all",
        "total_evidence_entries": len(entries),
        "controls": {
            k: {"count": len(v), "entries": v[:20]}
            for k, v in controls.items()
        },
    }


def _summarize_actions(entries: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.action] = counts.get(e.action, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:20])


def _summarize_outcomes(entries: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        outcome = e.outcome or "unknown"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/api/v1/compliance/audit-package")
def export_audit_package(req: AuditPackageRequest):
    """Export a self-contained audit evidence package with chain verification."""
    deps.metrics.inc("requests_governed")
    package = _build_audit_package(
        req.tenant_id, req.limit, req.include_chain_verification,
    )
    deps.audit_trail.record(
        action="compliance.export.audit_package",
        actor_id="api",
        tenant_id=req.tenant_id or "system",
        target="audit_package",
        outcome="success",
        detail={"entry_count": package["entry_count"]},
    )
    return {**package, "governed": True}


@router.post("/api/v1/compliance/incident-package")
def export_incident_package(req: IncidentPackageRequest):
    """Export blocked/failed action evidence for incident review."""
    deps.metrics.inc("requests_governed")
    package = _build_incident_package(req.tenant_id, req.limit)
    deps.audit_trail.record(
        action="compliance.export.incident_package",
        actor_id="api",
        tenant_id=req.tenant_id or "system",
        target="incident_package",
        outcome="success",
        detail={"incident_count": package["incident_count"]},
    )
    return {**package, "governed": True}


@router.post("/api/v1/compliance/mapping")
def export_compliance_mapping(req: ComplianceMappingRequest):
    """Export governance evidence mapped to compliance framework controls."""
    deps.metrics.inc("requests_governed")
    package = _build_compliance_mapping(
        req.tenant_id, req.framework, req.limit,
    )
    deps.audit_trail.record(
        action="compliance.export.mapping",
        actor_id="api",
        tenant_id=req.tenant_id or "system",
        target=f"compliance_mapping:{req.framework}",
        outcome="success",
        detail={"framework": req.framework},
    )
    return {**package, "governed": True}


@router.get("/api/v1/compliance/summary")
def compliance_summary():
    """Summary of available compliance evidence."""
    deps.metrics.inc("requests_governed")
    trail_summary = deps.audit_trail.summary()
    return {
        "total_audit_entries": trail_summary.get("entry_count", 0),
        "chain_intact": deps.audit_trail.verify_chain(),
        "available_exports": ["audit_package", "incident_package", "compliance_mapping"],
        "supported_frameworks": ["generic", "soc2", "iso27001", "eu_ai_act"],
        "governed": True,
    }
