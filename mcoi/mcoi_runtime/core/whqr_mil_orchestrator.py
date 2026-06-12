"""Purpose: orchestrate WHQR-to-audit governed execution flow.
Governance scope: compose semantic evaluation, MIL compilation, governed dispatch, terminal closure, learning admission, and audit reconstruction.
Dependencies: WHQR contracts, clarification contracts, MIL compiler, governed dispatcher bridge, terminal certificate, learning admission, and audit reconstruction.
Invariants: every stage is explicit; failures stop at their boundary; side effects occur only inside governed dispatcher.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from mcoi_runtime.contracts.conversation import ClarificationRequest, ClarificationResponse
from mcoi_runtime.contracts.goal import GoalDescriptor
from mcoi_runtime.contracts.meta_reasoning import ReplanRecommendation
from mcoi_runtime.core.adaptive_reasoning import ComplexityAssessment
from mcoi_runtime.contracts.whqr import WHQRDocument, WHQRExpr, WHRole
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult, GovernedDispatcher
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.meta_reasoning_integration import MetaReasoningBridge
from mcoi_runtime.core.mil_audit_reconstruction import MILAuditReconstruction, reconstruct_mil_audit
from mcoi_runtime.core.mil_dispatcher_bridge import dispatch_verified_mil
from mcoi_runtime.core.mil_learning_admission import MILLearningAdmissionResult, admit_mil_terminal_learning
from mcoi_runtime.core.mil_terminal_certificate import MILTerminalCertificateBundle, certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.clarification import (
    WHQRClarificationBindingMap,
    build_binding_clarification_requests,
    build_binding_map_from_clarification_responses,
)
from mcoi_runtime.whqr.entity_binder import bind_entities
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
    replan_recommendation: ReplanRecommendation | None = None
    complexity_assessment: ComplexityAssessment | None = None
    clarification_requests: tuple[ClarificationRequest, ...] = ()
    clarification_binding_map: WHQRClarificationBindingMap | None = None

def run_whqr_mil_orchestration(*,expr:WHQRExpr,goal:GoalDescriptor,subject_id:str,issued_at:str,governed:GovernedDispatcher,certifier:TerminalClosureCertifier,episodic:EpisodicMemory,actor_id:str,intent_id:str,template:Mapping[str,Any],bindings:Mapping[str,str],context:WHQREvaluationContext|None=None,required_roles:tuple[WHRole,...]=(),capability:str="capability.pending",mode:str="simulation",meta_reasoning:MetaReasoningEngine|None=None,complexity_classifier:Callable[[str],ComplexityAssessment]|None=None,case_id:str|None=None,clarification_thread_id:str|None=None,binding_clarification_requests:tuple[ClarificationRequest,...]=(),binding_clarification_responses:tuple[ClarificationResponse,...]=())->WHQRMILOrchestrationResult:
    clarification_binding_map=None
    bound_expr=expr
    if binding_clarification_responses:
        clarification_binding_map=build_binding_map_from_clarification_responses(
            binding_clarification_requests,
            binding_clarification_responses,
        )
        if clarification_binding_map.accepted_count:
            bound_expr=bind_entities(expr,clarification_binding_map.as_binding_candidates()).expr
    document=WHQRDocument(root=bound_expr)
    goal_compilation=compile_goal_from_whqr(bound_expr,goal,subject_id=subject_id,issued_at=issued_at,context=context,required_roles=required_roles)
    if clarification_binding_map is not None and not clarification_binding_map.passed:
        return WHQRMILOrchestrationResult(document,goal_compilation,None,None,None,None,None,False,"resolve_whqr_clarification_response",clarification_binding_map=clarification_binding_map)
    if not goal_compilation.ready_for_mil:
        clarifications=()
        if goal_compilation.next_step=="resolve_whqr_binding":
            clarifications=build_binding_clarification_requests(
                goal_compilation.binding_report,
                thread_id=clarification_thread_id or intent_id,
                requested_from_id=actor_id,
                requested_at=issued_at,
                request_prefix=f"whqr-binding:{goal.goal_id}",
            ).requests
        return WHQRMILOrchestrationResult(document,goal_compilation,None,None,None,None,None,False,goal_compilation.next_step,clarification_requests=clarifications,clarification_binding_map=clarification_binding_map)
    if meta_reasoning is not None:
        replan=MetaReasoningBridge.gate_goal_capability(meta_reasoning,capability_id=capability,affected_entity_id=goal.goal_id)
        if replan is not None:
            return WHQRMILOrchestrationResult(document,goal_compilation,None,None,None,None,None,False,"meta_reasoning_replan",replan,clarification_binding_map=clarification_binding_map)
    # Cognition metering: classify the goal and stamp the complexity tier
    # into the MIL program metadata. Advisory only — it never alters control
    # flow or blocks; provider routing reads it to meter model spend.
    complexity=complexity_classifier(goal.description) if complexity_classifier is not None else None
    extra_metadata=None if complexity is None else {
        "complexity.level":complexity.level.value,
        "complexity.confidence":complexity.confidence,
        "complexity.reason":complexity.reason,
        "complexity.suggested_model":complexity.suggested_model,
        "complexity.suggested_max_tokens":complexity.suggested_max_tokens,
    }
    program=compile_mil_from_whqr_goal(goal_compilation,issued_at=issued_at,capability=capability,extra_metadata=extra_metadata)
    dispatch_result=dispatch_verified_mil(program,governed,actor_id=actor_id,intent_id=intent_id,template=template,bindings=bindings,mode=mode)
    if dispatch_result.blocked:
        return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,None,None,None,False,"dispatch_blocked",complexity_assessment=complexity,clarification_binding_map=clarification_binding_map)
    terminal=certify_mil_dispatch_result(program,dispatch_result,certifier,case_id=case_id)
    learning=admit_mil_terminal_learning(terminal,episodic,issued_at=issued_at)
    if learning.memory_entry is None:
        return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,terminal,learning,None,False,"learning_deferred",complexity_assessment=complexity,clarification_binding_map=clarification_binding_map)
    audit=reconstruct_mil_audit(terminal,learning,whqr_document=document,recorded_at=issued_at)
    return WHQRMILOrchestrationResult(document,goal_compilation,program,dispatch_result,terminal,learning,audit,True,"complete",complexity_assessment=complexity,clarification_binding_map=clarification_binding_map)
