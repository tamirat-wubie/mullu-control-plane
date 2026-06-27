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
from urllib.parse import urlencode

from gateway.autonomous_capability_upgrade import (
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
)
from gateway.workflow_orchestration import (
    WorkflowOrchestrator,
    WorkflowTaskSpec,
    WorkflowTaskType,
    workflow_run_to_json_dict,
)


CAPABILITY_IMPROVEMENT_PORTFOLIO_SCHEMA_REF = "urn:mullusi:schema:capability-improvement-portfolio:1"
CAPABILITY_IMPROVEMENT_PORTFOLIO_HREF = "/runtime/self/capability-improvement-portfolio"
DEVELOPER_WORKFLOW_RUN_SCHEMA_REF = "urn:mullusi:schema:workflow-run:1"
DEVELOPER_WORKFLOW_RUN_HREF = "/operator/developer-workflow"
DEVELOPER_WORKFLOW_RUN_READ_MODEL_HREF = "/operator/developer-workflow/read-model"
UNLOCK_LEVELS = (
    {"level": "L0", "label": "read-only", "maximum_effect": "inspect repository or external state"},
    {"level": "L1", "label": "plan-only", "maximum_effect": "emit plans without mutation"},
    {"level": "L2", "label": "prepare-only", "maximum_effect": "prepare bounded artifacts without durable effects"},
    {"level": "L3", "label": "write-to-sandbox", "maximum_effect": "write local sandbox files with receipt"},
    {"level": "L4", "label": "run tests", "maximum_effect": "execute local quality gates"},
    {"level": "L5", "label": "create PR", "maximum_effect": "prepare or open pull request with approval"},
    {"level": "L6", "label": "merge with approval", "maximum_effect": "merge reviewed changes"},
    {"level": "L7", "label": "live connector read", "maximum_effect": "read credentialed connector state"},
    {"level": "L8", "label": "live connector write", "maximum_effect": "write credentialed connector state"},
    {"level": "L9", "label": "production/customer mode", "maximum_effect": "affect production or customer state"},
)
SAFE_AUTOMATIC_ZONES = (
    "write_docs",
    "write_tests",
    "write_examples",
    "write_local_demo_files",
    "update_readme",
    "generate_schemas",
    "generate_validators",
)
DANGEROUS_ZONES = (
    "delete_files",
    "touch_secrets",
    "send_email",
    "move_money",
    "deploy",
    "merge_to_main",
    "write_production_data",
)


def build_capability_friction_control_read_model(
    *,
    capability_admission_gate: Any | None = None,
    domain: str = "",
    risk_level: str = "",
    read_model_id: str = "capability_friction_control.foundation.v1",
) -> dict[str, Any]:
    """Build the formal capability friction-control read model.

    Input contract: optional governed capability admission gate plus bounded
    domain and risk filters.
    Output contract: JSON-serializable read-only projection of unlock levels,
    friction modes, lab/real-world boundaries, and Developer Workflow v1.
    Error contract: malformed capability records are skipped by the lower
    operator projection; this function never grants execution authority.
    """
    domain_filter = domain.strip()
    risk_filter = risk_level.strip()
    capabilities = _operator_capabilities(
        capability_admission_gate,
        domain_filter=domain_filter,
        risk_filter=risk_filter,
    )
    summary = _friction_control_summary(capabilities)
    return {
        "schema_version": 1,
        "read_model_id": read_model_id,
        "mode": "foundation",
        "read_model_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "capability_surface": "governed_capability_records",
            "domain_filter": domain_filter,
            "risk_level_filter": risk_filter,
        },
        "summary": {
            "capability_count": len(capabilities),
            "unlock_level_counts": _counts(capabilities, "unlock_level"),
            "operating_boundary_counts": _counts(capabilities, "operating_boundary"),
            "approval_required_count": sum(1 for item in capabilities if item.get("requires_approval") is True),
            "sandbox_required_count": sum(1 for item in capabilities if item.get("requires_sandbox") is True),
            "fast_mode_lab_ready_count": int(summary["fast_mode_lab_ready_count"]),
            "lab_mode_allowed_count": sum(1 for item in capabilities if item.get("lab_mode_allowed") is True),
            "real_world_mode_allowed_count": sum(
                1 for item in capabilities if item.get("real_world_mode_allowed") is True
            ),
            "real_world_write_status": str(summary["real_world_write_status"]),
        },
        "unlock_levels": summary["unlock_levels"],
        "friction_modes": summary["friction_modes"],
        "safe_automatic_zones": summary["safe_automatic_zones"],
        "dangerous_zones": summary["dangerous_zones"],
        "capabilities": [_friction_control_capability_card(item) for item in capabilities],
        "developer_workflow_v1": summary["developer_workflow_v1"],
        "validators": [
            {
                "validator_id": "capability_friction_control_validator",
                "command": "python scripts/validate_capability_friction_control.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "capability_friction_control_tests",
                "command": "python -m pytest tests/test_validate_capability_friction_control.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Use this read model as the operator-facing surface for local Developer Workflow v1.",
    }


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
    friction_control = _friction_control_summary(capabilities)
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
        "maturity_label_counts": _counts(capabilities, "maturity_label"),
        "production_ready_count": sum(1 for item in capabilities if item.get("production_ready") is True),
        "autonomy_ready_count": sum(1 for item in capabilities if item.get("autonomy_ready") is True),
        "approval_required_count": sum(1 for item in capabilities if item.get("requires_approval") is True),
        "sandbox_required_count": sum(1 for item in capabilities if item.get("requires_sandbox") is True),
        "receipt_required_count": sum(1 for item in capabilities if item.get("receipt_required") is True),
        "friction_control": friction_control,
        "unlock_level_counts": _counts(capabilities, "unlock_level"),
        "operating_boundary_counts": _counts(capabilities, "operating_boundary"),
        "admission_audits": audit_page,
        "admission_audit_count": len(audits),
        "admission_audit_status_filter": admission_status.strip(),
        "admission_audit_page": audit_page_meta,
        "plan_summary": plan_summary,
        "improvement_portfolio": improvement_portfolio,
    }


