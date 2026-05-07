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
from mcoi_runtime.core.memory import EpisodicMemory
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
