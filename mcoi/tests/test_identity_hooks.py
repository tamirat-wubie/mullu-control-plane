"""Purpose: verify identity hooks — explicit IDs on operator-loop reports and persistence round-trips.
Governance scope: identity-hook tests only.
Dependencies: operator loop, persistence stores, contracts.
Invariants: IDs are explicit, stable, and survive persistence round-trips.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)
from mcoi_runtime.persistence import ReplayStore, SnapshotStore, TraceStore


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


# --- Operator-loop report ID presence tests ---


def test_report_carries_goal_id() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-42",
            template=_VALID_TEMPLATE,
            bindings={},
        )
    )
    assert report.goal_id == "goal-42"


def test_report_carries_policy_decision_id() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
        )
    )
    assert report.policy_decision_id
    assert report.policy_decision_id == report.policy_decision.decision_id


def test_report_carries_execution_id_when_dispatched() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
        )
    )
    assert report.dispatched
    assert report.execution_id is not None
    assert report.execution_id == report.execution_result.execution_id


def test_report_execution_id_is_none_when_not_dispatched() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
            blocked_knowledge_ids=("blocked-1",),
        )
    )
    assert not report.dispatched
    assert report.execution_id is None


def test_report_verification_id_is_none_when_no_verification() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
        )
    )
    assert report.verification_id is None


def test_report_ids_present_on_admissibility_failure() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-99",
            template=_VALID_TEMPLATE,
            bindings={},
            knowledge_entries=(
                PlanningKnowledge("k-1", "constraint", KnowledgeLifecycle.BLOCKED),
            ),
        )
    )
    assert report.goal_id == "goal-99"
    assert report.policy_decision_id
    assert report.execution_id is None
    assert report.verification_id is None


# --- Persistence ID round-trip tests ---


def test_trace_id_survives_persistence_round_trip(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    entry = TraceEntry(
        trace_id="trace-abc-123",
        parent_trace_id=None,
        event_type="test",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash="hash-1",
        registry_hash="reg-hash-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )
    store.append(entry)
    loaded = store.load_trace("trace-abc-123")
    assert loaded.trace_id == "trace-abc-123"
    assert loaded.subject_id == "subject-1"
    assert loaded.goal_id == "goal-1"


def test_replay_id_survives_persistence_round_trip(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    record = ReplayRecord(
        replay_id="replay-xyz-789",
        trace_id="trace-1",
        source_hash="source-1",
        approved_effects=(
            ReplayEffect(
                effect_id="eff-1",
                control=EffectControl.CONTROLLED,
                artifact_id="art-1",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="art-1", payload_digest="dig-1"),),
        state_hash="state-abc",
        environment_digest="env-def",
    )
    store.save(record)
    loaded = store.load("replay-xyz-789")
    assert loaded.replay_id == "replay-xyz-789"
    assert loaded.trace_id == "trace-1"
    assert loaded.state_hash == "state-abc"
    assert loaded.environment_digest == "env-def"


def test_snapshot_id_survives_persistence_round_trip(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    meta = store.save_snapshot("snap-unique-42", {"data": "value"}, description="test")
    assert meta.snapshot_id == "snap-unique-42"

    loaded_meta, loaded_data = store.load_snapshot("snap-unique-42")
    assert loaded_meta.snapshot_id == "snap-unique-42"
    assert loaded_data == {"data": "value"}


def test_trace_parent_id_preserved(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    parent = TraceEntry(
        trace_id="trace-parent",
        parent_trace_id=None,
        event_type="root",
        subject_id="s-1",
        goal_id="g-1",
        state_hash="h-1",
        registry_hash="r-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )
    child = TraceEntry(
        trace_id="trace-child",
        parent_trace_id="trace-parent",
        event_type="step",
        subject_id="s-1",
        goal_id="g-1",
        state_hash="h-2",
        registry_hash="r-1",
        timestamp="2026-03-19T00:00:01+00:00",
    )
    store.append(parent)
    store.append(child)

    loaded_child = store.load_trace("trace-child")
    assert loaded_child.parent_trace_id == "trace-parent"
    loaded_parent = store.load_trace("trace-parent")
    assert loaded_parent.parent_trace_id is None
