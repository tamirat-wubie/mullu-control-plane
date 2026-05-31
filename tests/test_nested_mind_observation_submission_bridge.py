"""Tests for verified nested-mind observation bridge reports.

Purpose: verify that live observation bridge success requires an accepted
submission and a VERIFIED commit witness.
Governance scope: P2.3c bridge reporting only; no connector or memory mutation.
Dependencies: nested_mind_receipts and observation submission contracts.
Invariants: OBSERVED witnesses do not become bridge success; mismatches block.
"""

from __future__ import annotations

from dataclasses import replace

from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
    NestedMindReceiptBridgeStatus,
    build_verified_observation_bridge_report,
)


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


class Evidence:
    evidence_id = "evidence-1"
    mind_id = "root"
    mullu_receipt_hash = "mullu-receipt-hash-1"


def _submission(
    *,
    status: NestedMindObservationSubmissionStatus = NestedMindObservationSubmissionStatus.ACCEPTED,
    witness_id: str | None = "witness-1",
) -> NestedMindObservationSubmissionReport:
    return NestedMindObservationSubmissionReport(
        report_id="submission-1",
        plan_id="plan-1",
        mind_id="root",
        proposal_evidence_id="evidence-1",
        payload_hash="payload-hash-1",
        connector_result_id="connector-result-1",
        connector_response_digest="d" * 64,
        response_envelope_hash="envelope-hash-1",
        commit_witness_id=witness_id,
        status=status,
        submitted_at=_clock(),
        failures=("rejected",) if status is NestedMindObservationSubmissionStatus.REJECTED else (),
    )


def _witness(
    *,
    status: NestedMindCommitWitnessStatus = NestedMindCommitWitnessStatus.VERIFIED,
) -> NestedMindCommitWitness:
    return NestedMindCommitWitness(
        witness_id="witness-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        mullu_receipt_hash="mullu-receipt-hash-1",
        nested_mind_commit_hash="commit-hash-1",
        nested_mind_history_hash="history-hash-1",
        witnessed_at=_clock(),
        status=status,
    )


def test_verified_submission_creates_bridged_report() -> None:
    report = build_verified_observation_bridge_report(
        Evidence(),
        _submission(),
        _witness(),
        report_id="bridge-1",
        bridged_at=_clock(),
    )

    assert report.status is NestedMindReceiptBridgeStatus.BRIDGED
    assert report.commit_witness_id == "witness-1"
    assert report.blockers == ()


def test_observed_but_not_verified_witness_blocks() -> None:
    report = build_verified_observation_bridge_report(
        Evidence(),
        _submission(),
        _witness(status=NestedMindCommitWitnessStatus.OBSERVED),
        report_id="bridge-1",
        bridged_at=_clock(),
    )

    assert report.status is NestedMindReceiptBridgeStatus.BLOCKED
    assert "commit_witness_not_verified" in report.blockers


def test_mismatched_witness_blocks() -> None:
    mismatched = replace(_witness(), proposal_evidence_id="other-evidence")
    report = build_verified_observation_bridge_report(
        Evidence(),
        _submission(),
        mismatched,
        report_id="bridge-1",
        bridged_at=_clock(),
    )

    assert report.status is NestedMindReceiptBridgeStatus.BLOCKED
    assert "proposal_evidence_id_mismatch" in report.blockers


def test_rejected_submission_blocks() -> None:
    report = build_verified_observation_bridge_report(
        Evidence(),
        _submission(status=NestedMindObservationSubmissionStatus.REJECTED, witness_id=None),
        _witness(),
        report_id="bridge-1",
        bridged_at=_clock(),
    )

    assert report.status is NestedMindReceiptBridgeStatus.BLOCKED
    assert "submission_status_not_accepted" in report.blockers


def test_missing_witness_blocks() -> None:
    report = build_verified_observation_bridge_report(
        Evidence(),
        _submission(),
        None,
        report_id="bridge-1",
        bridged_at=_clock(),
    )

    assert report.status is NestedMindReceiptBridgeStatus.BLOCKED
    assert "commit_witness_required" in report.blockers
