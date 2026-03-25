"""Golden scenario tests for commitment extraction subsystem.

7 scenarios covering end-to-end extraction flows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.commitment_extraction import (
    CommitmentDisposition,
    CommitmentSourceType,
    CommitmentType,
)
from mcoi_runtime.core.commitment_extraction import CommitmentExtractionEngine
from mcoi_runtime.core.commitment_extraction_integration import CommitmentExtractionIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine


def _build():
    ee = CommitmentExtractionEngine()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    obl = ObligationRuntimeEngine()
    integ = CommitmentExtractionIntegration(
        extraction_engine=ee, event_spine=es,
        memory_engine=me, obligation_runtime=obl,
    )
    return ee, es, me, obl, integ


# ---------------------------------------------------------------------------
# Scenario 1: "approved, deploy by 5pm" → approval + deadline + obligation
# ---------------------------------------------------------------------------


class TestGolden1ApprovalDeadlineObligation:
    def test_approval_with_deadline_creates_obligation(self):
        ee, es, me, obl, integ = _build()

        result = integ.extract_and_create_obligations(
            "Approved, deploy by 5pm today",
            CommitmentSourceType.MESSAGE, "msg-deploy-1",
        )

        extraction = result["result"]

        # Approval detected
        assert len(extraction.approvals) >= 1
        assert any(a.approved for a in extraction.approvals)

        # Deadline detected
        assert len(extraction.deadlines) >= 1

        # Candidate with ACCEPTED disposition
        accepted = [c for c in extraction.candidates
                    if c.disposition == CommitmentDisposition.ACCEPTED]
        assert len(accepted) >= 1

        # Obligation created
        assert len(result["obligations"]) >= 1
        assert len(result["promotions"]) >= 1

        # Obligation has description from normalized text
        obl_record = result["obligations"][0]
        assert obl_record.description

        # Event emitted
        assert result["event"].payload["candidate_count"] >= 1


# ---------------------------------------------------------------------------
# Scenario 2: "maybe later" → AMBIGUOUS, no obligation
# ---------------------------------------------------------------------------


class TestGolden2AmbiguousNoObligation:
    def test_ambiguous_creates_no_obligation(self):
        ee, es, me, obl, integ = _build()

        result = integ.extract_and_create_obligations(
            "Maybe later we can approve this and follow up",
            CommitmentSourceType.MESSAGE, "msg-ambig-1",
        )

        extraction = result["result"]

        # Candidates should be AMBIGUOUS
        for c in extraction.candidates:
            assert c.disposition == CommitmentDisposition.AMBIGUOUS

        # No obligations created
        assert len(result["obligations"]) == 0
        assert len(result["promotions"]) == 0

        # Event still emitted (audit trail)
        assert result["event"] is not None


# ---------------------------------------------------------------------------
# Scenario 3: transcript "Alice will follow up tomorrow" → owner + deadline + obligation
# ---------------------------------------------------------------------------


class TestGolden3TranscriptFollowUp:
    def test_transcript_creates_follow_up_obligation(self):
        ee, es, me, obl, integ = _build()

        result = integ.extract_and_create_obligations(
            "Alice will follow up due tomorrow on the infrastructure review",
            CommitmentSourceType.CALL_TRANSCRIPT, "tr-review-1",
        )

        extraction = result["result"]

        # Owner detected
        assert len(extraction.owners) >= 1
        assert any(o.normalized_owner == "alice" for o in extraction.owners)

        # Deadline detected
        assert len(extraction.deadlines) >= 1

        # Follow-up candidate
        follow_ups = [c for c in extraction.candidates
                      if c.commitment_type == CommitmentType.FOLLOW_UP]
        assert len(follow_ups) >= 1

        # Owner propagated to candidate
        owner_candidates = [c for c in extraction.candidates if c.proposed_owner_id == "alice"]
        assert len(owner_candidates) >= 1

        # Obligation created
        assert len(result["obligations"]) >= 1


# ---------------------------------------------------------------------------
# Scenario 4: artifact ticket → escalation candidate routed
# ---------------------------------------------------------------------------


class TestGolden4ArtifactEscalation:
    def test_artifact_escalation_routed(self):
        ee, es, me, obl, integ = _build()

        ticket_text = "Critical issue: please escalate to security team immediately"
        result = integ.extract_from_artifact_ingestion(
            "art-ticket-1", ticket_text, create_obligations=True,
        )

        extraction = result["result"]

        # Escalation detected
        assert len(extraction.escalations) >= 1

        # Escalation candidate created
        esc_candidates = [c for c in extraction.candidates
                          if c.commitment_type == CommitmentType.ESCALATION]
        assert len(esc_candidates) >= 1

        # Obligation created (escalation is actionable)
        assert len(result["obligations"]) >= 1

        # Route the commitments
        decisions = ee.route_commitments(extraction, "default-ops")
        assert len(decisions) >= 1


# ---------------------------------------------------------------------------
# Scenario 5: rejected approval does not create executable obligation
# ---------------------------------------------------------------------------


class TestGolden5RejectedNoObligation:
    def test_rejected_approval_no_obligation(self):
        ee, es, me, obl, integ = _build()

        result = integ.extract_and_create_obligations(
            "This request is denied. Do not proceed with the deployment.",
            CommitmentSourceType.MESSAGE, "msg-deny-1",
        )

        extraction = result["result"]

        # Rejection detected
        assert any(not a.approved for a in extraction.approvals)

        # Candidates are REJECTED
        rejection_candidates = [c for c in extraction.candidates
                                if c.disposition == CommitmentDisposition.REJECTED]
        assert len(rejection_candidates) >= 1

        # No obligations created
        assert len(result["obligations"]) == 0


# ---------------------------------------------------------------------------
# Scenario 6: extracted commitment remembered + linked to event lineage
# ---------------------------------------------------------------------------


class TestGolden6CommitmentRememberedWithLineage:
    def test_commitment_in_memory_with_lineage(self):
        ee, es, me, obl, integ = _build()

        result = integ.extract_and_remember(
            "Approved, Alice will handle the deployment by Friday",
            CommitmentSourceType.MESSAGE, "msg-lineage-1",
            tags=("deployment",),
        )

        # Memory created
        mem = result["memory"]
        assert mem is not None
        assert "commitment_extraction" in mem.tags
        assert "deployment" in mem.tags
        assert mem.content["candidate_count"] >= 1

        # Memory has candidate details
        assert len(mem.content["candidates"]) >= 1
        candidate_info = mem.content["candidates"][0]
        assert "type" in candidate_info
        assert "disposition" in candidate_info
        assert "text" in candidate_info

        # Event emitted with correlation
        assert result["event"].correlation_id == "msg-lineage-1"

        # Memory engine has the record
        assert me.memory_count >= 1


# ---------------------------------------------------------------------------
# Scenario 7: repeated same commitment → idempotent, no duplicate obligations
# ---------------------------------------------------------------------------


class TestGolden7IdempotentNoDuplicates:
    def test_replay_does_not_duplicate_obligations(self):
        ee, es, me, obl, integ = _build()

        text = "Approved, go ahead with the release"
        source = CommitmentSourceType.MESSAGE
        ref = "msg-replay-1"

        # First extraction
        result1 = integ.extract_and_create_obligations(text, source, ref)
        obl_count_1 = len(result1["obligations"])
        assert obl_count_1 >= 1

        # Second extraction — same text, same ref
        result2 = integ.extract_and_create_obligations(text, source, ref)
        obl_count_2 = len(result2["obligations"])

        # No new obligations (already promoted or already exists)
        assert obl_count_2 == 0

        # Total promotion count should be same as first run
        assert ee.promotion_count == obl_count_1