def render_operator_capability_console(read_model: dict[str, Any]) -> str:
    """Render a compact read-only HTML operator console."""
    friction_control = read_model.get("friction_control", {})
    developer_workflow = friction_control.get("developer_workflow_v1", {}) if isinstance(friction_control, dict) else {}
    domain_filter = str(read_model.get("domain_filter", ""))
    risk_filter = str(read_model.get("risk_level_filter", ""))
    friction_href = "/operator/capabilities/friction-control/read-model"
    friction_query: dict[str, str] = {}
    if domain_filter:
        friction_query["domain"] = domain_filter
    if risk_filter:
        friction_query["risk_level"] = risk_filter
    if friction_query:
        friction_href = friction_href + "?" + urlencode(friction_query)
    friction_href_html = escape(friction_href)
    capability_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('domain', '')))}</td>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td>{escape(str(item.get('maturity_level', '')))}</td>"
        f"<td>{escape(str(item.get('maturity_label', '')))}</td>"
        f"<td>{escape(str(item.get('unlock_level', '')))}</td>"
        f"<td>{escape(str(item.get('friction_status', '')))}</td>"
        f"<td>{escape(str(item.get('next_unlock', '')))}</td>"
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
    <span class="metric">Fast lab ready: {int(read_model.get("friction_control", {}).get("fast_mode_lab_ready_count", 0))}</span>
    <span class="metric">Raw tools exposed: {escape(str(read_model.get("raw_tool_surface_exposed", False)).lower())}</span>
  </header>
  <section>
    <h2>Friction Control</h2>
    <span class="metric">Boundary: {escape(str(friction_control.get("default_boundary", "")))}</span>
    <span class="metric">Fast mode: {escape(str(friction_control.get("fast_mode_summary", "")))}</span>
    <span class="metric">Real-world writes: {escape(str(friction_control.get("real_world_write_status", "")))}</span>
    <span class="metric">Workflow: {escape(str(developer_workflow.get("status", "")))}</span>
    <span class="metric">Approval: {escape(str(developer_workflow.get("approval_boundary", "")))}</span>
    <a href="{friction_href_html}">friction read model</a>
  </section>
  <nav>
    <a href="{portfolio_href}">Capability improvement portfolio</a>
    <a href="/operator/control-tower">Operator control tower</a>
    <span class="metric">Schema: {portfolio_schema}</span>
    <span class="metric">Activation blocked: {escape(str(portfolio.get("activation_blocked", True)).lower())}</span>
  </nav>
  <section>
    <h2>Governed Capability Records</h2>
    <table>
      <thead><tr><th>Capability</th><th>Domain</th><th>Risk</th><th>Maturity</th><th>Label</th><th>Unlock</th><th>Status</th><th>Next</th><th>Production</th><th>Approval</th><th>Sandbox</th><th>Allowed Tools</th></tr></thead>
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
        projected.update(_friction_projection(projected))
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


