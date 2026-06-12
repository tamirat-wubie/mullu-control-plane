"""Purpose: compile WHQR policy outputs into goal-level MIL readiness records.
Governance scope: side-effect-free WHQR goal compilation before MIL construction.
Dependencies: goal contracts, policy contracts, proof contracts, WHQR binding preflight, evaluator context, and WHQR governance.
Invariants: binding readiness and policy status determine MIL readiness and next-step routing deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.goal import GoalDescriptor
from mcoi_runtime.contracts.policy import PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.proof import GuardVerdict
from mcoi_runtime.contracts.whqr import WHQRExpr, WHRole
from mcoi_runtime.whqr.binding_preflight import BindingPreflightReport, validate_binding_preflight
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.governance import build_guard_verdict, build_policy_decision


@dataclass(frozen=True, slots=True)
class WHQRGoalCompilation:
    """Verifier-ready WHQR goal compilation result."""

    goal: GoalDescriptor
    policy_decision: PolicyDecision
    guard_verdict: GuardVerdict
    binding_report: BindingPreflightReport
    ready_for_mil: bool
    next_step: str


def compile_goal_from_whqr(
    expr: WHQRExpr,
    goal: GoalDescriptor,
    *,
    subject_id: str,
    issued_at: str,
    context: WHQREvaluationContext | None = None,
    required_roles: tuple[WHRole, ...] = (),
) -> WHQRGoalCompilation:
    """Compile a WHQR expression into a governed goal decision."""
    binding_report = validate_binding_preflight(expr)
    decision = build_policy_decision(
        expr,
        subject_id=subject_id,
        issued_at=issued_at,
        goal_id=goal.goal_id,
        context=context,
        required_roles=required_roles,
    )
    guard_verdict = build_guard_verdict(decision)
    return WHQRGoalCompilation(
        goal=goal,
        policy_decision=decision,
        guard_verdict=guard_verdict,
        binding_report=binding_report,
        ready_for_mil=decision.status is PolicyDecisionStatus.ALLOW,
        next_step=_next_step(decision.status, binding_report),
    )


def _next_step(status: PolicyDecisionStatus, binding_report: BindingPreflightReport) -> str:
    if status is PolicyDecisionStatus.ALLOW:
        return "compile_mil"
    if not binding_report.passed:
        return "resolve_whqr_binding"
    if status is PolicyDecisionStatus.ESCALATE:
        return "resolve_whqr_escalation"
    return "halt_whqr_denial"
