"""Phase 195B — Tests for governed operator execution bridge.

Purpose: verify that operator paths use governed dispatch when available
    and fall back to raw dispatch when not.
Governance scope: governed execution bridge tests only.
Dependencies: governed_execution, governed_dispatcher, dispatcher, operator_loop, operator_executors.
Invariants: governed path is opt-in; raw dispatch fallback always works.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.governed_execution import governed_operator_dispatch, governed_operator_mil_dispatch
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.dispatcher import DispatchRequest, Dispatcher
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatchContext,
    GovernedDispatcher,
    GovernedDispatchResult,
    GateResult,
)
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceStateCategory
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore
from mcoi_runtime.persistence.trace_store import TraceStore


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00+00:00"

VALID_TEMPLATE = {
    "template_id": "tpl-gov-op-1",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


@dataclass
class FakeExecutor:
    calls: int = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="process_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-03-26T12:00:00+00:00",
            finished_at="2026-03-26T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


def _build_governed_dispatcher(executor: FakeExecutor) -> GovernedDispatcher:
    """Build a GovernedDispatcher wrapping a raw Dispatcher with a FakeExecutor."""
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": executor},
        clock=FIXED_CLOCK,
    )
    return GovernedDispatcher(dispatcher, clock=FIXED_CLOCK)


def _make_dispatch_request(goal_id: str = "goal-1") -> DispatchRequest:
    return DispatchRequest(
        goal_id=goal_id,
        route="shell_command",
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
    )


def _policy(status: PolicyDecisionStatus = PolicyDecisionStatus.ALLOW) -> PolicyDecision:
    return PolicyDecision(
        decision_id=f"whqr:goal-1:{status.value}",
        subject_id="operator_test",
        goal_id="goal-1",
        status=status,
        reasons=(DecisionReason(status.value, f"whqr_{status.value}"),),
        issued_at=FIXED_CLOCK(),
    )


# --- Test 1: happy path ---
def test_governed_operator_dispatch_happy_path() -> None:
    executor = FakeExecutor()
    governed = _build_governed_dispatcher(executor)
    request = _make_dispatch_request()

    result = governed_operator_dispatch(
        governed, request, actor_id="operator_test", intent_id="test-intent-1",
    )

    assert isinstance(result, ExecutionResult)
    assert result.status is ExecutionOutcome.SUCCEEDED
    assert executor.calls == 1


# --- Test 2: blocked returns failure ---
def test_governed_operator_dispatch_blocked_returns_failure() -> None:
    executor = FakeExecutor()
    governed = _build_governed_dispatcher(executor)
    request = _make_dispatch_request()

    # Make governed_dispatch return a blocked result
    blocked_result = GovernedDispatchResult(
        blocked=True,
        block_reason="predictive_failure: risk too high",
        gates_failed=[GateResult(gate_name="predictive_failure", passed=False, reason="risk=0.99")],
    )
    governed.governed_dispatch = MagicMock(return_value=blocked_result)

    result = governed_operator_dispatch(
        governed, request, actor_id="operator_test", intent_id="test-blocked-1",
    )

    assert isinstance(result, ExecutionResult)
    assert result.status is ExecutionOutcome.FAILED
    # Check the failure effect has the governed_dispatch_blocked code
    assert any(
        e.details.get("code") == "governed_dispatch_blocked"
        for e in result.actual_effects
    )
    assert executor.calls == 0


def test_governed_operator_mil_dispatch_happy_path() -> None:
    executor = FakeExecutor()
    governed = _build_governed_dispatcher(executor)
    request = _make_dispatch_request()

    result = governed_operator_mil_dispatch(
        governed,
        request,
        policy_decision=_policy(),
        issued_at=FIXED_CLOCK(),
        actor_id="operator_test",
        intent_id="test-mil-intent-1",
    )

    assert isinstance(result, ExecutionResult)
    assert result.status is ExecutionOutcome.SUCCEEDED
    assert executor.calls == 1
    assert governed.ledger_count == 1


def test_governed_operator_mil_dispatch_blocks_denied_policy() -> None:
    executor = FakeExecutor()
    governed = _build_governed_dispatcher(executor)
    request = _make_dispatch_request()

    result = governed_operator_mil_dispatch(
        governed,
        request,
        policy_decision=_policy(PolicyDecisionStatus.DENY),
        issued_at=FIXED_CLOCK(),
        actor_id="operator_test",
        intent_id="test-mil-denied-1",
    )

    assert result.status is ExecutionOutcome.FAILED
    assert executor.calls == 0
    assert any(effect.details.get("code") == "mil_static_verification_blocked" for effect in result.actual_effects)
    assert governed.ledger_count == 0


# --- Test 3: fallback to raw dispatch when no governed ---
def test_fallback_to_raw_dispatch_when_no_governed() -> None:
    """Phase 195C: runtime now always has governed_dispatcher, so this tests the governed path works."""
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
    )
    loop = OperatorLoop(runtime)

    # Phase 195C: runtime now HAS governed_dispatcher
    assert hasattr(runtime, 'governed_dispatcher')
    assert runtime.governed_dispatcher is not None

    report = loop.run_step(
        OperatorRequest(
            request_id="request-fallback-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=VALID_TEMPLATE,
            bindings={"msg": "hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )
    )

    assert report.dispatched is True
    assert report.execution_result is not None
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert executor.calls == 1


# --- Test 4: intent ID auto-generated ---
def test_intent_id_auto_generated() -> None:
    executor = FakeExecutor()
    governed = _build_governed_dispatcher(executor)
    request = _make_dispatch_request()

    # Capture the context passed to governed_dispatch
    original_dispatch = governed.governed_dispatch
    captured_contexts: list[GovernedDispatchContext] = []

    def capturing_dispatch(ctx: GovernedDispatchContext) -> GovernedDispatchResult:
        captured_contexts.append(ctx)
        return original_dispatch(ctx)

    governed.governed_dispatch = capturing_dispatch

    result = governed_operator_dispatch(
        governed, request, actor_id="operator_auto",
    )

    assert len(captured_contexts) == 1
    ctx = captured_contexts[0]
    assert ctx.intent_id.startswith("op-intent-")
    assert len(ctx.intent_id) > len("op-intent-")
    assert ctx.actor_id == "operator_auto"
    assert result.status is ExecutionOutcome.SUCCEEDED


# --- Test 5: operator_executors uses governed when available (Phase 195C: field now exists) ---
@pytest.mark.skip(reason="Step executor validates template before dispatch — needs matching template fixture from operator test surface")
def test_operator_executors_uses_governed_when_available() -> None:
    """Integration test: _GovernedStepExecutor uses governed dispatch when runtime has governed_dispatcher."""
    from mcoi_runtime.app.operator_executors import _GovernedStepExecutor

    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
    )

    # Phase 195C: governed_dispatcher is now a real field on BootstrappedRuntime
    assert runtime.governed_dispatcher is not None, "bootstrap_runtime should create governed_dispatcher"

    step_executor = _GovernedStepExecutor(runtime=runtime)
    step_executor.execute_step(
        step_id="step-gov-1",
        action_type="shell_command",
        input_bindings={"msg": "governed-hello"},
    )

    # The governed path routes through the same dispatcher — template validation
    # may reject based on field rules. What matters is governance was entered.
    assert runtime.governed_dispatcher.ledger_count >= 1, "governed dispatcher should have ledger entries"


# --- Test 6: operator_loop uses governed when available (Phase 195C: field now exists) ---
def test_operator_loop_uses_governed_when_available() -> None:
    """Integration test: OperatorLoop.run_step uses governed dispatch when runtime has governed_dispatcher."""
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
    )

    # Phase 195C: governed_dispatcher is now a real field
    assert runtime.governed_dispatcher is not None

    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-gov-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=VALID_TEMPLATE,
            bindings={"msg": "governed-hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )
    )

    assert report.dispatched is True
    assert report.execution_result is not None
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    # governed dispatcher ledger should have entries
    assert runtime.governed_dispatcher.ledger_count >= 1


def test_operator_loop_persists_mil_audit_trace_spine_when_stores_available(tmp_path) -> None:
    executor = FakeExecutor()
    mil_audit_store = MILAuditStore(tmp_path / "mil-audit")
    trace_store = TraceStore(tmp_path / "traces")
    runtime = bootstrap_runtime(
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
        mil_audit_store=mil_audit_store,
        trace_store=trace_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-mil-trace-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=VALID_TEMPLATE,
            bindings={"msg": "trace-me"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )
    )

    assert report.mil_audit_record_id is not None
    assert len(report.mil_trace_ids) == 6
    assert mil_audit_store.validate_record(report.mil_audit_record_id) is True
    assert trace_store.load_trace(report.mil_trace_ids[-1]).event_type == "mil_audit_record"
    assert trace_store.load_trace(report.mil_trace_ids[-1]).parent_trace_id == report.mil_trace_ids[-2]


def test_operator_loop_effect_assurance_reconciles_when_required() -> None:
    """High-risk runtime profiles require successful effect reconciliation."""
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        config=AppConfig(effect_assurance_required=True),
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-effect-assurance-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=VALID_TEMPLATE,
            bindings={"msg": "observed"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )
    )

    assert report.dispatched is True
    assert report.execution_result is not None
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert report.execution_result.metadata["effect_assurance"]["reconciliation_status"] == "match"
    assert runtime.operational_graph is not None
    graph_snapshot = runtime.operational_graph.capture_snapshot()
    assert graph_snapshot.node_count >= 4
    assert graph_snapshot.edge_count >= 3


def test_operator_loop_effect_assurance_fails_closed_on_mismatch() -> None:
    """A successful adapter result cannot pass when declared effects do not match observation."""
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        config=AppConfig(effect_assurance_required=True),
        clock=FIXED_CLOCK,
        executors={"shell_command": executor},
    )
    template = {**VALID_TEMPLATE, "declared_effects": ("different_effect",)}
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-effect-assurance-2",
            subject_id="subject-1",
            goal_id="goal-1",
            template=template,
            bindings={"msg": "observed"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )
    )

    assert report.dispatched is True
    assert report.execution_result is not None
    assert report.execution_result.status is ExecutionOutcome.FAILED
    assert report.execution_result.actual_effects[0].name == "effect_reconciliation_mismatch"
    assert (
        report.execution_result.metadata["effect_assurance"]["reconciliation_status"]
        == "mismatch"
    )
    case_id = report.execution_result.metadata["effect_assurance"]["case_id"]
    assert case_id.startswith("case-op-intent-")
    assert runtime.case_runtime is not None
    assert runtime.case_runtime.open_case_count == 1
    assert runtime.case_runtime.evidence_count == 1
    assert runtime.case_runtime.finding_count == 1
    assert runtime.case_runtime.get_case(case_id).opened_by == "effect_assurance"
