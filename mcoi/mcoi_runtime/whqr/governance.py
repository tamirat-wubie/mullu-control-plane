from __future__ import annotations
from mcoi_runtime.contracts.policy import DecisionReason,PolicyDecision,PolicyDecisionStatus
from mcoi_runtime.contracts.proof import GuardVerdict
from mcoi_runtime.contracts.whqr import EvidenceGate,GateResult,NormGate,TruthGate,WHQRExpr,WHRole
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext,evaluate
from mcoi_runtime.whqr.static_checks import validate_static
def build_policy_decision(expr:WHQRExpr,*,subject_id:str,issued_at:str,goal_id:str="whqr-goal",context:WHQREvaluationContext|None=None,required_roles:tuple[WHRole,...]=())->PolicyDecision:
 static=validate_static(expr,required_roles); r=evaluate(expr,context); s=_status(static.passed,r); reason=DecisionReason(_msg(s),f"whqr_{s.value}",{"truth":r.truth.value,"norm":r.norm.value if r.norm else None,"evidence":r.evidence.value if r.evidence else None})
 return PolicyDecision(f"whqr:{goal_id}:{s.value}",subject_id,goal_id,s,(reason,),issued_at)
def build_guard_verdict(d:PolicyDecision)->GuardVerdict: return GuardVerdict("whqr_policy",d.status is PolicyDecisionStatus.ALLOW,d.reasons[0].message,{"policy_status":d.status.value})
def _status(ok:bool,r:GateResult)->PolicyDecisionStatus:
 if (not ok) or r.truth is TruthGate.FALSE or r.norm is NormGate.FORBIDDEN or r.evidence is EvidenceGate.CONTRADICTED: return PolicyDecisionStatus.DENY
 if r.truth is TruthGate.UNKNOWN or r.norm in {NormGate.ESCALATE,NormGate.REQUIRES_APPROVAL} or r.evidence in {EvidenceGate.UNPROVEN,EvidenceGate.STALE,EvidenceGate.BUDGET_UNKNOWN,EvidenceGate.FORBIDDEN_UNKNOWN}: return PolicyDecisionStatus.ESCALATE
 return PolicyDecisionStatus.ALLOW
def _msg(s:PolicyDecisionStatus)->str: return "WHQR tree satisfied truth, norm, and evidence gates" if s is PolicyDecisionStatus.ALLOW else ("WHQR tree denied by static, truth, norm, or evidence gate" if s is PolicyDecisionStatus.DENY else "WHQR tree requires escalation before MIL compilation")
