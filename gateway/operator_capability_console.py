"""Gateway Operator Capability Console.

Purpose: project governed capability status, admission audits, and plan
    recovery signals into read-only operator surfaces.
Governance scope: operator visibility only; no capability execution or raw
    tool descriptors are exposed.
Dependencies: capability admission gate, autonomous capability upgrade loop,
    command ledger, and plan ledger read models.
Invariants:
  - Surface is observational and side-effect free.
  - Capabilities are projected from governed records only.
  - Improvement portfolios are activation-blocked proposal witnesses only.
  - Raw capability fabric extensions and schema internals are not exposed.
  - Pagination is bounded and deterministic.
"""

from __future__ import annotations

from html import escape
from typing import Any

from gateway.autonomous_capability_upgrade import (
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
)


CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF = "urn:mullusi:schema:capability-improvement-portfolio:1"
CAPABILITY_IMPROVEMENT_PORTFOLIO_HREF = "/runtime/self/capability-improvement-portfolio"


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
    include_improvement_portfolio: bool = False,
    improvement_generated_at: str = "1970-01-01T00:00:00+00:00",
    improvement_candidate_limit: int = 5,
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
    improvement_portfolio = (
        _improvement_portfolio_summary(
            capabilities,
            generated_at=improvement_generated_at,
            limit=improvement_candidate_limit,
        )
        if include_improvement_portfolio and capabilities
        else _default_improvement_portfolio()
    )
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
        "maturity_counts": _counts(capabilities, "maturity_level"),
        "production_ready_count": sum(1 for item in capabilities if item.get("production_ready") is True),
        "autonomy_ready_count": sum(1 for item in capabilities if item.get("autonomy_ready") is True),
        "approval_required_count": sum(1 for item in capabilities if item.get("requires_approval") is True),
        "sandbox_required_count": sum(1 for item in capabilities if item.get("requires_sandbox") is True),
        "receipt_required_count": sum(1 for item in capabilities if item.get("receipt_required") is True),
        "admission_audits": audit_page,
        "admission_audit_count": len(audits),
        "admission_audit_status_filter": admission_status.strip(),
        "admission_audit_page": audit_page_meta,
        "plan_summary": plan_summary,
        "improvement_portfolio": improvement_portfolio,
    }


def render_operator_capability_console(read_model: dict[str, Any]) -> str:
    """Render a compact read-only HTML operator console."""
    capability_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('domain', '')))}</td>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td>{escape(str(item.get('maturity_level', '')))}</td>"
        f"<td>{_bool_cell(item.get('production_ready'))}</td>"
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
    portfolio = read_model.get("improvement_portfolio", {})
    portfolio_href = escape(str(portfolio.get("href", CAPABILITY_IMPROVEMENT_PORTFOLIO_HREF)))
    portfolio_schema = escape(str(portfolio.get("schema_ref", CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF)))
    improvement_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('severity', '')))}</td>"
        f"<td>{escape(str(item.get('target_maturity_level', '')))}</td>"
        f"<td>{escape(', '.join(str(code) for code in item.get('weakness_codes', ())))}</td>"
        "</tr>"
        for item in portfolio.get("top_plans", ())
    )
    improvement_section = ""
    if portfolio.get("surface") == "activation_blocked_capability_improvement_portfolio":
        improvement_section = f"""
  <section>
    <h2>Improvement Portfolio</h2>
    <span class="metric">Operator review: {escape(str(portfolio.get("operator_review_required", True)).lower())}</span>
    <span class="metric">Plans: {int(portfolio.get("plan_count", 0))}</span>
    <span class="metric">Systemic weakness: {escape(', '.join(str(code) for code in portfolio.get("systemic_weakness_codes", ())))}</span>
    <table>
      <thead><tr><th>Capability</th><th>Severity</th><th>Target</th><th>Weakness</th></tr></thead>
      <tbody>{improvement_rows}</tbody>
    </table>
  </section>"""
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
    <span class="metric">Production ready: {int(read_model.get("production_ready_count", 0))}</span>
    <span class="metric">Approval required: {int(read_model.get("approval_required_count", 0))}</span>
    <span class="metric">Sandbox required: {int(read_model.get("sandbox_required_count", 0))}</span>
    <span class="metric">Raw tools exposed: {escape(str(read_model.get("raw_tool_surface_exposed", False)).lower())}</span>
  </header>
  <nav>
    <a href="{portfolio_href}">Capability improvement portfolio</a>
    <span class="metric">Schema: {portfolio_schema}</span>
    <span class="metric">Activation blocked: {escape(str(portfolio.get("activation_blocked", True)).lower())}</span>
  </nav>
  <section>
    <h2>Governed Capability Records</h2>
    <table>
      <thead><tr><th>Capability</th><th>Domain</th><th>Risk</th><th>Maturity</th><th>Production</th><th>Approval</th><th>Sandbox</th><th>Allowed Tools</th></tr></thead>
      <tbody>{capability_rows}</tbody>
    </table>
  </section>
  {improvement_section}
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