def _friction_projection(item: dict[str, Any]) -> dict[str, Any]:
    capability_id = str(item.get("capability_id") or "")
    forbidden_effects = tuple(str(effect) for effect in item.get("forbidden_effects", ()))
    world_mutating = item.get("world_mutating") is True
    requires_approval = item.get("requires_approval") is True
    requires_sandbox = item.get("requires_sandbox") is True
    rollback_required = item.get("rollback_or_compensation_required") is True
    production_ready = item.get("production_ready") is True
    allowed_networks = item.get("allowed_networks", ())
    network_blocked = (
        "network_enabled_by_default" in forbidden_effects
        or "network_egress_used" in forbidden_effects
        or allowed_networks == []
        or allowed_networks == ()
    )
    production_blocked = "production_deployment_started" in forbidden_effects
    lab_ready = (
        world_mutating
        and requires_sandbox
        and rollback_required
        and network_blocked
        and production_blocked
    )
    unlock_level = _unlock_level_for_capability(item)
    blocked = _blocked_actions_for_capability(item)
    required = _required_unlock_evidence(item)
    return {
        "unlock_level": unlock_level,
        "unlock_label": _unlock_label(unlock_level),
        "operating_boundary": "lab" if requires_sandbox or not production_ready else "real_world",
        "friction_status": _friction_status(item, lab_ready=lab_ready),
        "fast_mode_admission": _fast_mode_admission(world_mutating=world_mutating, lab_ready=lab_ready),
        "balanced_mode_admission": "approval_required" if requires_approval else "allowed",
        "strict_mode_admission": "approval_required" if world_mutating or requires_approval else "allowed",
        "lab_mode_allowed": lab_ready or not world_mutating,
        "real_world_mode_allowed": production_ready and not requires_approval,
        "blocked_actions": blocked,
        "blocked_action_count": len(blocked),
        "required_before_unlock": required,
        "next_unlock": _next_unlock(item, current_level=unlock_level, required=required),
        "rollback_default": rollback_required or not world_mutating,
    }


def _friction_control_summary(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    developer_workflow = _developer_workflow_v1(capabilities)
    return {
        "surface": "capability_friction_control",
        "execution_authority_granted": False,
        "default_boundary": "lab",
        "unlock_levels": list(UNLOCK_LEVELS),
        "friction_modes": [
            {
                "mode": "strict",
                "rule": "approval before effect-bearing action and production evidence before real-world writes",
            },
            {
                "mode": "balanced",
                "rule": "read and prepare are automatic; risky local changes require approval",
            },
            {
                "mode": "fast",
                "rule": "local lab actions are automatic only when sandbox, receipt, rollback, and no-network constraints hold",
            },
        ],
        "safe_automatic_zones": list(SAFE_AUTOMATIC_ZONES),
        "dangerous_zones": list(DANGEROUS_ZONES),
        "fast_mode_summary": "local_lab_only",
        "fast_mode_lab_ready_count": sum(1 for item in capabilities if item.get("fast_mode_admission") == "allowed_lab"),
        "real_world_write_status": "blocked_until_production_witness",
        "developer_workflow_v1": developer_workflow,
    }


def _developer_workflow_v1(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(item.get("capability_id")): item for item in capabilities}
    stages = [
        _workflow_stage("request_intake", "observation", "operator.user_request", True),
        _workflow_stage("repo_map", "skill_execution", "software_dev.repo_map.read", "software_dev.repo_map.read" in by_id),
        _workflow_stage("context_bundle", "skill_execution", "software_dev.context_bundle.build", "software_dev.context_bundle.build" in by_id),
        _workflow_stage("gate_plan", "skill_execution", "software_dev.gate_plan.select", "software_dev.gate_plan.select" in by_id),
        _workflow_stage("sandbox_change", "skill_execution", "software_dev.change.run", "software_dev.change.run" in by_id),
        _workflow_stage("receipt_review", "observation", "software_change_receipt", "software_dev.change.run" in by_id),
        _workflow_stage("operator_approval", "approval_gate", "developer_reviewer", "software_dev.pr_candidate.prepare" in by_id),
        _workflow_stage("pr_candidate", "skill_execution", "software_dev.pr_candidate.prepare", "software_dev.pr_candidate.prepare" in by_id),
    ]
    missing = [stage["capability_id"] for stage in stages if stage["available"] is False]
    risky_capabilities = [
        by_id[capability_id]
        for capability_id in ("software_dev.change.run", "software_dev.pr_candidate.prepare")
        if capability_id in by_id
    ]
    lab_ready = bool(risky_capabilities) and all(item.get("lab_mode_allowed") is True for item in risky_capabilities)
    return {
        "workflow_id": "mullu_developer_workflow.v1",
        "status": "preflight_ready" if not missing and lab_ready else "awaiting_evidence",
        "terminal_closure": "diff_receipt_reviewed_then_pr_candidate_prepared",
        "lab_mode_allowed": lab_ready,
        "real_world_effects_allowed": False,
        "approval_boundary": "before_pull_request_or_external_write",
        "stages": stages,
        "missing_capability_ids": missing,
        "next_unlock": "operator_approval_for_pr_candidate" if not missing else "register_missing_capabilities",
    }


def _friction_control_capability_card(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_id": str(item.get("capability_id", "")),
        "domain": str(item.get("domain", "")),
        "risk_level": str(item.get("risk_level", "")),
        "maturity_level": str(item.get("maturity_level", "")),
        "unlock_level": str(item.get("unlock_level", "")),
        "unlock_label": str(item.get("unlock_label", "")),
        "operating_boundary": str(item.get("operating_boundary", "")),
        "friction_status": str(item.get("friction_status", "")),
        "fast_mode_admission": str(item.get("fast_mode_admission", "")),
        "balanced_mode_admission": str(item.get("balanced_mode_admission", "")),
        "strict_mode_admission": str(item.get("strict_mode_admission", "")),
        "lab_mode_allowed": item.get("lab_mode_allowed") is True,
        "real_world_mode_allowed": item.get("real_world_mode_allowed") is True,
        "blocked_actions": [str(action) for action in item.get("blocked_actions", ())],
        "blocked_action_count": int(item.get("blocked_action_count", 0)),
        "required_before_unlock": [str(requirement) for requirement in item.get("required_before_unlock", ())],
        "next_unlock": str(item.get("next_unlock", "")),
        "rollback_default": item.get("rollback_default") is True,
    }


def _workflow_stage(stage_id: str, stage_type: str, capability_id: str, available: bool) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_type": stage_type,
        "capability_id": capability_id,
        "available": available,
        "verification_required": True,
    }


