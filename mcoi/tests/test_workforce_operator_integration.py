"""Purpose: verify governed operator-surface workforce reconciliation and restore flows.
Governance scope: workforce operator integration only.
Dependencies: app bootstrap/operator facade, workforce runtime persistence, and autonomy enforcement.
Invariants:
  - workforce restore is explicit and never automatic.
  - read-only assessment remains available under analyze-permitted autonomy modes.
  - invalid persisted workforce witnesses fail closed before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import OperatorLoop, WorkforceReconcileRequest
from mcoi_runtime.contracts.workforce_runtime import WorkerStatus
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.persistence.workforce_store import WorkforceStore


def _seed_store_with_gap(base_path: Path) -> WorkforceStore:
    store = WorkforceStore(base_path)
    engine = WorkforceRuntimeEngine(
        EventSpineEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    )
    engine.register_worker(
        worker_id="worker-gap-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-1",
        display_name="Gap Worker",
        status=WorkerStatus.ON_LEAVE,
    )
    engine.request_assignment(
        request_id="request-gap-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-gap-1",
        role_ref="ops",
    )
    store.save_state(engine)
    return store


def _seed_store_with_assignment(base_path: Path) -> WorkforceStore:
    store = WorkforceStore(base_path)
    engine = WorkforceRuntimeEngine(
        EventSpineEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    )
    engine.register_worker(
        worker_id="worker-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-1",
        display_name="Assigned Worker",
    )
    engine.request_assignment(
        request_id="request-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-1",
        role_ref="ops",
    )
    engine.decide_assignment(
        decision_id="decision-1",
        request_id="request-1",
        worker_id="worker-1",
    )
    store.save_state(engine)
    return store


def test_reconcile_workforce_assesses_in_memory_state_under_observe_only() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="observe_only"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )
    runtime.workforce_engine.register_worker(
        worker_id="worker-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-1",
        display_name="Worker One",
    )
    runtime.workforce_engine.request_assignment(
        request_id="request-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-1",
        role_ref="ops",
    )
    runtime.workforce_engine.decide_assignment(
        decision_id="decision-1",
        request_id="request-1",
        worker_id="worker-1",
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_workforce(
        WorkforceReconcileRequest(
            request_id="reconcile-1",
            subject_id="subject-1",
            tenant_id="tenant-1",
            detect_gaps=False,
            detect_violations=False,
        )
    )

    assert report.restored is False
    assert report.autonomy_decision == "allowed"
    assert report.policy_status == "allow"
    assert report.worker_count == 1
    assert report.active_worker_count == 1
    assert report.request_count == 1
    assert report.decision_count == 1
    assert report.gap_count == 0
    assert report.violation_count == 0
    assert report.errors == ()


def test_reconcile_workforce_restores_and_detects_gaps_and_violations(tmp_path: Path) -> None:
    store = _seed_store_with_gap(tmp_path / "workforce")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        workforce_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_workforce(
        WorkforceReconcileRequest(
            request_id="reconcile-2",
            subject_id="subject-1",
            tenant_id="tenant-1",
            restore_from_store=True,
            detect_gaps=True,
            detect_violations=True,
        )
    )

    assert report.restored is True
    assert report.policy_status == "allow"
    assert report.assessment_id is not None
    assert report.worker_count == 1
    assert report.active_worker_count == 0
    assert report.request_count == 1
    assert report.decision_count == 0
    assert report.gap_count == 1
    assert report.violation_count == 1
    assert len(report.new_gap_ids) == 1
    assert len(report.new_violation_ids) == 1
    assert report.errors == ()
    assert runtime.workforce_engine.worker_count == 1


def test_reconcile_workforce_fails_closed_without_configured_store() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    loop = OperatorLoop(runtime)

    report = loop.reconcile_workforce(
        WorkforceReconcileRequest(
            request_id="reconcile-3",
            subject_id="subject-1",
            tenant_id="tenant-1",
            restore_from_store=True,
            detect_gaps=False,
            detect_violations=False,
        )
    )

    assert report.restored is False
    assert report.assessment_id is None
    assert report.worker_count == 0
    assert report.request_count == 0
    assert report.errors[0].error_code == "workforce_store_not_configured"


def test_reconcile_workforce_fails_closed_on_invalid_persisted_state(tmp_path: Path) -> None:
    store = _seed_store_with_assignment(tmp_path / "workforce")
    state_path = tmp_path / "workforce" / "workforce_runtime.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["decisions"][0]["worker_id"] = "missing-worker"
    state_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        workforce_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_workforce(
        WorkforceReconcileRequest(
            request_id="reconcile-4",
            subject_id="subject-1",
            tenant_id="tenant-1",
            restore_from_store=True,
            detect_gaps=False,
            detect_violations=False,
        )
    )

    assert report.restored is False
    assert report.assessment_id is None
    assert report.worker_count == 0
    assert report.errors[0].error_code == "workforce_restore_failed"
    assert runtime.workforce_engine.worker_count == 0


def test_reconcile_workforce_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    store = _seed_store_with_assignment(tmp_path / "workforce")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
        workforce_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_workforce(
        WorkforceReconcileRequest(
            request_id="reconcile-5",
            subject_id="subject-1",
            tenant_id="tenant-1",
            restore_from_store=True,
            detect_gaps=False,
            detect_violations=False,
        )
    )

    assert report.restored is False
    assert report.assessment_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.policy_decision_id is None
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.workforce_engine.worker_count == 0
