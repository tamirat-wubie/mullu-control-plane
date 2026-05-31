"""Tests for the internal nested-mind evidence store.

Purpose: verify append-only persistence and sensitive-field rejection for
runtime-only nested-mind observation evidence.
Governance scope: P2.5 internal evidence ledger only; no public schema.
Dependencies: nested_mind_store and nested-mind runtime contracts.
Invariants: duplicate IDs are rejected; raw tokens and raw response bodies are
not accepted; query projections are read-only.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindObservationReconciliationReport,
    NestedMindObservationReconciliationStatus,
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
    NestedMindReceiptBridgeReport,
    NestedMindReceiptBridgeStatus,
    stable_json_hash,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceWriteError
from mcoi_runtime.persistence import NestedMindEvidenceStore


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _payload() -> dict:
    return {
        "kind": "record_observation",
        "ops": (
            {
                "op": "set",
                "key": "observations/obs-1",
                "value": {"observation_id": "obs-1"},
            },
        ),
        "metadata": {"proposal_evidence_hash": "proposal-evidence-hash-1"},
    }


def _plan(plan_id: str = "plan-1", mind_id: str = "root") -> NestedMindObservationProposalPlan:
    payload = _payload()
    return NestedMindObservationProposalPlan(
        plan_id=plan_id,
        proposal_evidence_id="evidence-1",
        mind_id=mind_id,
        method="POST",
        target_route=f"/minds/{mind_id}/proposals",
        proposal_payload=payload,
        payload_hash=stable_json_hash(payload),
        mullu_receipt_hash="mullu-receipt-hash-1",
        authority_receipt_hash="authority-receipt-hash-1",
        status=NestedMindObservationProposalPlanStatus.PLANNED,
        planned_at=_clock(),
    )


def _submission() -> NestedMindObservationSubmissionReport:
    return NestedMindObservationSubmissionReport(
        report_id="submission-1",
        plan_id="plan-1",
        mind_id="root",
        proposal_evidence_id="evidence-1",
        payload_hash=_plan().payload_hash,
        connector_result_id="connector-result-1",
        connector_response_digest="d" * 64,
        response_envelope_hash="envelope-hash-1",
        commit_witness_id="witness-1",
        status=NestedMindObservationSubmissionStatus.ACCEPTED,
        submitted_at=_clock(),
    )


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


def _bridge() -> NestedMindReceiptBridgeReport:
    return NestedMindReceiptBridgeReport(
        report_id="bridge-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        commit_witness_id="witness-1",
        status=NestedMindReceiptBridgeStatus.BRIDGED,
        bridged_at=_clock(),
    )


def _reconciliation() -> NestedMindObservationReconciliationReport:
    return NestedMindObservationReconciliationReport(
        report_id="reconciliation-1",
        plan_id="plan-1",
        commit_witness_id="witness-1",
        mind_id="root",
        expected_commit_hash="commit-hash-1",
        expected_history_hash="history-hash-1",
        projection_connector_result_id="projection-result-1",
        audit_connector_result_id="audit-result-1",
        replay_connector_result_id=None,
        status=NestedMindObservationReconciliationStatus.VERIFIED,
        checked_at=_clock(),
        metadata={"memory_admission": False},
    )


def test_append_only_duplicate_rejection(tmp_path) -> None:
    store = NestedMindEvidenceStore(tmp_path / "nested-mind.jsonl")
    store.record_plan(_plan())

    with pytest.raises(PersistenceWriteError, match="already exists"):
        store.record_plan(_plan())


def test_list_by_mind_id(tmp_path) -> None:
    path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(path)
    store.record_plan(_plan())
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_bridge_report(_bridge())
    store.record_reconciliation_report(_reconciliation())
    reloaded = NestedMindEvidenceStore(path)

    entries = reloaded.list_by_mind_id("root")
    assert [entry.record_type for entry in entries] == [
        "plan",
        "submission_report",
        "commit_witness",
        "bridge_report",
        "reconciliation_report",
    ]
    assert all(entry.mind_id == "root" for entry in entries)


def test_list_by_mullu_receipt_hash(tmp_path) -> None:
    store = NestedMindEvidenceStore(tmp_path / "nested-mind.jsonl")
    store.record_plan(_plan())
    store.record_commit_witness(_witness())
    store.record_plan(_plan(plan_id="plan-2", mind_id="tenant-2"))

    entries = store.list_by_mullu_receipt_hash("mullu-receipt-hash-1")
    assert [entry.record_type for entry in entries] == ["plan", "commit_witness", "plan"]
    assert all(entry.mullu_receipt_hash == "mullu-receipt-hash-1" for entry in entries)


def test_no_token_fields_stored(tmp_path) -> None:
    store = NestedMindEvidenceStore(tmp_path / "nested-mind.jsonl")
    unsafe_plan = replace(_plan(), metadata={"bearer_token": "secret"})

    with pytest.raises(PersistenceWriteError, match="forbidden sensitive field"):
        store.record_plan(unsafe_plan)


def test_raw_response_body_not_accepted(tmp_path) -> None:
    store = NestedMindEvidenceStore(tmp_path / "nested-mind.jsonl")
    unsafe_report = replace(_submission(), metadata={"raw_response_body": "{}"})

    with pytest.raises(PersistenceWriteError, match="forbidden sensitive field"):
        store.record_submission_report(unsafe_report)


def test_existing_store_rejects_unexpected_top_level_fields(tmp_path) -> None:
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    entry = store_path.read_text(encoding="utf-8").strip()
    unsafe_entry = entry[:-1] + ',"authorization":"secret"}'
    store_path.write_text(unsafe_entry + "\n", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="unexpected fields"):
        NestedMindEvidenceStore(store_path)
