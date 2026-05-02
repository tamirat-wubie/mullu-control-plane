"""Gateway Operator Capability Console.

Purpose: project governed capability status, admission audits, and plan
    recovery signals into read-only operator surfaces.
Governance scope: operator visibility only; no capability execution or raw
    tool descriptors are exposed.
Dependencies: capability admission gate, command ledger, and plan ledger read
    models.
Invariants:
  - Surface is observational and side-effect free.
  - Capabilities are projected from governed records only.
  - Raw capability fabric extensions and schema internals are not exposed.
  - Pagination is bounded and deterministic.
"""

from __future__ import annotations

from html import escape
from typing import Any


def build_operator_capability_read_model(
    *,
    capability_admission_gate: Any | None = None,
    command_ledger: Any | None = None,
    plan_ledger: Any | None = None,
    domain: str = "",
    risk_level: str = "",
    admission_status: str = "",
    audit_limit: int = 100,
    audit_offset: int = 0,
) -> dict[str, Any]:
    """Build the general operator capability read model."""
    domain_filter = domain.strip()
    risk_filter = risk_level.strip()
    capabilities = _operator_capabilities(
        capability_admission_gate,
        domain_filter=domain_filter,
        risk_filter=risk_filter,
    )
    audits = _admission_audits(
        command_ledger,
        status_filter=admission_status.strip(),
    )
    audit_page, audit_page_meta = _page(
        audits,
        limit=_bounded_limit(audit_limit),
        offset=_bounded_offset(audit_offset),
    )
    plan_summary = _plan_summary(plan_ledger)
    return {
        "enabled": capability_admission_gate is not None,
        "capability_surface": "governed_capability_records",
        "raw_tool_surface_exposed": False,
        "domain_filter": domain_filter,
        "risk_level_filter": risk_filter,
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "domain_counts": _counts(capabilities, "domain"),
        "risk_counts": _counts(capabilities, "risk_level"),
        "approval_required_count": sum(1 for item in capabilities if item.get("requires_approval") is True),
        "sandbox_required_count": sum(1 for item in capabilities if item.get("requires_sandbox") is True),
        "receipt_required_count": sum(1 for item in capabilities if item.get("receipt_required") is True),
        "admission_audits": audit_page,
        "admission_audit_count": len(audits),
        "admission_audit_status_filter": admission_status.strip(),
        "admission_audit_page": audit_page_meta,
        "plan_summary": plan_summary,
    }


def render_operator_capability_console(read_model: dict[str, Any]) -> str:
    """Render a compact read-only HTML operator console."""
    capability_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('domain', '')))}</td>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td>{_bool_cell(item.get('requires_approval'))}</td>"
        f"<td>{_bool_cell(item.get('requires_sandbox'))}</td>"
        f"<td>{escape(', '.join(str(tool) for tool in item.get('allowed_tools', ())))}</td>"
        "</tr>"
        for item in read_model.get("capabilities", ())
    )
    audit_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('command_id', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('reason', '')))}</td>"
        "</tr>"
        for item in read_model.get("admission_audits", ())
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Operator Capabilities</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; }}
    header {{ margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f6f8fa; }}
    .metric {{ display: inline-block; margin-right: 18px; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu Operator Capabilities</h1>
    <span class="metric">Capabilities: {int(read_model.get("capability_count", 0))}</span>
    <span class="metric">Approval required: {int(read_model.get("approval_required_count", 0))}</span>
    <span class="metric">Sandbox required: {int(read_model.get("sandbox_required_count", 0))}</span>
    <span class="metric">Raw tools exposed: {escape(str(read_model.get("raw_tool_surface_exposed", False)).lower())}</span>
  </header>
  <section>
    <h2>Governed Capability Records</h2>
    <table>
      <thead><tr><th>Capability</th><th>Domain</th><th>Risk</th><th>Approval</th><th>Sandbox</th><th>Allowed Tools</th></tr></thead>
      <tbody>{capability_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Admission Audits</h2>
    <table>
      <thead><tr><th>Command</th><th>Status</th><th>Capability</th><th>Reason</th></tr></thead>
      <tbody>{audit_rows}</tbody>
    </table>
  </section>
</body>
</html>"""


def _operator_capabilities(
    capability_admission_gate: Any | None,
    *,
    domain_filter: str,
    risk_filter: str,
) -> list[dict[str, Any]]:
    if capability_admission_gate is None:
        return []
    read_model = capability_admission_gate.read_model()
    raw_capabilities = read_model.get("governed_capability_records", ())
    capabilities: list[dict[str, Any]] = []
    for item in raw_capabilities:
        if not isinstance(item, dict):
            continue
        projected = {
            key: value
            for key, value in item.items()
            if key not in {"extensions", "input_schema_ref", "output_schema_ref"}
        }
        projected.setdefault("domain", _domain_for(str(projected.get("capability_id", ""))))
        if domain_filter and projected.get("domain") != domain_filter:
            continue
        if risk_filter and projected.get("risk_level") != risk_filter:
            continue
        capabilities.append(projected)
    return capabilities


def _admission_audits(command_ledger: Any | None, *, status_filter: str) -> tuple[dict[str, Any], ...]:
    if command_ledger is None or not hasattr(command_ledger, "capability_admission_audits"):
        return ()
    return tuple(command_ledger.capability_admission_audits(status=status_filter, limit=1000))


def _plan_summary(plan_ledger: Any | None) -> dict[str, Any]:
    if plan_ledger is None or not hasattr(plan_ledger, "read_model"):
        return {"enabled": False}
    read_model = plan_ledger.read_model(failed_witness_limit=10, recovery_attempt_limit=10)
    return {
        "enabled": True,
        "plan_certificate_count": int(read_model.get("plan_certificate_count", 0)),
        "failed_plan_witness_count": int(read_model.get("failed_plan_witness_count", 0)),
        "recovery_attempt_count": int(read_model.get("recovery_attempt_count", 0)),
    }


def _counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _domain_for(capability_id: str) -> str:
    if "." not in capability_id:
        return ""
    return capability_id.split(".", 1)[0]


def _bool_cell(value: Any) -> str:
    return "yes" if value is True else "no"


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
