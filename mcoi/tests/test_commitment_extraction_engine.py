"""Engine-level tests for CommitmentExtractionEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.commitment_extraction import (
    CommitmentDisposition,
    CommitmentSourceType,
    CommitmentType,
    ExtractionConfidenceLevel,
)
from mcoi_runtime.core.commitment_extraction import CommitmentExtractionEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Approval detection
# ---------------------------------------------------------------------------


class TestApprovalDetection:
    def test_approve(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-1", "I approve this request")
        assert len(result.approvals) >= 1
        assert result.approvals[0].approved is True

    def test_approved(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-2", "This is approved, go ahead")
        assert any(a.approved for a in result.approvals)

    def test_go_ahead(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-3", "Go ahead with the deployment")
        assert any(a.approved for a in result.approvals)

    def test_proceed(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-4", "Please proceed")
        assert any(a.approved for a in result.approvals)

    def test_rejected(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-5", "This request is rejected")
        assert any(not a.approved for a in result.approvals)

    def test_denied(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-6", "Access denied")
        assert any(not a.approved for a in result.approvals)

    def test_do_not_proceed(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-7", "Do not proceed with this")
        assert any(not a.approved for a in result.approvals)

    def test_no_approval_in_plain_text(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-8", "Hello, how are you today?")
        assert len(result.approvals) == 0


# ---------------------------------------------------------------------------
# Deadline detection
# ---------------------------------------------------------------------------


class TestDeadlineDetection:
    def test_by_friday(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d1", "Please finish by Friday")
        assert len(result.deadlines) >= 1

    def test_before_5pm(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d2", "Submit before 5pm")
        assert len(result.deadlines) >= 1

    def test_due_tomorrow(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d3", "This is due tomorrow")
        assert len(result.deadlines) >= 1

    def test_within_hours(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d4", "Complete within 2 hours")
        assert len(result.deadlines) >= 1

    def test_by_eod(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d5", "Need this by end of day")
        assert len(result.deadlines) >= 1

    def test_no_deadline(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-d6", "Take your time with this")
        assert len(result.deadlines) == 0


# ---------------------------------------------------------------------------
# Owner detection
# ---------------------------------------------------------------------------


class TestOwnerDetection:
    def test_will_handle(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-o1", "Alice will handle this")
        assert len(result.owners) >= 1
        assert result.owners[0].normalized_owner == "alice"

    def test_assign_to(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-o2", "Assign to ops team")
        assert len(result.owners) >= 1
        assert result.owners[0].normalized_owner == "ops"

    def test_send_to(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-o3", "Send it to support")
        assert len(result.owners) >= 1
        assert result.owners[0].normalized_owner == "support"

    def test_skip_pronouns(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-o4", "I will handle this")
        assert len(result.owners) == 0

    def test_skip_they(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-o5", "They will handle this")
        assert len(result.owners) == 0


# ---------------------------------------------------------------------------
# Escalation detection
# ---------------------------------------------------------------------------


class TestEscalationDetection:
    def test_escalate_to_manager(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-e1", "Please escalate to manager")
        assert len(result.escalations) >= 1

    def test_notify(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-e2", "Notify security team")
        assert len(result.escalations) >= 1

    def test_urgent_escalation(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-e3", "This needs urgent escalation")
        assert len(result.escalations) >= 1
        assert result.escalations[0].urgency == "urgent"

    def test_no_escalation(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-e4", "Everything looks fine")
        assert len(result.escalations) == 0


# ---------------------------------------------------------------------------
# Ambiguity detection
# ---------------------------------------------------------------------------


class TestAmbiguityDetection:
    def test_maybe_later(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-a1", "Maybe later we can approve this")
        # Should have approval signal but AMBIGUOUS disposition on candidate
        for c in result.candidates:
            assert c.disposition == CommitmentDisposition.AMBIGUOUS

    def test_not_sure(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-a2", "Not sure if we should proceed")
        for c in result.candidates:
            assert c.disposition == CommitmentDisposition.AMBIGUOUS

    def test_tbd(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-a3", "TBD, Alice will follow up")
        for c in result.candidates:
            assert c.disposition == CommitmentDisposition.AMBIGUOUS


# ---------------------------------------------------------------------------
# Candidate building
# ---------------------------------------------------------------------------


class TestCandidateBuilding:
    def test_approval_creates_candidate(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c1", "Approved, deploy by 5pm")
        assert len(result.candidates) >= 1
        approval_candidates = [c for c in result.candidates if c.commitment_type == CommitmentType.APPROVAL]
        assert len(approval_candidates) >= 1
        assert approval_candidates[0].disposition == CommitmentDisposition.ACCEPTED
        assert approval_candidates[0].reason == "approval signal detected"
        assert "approved" not in approval_candidates[0].reason

    def test_rejection_creates_rejected_candidate(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c2", "This is rejected")
        rejection_candidates = [c for c in result.candidates if c.commitment_type == CommitmentType.APPROVAL]
        assert len(rejection_candidates) >= 1
        assert rejection_candidates[0].disposition == CommitmentDisposition.REJECTED
        assert rejection_candidates[0].reason == "rejection signal detected"
        assert "msg-c2" not in rejection_candidates[0].reason

    def test_follow_up_candidate(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c3", "Please follow up on this request")
        follow_ups = [c for c in result.candidates if c.commitment_type == CommitmentType.FOLLOW_UP]
        assert len(follow_ups) >= 1

    def test_escalation_candidate(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c4", "Escalate to manager immediately")
        esc_candidates = [c for c in result.candidates if c.commitment_type == CommitmentType.ESCALATION]
        assert len(esc_candidates) >= 1

    def test_owner_assignment_task(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c5", "Alice will handle the review")
        task_candidates = [c for c in result.candidates if c.commitment_type == CommitmentType.TASK]
        assert len(task_candidates) >= 1
        assert task_candidates[0].proposed_owner_id == "alice"

    def test_approval_with_deadline(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c6", "Approved, complete by Friday")
        approval_candidates = [c for c in result.candidates if c.commitment_type == CommitmentType.APPROVAL]
        assert len(approval_candidates) >= 1
        assert approval_candidates[0].proposed_due_at != ""

    def test_empty_text_no_candidates(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-c7", "Hello, how are you?")
        assert len(result.candidates) == 0


# ---------------------------------------------------------------------------
# Source-type extraction methods
# ---------------------------------------------------------------------------


class TestSourceTypeMethods:
    def test_extract_from_transcript(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_transcript("tr-1", "Alice will follow up tomorrow")
        assert result.source_type == CommitmentSourceType.CALL_TRANSCRIPT

    def test_extract_from_artifact(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_artifact("art-1", "Assign to ops team")
        assert result.source_type == CommitmentSourceType.ARTIFACT


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouting:
    def test_route_proposed(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-r1", "Alice will handle the deployment")
        decisions = engine.route_commitments(result, "default-id")
        assert len(decisions) >= 1
        assert decisions[0].routed_to_identity_id == "alice"
        assert decisions[0].reason == "commitment routed"
        assert engine.get_candidate(decisions[0].commitment_id).commitment_type.value not in decisions[0].reason

    def test_route_uses_default(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-r2", "Please follow up on this")
        decisions = engine.route_commitments(result, "default-id")
        for d in decisions:
            if not engine.get_candidate(d.commitment_id).proposed_owner_id:
                assert d.routed_to_identity_id == "default-id"

    def test_route_skips_rejected(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-r3", "This request is rejected")
        decisions = engine.route_commitments(result, "default-id")
        assert len(decisions) == 0

    def test_route_skips_ambiguous(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-r4", "Maybe later we can follow up")
        decisions = engine.route_commitments(result, "default-id")
        assert len(decisions) == 0


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_promote_valid(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-p1", "Approved, go ahead")
        assert len(result.candidates) >= 1
        cid = result.candidates[0].commitment_id
        promo = engine.promote_commitment(cid, "obl-1")
        assert promo.obligation_id == "obl-1"
        assert engine.is_promoted(cid)

    def test_promote_missing_rejected(self):
        engine = CommitmentExtractionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            engine.promote_commitment("missing", "obl-1")
        assert "missing" not in str(exc_info.value)

    def test_promote_rejected_commitment_rejected(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-p2", "This is rejected")
        if result.candidates:
            cid = result.candidates[0].commitment_id
            with pytest.raises(RuntimeCoreInvariantError, match="cannot promote") as exc_info:
                engine.promote_commitment(cid, "obl-1")
            assert cid not in str(exc_info.value)

    def test_double_promote_rejected(self):
        engine = CommitmentExtractionEngine()
        result = engine.extract_from_message("msg-p3", "Approved and proceed")
        if result.candidates:
            cid = result.candidates[0].commitment_id
            engine.promote_commitment(cid, "obl-1")
            with pytest.raises(RuntimeCoreInvariantError, match="already promoted") as exc_info:
                engine.promote_commitment(cid, "obl-2")
            assert cid not in str(exc_info.value)


# ---------------------------------------------------------------------------
# State hash and properties
# ---------------------------------------------------------------------------


class TestStateHashAndProperties:
    def test_candidate_count(self):
        engine = CommitmentExtractionEngine()
        assert engine.candidate_count == 0
        engine.extract_from_message("msg-s1", "Approved")
        assert engine.candidate_count >= 1

    def test_result_count(self):
        engine = CommitmentExtractionEngine()
        engine.extract_from_message("msg-s2", "Hello")
        assert engine.result_count == 1

    def test_state_hash_deterministic(self):
        e1 = CommitmentExtractionEngine()
        e2 = CommitmentExtractionEngine()
        assert e1.state_hash() == e2.state_hash()

    def test_state_hash_changes(self):
        engine = CommitmentExtractionEngine()
        h1 = engine.state_hash()
        engine.extract_from_message("msg-s3", "Approved")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_length(self):
        engine = CommitmentExtractionEngine()
        assert len(engine.state_hash()) == 64
