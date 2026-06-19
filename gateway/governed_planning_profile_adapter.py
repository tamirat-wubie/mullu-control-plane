"""Governed Planning Profile read-only admission adapter.

Purpose: project compiled gateway plans and causal simulation receipts into a
GovernedPlanningProfile admission report without registering a planner or
granting execution authority.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: gateway.command_spine canonical hashing and structural plan
objects supplied by the gateway planning/simulation lineage.
Invariants: projection is deterministic, read-only, non-executable, authority
neutral, Mfidel-safe, and does not import or wire the goal compiler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


PROFILE_ID = "governed-planning-profile-foundation-v1"
PROFILE_VERSION = "governed_planning_profile.v1"
REPORT_VERSION = "governed_planning_profile_admission_report.v1"


@dataclass(frozen=True, slots=True)
class PlanningProfileProjection:
    """Read-only summary of source plan shape against the planning profile."""

    profile_id: str
    profile_version: str
    source_plan_id: str
    goal_id: str
    tenant_id: str
    actor_id: str
    goal_status: str
    source_plan_status: str
    risk_tier: str
    step_count: int
    dag_step_count: int
    edge_count: int
    evidence_obligation_count: int
    rollback_obligation_count: int
    approval_obligation_count: int
    terminal_condition_count: int
    simulation_receipt_id: str
    simulation_would_execute: bool
    simulation_required_control_count: int
    simulation_failure_mode_count: int
    read_only: bool = True
    execution_allowed: bool = False
    dispatch_allowed: bool = False
    runtime_replanning_enabled: bool = False
    terminal_closure_allowed: bool = False
    success_claim_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe projection payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlanningProfileShadowFinding:
    """One mismatch or promotion blocker found during profile shadowing."""

    finding_id: str
    category: str
    expected_ref: str
    observed_ref: str
    severity: str
    proof_state: str

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe finding payload."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GovernedPlanningProfileAdmissionReport:
    """Deterministic no-effect admission report for one projected plan."""

    report_id: str
    report_version: str
    profile_id: str
    source_plan_id: str
    plan_certificate_id: str
    simulation_receipt_id: str
    admission_decision: str
    solver_outcome: str
    shadow_parity_status: str
    projection: PlanningProfileProjection
    shadow_mismatches: tuple[PlanningProfileShadowFinding, ...]
    promotion_blockers: tuple[PlanningProfileShadowFinding, ...]
    missing_evidence_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    receipt_envelope: dict[str, str]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe admission report payload."""
        return asdict(self)


