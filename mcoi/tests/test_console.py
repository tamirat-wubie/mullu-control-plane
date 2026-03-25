"""Purpose: verify operator console view models and rendering.
Governance scope: console display tests only.
Dependencies: view_models, console renderer, runtime artifacts.
Invariants: view models are read-only projections; rendering is deterministic.
"""

from __future__ import annotations

from pathlib import Path
import sys

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import (
    render_coordination_summary,
    render_execution_summary,
    render_replay_summary,
    render_run_summary,
    render_runbook_summary,
    render_temporal_task,
)
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.app.view_models import (
    CoordinationSummaryView,
    ExecutionSummaryView,
    ReplaySummaryView,
    RunSummaryView,
    RunbookSummaryView,
    TemporalTaskView,
)
from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    DelegationRequest,
    HandoffRecord,
)
from mcoi_runtime.contracts.temporal import (
    TemporalState,
    TemporalTask,
    TemporalTrigger,
    TriggerType,
)
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.core.persisted_replay import PersistedReplayResult
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge
from mcoi_runtime.core.replay_engine import ReplayValidationResult, ReplayVerdict
from mcoi_runtime.core.runbook import RunbookAdmissionResult, RunbookAdmissionStatus


_CLOCK = "2026-03-19T00:00:00+00:00"

_VALID_TEMPLATE = {
    "template_id": "test-tpl",
    "action_type": "shell_command",
    "command_argv": [sys.executable, "-c", "print('hello')"],
}


def _make_loop() -> OperatorLoop:
    runtime = bootstrap_runtime(
        config=AppConfig(
            allowed_planning_classes=("constraint",),
            enabled_executor_routes=("shell_command",),
            enabled_observer_routes=("filesystem",),
        ),
        clock=lambda: _CLOCK,
    )
    return OperatorLoop(runtime=runtime)


# --- RunSummaryView tests ---


def test_run_summary_from_successful_report() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    view = RunSummaryView.from_report(report)

    assert view.request_id == "req-1"
    assert view.goal_id == "g-1"
    assert view.dispatched is True
    assert view.execution_id is not None
    assert view.structured_errors == ()


def test_run_summary_from_failed_report() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
        blocked_knowledge_ids=("blocked-1",),
    ))
    view = RunSummaryView.from_report(report)

    assert view.dispatched is False
    assert view.execution_id is None
    assert len(view.structured_errors) == 1
    assert view.structured_errors[0].family == "PolicyError"


def test_run_summary_renders() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    view = RunSummaryView.from_report(report)
    output = render_run_summary(view)

    assert "Run Summary" in output
    assert "req-1" in output
    assert "g-1" in output
    assert view.policy_decision_id in output


# --- ExecutionSummaryView tests ---


def test_execution_summary_dispatched() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    view = ExecutionSummaryView.from_report(report)

    assert view.dispatched is True
    assert view.execution_id is not None
    assert view.status is not None


def test_execution_summary_not_dispatched() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
        blocked_knowledge_ids=("b-1",),
    ))
    view = ExecutionSummaryView.from_report(report)

    assert view.dispatched is False
    assert view.execution_id is None

    output = render_execution_summary(view)
    assert "not dispatched" in output


# --- ReplaySummaryView tests ---


def test_replay_summary_from_result() -> None:
    result = PersistedReplayResult(
        replay_id="replay-1",
        trace_id="trace-1",
        validation=ReplayValidationResult(
            ready=True, reasons=(), artifacts=(),
            verdict=ReplayVerdict.MATCH,
        ),
        trace_found=True,
        trace_hash_matches=True,
    )
    view = ReplaySummaryView.from_result(result)

    assert view.replay_id == "replay-1"
    assert view.verdict == "replay_match"
    assert view.ready is True

    output = render_replay_summary(view)
    assert "replay-1" in output
    assert "replay_match" in output


# --- TemporalTaskView tests ---


def test_temporal_task_view() -> None:
    task = TemporalTask(
        task_id="task-1", goal_id="g-1", description="test",
        trigger=TemporalTrigger(trigger_id="t-1", trigger_type=TriggerType.AT_TIME, value="2027-01-01T00:00:00+00:00"),
        state=TemporalState.PENDING,
        created_at=_CLOCK,
        deadline="2027-06-01T00:00:00+00:00",
    )
    view = TemporalTaskView.from_task(task, has_checkpoint=True, transition_count=2)

    assert view.task_id == "task-1"
    assert view.state == "pending"
    assert view.trigger_type == "at_time"
    assert view.has_checkpoint is True
    assert view.transition_count == 2

    output = render_temporal_task(view)
    assert "task-1" in output
    assert "pending" in output
    assert "at_time" in output


# --- CoordinationSummaryView tests ---


def test_coordination_summary() -> None:
    engine = CoordinationEngine()
    engine.request_delegation(DelegationRequest(
        delegation_id="d-1", delegator_id="a", delegate_id="b",
        goal_id="g-1", action_scope="s",
    ))
    engine.record_handoff(HandoffRecord(
        handoff_id="h-1", from_party="a", to_party="b",
        goal_id="g-1", context_ids=("c-1",), handed_off_at=_CLOCK,
    ))
    engine.record_conflict(ConflictRecord(
        conflict_id="cf-1", goal_id="g-1",
        conflicting_ids=("x", "y"),
        strategy=ConflictStrategy.ESCALATE, resolved=False,
    ))

    view = CoordinationSummaryView.from_engine(engine)

    assert view.delegation_count == 1
    assert view.handoff_count == 1
    assert view.unresolved_conflict_count == 1

    output = render_coordination_summary(view)
    assert "1" in output


# --- RunbookSummaryView tests ---


def test_runbook_summary_admitted() -> None:
    view = RunbookSummaryView(
        runbook_id="rb-1",
        status="admitted",
        reasons=("all_admission_gates_passed",),
        provenance_execution_id="exec-1",
        provenance_replay_id="replay-1",
    )

    output = render_runbook_summary(view)
    assert "rb-1" in output
    assert "admitted" in output
    assert "exec-1" in output


def test_runbook_summary_rejected() -> None:
    result = RunbookAdmissionResult(
        runbook_id="rb-2",
        status=RunbookAdmissionStatus.REJECTED,
        reasons=("execution_did_not_succeed",),
    )
    view = RunbookSummaryView.from_admission(result)

    assert view.status == "rejected"
    assert view.provenance_execution_id is None

    output = render_runbook_summary(view)
    assert "rejected" in output
