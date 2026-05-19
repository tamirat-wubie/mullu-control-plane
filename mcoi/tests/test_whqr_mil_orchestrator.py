"""Purpose: verify WHQR-to-audit orchestration facade.
Governance scope: deterministic composition of WHQR, MIL, governed dispatch, terminal closure, learning admission, and audit reconstruction.
Dependencies: orchestrator, governed dispatcher, dispatcher, WHQR contracts, memory, and terminal closure certifier.
Invariants: unresolved WHQR stops before MIL; successful flow reaches observation-only audit reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalPriority
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence, ReplanReason
from mcoi_runtime.contracts.replay import ReplayMode
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.whqr import (
    Connector,
    ConnectorExpr,
    EvidenceGate,
    GateResult,
    NormGate,
    TruthGate,
    WHQRNode,
    WHRole,
)
from mcoi_runtime.core.dispatcher import Dispatcher
from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
from mcoi_runtime.core.adaptive_reasoning import ComplexityLevel, classify_complexity
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.system_stabilization import EquilibriumEngine
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.whqr_mil_orchestrator import run_whqr_mil_orchestration
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext

VALID_TEMPLATE = {
    "template_id": "tpl-gov",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


def clock() -> str:
    return "2026-05-06T12:00:00+00:00"


@dataclass
class FakeExecutor:
    """Executor test double that records deterministic successful calls."""

    calls: int = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            request.execution_id,
            request.goal_id,
            ExecutionOutcome.SUCCEEDED,
            (EffectRecord("process_completed", {"argv": list(request.argv)}),),
            (),
            clock(),
            clock(),
        )


def test_whqr_mil_orchestrator_completes_to_audit_reconstruction() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
    )

    assert result.completed is True
    assert result.next_step == "complete"
    assert result.mil_program is not None
    assert result.terminal_bundle is not None
    assert result.terminal_bundle.certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert result.learning_result is not None
    assert result.learning_result.decision.status is LearningAdmissionStatus.ADMIT
    assert result.audit_reconstruction is not None
    assert result.audit_reconstruction.replay_record.mode is ReplayMode.OBSERVATION_ONLY
    assert memory.size == 1
    assert executor.calls == 1


def test_whqr_mil_orchestrator_stops_before_mil_when_whqr_unresolved() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    result = run_whqr_mil_orchestration(
        expr=WHQRNode(WHRole.WHO, "approver"),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
    )

    assert result.completed is False
    assert result.next_step == "resolve_whqr_escalation"
    assert result.mil_program is None
    assert result.dispatch_result is None
    assert memory.size == 0
    assert executor.calls == 0


def test_meta_reasoning_gate_halts_before_mil_when_capability_degraded() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()
    engine = MetaReasoningEngine(clock=clock)
    engine.update_confidence(_degraded_confidence("shell_command"))
    assert engine.is_degraded("shell_command") is True

    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
        meta_reasoning=engine,
    )

    assert result.completed is False
    assert result.next_step == "meta_reasoning_replan"
    assert result.mil_program is None
    assert result.dispatch_result is None
    assert result.terminal_bundle is None
    assert result.replan_recommendation is not None
    assert result.replan_recommendation.reason is ReplanReason.SUBSYSTEM_DEGRADED
    assert result.replan_recommendation.affected_entity_id == "goal"
    # The gate is a hard stop: no dispatch, no learning, no audit.
    assert memory.size == 0
    assert executor.calls == 0


def test_meta_reasoning_gate_allows_when_capability_healthy() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()
    engine = MetaReasoningEngine(clock=clock)
    engine.update_confidence(_healthy_confidence("shell_command"))
    assert engine.is_degraded("shell_command") is False

    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
        meta_reasoning=engine,
    )

    assert result.completed is True
    assert result.next_step == "complete"
    assert result.replan_recommendation is None
    assert result.audit_reconstruction is not None
    assert memory.size == 1
    assert executor.calls == 1


def test_meta_reasoning_gate_absent_engine_is_backward_compatible() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    # Explicitly passing meta_reasoning=None must be identical to omitting it.
    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
        meta_reasoning=None,
    )

    assert result.completed is True
    assert result.next_step == "complete"
    assert result.replan_recommendation is None
    assert memory.size == 1
    assert executor.calls == 1


def test_complexity_classifier_stamps_tier_into_mil_metadata_and_result() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
        complexity_classifier=classify_complexity,
    )

    assert result.completed is True
    assert result.complexity_assessment is not None
    # "Govern shell command" is <=10 words with no complex signals -> LOW.
    assert result.complexity_assessment.level is ComplexityLevel.LOW
    md = result.mil_program.metadata
    # Tier is metered into the durable, replayable MIL record.
    assert md["complexity.level"] == "low"
    assert md["complexity.suggested_model"] == result.complexity_assessment.suggested_model
    assert md["complexity.suggested_max_tokens"] == result.complexity_assessment.suggested_max_tokens
    # Compiler-owned keys win — caller metadata cannot spoof identity.
    assert md["compiler"] == "whqr_policy_mil_compiler"
    assert md["capability"] == "shell_command"
    # Classification is deterministic for the same input.
    assert classify_complexity(_goal().description).level is ComplexityLevel.LOW


def test_complexity_classifier_is_advisory_and_never_blocks() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    # A MAX-complexity goal must still complete — metering is not a gate.
    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal_desc("comprehensive security audit end-to-end review"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
        complexity_classifier=classify_complexity,
    )

    assert result.completed is True
    assert result.next_step == "complete"
    assert result.complexity_assessment is not None
    assert result.complexity_assessment.level is ComplexityLevel.MAX
    assert result.audit_reconstruction is not None
    assert memory.size == 1
    assert executor.calls == 1


def test_complexity_classifier_absent_leaves_metadata_unchanged() -> None:
    governed, executor = _governed()
    memory = EpisodicMemory()

    result = run_whqr_mil_orchestration(
        expr=_expr(),
        goal=_goal(),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        governed=governed,
        certifier=TerminalClosureCertifier(clock=clock),
        episodic=memory,
        actor_id="operator",
        intent_id="intent",
        template=VALID_TEMPLATE,
        bindings={"msg": "hi"},
        context=_context(),
        required_roles=(WHRole.WHAT, WHRole.WHY),
        capability="shell_command",
    )

    assert result.completed is True
    assert result.complexity_assessment is None
    md = result.mil_program.metadata
    assert not any(k.startswith("complexity.") for k in md)
    assert md["compiler"] == "whqr_policy_mil_compiler"
    assert md["capability"] == "shell_command"


def _goal_desc(description: str) -> GoalDescriptor:
    return GoalDescriptor("goal", description, GoalPriority.NORMAL, "2026-05-06T11:59:00Z")


def _degraded_confidence(capability_id: str) -> CapabilityConfidence:
    # overall = 0.3 * 0.3 * (1 - 0.5) = 0.045 < 0.5 default threshold.
    return CapabilityConfidence(
        capability_id=capability_id,
        success_rate=0.3,
        verification_pass_rate=0.3,
        timeout_rate=0.2,
        error_rate=0.5,
        sample_count=12,
        assessed_at=clock(),
    )


def _healthy_confidence(capability_id: str) -> CapabilityConfidence:
    # overall = 0.95 * 0.95 * (1 - 0.01) ~= 0.893 > 0.5 default threshold.
    return CapabilityConfidence(
        capability_id=capability_id,
        success_rate=0.95,
        verification_pass_rate=0.95,
        timeout_rate=0.01,
        error_rate=0.01,
        sample_count=40,
        assessed_at=clock(),
    )


def _governed() -> tuple[GovernedDispatcher, FakeExecutor]:
    executor = FakeExecutor()
    equilibrium = EquilibriumEngine()
    equilibrium.register_agent("operator")
    dispatcher = Dispatcher(TemplateValidator(), {"shell_command": executor}, clock)
    return GovernedDispatcher(dispatcher, equilibrium=equilibrium, clock=clock), executor


def _goal() -> GoalDescriptor:
    return GoalDescriptor(
        "goal",
        "Govern shell command",
        GoalPriority.NORMAL,
        "2026-05-06T11:59:00Z",
    )


def _expr() -> ConnectorExpr:
    return ConnectorExpr(
        Connector.BECAUSE,
        WHQRNode(WHRole.WHAT, "command_request"),
        WHQRNode(WHRole.WHY, "operator_requested"),
    )


def _context() -> WHQREvaluationContext:
    return WHQREvaluationContext(
        node_results={
            "command_request": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.PROVEN),
            "operator_requested": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
        }
    )
