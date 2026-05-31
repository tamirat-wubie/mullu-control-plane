"""Tests for the nested-mind P3 readiness validator.

Purpose: ensure P3 memory-lattice work is gated by live verified
record_observation evidence.
Governance scope: read-only readiness validation.
Dependencies: validate_nested_mind_p3_readiness script and evidence store.
Invariants: missing evidence blocks; accepted submission, verified witness,
and verified reconciliation must bind as one causal chain.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from mcoi_runtime.contracts.nested_mind_observation_reconciliation import (
    NestedMindObservationReconciliationReport,
    NestedMindObservationReconciliationStatus,
)
from mcoi_runtime.contracts.nested_mind_observation_submission import (
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
)
from mcoi_runtime.contracts.nested_mind_receipts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
)
from mcoi_runtime.persistence.nested_mind_store import NestedMindEvidenceStore

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_nested_mind_p3_readiness.py"


def _module():
    spec = importlib.util.spec_from_file_location("validate_nested_mind_p3_readiness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _submission() -> NestedMindObservationSubmissionReport:
    return NestedMindObservationSubmissionReport(
        report_id="submission-1",
        plan_id="plan-1",
        mind_id="root",
        proposal_evidence_id="evidence-1",
        payload_hash="payload-hash-1",
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


def test_p3_readiness_blocks_when_evidence_missing(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    NestedMindEvidenceStore(store_path)

    result = module.validate_p3_readiness(store_path)

    assert result["status"] == "blocked"
    assert "accepted_submission_missing" in result["blockers"]
    assert "verified_commit_witness_missing" in result["blockers"]
    assert "verified_reconciliation_missing" in result["blockers"]


def test_p3_readiness_passes_for_bound_verified_chain(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(_reconciliation())

    result = module.validate_p3_readiness(store_path, mind_id="root")

    assert result["status"] == "ready"
    assert result["plan_id"] == "plan-1"
    assert result["commit_witness_id"] == "witness-1"
    assert result["reconciliation_report_id"] == "reconciliation-1"


def test_p3_readiness_blocks_when_chain_does_not_bind(tmp_path) -> None:
    module = _module()
    store_path = tmp_path / "nested-mind.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_submission_report(_submission())
    store.record_commit_witness(_witness())
    store.record_reconciliation_report(
        NestedMindObservationReconciliationReport(
            report_id="reconciliation-1",
            plan_id="plan-1",
            commit_witness_id="witness-1",
            mind_id="root",
            expected_commit_hash="wrong-commit",
            expected_history_hash="history-hash-1",
            projection_connector_result_id="projection-result-1",
            audit_connector_result_id="audit-result-1",
            replay_connector_result_id=None,
            status=NestedMindObservationReconciliationStatus.VERIFIED,
            checked_at=_clock(),
        )
    )

    result = module.validate_p3_readiness(store_path)

    assert result["status"] == "blocked"
    assert result["blockers"] == ("verified_causal_chain_missing",)
