"""Purpose: verify world-state and meta-reasoning integration into the live operator loop.
Governance scope: runtime integration tests only.
Dependencies: operator loop, bootstrap, world-state engine, meta-reasoning engine.
Invariants:
  - Dispatched runs populate world-state entities and capability confidence.
  - Reports expose world-state hash, entity count, degraded capabilities.
  - Execution semantics are unchanged.
"""

from __future__ import annotations

import sys

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import render_run_summary
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.app.view_models import RunSummaryView
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge


_VALID_TEMPLATE = {
    "template_id": "test-tpl",
    "action_type": "shell_command",
    "command_argv": [sys.executable, "-c", "print('hello')"],
}
_CLOCK = "2026-03-19T00:00:00+00:00"


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


# --- World-state integration ---


def test_dispatched_run_populates_world_state() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))

    assert report.dispatched
    assert report.world_state_hash is not None
    assert len(report.world_state_hash) == 64
    assert report.world_state_entity_count >= 1


def test_non_dispatched_run_has_empty_world_state() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
        blocked_knowledge_ids=("blocked-1",),
    ))

    assert not report.dispatched
    assert report.world_state_entity_count == 0


def test_world_state_hash_changes_across_runs() -> None:
    loop = _make_loop()
    report1 = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    report2 = loop.run_step(OperatorRequest(
        request_id="req-2", subject_id="s-1", goal_id="g-2",
        template=_VALID_TEMPLATE, bindings={},
    ))

    # Two different runs should produce different world-state hashes
    # (different entities registered)
    assert report1.world_state_hash != report2.world_state_hash
    assert report2.world_state_entity_count == 2


# --- Meta-reasoning integration ---


def test_dispatched_run_updates_capability_confidence() -> None:
    loop = _make_loop()
    loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))

    confidence = loop.runtime.meta_reasoning.get_confidence("shell_command")
    assert confidence is not None
    assert confidence.sample_count == 1
    assert confidence.success_rate > 0


def test_multiple_runs_accumulate_confidence() -> None:
    loop = _make_loop()
    for i in range(3):
        loop.run_step(OperatorRequest(
            request_id=f"req-{i}", subject_id="s-1", goal_id=f"g-{i}",
            template=_VALID_TEMPLATE, bindings={},
        ))

    confidence = loop.runtime.meta_reasoning.get_confidence("shell_command")
    assert confidence is not None
    assert confidence.sample_count == 3


def test_degraded_capabilities_reported() -> None:
    loop = _make_loop()
    # Set a very high threshold so shell_command becomes degraded
    loop.runtime.meta_reasoning.set_threshold("shell_command", 0.99)
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))

    # After one run, confidence won't be 0.99 so it should be degraded
    assert "shell_command" in report.degraded_capabilities


# --- Console rendering ---


def test_console_shows_world_state_in_dispatched_run() -> None:
    loop = _make_loop()
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    view = RunSummaryView.from_report(report)
    output = render_run_summary(view)

    assert "world_state_hash" in output
    assert "entities" in output


def test_console_shows_degraded_capabilities() -> None:
    loop = _make_loop()
    loop.runtime.meta_reasoning.set_threshold("shell_command", 0.99)
    report = loop.run_step(OperatorRequest(
        request_id="req-1", subject_id="s-1", goal_id="g-1",
        template=_VALID_TEMPLATE, bindings={},
    ))
    view = RunSummaryView.from_report(report)
    output = render_run_summary(view)

    assert "degraded" in output
    assert "shell_command" in output