def _default_improvement_portfolio() -> dict[str, Any]:
    return {
        "enabled": True,
        "href": CAPABILITY_IMPROVEMENT_PORTFOLIO_HREF,
        "schema_ref": CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF,
        "mutation_applied": False,
        "activation_blocked": True,
        "operator_review_required": True,
    }


def _improvement_portfolio_summary(
    capabilities: list[dict[str, Any]],
    *,
    generated_at: str,
    limit: int,
) -> dict[str, Any]:
    signals = tuple(
        signal
        for item in capabilities
        if (signal := _health_signal_from_capability(item, generated_at=generated_at)) is not None
    )
    if not signals:
        return _default_improvement_portfolio()
    portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
        signals,
        generated_at=generated_at,
        max_candidates=_bounded_limit(limit),
    )
    top_plans = [
        {
            "plan_id": plan.plan_id,
            "capability_id": plan.capability_id,
            "severity": plan.diagnosis.severity,
            "target_maturity_level": plan.candidate.target_maturity_level,
            "weakness_codes": list(plan.diagnosis.weakness_codes),
            "blocked_reasons": list(plan.blocked_reasons),
        }
        for plan in portfolio.plans
    ]
    return {
        "enabled": True,
        "href": CAPABILITY_IMPROVEMENT_PORTFOLIO_HREF,
        "schema_ref": CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF,
        "mutation_applied": False,
        "surface": "activation_blocked_capability_improvement_portfolio",
        "portfolio_id": portfolio.portfolio_id,
        "generated_at": portfolio.generated_at,
        "plan_count": len(portfolio.plans),
        "prioritized_capability_ids": list(portfolio.prioritized_capability_ids),
        "systemic_weakness_codes": list(portfolio.systemic_weakness_codes),
        "blocked_reasons": list(portfolio.blocked_reasons),
        "operator_review_required": portfolio.operator_review_required,
        "activation_blocked": portfolio.activation_blocked,
        "portfolio_hash": portfolio.portfolio_hash,
        "metadata": dict(portfolio.metadata),
        "top_plans": top_plans,
    }


def _health_signal_from_capability(
    item: dict[str, Any],
    *,
    generated_at: str,
) -> CapabilityHealthSignal | None:
    capability_id = str(item.get("capability_id") or "").strip()
    if not capability_id:
        return None
    blocker_codes: list[str] = []
    if item.get("production_ready") is not True:
        blocker_codes.append("production_certification_missing")
    if item.get("requires_sandbox") is True:
        blocker_codes.append("sandbox_receipt_required")
    if item.get("receipt_required") is True:
        blocker_codes.append("receipt_closure_required")
    if item.get("requires_approval") is True:
        blocker_codes.append("operator_approval_required")
    evidence_refs = [f"capability_registry:{capability_id}"]
    maturity_ref = str(item.get("maturity_assessment_id") or "").strip()
    if maturity_ref:
        evidence_refs.append(f"capability_maturity:{maturity_ref}")
    return CapabilityHealthSignal(
        capability_id=capability_id,
        observed_at=generated_at,
        maturity_level=str(item.get("maturity_level") or "C0"),
        success_rate=1.0,
        failure_count=0,
        mean_latency_ms=0,
        cost_per_success=float(item.get("max_cost", 0.0) or 0.0),
        open_incidents=0,
        blocker_codes=tuple(blocker_codes),
        evidence_refs=tuple(evidence_refs),
        metadata={
            "source_surface": "operator_capability_console",
            "risk_level": str(item.get("risk_level") or ""),
        },
    )


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
