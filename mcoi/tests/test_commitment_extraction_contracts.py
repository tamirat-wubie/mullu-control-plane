"""Contract-level tests for commitment_extraction contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.commitment_extraction import (
    ApprovalSignal,
    CommitmentCandidate,
    CommitmentDisposition,
    CommitmentExtractionResult,
    CommitmentPromotionRecord,
    CommitmentRoutingDecision,
    CommitmentSourceType,
    CommitmentType,
    DeadlineSignal,
    EscalationSignal,
    ExtractionConfidenceLevel,
    OwnerSignal,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_commitment_type_count(self):
        assert len(CommitmentType) == 9

    def test_source_type_count(self):
        assert len(CommitmentSourceType) == 6

    def test_confidence_level_count(self):
        assert len(ExtractionConfidenceLevel) == 4

    def test_disposition_count(self):
        assert len(CommitmentDisposition) == 5


# ---------------------------------------------------------------------------
# CommitmentCandidate
# ---------------------------------------------------------------------------


class TestCommitmentCandidate:
    def _make(self, **kw):
        defaults = dict(
            commitment_id="cc-1",
            source_type=CommitmentSourceType.MESSAGE,
            source_ref_id="msg-1",
            commitment_type=CommitmentType.TASK,
            text_span="handle the deployment",
            normalized_text="Task: handle the deployment",
            created_at=NOW,
        )
        defaults.update(kw)
        return CommitmentCandidate(**defaults)

    def test_valid(self):
        c = self._make()
        assert c.commitment_id == "cc-1"
        assert c.disposition == CommitmentDisposition.PROPOSED

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(commitment_id="")

    def test_empty_text_span_rejected(self):
        with pytest.raises(ValueError):
            self._make(text_span="")

    def test_invalid_source_type(self):
        with pytest.raises(ValueError):
            self._make(source_type="pigeon")

    def test_invalid_commitment_type(self):
        with pytest.raises(ValueError):
            self._make(commitment_type="wish")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.5)

    def test_all_dispositions(self):
        for d in CommitmentDisposition:
            c = self._make(disposition=d)
            assert c.disposition == d

    def test_all_source_types(self):
        for st in CommitmentSourceType:
            c = self._make(source_type=st)
            assert c.source_type == st

    def test_all_commitment_types(self):
        for ct in CommitmentType:
            c = self._make(commitment_type=ct)
            assert c.commitment_type == ct

    def test_metadata_frozen(self):
        c = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            c.metadata["new"] = "val"

    def test_frozen(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.commitment_id = "new"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["source_type"] == "message"
        assert d["commitment_type"] == "task"


# ---------------------------------------------------------------------------
# ApprovalSignal
# ---------------------------------------------------------------------------


class TestApprovalSignal:
    def test_valid_approved(self):
        s = ApprovalSignal(
            signal_id="appr-1", source_ref_id="msg-1",
            approved=True, text_span="approved", created_at=NOW,
        )
        assert s.approved is True

    def test_valid_rejected(self):
        s = ApprovalSignal(
            signal_id="appr-2", source_ref_id="msg-1",
            approved=False, text_span="rejected", created_at=NOW,
        )
        assert s.approved is False

    def test_approved_must_be_bool(self):
        with pytest.raises(ValueError):
            ApprovalSignal(
                signal_id="appr-bad", source_ref_id="msg-1",
                approved="yes", text_span="ok", created_at=NOW,
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            ApprovalSignal(
                signal_id="appr-bad2", source_ref_id="msg-1",
                approved=True, text_span="ok", confidence=2.0, created_at=NOW,
            )


# ---------------------------------------------------------------------------
# DeadlineSignal
# ---------------------------------------------------------------------------


class TestDeadlineSignal:
    def test_valid(self):
        s = DeadlineSignal(
            signal_id="dl-1", source_ref_id="msg-1",
            text_span="by Friday", normalized_deadline="by friday",
            created_at=NOW,
        )
        assert s.normalized_deadline == "by friday"

    def test_empty_deadline_rejected(self):
        with pytest.raises(ValueError):
            DeadlineSignal(
                signal_id="dl-bad", source_ref_id="msg-1",
                text_span="by Friday", normalized_deadline="",
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# OwnerSignal
# ---------------------------------------------------------------------------


class TestOwnerSignal:
    def test_valid(self):
        s = OwnerSignal(
            signal_id="own-1", source_ref_id="msg-1",
            text_span="Alice will handle this",
            normalized_owner="alice", created_at=NOW,
        )
        assert s.normalized_owner == "alice"

    def test_empty_owner_rejected(self):
        with pytest.raises(ValueError):
            OwnerSignal(
                signal_id="own-bad", source_ref_id="msg-1",
                text_span="someone", normalized_owner="",
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# EscalationSignal
# ---------------------------------------------------------------------------


class TestEscalationSignal:
    def test_valid(self):
        s = EscalationSignal(
            signal_id="esc-1", source_ref_id="msg-1",
            text_span="escalate to manager",
            target_description="manager", created_at=NOW,
        )
        assert s.target_description == "manager"

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError):
            EscalationSignal(
                signal_id="esc-bad", source_ref_id="msg-1",
                text_span="escalate", target_description="",
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# CommitmentExtractionResult
# ---------------------------------------------------------------------------


class TestCommitmentExtractionResult:
    def test_valid_empty(self):
        r = CommitmentExtractionResult(
            result_id="res-1",
            source_type=CommitmentSourceType.MESSAGE,
            source_ref_id="msg-1",
            created_at=NOW,
        )
        assert r.candidates == ()

    def test_invalid_candidate(self):
        with pytest.raises(ValueError, match="CommitmentCandidate"):
            CommitmentExtractionResult(
                result_id="res-bad",
                source_type=CommitmentSourceType.MESSAGE,
                source_ref_id="msg-1",
                candidates=("not a candidate",),
                created_at=NOW,
            )

    def test_invalid_approval(self):
        with pytest.raises(ValueError, match="ApprovalSignal"):
            CommitmentExtractionResult(
                result_id="res-bad2",
                source_type=CommitmentSourceType.MESSAGE,
                source_ref_id="msg-1",
                approvals=("not an approval",),
                created_at=NOW,
            )

    def test_with_all_signals(self):
        candidate = CommitmentCandidate(
            commitment_id="cc-1",
            source_type=CommitmentSourceType.MESSAGE,
            source_ref_id="msg-1",
            commitment_type=CommitmentType.TASK,
            text_span="do it",
            normalized_text="Task: do it",
            created_at=NOW,
        )
        approval = ApprovalSignal(
            signal_id="a-1", source_ref_id="msg-1",
            approved=True, text_span="approved", created_at=NOW,
        )
        r = CommitmentExtractionResult(
            result_id="res-full",
            source_type=CommitmentSourceType.MESSAGE,
            source_ref_id="msg-1",
            candidates=(candidate,),
            approvals=(approval,),
            created_at=NOW,
        )
        assert len(r.candidates) == 1
        assert len(r.approvals) == 1


# ---------------------------------------------------------------------------
# CommitmentRoutingDecision
# ---------------------------------------------------------------------------


class TestCommitmentRoutingDecision:
    def test_valid(self):
        d = CommitmentRoutingDecision(
            decision_id="rd-1", commitment_id="cc-1",
            routed_to_identity_id="id-1",
            reason="Routed task", created_at=NOW,
        )
        assert d.routed_to_identity_id == "id-1"

    def test_empty_commitment_id_rejected(self):
        with pytest.raises(ValueError):
            CommitmentRoutingDecision(
                decision_id="rd-bad", commitment_id="",
                routed_to_identity_id="id-1", created_at=NOW,
            )


# ---------------------------------------------------------------------------
# CommitmentPromotionRecord
# ---------------------------------------------------------------------------


class TestCommitmentPromotionRecord:
    def test_valid(self):
        p = CommitmentPromotionRecord(
            promotion_id="promo-1", commitment_id="cc-1",
            obligation_id="obl-1", promoted_at=NOW,
        )
        assert p.obligation_id == "obl-1"

    def test_empty_obligation_id_rejected(self):
        with pytest.raises(ValueError):
            CommitmentPromotionRecord(
                promotion_id="promo-bad", commitment_id="cc-1",
                obligation_id="", promoted_at=NOW,
            )

    def test_frozen(self):
        p = CommitmentPromotionRecord(
            promotion_id="promo-2", commitment_id="cc-1",
            obligation_id="obl-1", promoted_at=NOW,
        )
        with pytest.raises(AttributeError):
            p.obligation_id = "new"