def build_governed_planning_profile_admission_report(
    *,
    compiled_plan: Any,
    simulation_receipt: Any,
    profile_id: str = PROFILE_ID,
) -> GovernedPlanningProfileAdmissionReport:
    """Project source planning evidence into a no-effect admission report.

    Input contract: ``compiled_plan`` exposes goal, plan_dag, steps,
    terminal_conditions, and certificate fields; ``simulation_receipt`` exposes
    the dry-run receipt fields produced by the causal simulator.
    Output contract: a deterministic report that may prove shadow parity but
    never grants execution, dispatch, replanning, success, or closure authority.
    Error contract: missing structural identity is represented as explicit
    findings instead of implicit promotion.
    """
    goal = getattr(compiled_plan, "goal", None)
    plan_dag = getattr(compiled_plan, "plan_dag", None)
    certificate = getattr(compiled_plan, "certificate", None)
    steps = tuple(getattr(compiled_plan, "steps", ()) or ())
    terminal_conditions = tuple(getattr(compiled_plan, "terminal_conditions", ()) or ())
    plan_id = _text(getattr(plan_dag, "plan_id", ""))
    goal_id = _text(getattr(goal, "goal_id", ""))
    tenant_id = _text(getattr(goal, "tenant_id", ""))
    actor_id = _text(getattr(goal, "identity_id", ""))
    receipt_id = _text(getattr(simulation_receipt, "simulation_id", ""))

    projection = PlanningProfileProjection(
        profile_id=profile_id,
        profile_version=PROFILE_VERSION,
        source_plan_id=plan_id,
        goal_id=goal_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        goal_status=_text(getattr(goal, "status", "")),
        source_plan_status=_text(getattr(certificate, "status", "")),
        risk_tier=_text(getattr(goal, "risk_tier", "")),
        step_count=len(steps),
        dag_step_count=len(tuple(getattr(plan_dag, "step_ids", ()) or ())),
        edge_count=len(tuple(getattr(plan_dag, "edges", ()) or ())),
        evidence_obligation_count=sum(len(tuple(getattr(step, "required_evidence", ()) or ())) for step in steps),
        rollback_obligation_count=sum(1 for step in steps if bool(getattr(getattr(step, "rollback", None), "required", False))),
        approval_obligation_count=sum(1 for step in steps if bool(getattr(getattr(step, "approval", None), "required", False))),
        terminal_condition_count=len(terminal_conditions),
        simulation_receipt_id=receipt_id,
        simulation_would_execute=bool(getattr(simulation_receipt, "would_execute", False)),
        simulation_required_control_count=len(tuple(getattr(simulation_receipt, "required_controls", ()) or ())),
        simulation_failure_mode_count=len(tuple(getattr(simulation_receipt, "failure_modes", ()) or ())),
    )
    mismatches = _shadow_mismatches(compiled_plan=compiled_plan, simulation_receipt=simulation_receipt, projection=projection)
    blockers = _promotion_blockers(compiled_plan=compiled_plan, simulation_receipt=simulation_receipt, projection=projection)
    missing_evidence_refs = _missing_evidence_refs(mismatches=mismatches, blockers=blockers)
    evidence_refs = _dedupe((
        "schemas/governed_planning_profile.schema.json",
        "schemas/governed_planning_profile_admission_report.schema.json",
        "gateway/governed_planning_profile_adapter.py",
        "gateway/goal_compiler.py#CompiledGoalPlan",
        "gateway/causal_simulator.py#CausalSimulationReceipt",
        "docs/GOVERNED_PLANNING_PROFILE.md",
    ))
    shadow_parity_status = "matched" if not mismatches else "blocked"
    admission_decision = "shadow_parity_ready" if shadow_parity_status == "matched" and not blockers else "blocked"
    report = GovernedPlanningProfileAdmissionReport(
        report_id="pending",
        report_version=REPORT_VERSION,
        profile_id=profile_id,
        source_plan_id=plan_id,
        plan_certificate_id=_text(getattr(certificate, "certificate_id", "")),
        simulation_receipt_id=receipt_id,
        admission_decision=admission_decision,
        solver_outcome="AwaitingEvidence",
        shadow_parity_status=shadow_parity_status,
        projection=projection,
        shadow_mismatches=mismatches,
        promotion_blockers=blockers,
        missing_evidence_refs=missing_evidence_refs,
        evidence_refs=evidence_refs,
        receipt_envelope=_receipt_envelope(plan_id=plan_id or "missing-plan"),
        metadata={
            "adapter": "governed_planning_profile_adapter",
            "adapter_mode": "reference_only_shadow_projection",
            "runtime_registration": "not_performed",
            "authority_effect": "none",
            "read_only": True,
        },
    )
    report_hash = canonical_hash(report.to_dict())
    return replace(
        report,
        report_id=f"governed-planning-profile-admission-{report_hash[:16]}",
        report_hash=report_hash,
    )


def _shadow_mismatches(
    *,
    compiled_plan: Any,
    simulation_receipt: Any,
    projection: PlanningProfileProjection,
) -> tuple[PlanningProfileShadowFinding, ...]:
    plan_dag = getattr(compiled_plan, "plan_dag", None)
    certificate = getattr(compiled_plan, "certificate", None)
    steps = tuple(getattr(compiled_plan, "steps", ()) or ())
    step_ids = tuple(str(step_id) for step_id in tuple(getattr(plan_dag, "step_ids", ()) or ()))
    receipt_steps = tuple(getattr(simulation_receipt, "step_results", ()) or ())
    findings: list[PlanningProfileShadowFinding] = []
    _add_if(findings, not projection.profile_id, "identity", PROFILE_ID, projection.profile_id, "high", "Fail")
    _add_if(findings, not projection.source_plan_id, "identity", "source_plan_id", projection.source_plan_id, "high", "Fail")
    _add_if(findings, not projection.goal_id, "identity", "goal_id", projection.goal_id, "high", "Fail")
    _add_if(findings, projection.tenant_id != _text(getattr(simulation_receipt, "tenant_id", "")), "identity", projection.tenant_id, _text(getattr(simulation_receipt, "tenant_id", "")), "high", "Fail")
    _add_if(findings, projection.source_plan_id != _text(getattr(simulation_receipt, "plan_id", "")), "identity", projection.source_plan_id, _text(getattr(simulation_receipt, "plan_id", "")), "high", "Fail")
    _add_if(findings, projection.goal_id != _text(getattr(simulation_receipt, "goal_id", "")), "identity", projection.goal_id, _text(getattr(simulation_receipt, "goal_id", "")), "high", "Fail")
    _add_if(findings, projection.step_count != projection.dag_step_count, "topology", f"steps:{projection.step_count}", f"dag_step_ids:{projection.dag_step_count}", "high", "Fail")
    _add_if(findings, projection.step_count != int(getattr(certificate, "step_count", -1)), "topology", f"steps:{projection.step_count}", f"certificate:{getattr(certificate, 'step_count', '')}", "high", "Fail")
    _add_if(findings, bool(steps) and len(receipt_steps) != projection.step_count, "simulation", f"step_results:{projection.step_count}", f"step_results:{len(receipt_steps)}", "medium", "Fail")
    declared_step_ids = {str(getattr(step, "step_id", "")) for step in steps}
    _add_if(findings, set(step_ids) != declared_step_ids, "topology", ",".join(sorted(declared_step_ids)), ",".join(sorted(step_ids)), "high", "Fail")
    return tuple(findings)


