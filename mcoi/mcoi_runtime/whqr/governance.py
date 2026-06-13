"""Purpose: convert WHQR evaluation results into policy and guard decisions.
Governance scope: deterministic WHQR truth, norm, evidence, and static-role admission.
Dependencies: policy contracts, proof contracts, WHQR contracts, binding preflight, evaluator, and static checks.
Invariants: false, forbidden, contradicted, or static-invalid inputs deny; uncertain or binding-incomplete inputs escalate.
"""

from __future__ import annotations

from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.proof import GuardVerdict
from mcoi_runtime.contracts.whqr import EvidenceGate, GateResult, NormGate, TruthGate, WHQRDocument, WHQRExpr, WHRole
from mcoi_runtime.whqr.binding_preflight import BindingPreflightReport, validate_binding_preflight
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext, evaluate
from mcoi_runtime.whqr.static_checks import validate_static


def build_policy_decision(
    expr: WHQRExpr,
    *,
    subject_id: str,
    issued_at: str,
    goal_id: str = "whqr-goal",
    context: WHQREvaluationContext | None = None,
    required_roles: tuple[WHRole, ...] = (),
) -> PolicyDecision:
    """Build one deterministic policy decision from a WHQR expression."""
    static_report = validate_static(expr, required_roles)
    binding_report = validate_binding_preflight(expr)
    gate_result = evaluate(expr, context)
    status = _status(static_report.passed, binding_report, gate_result)
    document = WHQRDocument(root=expr)
    expr_hash = document.canonical_hash()
    reason_code = _reason_code(status, static_report.passed, binding_report, gate_result)
    reason = DecisionReason(
        _message(status, binding_report),
        reason_code,
        {
            "truth": gate_result.truth.value,
            "norm": gate_result.norm.value if gate_result.norm else None,
            "evidence": gate_result.evidence.value if gate_result.evidence else None,
            "gate_reason": gate_result.reason,
            "gate_metadata": dict(gate_result.metadata),
            "static_issues": tuple(
                {
                    "code": issue.code,
                    "message": issue.message,
                    "target": issue.target,
                }
                for issue in static_report.issues
            ),
            "binding_issues": tuple(
                {
                    "code": issue.code,
                    "target": issue.target,
                    "node_id": issue.node_id,
                    "expected_type": issue.expected_type,
                }
                for issue in binding_report.issues
            ),
        },
    )
    return PolicyDecision(
        f"whqr:{goal_id}:{status.value}:{reason_code}:{expr_hash}",
        subject_id,
        goal_id,
        status,
        (reason,),
        issued_at,
        metadata={
            "reason_code": reason_code,
            "whqr_canonical_hash": expr_hash,
            "whqr_semantics_hash": document.semantics_hash,
            "whqr_version": document.whqr_version,
        },
    )


def build_guard_verdict(decision: PolicyDecision) -> GuardVerdict:
    """Build a guard verdict from a WHQR policy decision."""
    reason = decision.reasons[0]
    return GuardVerdict(
        "whqr_policy",
        decision.status is PolicyDecisionStatus.ALLOW,
        reason.message,
        {
            "decision_id": decision.decision_id,
            "goal_id": decision.goal_id,
            "policy_status": decision.status.value,
            "reason_code": reason.code,
            "reason_details": reason.details,
            "subject_id": decision.subject_id,
            "issued_at": decision.issued_at,
            "decision_metadata": decision.metadata,
            "whqr_canonical_hash": decision.metadata.get("whqr_canonical_hash"),
            "whqr_semantics_hash": decision.metadata.get("whqr_semantics_hash"),
            "whqr_version": decision.metadata.get("whqr_version"),
        },
    )


def _status(static_ok: bool, binding_report: BindingPreflightReport, gate_result: GateResult) -> PolicyDecisionStatus:
    if (
        not static_ok
        or gate_result.truth is TruthGate.FALSE
        or gate_result.norm is NormGate.FORBIDDEN
        or gate_result.evidence is EvidenceGate.CONTRADICTED
    ):
        return PolicyDecisionStatus.DENY
    if not binding_report.passed:
        return PolicyDecisionStatus.ESCALATE
    if (
        gate_result.truth is TruthGate.UNKNOWN
        or gate_result.norm in {NormGate.ESCALATE, NormGate.REQUIRES_APPROVAL}
        or gate_result.evidence
        in {
            EvidenceGate.UNPROVEN,
            EvidenceGate.STALE,
            EvidenceGate.BUDGET_UNKNOWN,
            EvidenceGate.FORBIDDEN_UNKNOWN,
        }
    ):
        return PolicyDecisionStatus.ESCALATE
    return PolicyDecisionStatus.ALLOW


def _message(status: PolicyDecisionStatus, binding_report: BindingPreflightReport) -> str:
    if not binding_report.passed and status is PolicyDecisionStatus.ESCALATE:
        return "WHQR tree requires entity or evidence binding before MIL compilation"
    if status is PolicyDecisionStatus.ALLOW:
        return "WHQR tree satisfied truth, norm, and evidence gates"
    if status is PolicyDecisionStatus.DENY:
        return "WHQR tree denied by static, truth, norm, or evidence gate"
    return "WHQR tree requires escalation before MIL compilation"


def _reason_code(
    status: PolicyDecisionStatus,
    static_ok: bool,
    binding_report: BindingPreflightReport,
    gate_result: GateResult,
) -> str:
    if status is PolicyDecisionStatus.ALLOW:
        return "whqr_allow"
    if not static_ok:
        return "whqr_static_deny"
    if status is PolicyDecisionStatus.DENY:
        if gate_result.truth is TruthGate.FALSE:
            return "whqr_truth_deny"
        if gate_result.norm is NormGate.FORBIDDEN:
            return "whqr_norm_deny"
        if gate_result.evidence is EvidenceGate.CONTRADICTED:
            return "whqr_evidence_deny"
        return "whqr_deny"
    if not binding_report.passed:
        return "whqr_binding_escalate"
    if gate_result.truth is TruthGate.UNKNOWN:
        return "whqr_truth_escalate"
    if gate_result.norm in {NormGate.ESCALATE, NormGate.REQUIRES_APPROVAL}:
        return "whqr_norm_escalate"
    if gate_result.evidence is EvidenceGate.UNPROVEN:
        return "whqr_evidence_unproven_escalate"
    if gate_result.evidence is EvidenceGate.STALE:
        return "whqr_evidence_stale_escalate"
    if gate_result.evidence is EvidenceGate.BUDGET_UNKNOWN:
        return "whqr_evidence_budget_unknown_escalate"
    if gate_result.evidence is EvidenceGate.FORBIDDEN_UNKNOWN:
        return "whqr_evidence_forbidden_unknown_escalate"
    return "whqr_escalate"
