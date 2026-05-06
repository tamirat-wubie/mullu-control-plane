from __future__ import annotations
from dataclasses import dataclass
from mcoi_runtime.contracts.goal import GoalDescriptor
from mcoi_runtime.contracts.policy import PolicyDecision,PolicyDecisionStatus
from mcoi_runtime.contracts.proof import GuardVerdict
from mcoi_runtime.contracts.whqr import WHQRExpr,WHRole
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.governance import build_guard_verdict,build_policy_decision
@dataclass(frozen=True,slots=True)
class WHQRGoalCompilation: goal:GoalDescriptor; policy_decision:PolicyDecision; guard_verdict:GuardVerdict; ready_for_mil:bool; next_step:str
def compile_goal_from_whqr(expr:WHQRExpr,goal:GoalDescriptor,*,subject_id:str,issued_at:str,context:WHQREvaluationContext|None=None,required_roles:tuple[WHRole,...]=())->WHQRGoalCompilation:
 d=build_policy_decision(expr,subject_id=subject_id,issued_at=issued_at,goal_id=goal.goal_id,context=context,required_roles=required_roles); g=build_guard_verdict(d)
 return WHQRGoalCompilation(goal,d,g,d.status is PolicyDecisionStatus.ALLOW,"compile_mil" if d.status is PolicyDecisionStatus.ALLOW else ("resolve_whqr_escalation" if d.status is PolicyDecisionStatus.ESCALATE else "halt_whqr_denial"))
