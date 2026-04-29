"""Gateway MCP Operator Read Model.

Purpose: Project certified MCP capability fabric entries, authority bindings,
    and governed MCP execution audits into one operator-facing view.
Governance scope: MCP capability visibility, authority evidence, execution
    audit filtering, and bounded pagination.
Dependencies: command capability admission gate, authority mesh store, and
    governed MCP executor audit API.
Invariants:
  - Read model is observational and side-effect free.
  - Only MCP-domain capability and authority records are included.
  - Audit pagination is bounded and deterministic.
  - Missing optional runtime components produce explicit disabled sections.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


def build_mcp_operator_read_model(
    *,
    capability_admission_gate: Any | None = None,
    authority_mesh_store: Any | None = None,
    mcp_executor: Any | None = None,
    capability_id: str = "",
    audit_status: str = "",
    audit_limit: int = 100,
    audit_offset: int = 0,
) -> dict[str, Any]:
    """Build the MCP operator read model from available runtime surfaces."""
    capability_filter = capability_id.strip()
    capabilities = _mcp_capabilities(capability_admission_gate, capability_filter=capability_filter)
    ownership = _mcp_ownership(authority_mesh_store, capability_filter=capability_filter)
    approval_policies = _mcp_approval_policies(authority_mesh_store, capability_filter=capability_filter)
    escalation_policies = _mcp_escalation_policies(authority_mesh_store)
    audits = _mcp_audits(
        mcp_executor,
        capability_filter=capability_filter,
        status_filter=audit_status.strip(),
    )
    audit_page, audit_page_meta = _page(
        audits,
        limit=_bounded_limit(audit_limit),
        offset=_bounded_offset(audit_offset),
    )
    return {
        "enabled": capability_admission_gate is not None,
        "executor_enabled": mcp_executor is not None,
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "ownership": ownership,
        "ownership_count": len(ownership),
        "approval_policies": approval_policies,
        "approval_policy_count": len(approval_policies),
        "escalation_policies": escalation_policies,
        "escalation_policy_count": len(escalation_policies),
        "execution_audits": audit_page,
        "execution_audit_count": len(audits),
        "execution_audit_status_filter": audit_status.strip(),
        "execution_audit_page": audit_page_meta,
        "capability_filter": capability_filter,
    }


def _mcp_capabilities(capability_admission_gate: Any | None, *, capability_filter: str) -> list[dict[str, Any]]:
    if capability_admission_gate is None:
        return []
    read_model = capability_admission_gate.read_model()
    raw_capabilities = read_model.get("capabilities", ())
    capabilities: list[dict[str, Any]] = []
    for item in raw_capabilities:
        if not isinstance(item, dict) or item.get("domain") != "mcp":
            continue
        if capability_filter and item.get("capability_id") != capability_filter:
            continue
        capabilities.append(dict(item))
    return capabilities


def _mcp_ownership(authority_mesh_store: Any | None, *, capability_filter: str) -> list[dict[str, Any]]:
    if authority_mesh_store is None:
        return []
    return [
        asdict(item)
        for item in authority_mesh_store.list_ownership()
        if _matches_mcp_ref(getattr(item, "resource_ref", ""), capability_filter)
    ]


def _mcp_approval_policies(authority_mesh_store: Any | None, *, capability_filter: str) -> list[dict[str, Any]]:
    if authority_mesh_store is None:
        return []
    return [
        asdict(item)
        for item in authority_mesh_store.list_approval_policies()
        if _matches_mcp_ref(getattr(item, "capability", ""), capability_filter)
    ]


def _mcp_escalation_policies(authority_mesh_store: Any | None) -> list[dict[str, Any]]:
    if authority_mesh_store is None:
        return []
    return [
        asdict(item)
        for item in authority_mesh_store.list_escalation_policies()
        if str(getattr(item, "policy_id", "")).startswith("mcp-escalation-")
    ]


def _mcp_audits(mcp_executor: Any | None, *, capability_filter: str, status_filter: str) -> tuple[dict[str, Any], ...]:
    if mcp_executor is None:
        return ()
    records = mcp_executor.audit_records(status=status_filter, limit=1000)
    return tuple(
        asdict(record)
        for record in records
        if not capability_filter or record.capability_id == capability_filter
    )


def _matches_mcp_ref(value: str, capability_filter: str) -> bool:
    ref = str(value)
    if not ref.startswith("mcp."):
        return False
    return not capability_filter or ref == capability_filter


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 500))


def _bounded_offset(offset: int) -> int:
    return max(0, int(offset))


def _page(items: tuple[dict[str, Any], ...], *, limit: int, offset: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total = len(items)
    page = list(items[offset:offset + limit])
    next_offset = offset + limit if offset + limit < total else None
    return page, {
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset,
    }