def _promotion_blockers(
    *,
    compiled_plan: Any,
    simulation_receipt: Any,
    projection: PlanningProfileProjection,
) -> tuple[PlanningProfileShadowFinding, ...]:
    blockers: list[PlanningProfileShadowFinding] = []
    if projection.approval_obligation_count:
        blockers.append(_finding(
            "authority",
            "approval_obligation_count:0",
            f"approval_obligation_count:{projection.approval_obligation_count}",
            "medium",
            "Unknown",
        ))
    if projection.simulation_required_control_count:
        blockers.append(_finding(
            "authority",
            "required_controls:0",
            f"required_controls:{projection.simulation_required_control_count}",
            "medium",
            "Unknown",
        ))
    if projection.evidence_obligation_count:
        blockers.append(_finding(
            "evidence",
            "post_execution_evidence:present",
            f"post_execution_evidence:{projection.evidence_obligation_count}",
            "medium",
            "Unknown",
        ))
    if projection.terminal_condition_count:
        blockers.append(_finding(
            "closure",
            "terminal_closure_certificate:present",
            f"terminal_conditions:{projection.terminal_condition_count}",
            "medium",
            "Unknown",
        ))
    if not projection.read_only or projection.execution_allowed or projection.dispatch_allowed:
        blockers.append(_finding(
            "profile_scope",
            "read_only_no_effect",
            "authority_drift",
            "high",
            "Fail",
        ))
    if bool(getattr(simulation_receipt, "would_execute", False)):
        blockers.append(_finding(
            "profile_scope",
            "simulation_only",
            "source_simulation_would_execute",
            "low",
            "Unknown",
        ))
    if _text(getattr(getattr(compiled_plan, "certificate", None), "status", "")) == "blocked":
        blockers.append(_finding(
            "simulation",
            "compiled_or_reviewable_plan",
            "blocked_plan",
            "high",
            "Fail",
        ))
    return tuple(blockers)


def _missing_evidence_refs(
    *,
    mismatches: tuple[PlanningProfileShadowFinding, ...],
    blockers: tuple[PlanningProfileShadowFinding, ...],
) -> tuple[str, ...]:
    refs = [
        "unknown://governed-planning-profile/operator-shadow-pilot",
        "unknown://governed-planning-profile/runtime-promotion-approval",
    ]
    refs.extend(f"missing://governed-planning-profile/{finding.category}/{finding.finding_id}" for finding in mismatches)
    refs.extend(f"missing://governed-planning-profile/{finding.category}/{finding.finding_id}" for finding in blockers)
    return _dedupe(refs)


def _add_if(
    findings: list[PlanningProfileShadowFinding],
    condition: bool,
    category: str,
    expected_ref: str,
    observed_ref: str,
    severity: str,
    proof_state: str,
) -> None:
    if condition:
        findings.append(_finding(category, expected_ref, observed_ref, severity, proof_state))


def _finding(
    category: str,
    expected_ref: str,
    observed_ref: str,
    severity: str,
    proof_state: str,
) -> PlanningProfileShadowFinding:
    seed = {
        "category": category,
        "expected_ref": expected_ref,
        "observed_ref": observed_ref,
        "severity": severity,
        "proof_state": proof_state,
    }
    return PlanningProfileShadowFinding(
        finding_id=f"planning-profile-shadow-{canonical_hash(seed)[:16]}",
        category=category,
        expected_ref=expected_ref,
        observed_ref=observed_ref,
        severity=severity,
        proof_state=proof_state,
    )


def _receipt_envelope(*, plan_id: str) -> dict[str, str]:
    safe_plan_id = _safe_id(plan_id)
    return {
        "uao_ref": f"uao://governed-planning-profile/admission/{safe_plan_id}",
        "causal_decision_trace_ref": f"trace://governed-planning-profile/admission/{safe_plan_id}",
        "receipt_ref": f"receipt://governed-planning-profile/admission/{safe_plan_id}",
    }


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.append(text)
    return tuple(seen)


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in str(value)).strip("-").lower() or "unknown"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""
