"""Purpose: orchestrate WHQR-to-audit governed execution flow.
Governance scope: compose semantic evaluation, MIL compilation, governed dispatch, terminal closure, learning admission, and audit reconstruction.
Dependencies: WHQR contracts, MIL compiler, governed dispatcher bridge, terminal certificate, learning admission, and audit reconstruction.
Invariants: every stage is explicit; failures stop at their boundary; side effects occur only inside governed dispatcher.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from mcoi_runtime.contracts.goal import GoalDescriptor
from mcoi_runtime.contracts.whqr import WHQRDocument, WHQRExpr, WHRole
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult, GovernedDispatcher
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.mil_audit_reconstruction import MILAuditReconstruction, reconstruct_mil_audit
from mcoi_runtime.core.mil_dispatcher_bridge import dispatch_verified_mil
from mcoi_runtime.core.mil_learning_admission import MILLearningAdmissionResult, admit_mil_terminal_learning
from mcoi_runtime.core.mil_terminal_certificate import MILTerminalCertificateBundle, certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.goal_compiler import WHQRGoalCompilation, compile_goal_from_whqr
from mcoi_runtime.whqr.mil_compiler import compile_mil_from_whqr_goal

@dataclass(frozen=True, slots=True)
class WHQRMILOrchestrationResult:
    whqr_document: WHQRDocument
    goal_compilation: WHQRGoalCompilation
    mil_program: MILProgram | None
    dispatch_result: GovernedDispatchResult | None
    terminal_bundle: MILTerminalCertificateBundle | None
    learning_result: MILLearningAdmissionResult | None
    audit_reconstruction: MILAuditReconstruction | None
    completed: bool
    next_step: str

def run_whqr_mil_orchestration(*,expr:WHQRExpr,goal:GoalDescriptor,subject_id:str,issued_at:str,governed:GovernedDispatcher,certifier:TerminalClosureCertifier,episodic:EpisodicMemory,actor_id:str,intent_id:str,template:Mapping[str,Any],bindings:Mapping[str,str],context:WHQREvaluationContext|None=None,required_roles:tuple[WHRole,...]=(),capability:str="capability.pending",mode:str="simulation",case_id:str|None=None)->WHQRMILOrchestrationResult:
    document=WHQRDocument(root=expr)
    goal_compilation=compile_goal_from_whqr(expr,goal,subject_id=subject_id,issued_at=issued_at,context=context,required_roles=required_roles)
    if not goal_compilation.ready_for_mil:
        return WHQRMILOrchestrationResult(document,goal_compilation,None,None,None,None,None,False,goal_compilation.next_step)
    program=compile_mil_from_whqr_goal(goal_compilation,issued_at=issued_at,capability=capability)
    dispatch_result=dispatch_verified_mil(program,governed,actor_id=actor_id,intent_id=intent_id,template=template,bindings=bindings,mode=mode)
    if dispatch_result.blocked:
        return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,None,None,None,False,"dispatch_blocked")
    terminal=certify_mil_dispatch_result(program,dispatch_result,certifier,case_id=case_id)
    learning=admit_mil_terminal_learning(terminal,episodic,issued_at=issued_at)
    if learning.memory_entry is None:
        return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,terminal,learning,None,False,"learning_deferred")
    audit=reconstruct_mil_audit(terminal,learning,whqr_document=document,recorded_at=issued_at)
    return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,terminal,learning,audit,True,"complete")
