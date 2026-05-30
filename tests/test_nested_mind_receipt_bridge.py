"""Tests for nested-mind receipt bridge contracts.

Purpose: verify that Mullu transition receipts can be bound to nested-mind
proposal evidence and commit witnesses without adding a submission path.
Governance scope: evidence and witness typing only.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts._shared_enums import EffectClass
from mcoi_runtime.contracts.nested_mind_receipts import (
    NestedMindBridgeStatus,
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    build_bridge_report,
    build_commit_witness,
    build_proposal_evidence,
    proposal_evidence_hash,
    receipt_ref_from_transition_receipt,
)
from mcoi_runtime.contracts.proof import GuardVerdict, TransitionReceipt
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _transition_receipt() -> TransitionReceipt:
    return TransitionReceipt(
        receipt_id="rcpt-1",
        machine_id="maf-test-machine",
        entity_id="entity-1",
        from_state="draft",
        to_state="observed",
        action="record_observation",
        before_state_hash="before-hash",
        after_state_hash="after-hash",
        guard_verdicts=(GuardVerdict("authority", True, "ok"),),
        verdict=TransitionVerdict.ALLOWED,
        replay_token="replay-1",
        causal_parent="genesis",
        issued_at="2026-05-30T00:00:00+00:00",
        receipt_hash="mullu-receipt-hash-1",
        signature="sig-1",
        signing_key_id="key-1",
    )


def test_receipt_ref_preserves_mullu_transition_hash() -> None:
    ref = receipt_ref_from_transition_receipt(_transition_receipt())

    assert ref.receipt_id == "rcpt-1"
    assert ref.receipt_hash == "mullu-receipt-hash-1"
    assert ref.signed is True
    assert ref.signing_key_id == "key-1"


def test_build_proposal_evidence_binds_receipt_and_authority_hash() -> None:
    evidence = build_proposal_evidence(
        evidence_id="evidence-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )

    assert evidence.mullu_receipt.receipt_hash == "mullu-receipt-hash-1"
    assert evidence.authority_receipt_hash == "authority-receipt-hash-1"
    assert evidence.evidence_hash == proposal_evidence_hash(evidence)


def test_proposal_evidence_rejects_write_effect_class() -> None:
    with pytest.raises(ValueError, match="pure/read"):
        build_proposal_evidence(
            evidence_id="evidence-1",
            mind_id="root",
            transition_receipt=_transition_receipt(),
            actor_id="operator-a",
            reason="bad effect class",
            authority_receipt_hash="authority-receipt-hash-1",
            requested_at="2026-05-30T00:00:01+00:00",
            effect_class=EffectClass.EXTERNAL_WRITE,
        )


def test_proposal_evidence_requires_authority_receipt_hash() -> None:
    with pytest.raises(ValueError, match="authority_receipt_hash"):
        build_proposal_evidence(
            evidence_id="evidence-1",
            mind_id="root",
            transition_receipt=_transition_receipt(),
            actor_id="operator-a",
            reason="missing authority",
            authority_receipt_hash="",
            requested_at="2026-05-30T00:00:01+00:00",
        )


def test_commit_witness_and_bridge_report_success() -> None:
    evidence = build_proposal_evidence(
        evidence_id="evidence-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )
    witness = build_commit_witness(
        evidence,
        witness_id="witness-1",
        nested_mind_commit_hash="nested-commit-hash-1",
        nested_mind_history_hash="nested-history-hash-1",
        witnessed_at="2026-05-30T00:00:02+00:00",
    )
    report = build_bridge_report(
        evidence,
        witness,
        report_id="bridge-report-1",
        bridged_at="2026-05-30T00:00:03+00:00",
    )

    assert witness.mullu_receipt_hash == evidence.mullu_receipt.receipt_hash
    assert report.status is NestedMindBridgeStatus.BRIDGED
    assert report.blockers == ()


def test_bridge_report_blocks_mismatched_witness() -> None:
    evidence = build_proposal_evidence(
        evidence_id="evidence-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )
    witness = NestedMindCommitWitness(
        witness_id="witness-1",
        proposal_evidence_id="other-evidence",
        mind_id="root",
        mullu_receipt_hash=evidence.mullu_receipt.receipt_hash,
        nested_mind_commit_hash="nested-commit-hash-1",
        nested_mind_history_hash="nested-history-hash-1",
        witnessed_at="2026-05-30T00:00:02+00:00",
        status=NestedMindCommitWitnessStatus.OBSERVED,
    )
    report = build_bridge_report(
        evidence,
        witness,
        report_id="bridge-report-1",
        bridged_at="2026-05-30T00:00:03+00:00",
    )

    assert report.status is NestedMindBridgeStatus.BLOCKED
    assert "proposal_evidence_id_mismatch" in report.blockers


def test_rejected_commit_witness_requires_failure_reason() -> None:
    evidence = build_proposal_evidence(
        evidence_id="evidence-1",
        mind_id="root",
        transition_receipt=_transition_receipt(),
        actor_id="operator-a",
        reason="record bounded observation",
        authority_receipt_hash="authority-receipt-hash-1",
        requested_at="2026-05-30T00:00:01+00:00",
    )

    with pytest.raises(ValueError, match="include failures"):
        build_commit_witness(
            evidence,
            witness_id="witness-1",
            nested_mind_commit_hash="nested-commit-hash-1",
            nested_mind_history_hash="nested-history-hash-1",
            witnessed_at="2026-05-30T00:00:02+00:00",
            status=NestedMindCommitWitnessStatus.REJECTED,
        )
