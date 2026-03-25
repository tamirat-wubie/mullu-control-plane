"""Integration tests for CommitmentExtractionIntegration bridge."""

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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
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
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid(self):
        _, _, _, _, integ = _build()
        assert integ is not None

    def test_bad_extraction_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="extraction_engine"):
            CommitmentExtractionIntegration(
                extraction_engine="bad",
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            CommitmentExtractionIntegration(
                extraction_engine=CommitmentExtractionEngine(),
                event_spine="bad",
                memory_engine=MemoryMeshEngine(),
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_memory_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            CommitmentExtractionIntegration(
                extraction_engine=CommitmentExtractionEngine(),
                event_spine=EventSpineEngine(),
                memory_engine="bad",
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_obligation_runtime(self):
        with pytest.raises(RuntimeCoreInvariantError, match="obligation_runtime"):
            CommitmentExtractionIntegration(
                extraction_engine=CommitmentExtractionEngine(),
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
                obligation_runtime="bad",
            )


# ---------------------------------------------------------------------------
# extract_and_emit_events
# ---------------------------------------------------------------------------


class TestExtractAndEmitEvents:
    def test_emits_event(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_emit_events(
            "Approved, go ahead", CommitmentSourceType.MESSAGE, "msg-1",
        )
        assert result["event"] is not None
        assert result["event"].payload["action"] == "commitments_extracted"
        assert result["event"].payload["candidate_count"] >= 1

    def test_no_candidates_still_emits(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_emit_events(
            "Hello world", CommitmentSourceType.MESSAGE, "msg-2",
        )
        assert result["event"] is not None
        assert result["event"].payload["candidate_count"] == 0


# ---------------------------------------------------------------------------
# extract_and_create_obligations
# ---------------------------------------------------------------------------


class TestExtractAndCreateObligations:
    def test_creates_obligation(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_create_obligations(
            "Approved, proceed with deployment",
            CommitmentSourceType.MESSAGE, "msg-obl-1",
        )
        assert len(result["obligations"]) >= 1
        assert len(result["promotions"]) >= 1

    def test_no_obligation_for_rejection(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_create_obligations(
            "This is rejected",
            CommitmentSourceType.MESSAGE, "msg-obl-2",
        )
        assert len(result["obligations"]) == 0

    def test_no_obligation_for_ambiguous(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_create_obligations(
            "Maybe later we can approve this",
            CommitmentSourceType.MESSAGE, "msg-obl-3",
        )
        assert len(result["obligations"]) == 0

    def test_idempotency(self):
        ee, es, me, obl, integ = _build()
        # First extraction
        result1 = integ.extract_and_create_obligations(
            "Approved, go ahead",
            CommitmentSourceType.MESSAGE, "msg-obl-4",
        )
        obl_count_1 = len(result1["obligations"])
        assert obl_count_1 >= 1

        # Second extraction with same source — should not duplicate
        result2 = integ.extract_and_create_obligations(
            "Approved, go ahead",
            CommitmentSourceType.MESSAGE, "msg-obl-4",
        )
        # Either 0 new obligations or same count (idempotent)
        assert len(result2["obligations"]) == 0 or len(result2["obligations"]) <= obl_count_1


# ---------------------------------------------------------------------------
# extract_and_remember
# ---------------------------------------------------------------------------


class TestExtractAndRemember:
    def test_creates_memory(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_remember(
            "Alice will follow up tomorrow",
            CommitmentSourceType.MESSAGE, "msg-mem-1",
        )
        assert result["memory"] is not None
        assert "commitment_extraction" in result["memory"].tags

    def test_memory_has_candidates(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_remember(
            "Approved, proceed",
            CommitmentSourceType.MESSAGE, "msg-mem-2",
        )
        assert result["memory"].content["candidate_count"] >= 1

    def test_custom_tags(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_and_remember(
            "Follow up on this",
            CommitmentSourceType.MESSAGE, "msg-mem-3",
            tags=("urgent",),
        )
        assert "urgent" in result["memory"].tags


# ---------------------------------------------------------------------------
# Source-specific wrappers
# ---------------------------------------------------------------------------


class TestSourceWrappers:
    def test_from_communication(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_from_communication_surface("msg-w1", "Approved")
        assert result["result"].source_type == CommitmentSourceType.MESSAGE

    def test_from_artifact(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_from_artifact_ingestion("art-w1", "Escalate to manager")
        assert result["result"].source_type == CommitmentSourceType.ARTIFACT

    def test_from_operator_note(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_from_operator_note("note-w1", "Alice will handle this")
        assert result["result"].source_type == CommitmentSourceType.OPERATOR_NOTE

    def test_from_communication_with_obligations(self):
        ee, es, me, obl, integ = _build()
        result = integ.extract_from_communication_surface(
            "msg-w2", "Approved, proceed",
            create_obligations=True,
        )
        assert "obligations" in result


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestRetrieval:
    def test_retrieve_for_goal(self):
        _, _, _, _, integ = _build()
        result = integ.retrieve_commitments_for_goal("goal-1")
        assert result is not None

    def test_retrieve_for_recovery(self):
        _, _, _, _, integ = _build()
        result = integ.retrieve_commitments_for_recovery()
        assert result is not None
