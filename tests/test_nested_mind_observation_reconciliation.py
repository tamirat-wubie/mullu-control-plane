"""Tests for nested-mind observation read-after-write reconciliation.

Purpose: verify read-only projection/audit/replay checks after a live
record_observation submission.
Governance scope: P2.4 reconciliation only; no memory admission.
Dependencies: observation reconciler and transient JSON connector outcomes.
Invariants: connector failures fail closed; projection/audit mismatches are
typed; verified reports explicitly state no memory admission.
"""

from __future__ import annotations

from mcoi_runtime.adapters import (
    JsonConnectorOutcome,
    NestedMindObservationReconciler,
)
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindObservationReconciliationStatus,
)


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _result(result_id: str, status: ConnectorStatus = ConnectorStatus.SUCCEEDED) -> ConnectorResult:
    return ConnectorResult(
        result_id=result_id,
        connector_id="nested-mind-readonly",
        status=status,
        response_digest="d" * 64 if status is ConnectorStatus.SUCCEEDED else "none",
        started_at=_clock(),
        finished_at=_clock(),
        error_code=None if status is ConnectorStatus.SUCCEEDED else "read_failed",
    )


def _outcome(result_id: str, payload: dict, status: ConnectorStatus = ConnectorStatus.SUCCEEDED) -> JsonConnectorOutcome:
    return JsonConnectorOutcome(connector_result=_result(result_id, status), json_payload=payload)


def _witness() -> NestedMindCommitWitness:
    return NestedMindCommitWitness(
        witness_id="witness-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        mullu_receipt_hash="mullu-receipt-hash-1",
        nested_mind_commit_hash="commit-hash-1",
        nested_mind_history_hash="history-hash-1",
        witnessed_at=_clock(),
        status=NestedMindCommitWitnessStatus.VERIFIED,
    )


class FakeReadConnector:
    def __init__(
        self,
        *,
        projection: JsonConnectorOutcome | None = None,
        audit: JsonConnectorOutcome | None = None,
        replay: JsonConnectorOutcome | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.projection = projection or _outcome(
            "projection-result-1",
            {"commit_hash": "commit-hash-1", "history_hash": "history-hash-1"},
        )
        self.audit = audit or _outcome(
            "audit-result-1",
            {"verified_history_hash": "history-hash-1"},
        )
        self.replay = replay or _outcome(
            "replay-result-1",
            {"causal_chain_verified": True},
        )

    def read_projection_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("projection", mind_id))
        return self.projection

    def verify_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("audit", mind_id))
        return self.audit

    def replay_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        self.calls.append(("replay", mind_id))
        return self.replay


def test_successful_submit_then_projection_and_audit_hashes_match_verified() -> None:
    report = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(),
    ).reconcile(plan_id="plan-1", witness=_witness())

    assert report.status is NestedMindObservationReconciliationStatus.VERIFIED
    assert report.projection_connector_result_id == "projection-result-1"
    assert report.audit_connector_result_id == "audit-result-1"
    assert report.replay_connector_result_id == "replay-result-1"
    assert report.metadata["memory_admission"] is False


def test_projection_missing_commit_is_not_visible() -> None:
    report = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(projection=_outcome("projection-result-1", {})),
    ).reconcile(plan_id="plan-1", witness=_witness())

    assert report.status is NestedMindObservationReconciliationStatus.NOT_VISIBLE
    assert "projection_missing_commit_hash" in report.blockers


def test_audit_history_hash_mismatch_is_history_mismatch() -> None:
    report = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(
            audit=_outcome("audit-result-1", {"verified_history_hash": "wrong"})
        ),
    ).reconcile(plan_id="plan-1", witness=_witness())

    assert report.status is NestedMindObservationReconciliationStatus.HISTORY_MISMATCH
    assert "audit_history_hash_mismatch" in report.blockers


def test_connector_failure_is_failed() -> None:
    report = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(
            projection=_outcome("projection-result-1", {}, ConnectorStatus.FAILED)
        ),
    ).reconcile(plan_id="plan-1", witness=_witness())

    assert report.status is NestedMindObservationReconciliationStatus.FAILED
    assert "connector_read_failed" in report.blockers


def test_reconciliation_does_not_admit_memory() -> None:
    report = NestedMindObservationReconciler(
        clock=_clock,
        read_connector=FakeReadConnector(),
    ).reconcile(plan_id="plan-1", witness=_witness(), replay=False)

    assert report.status is NestedMindObservationReconciliationStatus.VERIFIED
    assert report.replay_connector_result_id is None
    assert report.metadata["memory_admission"] is False