def _unlock_level_for_capability(item: dict[str, Any]) -> str:
    capability_id = str(item.get("capability_id") or "")
    expected_effects = tuple(str(effect) for effect in item.get("expected_effects", ()))
    allowed_tools = tuple(str(tool) for tool in item.get("allowed_tools", ()))
    if ".pr_candidate." in capability_id or "pull_request" in " ".join(expected_effects):
        return "L5"
    if "quality_gates_executed" in expected_effects or any("execute_command" in tool for tool in allowed_tools):
        return "L4"
    if item.get("world_mutating") is True and item.get("requires_sandbox") is True:
        return "L3"
    if ".context_bundle." in capability_id or ".prepare" in capability_id or ".build" in capability_id:
        return "L2"
    if ".plan" in capability_id or ".gate_plan." in capability_id:
        return "L1"
    return "L0"


def _friction_status(item: dict[str, Any], *, lab_ready: bool) -> str:
    if item.get("certification_status") in {"suspended", "retired"}:
        return "blocked"
    if item.get("requires_approval") is True:
        return "approval_required"
    if lab_ready or item.get("world_mutating") is not True:
        return "unlocked"
    return "evidence_missing"


def _fast_mode_admission(*, world_mutating: bool, lab_ready: bool) -> str:
    if lab_ready:
        return "allowed_lab"
    if not world_mutating:
        return "allowed_read_only"
    return "approval_required"


def _blocked_actions_for_capability(item: dict[str, Any]) -> list[str]:
    blocked = [str(effect) for effect in item.get("forbidden_effects", ())]
    if item.get("production_ready") is not True:
        blocked.append("real_world_production_execution")
    if item.get("requires_approval") is True:
        blocked.append("unapproved_execution")
    return sorted(set(blocked))


def _required_unlock_evidence(item: dict[str, Any]) -> list[str]:
    required: list[str] = []
    if item.get("requires_approval") is True:
        required.append("approval")
    if item.get("rollback_or_compensation_required") is True:
        required.append("rollback")
    if item.get("receipt_required") is True:
        required.append("dry_run_receipt")
    if item.get("requires_sandbox") is True:
        required.append("workspace_boundary")
    if item.get("production_ready") is not True:
        required.append("production_witness")
    return required


def _next_unlock(item: dict[str, Any], *, current_level: str, required: list[str]) -> str:
    if item.get("production_ready") is not True and current_level in {"L7", "L8", "L9"}:
        return "production_witness"
    if required:
        return required[0]
    return "none"


def _unlock_label(level: str) -> str:
    for item in UNLOCK_LEVELS:
        if item["level"] == level:
            return str(item["label"])
    return ""


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
