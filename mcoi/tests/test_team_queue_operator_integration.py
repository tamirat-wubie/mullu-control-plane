"""Purpose: verify governed operator-surface team queue reconciliation and restore flows.
Governance scope: team queue operator integration only.
Dependencies: app bootstrap/operator facade, team queue persistence, and autonomy enforcement.
Invariants:
  - team queue restore is explicit and never automatic.
  - read-only queue assessment remains available under analyze-permitted autonomy modes.
  - invalid persisted team queue witnesses fail closed before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import OperatorLoop, TeamQueueReconcileRequest
from mcoi_runtime.persistence.team_queue_store import TeamQueueStore


def _seed_queue_store(base_path: Path) -> TeamQueueStore:
    store = TeamQueueStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.team_engine.capture_queue_state("team-a", queued=5, assigned=3, waiting=2)
    runtime.team_engine.capture_queue_state("team-b", queued=1, assigned=1, waiting=0)
    store.save_queue_states(runtime.team_engine)
    return store


def test_reconcile_team_queues_assesses_in_memory_state_under_observe_only() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="observe_only"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )
    runtime.team_engine.capture_queue_state("team-a", queued=5, assigned=3, waiting=2)
    runtime.team_engine.capture_queue_state("team-b", queued=1, assigned=1, waiting=0)
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-1",
            subject_id="subject-1",
        )
    )

    assert report.restored is False
    assert report.autonomy_decision == "allowed"
    assert report.policy_status == "allow"
    assert report.queue_state_count == 2
    assert report.team_ids == ("team-a", "team-b")
    assert report.total_queued_jobs == 6
    assert report.total_assigned_jobs == 4
    assert report.total_waiting_jobs == 2
    assert report.total_overloaded_workers == 0
    assert report.errors == ()


def test_reconcile_team_queues_restores_and_filters_selected_teams(tmp_path: Path) -> None:
    store = _seed_queue_store(tmp_path / "team-queue")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        team_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-2",
            subject_id="subject-1",
            team_ids=("team-b",),
            restore_from_store=True,
        )
    )

    assert report.restored is True
    assert report.policy_status == "allow"
    assert report.queue_state_count == 1
    assert report.team_ids == ("team-b",)
    assert report.total_queued_jobs == 1
    assert report.total_assigned_jobs == 1
    assert report.total_waiting_jobs == 0
    assert report.total_overloaded_workers == 0
    assert runtime.team_engine.queue_state_count == 2
    assert report.errors == ()


def test_reconcile_team_queues_fails_closed_without_configured_store() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-3",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.queue_state_count == 0
    assert report.errors[0].error_code == "team_queue_store_not_configured"


def test_reconcile_team_queues_fails_closed_on_invalid_persisted_state(tmp_path: Path) -> None:
    store = _seed_queue_store(tmp_path / "team-queue")
    payload_path = tmp_path / "team-queue" / "team_queue_states.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["queue_states"].append(dict(payload["queue_states"][0]))
    payload_path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        team_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-4",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.queue_state_count == 0
    assert report.errors[0].error_code == "team_queue_restore_failed"
    assert runtime.team_engine.queue_state_count == 0


def test_reconcile_team_queues_fails_closed_on_missing_requested_team(tmp_path: Path) -> None:
    store = _seed_queue_store(tmp_path / "team-queue")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        team_queue_store=store,
        restore_team_queue=True,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-5",
            subject_id="subject-1",
            team_ids=("team-missing",),
        )
    )

    assert report.restored is False
    assert report.queue_state_count == 0
    assert report.errors[0].error_code == "team_queue_state_missing"


def test_reconcile_team_queues_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    store = _seed_queue_store(tmp_path / "team-queue")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
        team_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_team_queues(
        TeamQueueReconcileRequest(
            request_id="queue-reconcile-6",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.policy_decision_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.team_engine.queue_state_count == 0
