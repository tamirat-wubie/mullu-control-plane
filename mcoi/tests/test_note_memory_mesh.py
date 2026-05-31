"""Tests for the governed note memory mesh.

Purpose: verify temporary notes, execution traces, decisions, rejected deltas,
and MemoryAnchor promotion behavior.
Governance scope: append-only note lineage, redaction-before-write, retrieval
guarding, ProofState promotion gates, and Mfidel atomicity rejection.
Dependencies: pytest and mcoi_runtime.core.note_memory_mesh.
Invariants: notes are never silently persisted with secrets, stale notes cannot
influence execution, and durable anchors require accepted Phi_gov receipts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_mesh import (
    EpisodeCapsuleDraft,
    NoteAction,
    NoteKind,
    NoteMemoryDraft,
    NoteMemoryMesh,
    NoteScope,
    PhiGovStatus,
    PromotionReceipt,
    ProofState,
    RetrievalGuard,
    TrustZone,
)


class MutableClock:
    """Frozen test clock with explicit advancement."""

    def __init__(self, value: str) -> None:
        self._value = datetime.fromisoformat(value).astimezone(timezone.utc)

    def __call__(self) -> str:
        return self._value.isoformat()

    def set(self, value: str) -> None:
        self._value = datetime.fromisoformat(value).astimezone(timezone.utc)


def _mesh(tmp_path, clock: MutableClock) -> NoteMemoryMesh:
    return NoteMemoryMesh(tmp_path / "notes", clock=clock)


def test_capture_redacts_sensitive_values_before_persistence(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    event = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="Investigate adapter with api_key=sk-secretvalue1234567890",
            source_ref="user_request password=super-secret",
            proof_state=ProofState.UNKNOWN,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-02T00:00:00+00:00",
        )
    )
    persisted = mesh.list_events()[0]

    assert mesh.event_count == 1
    assert event.checksum == persisted.expected_checksum()
    assert "sk-secretvalue" not in persisted.content_summary
    assert "super-secret" not in persisted.source_ref
    assert "[REDACTED:" in persisted.content_summary


def test_retrieval_guard_blocks_expired_contradicted_and_disallowed_notes(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    allowed = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="parser evidence should guide task execution",
            source_ref="test:allowed",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-03T00:00:00+00:00",
            evidence_refs=("test_allowed",),
        )
    )
    external = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="parser external claim should not guide execution",
            source_ref="external:claim",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.EXTERNAL,
            evidence_refs=("external_evidence",),
        )
    )
    contradicted = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="parser stale decision should be blocked",
            source_ref="test:stale",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_stale",),
        )
    )
    mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            action=NoteAction.CONTRADICT,
            scope=NoteScope.TASK,
            content_summary="parser newer decision contradicts stale decision",
            source_ref="test:contradiction",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_contradiction",),
            relation_refs=(contradicted.note_id,),
        )
    )

    retrieved = mesh.retrieve_notes("parser", RetrievalGuard(scope=NoteScope.TASK))
    retrieved_ids = {note.event.note_id for note in retrieved}

    assert allowed.note_id in retrieved_ids
    assert external.note_id not in retrieved_ids
    assert contradicted.note_id not in retrieved_ids
    assert all(note.guard_reasons == ("retrieval_guard_passed",) for note in retrieved)
    assert retrieved[0].score > 0


def test_retrieval_receipt_is_deterministic_and_read_only(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    allowed = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="retrieval receipt parser note should guide execution",
            source_ref="test:retrieval-receipt",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-03T00:00:00+00:00",
            evidence_refs=("test_retrieval_receipt_is_deterministic_and_read_only",),
        )
    )

    result = mesh.retrieve_notes_with_receipt(
        "retrieval receipt",
        RetrievalGuard(scope=NoteScope.TASK, now="2026-05-01T00:00:00+00:00"),
    )
    repeated = mesh.retrieve_notes_with_receipt(
        "retrieval receipt",
        RetrievalGuard(scope=NoteScope.TASK, now="2026-05-01T00:00:00+00:00"),
    )

    assert mesh.event_count == 1
    assert result.notes[0].event.note_id == allowed.note_id
    assert result.receipt.receipt_id.startswith("note-retrieval-")
    assert result.receipt.snapshot_hash == repeated.receipt.snapshot_hash
    assert result.receipt.receipt_id == repeated.receipt.receipt_id
    assert result.receipt.query_terms == ("retrieval", "receipt")
    assert result.receipt.guard_scope == "task"
    assert result.receipt.event_count == 1
    assert result.receipt.materialized_note_count == 1
    assert result.receipt.returned_count == 1
    assert result.receipt.returned_note_ids == (allowed.note_id,)
    assert result.receipt.returned_event_ids == (allowed.event_id,)
    assert result.receipt.proof_state == ProofState.PASS


def test_captured_decision_can_cite_retrieval_receipt_without_mutating_read(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="parser strategy note for downstream decision capture",
            source_ref="test:retrieval-influence-source",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-03T00:00:00+00:00",
            evidence_refs=("test_captured_decision_can_cite_retrieval_receipt_without_mutating_read",),
        )
    )

    result = mesh.retrieve_notes_with_receipt(
        "parser strategy",
        RetrievalGuard(scope=NoteScope.TASK, now="2026-05-01T00:00:00+00:00"),
    )
    event_count_after_read = mesh.event_count
    clock.set("2026-05-01T00:01:00+00:00")
    decision = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Decision cites the retrieval receipt that selected parser strategy evidence",
            source_ref="test:retrieval-influence-decision",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_captured_decision_can_cite_retrieval_receipt_without_mutating_read",),
            retrieval_receipt_refs=(result.receipt.receipt_id,),
        )
    )
    snapshot = mesh.dashboard_snapshot(now="2026-05-01T00:01:00+00:00")

    assert event_count_after_read == 1
    assert result.receipt.returned_note_ids == (source.note_id,)
    assert decision.retrieval_receipt_refs == (result.receipt.receipt_id,)
    assert mesh.event_count == 2
    assert snapshot["summary"]["event_count"] == 2
    assert snapshot["summary"]["retrieval_influence_count"] == 1
    assert snapshot["summary"]["retrieval_influence_total_count"] == 1
    assert snapshot["recent_notes"][0]["note_id"] == decision.note_id
    assert snapshot["recent_notes"][0]["retrieval_receipt_refs"] == [result.receipt.receipt_id]
    assert snapshot["retrieval_influence"][0]["receipt_id"] == result.receipt.receipt_id
    assert snapshot["retrieval_influence"][0]["citing_note_id"] == decision.note_id
    assert snapshot["retrieval_influence"][0]["citing_kind"] == "DecisionRecord"


def test_capture_rejects_malformed_retrieval_receipt_refs_without_persisting(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="retrieval_receipt_ref must reference a note retrieval receipt"):
        mesh.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.DECISION_RECORD,
                scope=NoteScope.TASK,
                content_summary="Decision must not cite arbitrary retrieval influence text",
                source_ref="test:malformed-retrieval-ref",
                proof_state=ProofState.PASS,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=("test_capture_rejects_malformed_retrieval_receipt_refs_without_persisting",),
                retrieval_receipt_refs=("manual-note-ref",),
            )
        )

    assert mesh.event_count == 0


def test_capture_deduplicates_retrieval_receipt_refs(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="parser strategy note for duplicate retrieval reference capture",
            source_ref="test:retrieval-duplicate-source",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-03T00:00:00+00:00",
            evidence_refs=("test_capture_deduplicates_retrieval_receipt_refs",),
        )
    )
    result = mesh.retrieve_notes_with_receipt(
        "duplicate retrieval",
        RetrievalGuard(scope=NoteScope.TASK, now="2026-05-01T00:00:00+00:00"),
    )

    decision = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Decision cites one retrieval receipt once after deduplication",
            source_ref="test:retrieval-duplicate-decision",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_capture_deduplicates_retrieval_receipt_refs",),
            retrieval_receipt_refs=(result.receipt.receipt_id, result.receipt.receipt_id),
        )
    )

    assert result.receipt.returned_note_ids == (source.note_id,)
    assert decision.retrieval_receipt_refs == (result.receipt.receipt_id,)
    assert mesh.event_count == 2


def test_dashboard_snapshot_limits_retrieval_influence_rows(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    first_receipt = "note-retrieval-111111111111"
    second_receipt = "note-retrieval-222222222222"
    first = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="First decision cites retrieval influence",
            source_ref="test:first-retrieval-influence",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_limits_retrieval_influence_rows",),
            retrieval_receipt_refs=(first_receipt,),
        )
    )
    clock.set("2026-05-01T00:01:00+00:00")
    second = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Second decision cites retrieval influence",
            source_ref="test:second-retrieval-influence",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_limits_retrieval_influence_rows",),
            retrieval_receipt_refs=(second_receipt,),
        )
    )

    snapshot = mesh.dashboard_snapshot(now="2026-05-01T00:02:00+00:00", limit=1)

    assert snapshot["summary"]["retrieval_influence_count"] == 2
    assert snapshot["summary"]["retrieval_influence_total_count"] == 2
    assert snapshot["summary"]["retrieval_receipt_count"] == 2
    assert snapshot["summary"]["retrieval_receipt_total_count"] == 2
    assert len(snapshot["retrieval_influence"]) == 1
    assert snapshot["retrieval_influence"][0]["receipt_id"] == second_receipt
    assert snapshot["retrieval_influence"][0]["citing_note_id"] == second.note_id
    assert snapshot["retrieval_influence"][0]["citing_note_id"] != first.note_id


def test_dashboard_snapshot_filters_retrieval_influence_by_receipt(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    first_receipt = "note-retrieval-111111111111"
    second_receipt = "note-retrieval-222222222222"
    first = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="First decision cites retrieval influence for dashboard filtering",
            source_ref="test:first-retrieval-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_filters_retrieval_influence_by_receipt",),
            retrieval_receipt_refs=(first_receipt,),
        )
    )
    clock.set("2026-05-01T00:01:00+00:00")
    second = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Second decision cites retrieval influence for dashboard filtering",
            source_ref="test:second-retrieval-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_filters_retrieval_influence_by_receipt",),
            retrieval_receipt_refs=(second_receipt,),
        )
    )

    snapshot = mesh.dashboard_snapshot(
        now="2026-05-01T00:02:00+00:00",
        limit=5,
        retrieval_receipt_ref=first_receipt,
    )

    assert snapshot["filters"]["retrieval_receipt_ref"] == first_receipt
    assert snapshot["filters"]["retrieval_citing_note_ref"] == ""
    assert snapshot["summary"]["event_count"] == 2
    assert snapshot["summary"]["retrieval_filter_active"] is True
    assert snapshot["summary"]["retrieval_influence_count"] == 1
    assert snapshot["summary"]["retrieval_influence_total_count"] == 2
    assert snapshot["summary"]["retrieval_receipt_count"] == 1
    assert snapshot["summary"]["retrieval_receipt_total_count"] == 2
    assert snapshot["retrieval_receipts"][0]["receipt_id"] == first_receipt
    assert snapshot["retrieval_receipts"][0]["citation_count"] == 1
    assert snapshot["retrieval_influence"][0]["receipt_id"] == first_receipt
    assert snapshot["retrieval_influence"][0]["citing_note_id"] == first.note_id
    assert snapshot["retrieval_influence"][0]["citing_note_id"] != second.note_id


def test_dashboard_snapshot_filters_retrieval_influence_by_citing_note(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    first_receipt = "note-retrieval-111111111111"
    second_receipt = "note-retrieval-222222222222"
    first = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="First decision cites retrieval influence for citing-note filtering",
            source_ref="test:first-citing-note-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_filters_retrieval_influence_by_citing_note",),
            retrieval_receipt_refs=(first_receipt,),
        )
    )
    clock.set("2026-05-01T00:01:00+00:00")
    second = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Second decision cites two retrieval receipts for citing-note filtering",
            source_ref="test:second-citing-note-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_filters_retrieval_influence_by_citing_note",),
            retrieval_receipt_refs=(first_receipt, second_receipt),
        )
    )

    snapshot = mesh.dashboard_snapshot(
        now="2026-05-01T00:02:00+00:00",
        limit=5,
        retrieval_citing_note_ref=second.note_id,
    )

    assert snapshot["filters"]["retrieval_receipt_ref"] == ""
    assert snapshot["filters"]["retrieval_citing_note_ref"] == second.note_id
    assert snapshot["summary"]["event_count"] == 2
    assert snapshot["summary"]["retrieval_filter_active"] is True
    assert snapshot["summary"]["retrieval_influence_count"] == 2
    assert snapshot["summary"]["retrieval_influence_total_count"] == 3
    assert snapshot["summary"]["retrieval_receipt_count"] == 2
    assert snapshot["summary"]["retrieval_receipt_total_count"] == 2
    assert {row["receipt_id"] for row in snapshot["retrieval_influence"]} == {first_receipt, second_receipt}
    assert {row["citing_note_id"] for row in snapshot["retrieval_influence"]} == {second.note_id}
    assert second.note_id != first.note_id


def test_dashboard_snapshot_combines_receipt_and_citing_note_filters(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    first_receipt = "note-retrieval-111111111111"
    second_receipt = "note-retrieval-222222222222"
    first = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="First decision cites the first retrieval receipt",
            source_ref="test:first-combined-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_combines_receipt_and_citing_note_filters",),
            retrieval_receipt_refs=(first_receipt,),
        )
    )
    clock.set("2026-05-01T00:01:00+00:00")
    second = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Second decision cites the second retrieval receipt",
            source_ref="test:second-combined-filter",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_combines_receipt_and_citing_note_filters",),
            retrieval_receipt_refs=(second_receipt,),
        )
    )

    snapshot = mesh.dashboard_snapshot(
        now="2026-05-01T00:02:00+00:00",
        limit=5,
        retrieval_receipt_ref=second_receipt,
        retrieval_citing_note_ref=second.note_id,
    )

    assert snapshot["filters"]["retrieval_receipt_ref"] == second_receipt
    assert snapshot["filters"]["retrieval_citing_note_ref"] == second.note_id
    assert snapshot["summary"]["retrieval_influence_count"] == 1
    assert snapshot["summary"]["retrieval_influence_total_count"] == 2
    assert snapshot["retrieval_influence"][0]["receipt_id"] == second_receipt
    assert snapshot["retrieval_influence"][0]["citing_note_id"] == second.note_id
    assert snapshot["retrieval_influence"][0]["citing_note_id"] != first.note_id


def test_dashboard_snapshot_rejects_malformed_retrieval_influence_filter(tmp_path) -> None:
    mesh = _mesh(tmp_path, MutableClock("2026-05-01T00:00:00+00:00"))

    with pytest.raises(RuntimeCoreInvariantError, match="retrieval_receipt_ref must reference a note retrieval receipt"):
        mesh.dashboard_snapshot(retrieval_receipt_ref="manual-note-ref")

    assert mesh.event_count == 0


def test_dashboard_snapshot_rejects_malformed_retrieval_citing_note_filter(tmp_path) -> None:
    mesh = _mesh(tmp_path, MutableClock("2026-05-01T00:00:00+00:00"))

    with pytest.raises(RuntimeCoreInvariantError, match="retrieval_citing_note_ref must be a bounded symbolic identifier"):
        mesh.dashboard_snapshot(retrieval_citing_note_ref="../bad-note")

    assert mesh.event_count == 0


def test_dashboard_snapshot_summarizes_retrieval_receipts_by_citation_count(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    first_receipt = "note-retrieval-111111111111"
    second_receipt = "note-retrieval-222222222222"
    mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="First decision cites one retrieval receipt",
            source_ref="test:first-retrieval-summary",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_summarizes_retrieval_receipts_by_citation_count",),
            retrieval_receipt_refs=(first_receipt,),
        )
    )
    clock.set("2026-05-01T00:01:00+00:00")
    second = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Second decision cites the more referenced receipt",
            source_ref="test:second-retrieval-summary",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_summarizes_retrieval_receipts_by_citation_count",),
            retrieval_receipt_refs=(second_receipt,),
        )
    )
    clock.set("2026-05-01T00:02:00+00:00")
    third = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="Third decision cites the same high influence retrieval receipt",
            source_ref="test:third-retrieval-summary",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_dashboard_snapshot_summarizes_retrieval_receipts_by_citation_count",),
            retrieval_receipt_refs=(second_receipt,),
        )
    )

    snapshot = mesh.dashboard_snapshot(now="2026-05-01T00:03:00+00:00", limit=5)

    assert snapshot["summary"]["retrieval_influence_count"] == 3
    assert snapshot["summary"]["retrieval_receipt_count"] == 2
    assert snapshot["retrieval_receipts"][0]["receipt_id"] == second_receipt
    assert snapshot["retrieval_receipts"][0]["citation_count"] == 2
    assert snapshot["retrieval_receipts"][0]["citing_note_id_count"] == 2
    assert snapshot["retrieval_receipts"][0]["sample_citing_note_ids"] == [third.note_id, second.note_id]
    assert snapshot["retrieval_receipts"][1]["receipt_id"] == first_receipt


def test_retrieval_receipt_bounds_query_text(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="query exceeds"):
        mesh.retrieve_notes_with_receipt("x" * 257, RetrievalGuard(scope=NoteScope.TASK))

    assert mesh.event_count == 0


def test_event_id_relation_refs_block_retrieval_and_promotion_queue(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="promotion queue source note should be blocked by event relation",
            source_ref="test:event-relation-source",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-03T00:00:00+00:00",
            evidence_refs=("test_event_relation_source",),
        )
    )
    blocker = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            action=NoteAction.CONTRADICT,
            scope=NoteScope.TASK,
            content_summary="promotion queue blocker contradicts source note by event id",
            source_ref="test:event-relation-blocker",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_event_relation_blocker",),
            relation_refs=(source.event_id,),
        )
    )

    retrieved_ids = {note.event.note_id for note in mesh.retrieve_notes("promotion queue", RetrievalGuard(scope=NoteScope.TASK))}

    with pytest.raises(RuntimeCoreInvariantError, match="materialized state"):
        mesh.queue_promotion(source.note_id)
    assert source.note_id not in retrieved_ids
    assert blocker.note_id in retrieved_ids
    assert blocker.relation_refs == (source.event_id,)


def test_claim_contradiction_detection_blocks_prior_active_note(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    prior = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="pilot extension health claim says note memory is disabled",
            source_ref="test:claim-prior",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_claim_prior",),
            claim_key="note-memory.extension.state",
            claim_value="disabled",
        )
    )
    current = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.TASK,
            content_summary="pilot extension health claim says note memory is mounted",
            source_ref="test:claim-current",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_claim_current",),
            claim_key="note-memory.extension.state",
            claim_value="mounted",
        )
    )

    retrieved_ids = {note.event.note_id for note in mesh.retrieve_notes("pilot extension", RetrievalGuard(scope=NoteScope.TASK))}
    snapshot = mesh.dashboard_snapshot(now="2026-05-01T00:00:00+00:00")

    assert mesh.event_count == 3
    assert prior.note_id not in retrieved_ids
    assert current.note_id in retrieved_ids
    assert snapshot["summary"]["contradiction_count"] == 1
    assert snapshot["summary"]["active_note_count"] == 1
    assert snapshot["contradictions"][0]["relation_refs"] == [prior.event_id]
    assert snapshot["audit_events"][0]["action"] == "contradict"


def test_claim_detection_requires_key_and_value_pair(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="claim_key and claim_value"):
        mesh.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.DECISION_RECORD,
                scope=NoteScope.TASK,
                content_summary="incomplete claim key",
                source_ref="test:claim-missing-value",
                proof_state=ProofState.PASS,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=("test_claim_detection_requires_key_and_value_pair",),
                claim_key="note-memory.extension.state",
            )
        )
    with pytest.raises(RuntimeCoreInvariantError, match="claim_key and claim_value"):
        mesh.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.DECISION_RECORD,
                scope=NoteScope.TASK,
                content_summary="incomplete claim value",
                source_ref="test:claim-missing-key",
                proof_state=ProofState.PASS,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=("test_claim_detection_requires_key_and_value_pair",),
                claim_value="mounted",
            )
        )

    assert mesh.event_count == 0


def test_episode_capsule_writes_structured_sidecar_and_can_queue_promotion(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    capsule = mesh.capture_episode_capsule(
        EpisodeCapsuleDraft(
            episode_id="episode-note-memory-console",
            goal="Add note-memory console read model",
            scope=NoteScope.REPOSITORY,
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            constraints=("fail closed when store path is missing",),
            decisions=("surface note-memory through read-only console route",),
            changed_files=("mcoi/mcoi_runtime/app/routers/console.py",),
            verification_refs=("python -m pytest mcoi/tests/test_operator_console.py",),
            open_risks=("live endpoint evidence not collected",),
            evidence_refs=("test_episode_capsule_writes_structured_sidecar",),
            relation_refs=("note-memory-console-route",),
        )
    )
    promotion_id = mesh.queue_promotion(capsule.note_id)
    capsule_path = tmp_path / "notes" / "episodes" / "episode-note-memory-console.json"
    persisted = json.loads(capsule_path.read_text(encoding="utf-8"))
    snapshot = mesh.dashboard_snapshot(now="2026-05-01T00:00:00+00:00")

    assert capsule.kind == NoteKind.EPISODE_CAPSULE
    assert capsule.action == NoteAction.CREATE
    assert capsule.note_id == "episode-note-memory-console"
    assert persisted["goal"] == "Add note-memory console read model"
    assert persisted["event_id"] == capsule.event_id
    assert persisted["verification_refs"] == ["python -m pytest mcoi/tests/test_operator_console.py"]
    assert "checksum" in persisted
    assert promotion_id.startswith("note-promotion-")
    assert snapshot["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(snapshot["snapshot_hash"]) == 64
    assert snapshot["assessed_at"] == "2026-05-01T00:00:00+00:00"
    assert snapshot["summary"]["episode_capsule_count"] == 1
    assert snapshot["episode_capsules"][0]["kind"] == "EpisodeCapsule"


def test_episode_capsule_requires_evidence_refs(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="requires evidence_refs"):
        mesh.capture_episode_capsule(
            EpisodeCapsuleDraft(
                goal="Evidence-free capsule",
                scope=NoteScope.TASK,
                proof_state=ProofState.UNKNOWN,
                trust_zone=TrustZone.WORKSPACE,
            )
        )

    assert mesh.event_count == 0


def test_episode_capsule_pass_requires_verification_refs(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="verification_refs"):
        mesh.capture_episode_capsule(
            EpisodeCapsuleDraft(
                goal="Unverified capsule",
                scope=NoteScope.TASK,
                proof_state=ProofState.PASS,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=("test_episode_capsule_pass_requires_verification_refs",),
            )
        )
    assert mesh.event_count == 0


def test_expire_temporary_notes_blocks_stale_working_note(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    event = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="temporary parser note",
            source_ref="test:temporary",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-01T01:00:00+00:00",
            evidence_refs=("test_temporary",),
        )
    )

    clock.set("2026-05-02T00:00:00+00:00")
    report = mesh.expire_temporary_notes()
    retrieved = mesh.retrieve_notes("temporary", RetrievalGuard(scope=NoteScope.TASK))

    assert report.expired_count == 1
    assert report.proof_state == ProofState.PASS
    assert len(report.emitted_event_ids) == 1
    assert mesh.event_count == 2
    assert event.note_id not in {note.event.note_id for note in retrieved}


def test_memory_anchor_promotion_requires_pass_receipt_and_writes_anchor(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.REPOSITORY,
            content_summary="note memory mesh contract is validated by focused tests",
            source_ref="test:promotion",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-04T00:00:00+00:00",
            evidence_refs=("test_note_memory_mesh.py::test_memory_anchor_promotion",),
        )
    )

    promotion_id = mesh.queue_promotion(source.note_id)
    receipt = PromotionReceipt(
        promotion_id=promotion_id,
        source_note_id=source.note_id,
        anchor_id="anchor-note-memory-contract",
        proof_state=ProofState.PASS,
        evidence_refs=source.evidence_refs,
        contradiction_scan=ProofState.PASS,
        phi_gov_status=PhiGovStatus.ACCEPTED,
        accepted_at="2026-05-01T00:05:00+00:00",
        accepted_by="test-governance",
        lineage_event_seq=source.event_seq,
    )
    anchor = mesh.promote_memory_anchor(source.note_id, receipt)
    anchor_path = tmp_path / "notes" / "anchors" / "anchor-note-memory-contract.json"

    assert anchor.kind == NoteKind.MEMORY_ANCHOR
    assert anchor.action == NoteAction.PROMOTE
    assert anchor.relation_refs == (source.note_id,)
    assert anchor_path.exists()
    assert json.loads(anchor_path.read_text(encoding="utf-8"))["promotion_receipt"]["phi_gov_status"] == "accepted"


def test_elapsed_ttl_blocks_queued_source_before_promotion(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.REPOSITORY,
            content_summary="queued source expires before promotion receipt is consumed",
            source_ref="test:promotion-expiry",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-02T00:00:00+00:00",
            evidence_refs=("test_elapsed_ttl_blocks_queued_source_before_promotion",),
        )
    )
    promotion_id = mesh.queue_promotion(source.note_id)
    receipt = PromotionReceipt(
        promotion_id=promotion_id,
        source_note_id=source.note_id,
        anchor_id="anchor-expired-source",
        proof_state=ProofState.PASS,
        evidence_refs=source.evidence_refs,
        contradiction_scan=ProofState.PASS,
        phi_gov_status=PhiGovStatus.ACCEPTED,
        accepted_at="2026-05-01T00:05:00+00:00",
        accepted_by="test-governance",
        lineage_event_seq=source.event_seq,
    )

    clock.set("2026-05-03T00:00:00+00:00")

    with pytest.raises(RuntimeCoreInvariantError, match="materialized state"):
        mesh.queue_promotion(source.note_id)
    with pytest.raises(RuntimeCoreInvariantError, match="materialized state"):
        mesh.promote_memory_anchor(source.note_id, receipt)
    assert not (tmp_path / "notes" / "anchors" / "anchor-expired-source.json").exists()


def test_promotion_receipt_must_match_queue_and_safe_anchor_identifier(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.REPOSITORY,
            content_summary="receipt identity is bound to queued source event",
            source_ref="test:promotion-receipt-binding",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_promotion_receipt_must_match_queue_and_safe_anchor_identifier",),
        )
    )

    with pytest.raises(RuntimeCoreInvariantError, match="queued promotion"):
        mesh.promote_memory_anchor(
            source.note_id,
            PromotionReceipt(
                promotion_id=stable_unqueued_promotion_id(source.note_id, source.event_seq),
                source_note_id=source.note_id,
                anchor_id="anchor-unqueued",
                proof_state=ProofState.PASS,
                evidence_refs=source.evidence_refs,
                contradiction_scan=ProofState.PASS,
                phi_gov_status=PhiGovStatus.ACCEPTED,
                accepted_at="2026-05-01T00:05:00+00:00",
                accepted_by="test-governance",
                lineage_event_seq=source.event_seq,
            ),
        )
    promotion_id = mesh.queue_promotion(source.note_id)
    with pytest.raises(RuntimeCoreInvariantError, match="lineage_event_seq mismatch"):
        mesh.promote_memory_anchor(
            source.note_id,
            PromotionReceipt(
                promotion_id=promotion_id,
                source_note_id=source.note_id,
                anchor_id="anchor-stale-lineage",
                proof_state=ProofState.PASS,
                evidence_refs=source.evidence_refs,
                contradiction_scan=ProofState.PASS,
                phi_gov_status=PhiGovStatus.ACCEPTED,
                accepted_at="2026-05-01T00:06:00+00:00",
                accepted_by="test-governance",
                lineage_event_seq=source.event_seq + 1,
            ),
        )
    with pytest.raises(RuntimeCoreInvariantError, match="bounded symbolic identifier"):
        PromotionReceipt(
            promotion_id=promotion_id,
            source_note_id=source.note_id,
            anchor_id="../outside-anchor",
            proof_state=ProofState.PASS,
            evidence_refs=source.evidence_refs,
            contradiction_scan=ProofState.PASS,
            phi_gov_status=PhiGovStatus.ACCEPTED,
            accepted_at="2026-05-01T00:07:00+00:00",
            accepted_by="test-governance",
            lineage_event_seq=source.event_seq,
        )
    assert not (tmp_path / "outside-anchor.json").exists()


def test_promotion_queue_is_idempotent_and_rejects_malformed_source_sequence(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.DECISION_RECORD,
            scope=NoteScope.REPOSITORY,
            content_summary="promotion queue replay remains a single pending entry",
            source_ref="test:promotion-queue-idempotent",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("test_promotion_queue_is_idempotent",),
        )
    )

    first_promotion_id = mesh.queue_promotion(source.note_id)
    second_promotion_id = mesh.queue_promotion(source.note_id)
    pending_path = tmp_path / "notes" / "promotions" / "pending.jsonl"
    pending_entries = [json.loads(line) for line in pending_path.read_text(encoding="utf-8").splitlines()]

    assert first_promotion_id == second_promotion_id
    assert len(pending_entries) == 1
    assert pending_entries[0]["source_event_seq"] == source.event_seq
    pending_entries[0]["source_event_seq"] = "not-an-int"
    pending_path.write_text(json.dumps(pending_entries[0], sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeCoreInvariantError, match="invalid promotion queue source_event_seq"):
        mesh.queue_promotion(source.note_id)


def test_promotion_receipt_is_removed_when_event_append_fails(tmp_path, monkeypatch) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    source = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.REPOSITORY,
            content_summary="anchor receipt rollback preserves promotion atomicity",
            source_ref="test:promotion-rollback",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-04T00:00:00+00:00",
            evidence_refs=("test_promotion_receipt_is_removed_when_event_append_fails",),
        )
    )
    promotion_id = mesh.queue_promotion(source.note_id)
    receipt = PromotionReceipt(
        promotion_id=promotion_id,
        source_note_id=source.note_id,
        anchor_id="anchor-rollback-source",
        proof_state=ProofState.PASS,
        evidence_refs=source.evidence_refs,
        contradiction_scan=ProofState.PASS,
        phi_gov_status=PhiGovStatus.ACCEPTED,
        accepted_at="2026-05-01T00:05:00+00:00",
        accepted_by="test-governance",
        lineage_event_seq=source.event_seq,
    )

    def fail_event_append(_sequenced) -> None:
        raise OSError("simulated event append failure")

    monkeypatch.setattr(mesh, "_write_event_locked", fail_event_append)
    with pytest.raises(OSError, match="simulated event append failure"):
        mesh.promote_memory_anchor(source.note_id, receipt)

    assert not (tmp_path / "notes" / "anchors" / "anchor-rollback-source.json").exists()
    assert mesh.event_count == 1
    assert source.note_id in {note.event.note_id for note in mesh.retrieve_notes("anchor receipt", RetrievalGuard(scope=NoteScope.REPOSITORY))}


def test_promotion_rejects_unknown_no_evidence_and_non_promotable_sources(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    unknown = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="unknown note cannot promote",
            source_ref="test:unknown",
            proof_state=ProofState.UNKNOWN,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-02T00:00:00+00:00",
            evidence_refs=("hypothesis",),
        )
    )
    no_evidence = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.TASK,
            content_summary="pass note without evidence cannot promote",
            source_ref="test:no-evidence",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-05-02T00:00:00+00:00",
        )
    )
    trace = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.EXECUTION_TRACE,
            scope=NoteScope.TASK,
            content_summary="execution trace is evidence but not a memory source",
            source_ref="test:trace",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("trace",),
        )
    )

    with pytest.raises(RuntimeCoreInvariantError, match="ProofState Pass"):
        mesh.queue_promotion(unknown.note_id)
    with pytest.raises(RuntimeCoreInvariantError, match="evidence_refs"):
        mesh.queue_promotion(no_evidence.note_id)
    with pytest.raises(RuntimeCoreInvariantError, match="cannot be promoted"):
        mesh.queue_promotion(trace.note_id)
    with pytest.raises(RuntimeCoreInvariantError, match="promote_memory_anchor"):
        mesh.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.MEMORY_ANCHOR,
                action=NoteAction.PROMOTE,
                scope=NoteScope.TASK,
                content_summary="direct anchor bypass should be blocked",
                source_ref="test:direct-anchor",
                proof_state=ProofState.PASS,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=("direct",),
            )
        )
    assert mesh.event_count == 3


def test_rebuild_reports_corrupt_lines_and_checksum_failures(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    event = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.EXECUTION_TRACE,
            scope=NoteScope.TASK,
            content_summary="trace survives rebuild",
            source_ref="test:rebuild",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            evidence_refs=("trace",),
        )
    )
    event_path = tmp_path / "notes" / "events" / "2026-05-01.jsonl"
    tampered = event.to_dict()
    tampered["event_id"] = "tampered"
    event_path.write_text(
        event_path.read_text(encoding="utf-8")
        + json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        + "\nnot-json\n",
        encoding="utf-8",
    )

    report = mesh.rebuild_index_from_events()

    assert report.valid_events == 1
    assert report.checksum_failures == 1
    assert report.rejected_lines == 1
    assert report.proof_state == ProofState.FAIL


def test_mfidel_decomposition_note_is_rejected_without_normalizing_symbols(tmp_path) -> None:
    clock = MutableClock("2026-05-01T00:00:00+00:00")
    mesh = _mesh(tmp_path, clock)

    with pytest.raises(RuntimeCoreInvariantError, match="Mfidel atomicity"):
        mesh.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.WORKING_NOTE,
                scope=NoteScope.TASK,
                content_summary="split fidel into consonant + vowel for parser identity",
                source_ref="test:mfidel",
                proof_state=ProofState.UNKNOWN,
                trust_zone=TrustZone.WORKSPACE,
                expires_at="2026-05-02T00:00:00+00:00",
            )
        )
    rejected = mesh.record_rejected_delta(
        content_summary="Rejected split fidel into consonant + vowel proposal as violation",
        source_ref="test:mfidel-rejected",
        evidence_refs=("mfidel_atomicity_policy",),
    )

    assert mesh.event_count == 1
    assert rejected.kind == NoteKind.REJECTED_DELTA
    assert rejected.proof_state == ProofState.FAIL
    assert "split fidel" in rejected.content_summary


def stable_unqueued_promotion_id(note_id: str, event_seq: int) -> str:
    return stable_identifier("note-promotion", {"note_id": note_id, "event_seq": event_seq})
