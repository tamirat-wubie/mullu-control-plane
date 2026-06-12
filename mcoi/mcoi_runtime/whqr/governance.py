"""Purpose: convert WHQR evaluation results into policy and guard decisions.
Governance scope: deterministic WHQR truth, norm, evidence, and static-role admission.
Dependencies: policy contracts, proof contracts, WHQR contracts, binding preflight, evaluator, and static checks.
Invariants: false, forbidden, contradicted, or static-invalid inputs deny; uncertain or binding-incomplete inputs escalate.
"""

from __future__ import annotations

from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.proof import GuardVerdict
from mcoi_runtime.contracts.whqr import EvidenceGate, GateResult, NormGate, TruthGate, WHQRExpr, WHRole
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
    reason = DecisionReason(
        _message(status, binding_report),
        _reason_code(status, binding_report),
        {
            "truth": gate_result.truth.value,
            "norm": gate_result.norm.value if gate_result.norm else None,
            "evidence": gate_result.evidence.value if gate_result.evidence else None,
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
        f"whqr:{goal_id}:{status.value}",
        subject_id,
        goal_id,
        status,
        (reason,),
        issued_at,
    )


def build_guard_verdict(decision: PolicyDecision) -> GuardVerdict:
    """Build a guard verdict from a WHQR policy decision."""
    return GuardVerdict(
        "whqr_policy",
        decision.status is PolicyDecisionStatus.ALLOW,
        decision.reasons[0].message,
        {"policy_status": decision.status.value},
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


def _reason_code(status: PolicyDecisionStatus, binding_report: BindingPreflightReport) -> str:
    if not binding_report.passed and status is PolicyDecisionStatus.ESCALATE:
        return "whqr_binding_escalate"
    return f"whqr_{status.value}"
