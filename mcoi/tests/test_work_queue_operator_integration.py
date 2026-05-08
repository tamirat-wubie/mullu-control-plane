"""Purpose: verify governed operator-surface work-queue reconciliation and restore flows.
Governance scope: work queue operator integration only.
Dependencies: app bootstrap/operator facade, work queue persistence, and autonomy enforcement.
Invariants:
  - work queue restore is explicit and never automatic.
  - read-only queue assessment remains available under analyze-permitted autonomy modes.
  - invalid persisted work-queue witnesses fail closed before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import OperatorLoop, WorkQueueReconcileRequest
from mcoi_runtime.contracts.job import JobPriority, WorkQueueEntry
from mcoi_runtime.persistence.work_queue_store import WorkQueueStore


def _seed_work_queue_store(base_path: Path) -> WorkQueueStore:
    store = WorkQueueStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-high",
            job_id="job-high",
            priority=JobPriority.HIGH,
            enqueued_at="2026-03-18T12:00:00+00:00",
            assigned_to_person_id="person-1",
        )
    )
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-normal",
            job_id="job-normal",
            priority=JobPriority.NORMAL,
            enqueued_at="2026-03-18T12:00:01+00:00",
            assigned_to_team_id="team-1",
        )
    )
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-low",
            job_id="job-low",
            priority=JobPriority.LOW,
            enqueued_at="2026-03-18T12:00:02+00:00",
        )
    )
    store.save_state(runtime.work_queue)
    return store


def test_reconcile_work_queue_assesses_in_memory_state_under_observe_only() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="observe_only"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-high",
            job_id="job-high",
            priority=JobPriority.HIGH,
            enqueued_at="2026-03-18T12:00:00+00:00",
            assigned_to_person_id="person-1",
        )
    )
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-normal",
            job_id="job-normal",
            priority=JobPriority.NORMAL,
            enqueued_at="2026-03-18T12:00:01+00:00",
            assigned_to_team_id="team-1",
        )
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-1",
            subject_id="subject-1",
        )
    )

    assert report.restored is False
    assert report.autonomy_decision == "allowed"
    assert report.policy_status == "allow"
    assert report.entry_count == 2
    assert report.entry_ids == ("entry-high", "entry-normal")
    assert report.next_entry_id == "entry-high"
    assert report.assigned_person_entry_count == 1
    assert report.assigned_team_entry_count == 1
    assert report.errors == ()


def test_reconcile_work_queue_restores_and_filters_selected_entries(tmp_path: Path) -> None:
    store = _seed_work_queue_store(tmp_path / "work-queue")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-2",
            subject_id="subject-1",
            entry_ids=("entry-normal",),
            restore_from_store=True,
        )
    )

    assert report.restored is True
    assert report.policy_status == "allow"
    assert report.entry_count == 1
    assert report.entry_ids == ("entry-normal",)
    assert report.next_entry_id == "entry-normal"
    assert report.assigned_person_entry_count == 0
    assert report.assigned_team_entry_count == 1
    assert len(runtime.work_queue.list_entries()) == 3
    assert report.errors == ()


def test_reconcile_work_queue_fails_closed_without_configured_store() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-3",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.entry_count == 0
    assert report.next_entry_id is None
    assert report.errors[0].error_code == "work_queue_store_not_configured"


def test_reconcile_work_queue_fails_closed_on_invalid_persisted_state(tmp_path: Path) -> None:
    store = _seed_work_queue_store(tmp_path / "work-queue")
    payload_path = tmp_path / "work-queue" / "work_queue.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["entries"].append(dict(payload["entries"][0]))
    payload_path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-4",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.entry_count == 0
    assert report.next_entry_id is None
    assert report.errors[0].error_code == "work_queue_restore_failed"
    assert runtime.work_queue.list_entries() == ()


def test_reconcile_work_queue_fails_closed_on_missing_requested_entry(tmp_path: Path) -> None:
    store = _seed_work_queue_store(tmp_path / "work-queue")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=store,
        restore_work_queue=True,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-5",
            subject_id="subject-1",
            entry_ids=("missing-entry",),
        )
    )

    assert report.restored is False
    assert report.entry_count == 0
    assert report.next_entry_id is None
    assert report.errors[0].error_code == "work_queue_entry_missing"


def test_reconcile_work_queue_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    store = _seed_work_queue_store(tmp_path / "work-queue")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_work_queue(
        WorkQueueReconcileRequest(
            request_id="work-queue-reconcile-6",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.entry_count == 0
    assert report.policy_decision_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.work_queue.list_entries() == ()
