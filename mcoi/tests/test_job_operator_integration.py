"""Purpose: verify governed operator-surface job-runtime reconciliation and restore flows.
Governance scope: job operator integration only.
Dependencies: app bootstrap/operator facade, job persistence, and autonomy enforcement.
Invariants:
  - job restore is explicit and never automatic.
  - read-only job assessment remains available under analyze-permitted autonomy modes.
  - invalid persisted job witnesses fail closed before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import JobReconcileRequest, OperatorLoop
from mcoi_runtime.contracts.job import JobDescriptor, JobPriority, JobState, JobStatus, SlaStatus
from mcoi_runtime.persistence.job_store import JobStore


def _seed_job_store(base_path: Path) -> JobStore:
    store = JobStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.job_engine.restore_job(
        JobDescriptor(
            job_id="job-active",
            name="Active Job",
            description="Persisted active job",
            priority=JobPriority.HIGH,
            created_at="2026-03-18T12:00:00+00:00",
        ),
        JobState(
            job_id="job-active",
            status=JobStatus.IN_PROGRESS,
            sla_status=SlaStatus.ON_TRACK,
            started_at="2026-03-18T12:00:01+00:00",
            updated_at="2026-03-18T12:00:01+00:00",
        ),
    )
    runtime.job_engine.restore_job(
        JobDescriptor(
            job_id="job-complete",
            name="Completed Job",
            description="Persisted completed job",
            priority=JobPriority.NORMAL,
            created_at="2026-03-18T12:00:00+00:00",
        ),
        JobState(
            job_id="job-complete",
            status=JobStatus.COMPLETED,
            sla_status=SlaStatus.NOT_APPLICABLE,
            started_at="2026-03-18T12:00:01+00:00",
            updated_at="2026-03-18T12:00:02+00:00",
        ),
    )
    runtime.job_engine.restore_job(
        JobDescriptor(
            job_id="job-failed",
            name="Failed Job",
            description="Persisted failed job",
            priority=JobPriority.LOW,
            created_at="2026-03-18T12:00:00+00:00",
        ),
        JobState(
            job_id="job-failed",
            status=JobStatus.FAILED,
            sla_status=SlaStatus.BREACHED,
            started_at="2026-03-18T12:00:01+00:00",
            updated_at="2026-03-18T12:00:03+00:00",
        ),
    )
    store.save_state(runtime.job_engine)
    return store


def test_reconcile_jobs_assesses_in_memory_state_under_observe_only() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="observe_only"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )
    first, _ = runtime.job_engine.create_job("Job One", "Live job one", JobPriority.HIGH)
    runtime.job_engine.start_job(first.job_id)
    second, _ = runtime.job_engine.create_job("Job Two", "Live job two", JobPriority.NORMAL)
    runtime.job_engine.start_job(second.job_id)
    runtime.job_engine.complete_job(second.job_id, "done")
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-1",
            subject_id="subject-1",
        )
    )

    assert report.restored is False
    assert report.autonomy_decision == "allowed"
    assert report.policy_status == "allow"
    assert report.job_count == 2
    assert report.active_job_count == 1
    assert report.completed_job_count == 1
    assert report.failed_job_count == 0
    assert report.errors == ()


def test_reconcile_jobs_restores_and_filters_selected_jobs(tmp_path: Path) -> None:
    store = _seed_job_store(tmp_path / "jobs")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-2",
            subject_id="subject-1",
            job_ids=("job-complete",),
            restore_from_store=True,
        )
    )

    assert report.restored is True
    assert report.policy_status == "allow"
    assert report.job_count == 1
    assert report.job_ids == ("job-complete",)
    assert report.active_job_count == 0
    assert report.completed_job_count == 1
    assert report.failed_job_count == 0
    assert len(runtime.job_engine.list_job_descriptors()) == 3
    assert report.errors == ()


def test_reconcile_jobs_fails_closed_without_configured_store() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-3",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.job_count == 0
    assert report.active_job_count == 0
    assert report.errors[0].error_code == "job_store_not_configured"


def test_reconcile_jobs_fails_closed_on_invalid_persisted_state(tmp_path: Path) -> None:
    store = _seed_job_store(tmp_path / "jobs")
    payload_path = tmp_path / "jobs" / "job_runtime.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["states"] = payload["states"][:-1]
    payload_path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-4",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.job_count == 0
    assert report.active_job_count == 0
    assert report.errors[0].error_code == "job_restore_failed"
    assert runtime.job_engine.list_job_descriptors() == ()


def test_reconcile_jobs_fails_closed_on_missing_requested_job(tmp_path: Path) -> None:
    store = _seed_job_store(tmp_path / "jobs")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=store,
        restore_jobs=True,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-5",
            subject_id="subject-1",
            job_ids=("missing-job",),
        )
    )

    assert report.restored is False
    assert report.job_count == 0
    assert report.completed_job_count == 0
    assert report.errors[0].error_code == "job_runtime_missing"


def test_reconcile_jobs_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    store = _seed_job_store(tmp_path / "jobs")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_jobs(
        JobReconcileRequest(
            request_id="job-reconcile-6",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.job_count == 0
    assert report.policy_decision_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.job_engine.list_job_descriptors() == ()
