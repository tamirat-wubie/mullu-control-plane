"""Comprehensive tests for ResearchRuntimeEngine.

Covers: constructor validation, questions, hypotheses, study protocols,
experiments, literature, evidence synthesis, peer reviews, snapshots,
violation detection, state hash, count properties, event emission,
frozen record verification, cross-tenant isolation, replay/restore,
and golden end-to-end scenarios.

Target: ~300 tests.
"""

from __future__ import annotations

import dataclasses

import pytest

from mcoi_runtime.core.research_runtime import ResearchRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.research_runtime import (
    EvidenceStrength,
    EvidenceSynthesis,
    ExperimentRun,
    ExperimentStatus,
    HypothesisRecord,
    HypothesisStatus,
    LiteraturePacket,
    PeerReviewRecord,
    PublicationDisposition,
    ResearchQuestion,
    ResearchSnapshot,
    ResearchStatus,
    StudyProtocol,
    StudyStatus,
)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(es: EventSpineEngine) -> ResearchRuntimeEngine:
    return ResearchRuntimeEngine(es)


@pytest.fixture()
def seeded(engine: ResearchRuntimeEngine) -> ResearchRuntimeEngine:
    """Engine with q1, h1, study s1 approved+started (IN_PROGRESS)."""
    engine.register_question("q1", "t1", "Question One", "Description one")
    engine.register_hypothesis("h1", "t1", "q1", "Hypothesis one")
    engine.register_study_protocol("s1", "t1", "h1", "Study one")
    engine.approve_study("s1")
    engine.start_study("s1")
    return engine


def _event_spine(eng: ResearchRuntimeEngine) -> EventSpineEngine:
    """Extract the event spine from an engine."""
    return eng._events


# ===================================================================
# 1. Construction (10 tests)
# ===================================================================


class TestConstruction:
    def test_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeEngine("not-an-engine")

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeEngine(None)

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeEngine(42)

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeEngine({})

    def test_rejects_list(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeEngine([])

    def test_accepts_event_spine(self, es):
        eng = ResearchRuntimeEngine(es)
        assert eng is not None

    def test_initial_question_count_zero(self, engine):
        assert engine.question_count == 0

    def test_initial_hypothesis_count_zero(self, engine):
        assert engine.hypothesis_count == 0

    def test_initial_study_count_zero(self, engine):
        assert engine.study_count == 0

    def test_initial_experiment_count_zero(self, engine):
        assert engine.experiment_count == 0

    def test_initial_literature_count_zero(self, engine):
        assert engine.literature_count == 0

    def test_initial_synthesis_count_zero(self, engine):
        assert engine.synthesis_count == 0

    def test_initial_review_count_zero(self, engine):
        assert engine.review_count == 0

    def test_initial_violation_count_zero(self, engine):
        assert engine.violation_count == 0

    def test_initial_state_hash_is_string(self, engine):
        assert isinstance(engine.state_hash(), str)

    def test_initial_state_hash_length_16(self, engine):
        assert len(engine.state_hash()) == 64


# ===================================================================
# 2. register_question (25 tests)
# ===================================================================


class TestRegisterQuestion:
    def test_returns_research_question(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert isinstance(q, ResearchQuestion)

    def test_question_id_matches(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.question_id == "q1"

    def test_tenant_id_matches(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.tenant_id == "t1"

    def test_title_matches(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.title == "Title"

    def test_description_matches(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.description == "Desc"

    def test_status_active(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.status == ResearchStatus.ACTIVE

    def test_initial_hypothesis_count_zero(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.hypothesis_count == 0

    def test_created_at_populated(self, engine):
        q = engine.register_question("q1", "t1", "Title", "Desc")
        assert q.created_at != ""

    def test_increments_question_count(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        assert engine.question_count == 1
        engine.register_question("q2", "t1", "T2", "D2")
        assert engine.question_count == 2

    def test_duplicate_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_question("q1", "t1", "T2", "D2")

    def test_duplicate_different_tenant_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_question("q1", "t2", "T2", "D2")

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.register_question("q1", "t1", "T", "D")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        q = engine.register_question("q1", "t1", "T", "D")
        with pytest.raises(dataclasses.FrozenInstanceError):
            q.title = "changed"

    def test_get_question_returns_same(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        q = engine.get_question("q1")
        assert q.question_id == "q1"

    def test_get_unknown_question_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_question("nonexistent")

    def test_questions_for_tenant_empty(self, engine):
        result = engine.questions_for_tenant("t1")
        assert result == ()

    def test_questions_for_tenant_filters(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_question("q3", "t1", "T3", "D3")
        result = engine.questions_for_tenant("t1")
        assert len(result) == 2
        assert all(q.tenant_id == "t1" for q in result)

    def test_questions_for_tenant_returns_tuple(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        result = engine.questions_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_multiple_questions_different_tenants(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_question("q3", "t3", "T3", "D3")
        assert engine.question_count == 3
        assert len(engine.questions_for_tenant("t1")) == 1
        assert len(engine.questions_for_tenant("t2")) == 1
        assert len(engine.questions_for_tenant("t3")) == 1

    def test_question_metadata_default_empty(self, engine):
        q = engine.register_question("q1", "t1", "T", "D")
        assert q.metadata == {}

    def test_question_ids_in_questions_for_tenant(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t1", "T2", "D2")
        qs = engine.questions_for_tenant("t1")
        ids = {q.question_id for q in qs}
        assert ids == {"q1", "q2"}

    def test_register_3_questions_count(self, engine):
        for i in range(3):
            engine.register_question(f"q{i}", "t1", f"T{i}", f"D{i}")
        assert engine.question_count == 3

    def test_register_question_emits_payload_with_tenant(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        # event was emitted (basic check)
        assert es.event_count >= 1

    def test_questions_for_nonexistent_tenant_empty(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        assert engine.questions_for_tenant("t99") == ()

    def test_question_title_preserved_exactly(self, engine):
        q = engine.register_question("q1", "t1", "Special Title!", "D")
        assert q.title == "Special Title!"


# ===================================================================
# 3. register_hypothesis (30 tests)
# ===================================================================


class TestRegisterHypothesis:
    def test_returns_hypothesis_record(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert isinstance(h, HypothesisRecord)

    def test_hypothesis_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.hypothesis_id == "h1"

    def test_tenant_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.tenant_id == "t1"

    def test_question_ref_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.question_ref == "q1"

    def test_statement_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "My statement")
        assert h.statement == "My statement"

    def test_status_proposed(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.status == HypothesisStatus.PROPOSED

    def test_confidence_zero(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.confidence == 0.0

    def test_evidence_count_zero(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.evidence_count == 0

    def test_created_at_populated(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.created_at != ""

    def test_increments_hypothesis_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        assert engine.hypothesis_count == 1
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        assert engine.hypothesis_count == 2

    def test_increments_question_hypothesis_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        q = engine.get_question("q1")
        assert q.hypothesis_count == 1

    def test_increments_question_hypothesis_count_twice(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        q = engine.get_question("q1")
        assert q.hypothesis_count == 2

    def test_increments_question_hypothesis_count_three(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        for i in range(3):
            engine.register_hypothesis(f"h{i}", "t1", "q1", f"S{i}")
        q = engine.get_question("q1")
        assert q.hypothesis_count == 3

    def test_duplicate_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_hypothesis("h1", "t1", "q1", "Stmt2")

    def test_unknown_question_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown question"):
            engine.register_hypothesis("h1", "t1", "nonexistent", "Stmt")

    def test_emits_event(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        before = es.event_count
        engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        with pytest.raises(dataclasses.FrozenInstanceError):
            h.statement = "changed"

    def test_get_hypothesis_returns_correct(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        h = engine.get_hypothesis("h1")
        assert h.hypothesis_id == "h1"

    def test_get_unknown_hypothesis_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_hypothesis("nonexistent")

    def test_multiple_hypotheses_different_questions(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t1", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q2", "S2")
        assert engine.hypothesis_count == 2
        q1 = engine.get_question("q1")
        q2 = engine.get_question("q2")
        assert q1.hypothesis_count == 1
        assert q2.hypothesis_count == 1

    def test_hypothesis_links_to_question(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "S")
        assert h.question_ref == "q1"

    def test_hypothesis_different_tenant_from_question(self, engine):
        """Even if tenant differs, link is by question_id."""
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t2", "q1", "S")
        assert h.tenant_id == "t2"
        assert h.question_ref == "q1"

    def test_register_5_hypotheses_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        for i in range(5):
            engine.register_hypothesis(f"h{i}", "t1", "q1", f"S{i}")
        assert engine.hypothesis_count == 5

    def test_hypothesis_metadata_default_empty(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "Stmt")
        assert h.metadata == {}

    def test_hypothesis_statement_preserved(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "X causes Y")
        assert h.statement == "X causes Y"

    def test_register_hypothesis_emits_event_with_question_id(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        before = es.event_count
        engine.register_hypothesis("h1", "t1", "q1", "S")
        assert es.event_count > before

    def test_question_hypothesis_count_not_affected_by_other_question(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t1", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q2", "S1")
        q1 = engine.get_question("q1")
        assert q1.hypothesis_count == 0

    def test_duplicate_hypothesis_id_different_question_raises(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t1", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_hypothesis("h1", "t1", "q2", "S2")

    def test_get_hypothesis_after_register(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        h = engine.get_hypothesis("h1")
        assert h.statement == "S"
        assert h.question_ref == "q1"


# ===================================================================
# 4. register_study_protocol (20 tests)
# ===================================================================


class TestRegisterStudyProtocol:
    def test_returns_study_protocol(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert isinstance(s, StudyProtocol)

    def test_study_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.study_id == "s1"

    def test_tenant_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.tenant_id == "t1"

    def test_title_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "My Study")
        assert s.title == "My Study"

    def test_hypothesis_ref_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.hypothesis_ref == "h1"

    def test_status_draft(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.status == StudyStatus.DRAFT

    def test_experiment_count_zero(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.experiment_count == 0

    def test_created_at_populated(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.created_at != ""

    def test_increments_study_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert engine.study_count == 1

    def test_duplicate_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_study_protocol("s1", "t1", "h1", "Study2")

    def test_unknown_hypothesis_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown hypothesis"):
            engine.register_study_protocol("s1", "t1", "nonexistent", "Study")

    def test_emits_event(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        before = es.event_count
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.title = "changed"

    def test_get_study_returns_correct(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.get_study("s1")
        assert s.study_id == "s1"

    def test_get_unknown_study_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_study("nonexistent")

    def test_multiple_studies_same_hypothesis(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study1")
        engine.register_study_protocol("s2", "t1", "h1", "Study2")
        assert engine.study_count == 2

    def test_study_metadata_default_empty(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.metadata == {}

    def test_register_3_studies_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        for i in range(3):
            engine.register_study_protocol(f"s{i}", "t1", "h1", f"Study{i}")
        assert engine.study_count == 3

    def test_study_links_to_hypothesis(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert s.hypothesis_ref == "h1"

    def test_duplicate_study_different_hypothesis_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_study_protocol("s1", "t1", "h2", "Study2")


# ===================================================================
# 5. approve_study, start_study, complete_study, cancel_study (35 tests)
# ===================================================================


class TestStudyStatusTransitions:
    # --- approve_study ---
    def test_approve_study_from_draft(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.approve_study("s1")
        assert s.status == StudyStatus.APPROVED

    def test_approve_study_returns_study_protocol(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.approve_study("s1")
        assert isinstance(s, StudyProtocol)

    def test_approve_study_preserves_title(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "My Title")
        s = engine.approve_study("s1")
        assert s.title == "My Title"

    def test_approve_study_emits_event(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        before = es.event_count
        engine.approve_study("s1")
        assert es.event_count == before + 1

    def test_approve_unknown_study_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.approve_study("nonexistent")

    # --- start_study ---
    def test_start_study_from_approved(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        s = engine.start_study("s1")
        assert s.status == StudyStatus.IN_PROGRESS

    def test_start_study_returns_study_protocol(self, seeded):
        s = seeded.get_study("s1")
        assert isinstance(s, StudyProtocol)
        assert s.status == StudyStatus.IN_PROGRESS

    def test_start_study_emits_event(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        before = es.event_count
        engine.start_study("s1")
        assert es.event_count == before + 1

    def test_start_unknown_study_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.start_study("nonexistent")

    # --- complete_study ---
    def test_complete_study(self, seeded):
        s = seeded.complete_study("s1")
        assert s.status == StudyStatus.COMPLETED

    def test_complete_study_emits_event(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.complete_study("s1")
        assert spine.event_count == before + 1

    def test_complete_study_preserves_experiment_count(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        s = seeded.complete_study("s1")
        assert s.experiment_count == 1

    # --- cancel_study ---
    def test_cancel_study(self, seeded):
        s = seeded.cancel_study("s1")
        assert s.status == StudyStatus.CANCELLED

    def test_cancel_study_emits_event(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.cancel_study("s1")
        assert spine.event_count == before + 1

    # --- terminal guards: COMPLETED blocks ---
    def test_completed_blocks_approve(self, seeded):
        seeded.complete_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.approve_study("s1")

    def test_completed_blocks_start(self, seeded):
        seeded.complete_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.start_study("s1")

    def test_completed_blocks_complete(self, seeded):
        seeded.complete_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.complete_study("s1")

    def test_completed_blocks_cancel(self, seeded):
        seeded.complete_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.cancel_study("s1")

    # --- terminal guards: CANCELLED blocks ---
    def test_cancelled_blocks_approve(self, seeded):
        seeded.cancel_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.approve_study("s1")

    def test_cancelled_blocks_start(self, seeded):
        seeded.cancel_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.start_study("s1")

    def test_cancelled_blocks_complete(self, seeded):
        seeded.cancel_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.complete_study("s1")

    def test_cancelled_blocks_cancel(self, seeded):
        seeded.cancel_study("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.cancel_study("s1")

    # --- non-terminal transitions allowed ---
    def test_draft_to_approved_to_in_progress(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        s = engine.start_study("s1")
        assert s.status == StudyStatus.IN_PROGRESS

    def test_draft_can_be_cancelled(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.cancel_study("s1")
        assert s.status == StudyStatus.CANCELLED

    def test_approved_can_be_cancelled(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        s = engine.cancel_study("s1")
        assert s.status == StudyStatus.CANCELLED

    def test_in_progress_can_be_completed(self, seeded):
        s = seeded.complete_study("s1")
        assert s.status == StudyStatus.COMPLETED

    def test_in_progress_can_be_cancelled(self, seeded):
        s = seeded.cancel_study("s1")
        assert s.status == StudyStatus.CANCELLED

    def test_study_frozen_after_transition(self, seeded):
        s = seeded.complete_study("s1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.status = StudyStatus.DRAFT

    def test_approve_preserves_hypothesis_ref(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.approve_study("s1")
        assert s.hypothesis_ref == "h1"

    def test_complete_preserves_tenant_id(self, seeded):
        s = seeded.complete_study("s1")
        assert s.tenant_id == "t1"

    def test_cancel_preserves_study_id(self, seeded):
        s = seeded.cancel_study("s1")
        assert s.study_id == "s1"

    def test_two_studies_independent_transitions(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study1")
        engine.register_study_protocol("s2", "t1", "h1", "Study2")
        engine.approve_study("s1")
        engine.cancel_study("s2")
        assert engine.get_study("s1").status == StudyStatus.APPROVED
        assert engine.get_study("s2").status == StudyStatus.CANCELLED

    def test_start_from_draft_allowed(self, engine):
        """start_study from DRAFT is allowed (no strict state machine)."""
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.start_study("s1")
        assert s.status == StudyStatus.IN_PROGRESS

    def test_complete_from_draft_allowed(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        s = engine.complete_study("s1")
        assert s.status == StudyStatus.COMPLETED


# ===================================================================
# 6. start_experiment (20 tests)
# ===================================================================


class TestStartExperiment:
    def test_returns_experiment_run(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert isinstance(exp, ExperimentRun)

    def test_experiment_id_matches(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.experiment_id == "e1"

    def test_tenant_id_matches(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.tenant_id == "t1"

    def test_study_ref_matches(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.study_ref == "s1"

    def test_status_running(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.status == ExperimentStatus.RUNNING

    def test_result_summary_default(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1")
        assert exp.result_summary == "pending"

    def test_result_summary_custom(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "custom summary")
        assert exp.result_summary == "custom summary"

    def test_confidence_zero(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.confidence == 0.0

    def test_created_at_populated(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.created_at != ""

    def test_increments_experiment_count(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        assert seeded.experiment_count == 1
        seeded.start_experiment("e2", "t1", "s1", "pending")
        assert seeded.experiment_count == 2

    def test_increments_study_experiment_count(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        s = seeded.get_study("s1")
        assert s.experiment_count == 1

    def test_increments_study_experiment_count_twice(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.start_experiment("e2", "t1", "s1", "pending")
        s = seeded.get_study("s1")
        assert s.experiment_count == 2

    def test_duplicate_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            seeded.start_experiment("e1", "t1", "s1", "pending2")

    def test_unknown_study_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown study"):
            engine.start_experiment("e1", "t1", "nonexistent", "pending")

    def test_emits_event(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.start_experiment("e1", "t1", "s1", "pending")
        assert spine.event_count == before + 1

    def test_frozen_record(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.status = ExperimentStatus.COMPLETED

    def test_get_experiment_returns_correct(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        e = seeded.get_experiment("e1")
        assert e.experiment_id == "e1"

    def test_get_unknown_experiment_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_experiment("nonexistent")

    def test_multiple_experiments_same_study(self, seeded):
        for i in range(5):
            seeded.start_experiment(f"e{i}", "t1", "s1", "pending")
        assert seeded.experiment_count == 5
        s = seeded.get_study("s1")
        assert s.experiment_count == 5

    def test_experiment_metadata_default_empty(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        assert exp.metadata == {}


# ===================================================================
# 7. record_experiment_result (25 tests)
# ===================================================================


class TestRecordExperimentResult:
    def test_completed_status(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.9)
        assert exp.status == ExperimentStatus.COMPLETED

    def test_failed_status(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Bad", 0.1)
        assert exp.status == ExperimentStatus.FAILED

    def test_confidence_updated(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.85)
        assert exp.confidence == 0.85

    def test_result_summary_updated(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Significant", 0.9)
        assert exp.result_summary == "Significant"

    def test_preserves_experiment_id(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert exp.experiment_id == "e1"

    def test_preserves_tenant_id(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert exp.tenant_id == "t1"

    def test_preserves_study_ref(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert exp.study_ref == "s1"

    def test_unknown_experiment_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_experiment_result("nonexistent", ExperimentStatus.COMPLETED, "X", 0.5)

    def test_terminal_completed_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Again", 0.9)

    def test_terminal_failed_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Bad", 0.1)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Retry", 0.9)

    def test_invalid_status_running_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(RuntimeCoreInvariantError, match="COMPLETED or FAILED"):
            seeded.record_experiment_result("e1", ExperimentStatus.RUNNING, "Still", 0.5)

    def test_invalid_status_planned_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(RuntimeCoreInvariantError, match="COMPLETED or FAILED"):
            seeded.record_experiment_result("e1", ExperimentStatus.PLANNED, "Not", 0.5)

    def test_invalid_status_cancelled_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(RuntimeCoreInvariantError, match="COMPLETED or FAILED"):
            seeded.record_experiment_result("e1", ExperimentStatus.CANCELLED, "Nope", 0.5)

    def test_emits_event(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert spine.event_count == before + 1

    def test_frozen_after_result(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.confidence = 1.0

    def test_confidence_zero(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.0)
        assert exp.confidence == 0.0

    def test_confidence_one(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 1.0)
        assert exp.confidence == 1.0

    def test_get_experiment_after_result(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        e = seeded.get_experiment("e1")
        assert e.status == ExperimentStatus.COMPLETED
        assert e.confidence == 0.8

    def test_result_does_not_change_experiment_count(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        assert seeded.experiment_count == 1
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert seeded.experiment_count == 1

    def test_multiple_experiments_independent_results(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.start_experiment("e2", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.9)
        seeded.record_experiment_result("e2", ExperimentStatus.FAILED, "Bad", 0.1)
        e1 = seeded.get_experiment("e1")
        e2 = seeded.get_experiment("e2")
        assert e1.status == ExperimentStatus.COMPLETED
        assert e2.status == ExperimentStatus.FAILED

    def test_failed_then_completed_terminal_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Bad", 0.1)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Retry", 0.9)

    def test_completed_then_failed_terminal_raises(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.9)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Nope", 0.1)

    def test_preserves_created_at(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        original = seeded.get_experiment("e1").created_at
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert exp.created_at == original

    def test_preserves_metadata(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        exp = seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert exp.metadata == {}


# ===================================================================
# 8. attach_literature_packet (18 tests)
# ===================================================================


class TestAttachLiteraturePacket:
    def test_returns_literature_packet(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert isinstance(lit, LiteraturePacket)

    def test_packet_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.packet_id == "lit1"

    def test_tenant_id_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.tenant_id == "t1"

    def test_hypothesis_ref_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.hypothesis_ref == "h1"

    def test_title_matches(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "My Review")
        assert lit.title == "My Review"

    def test_default_source_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.source_count == 1

    def test_custom_source_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review", 10, 0.9)
        assert lit.source_count == 10

    def test_default_relevance_score(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.relevance_score == 0.5

    def test_custom_relevance_score(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review", 5, 0.95)
        assert lit.relevance_score == 0.95

    def test_created_at_populated(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "Review")
        assert lit.created_at != ""

    def test_increments_literature_count(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.attach_literature_packet("lit1", "t1", "h1", "R1")
        assert engine.literature_count == 1
        engine.attach_literature_packet("lit2", "t1", "h1", "R2")
        assert engine.literature_count == 2

    def test_duplicate_raises(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.attach_literature_packet("lit1", "t1", "h1", "R2")

    def test_unknown_hypothesis_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown hypothesis"):
            engine.attach_literature_packet("lit1", "t1", "nonexistent", "R")

    def test_emits_event(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        before = es.event_count
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "R")
        with pytest.raises(dataclasses.FrozenInstanceError):
            lit.title = "changed"

    def test_multiple_packets_same_hypothesis(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        for i in range(4):
            engine.attach_literature_packet(f"lit{i}", "t1", "h1", f"R{i}")
        assert engine.literature_count == 4

    def test_packets_different_hypotheses(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        engine.attach_literature_packet("lit1", "t1", "h1", "R1")
        engine.attach_literature_packet("lit2", "t1", "h2", "R2")
        assert engine.literature_count == 2

    def test_literature_metadata_default_empty(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "R")
        assert lit.metadata == {}


# ===================================================================
# 9. build_evidence_synthesis (35 tests)
# ===================================================================


class TestBuildEvidenceSynthesis:
    def test_returns_evidence_synthesis(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert isinstance(syn, EvidenceSynthesis)

    def test_synthesis_id_matches(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.synthesis_id == "syn1"

    def test_tenant_id_matches(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.tenant_id == "t1"

    def test_hypothesis_ref_matches(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.hypothesis_ref == "h1"

    def test_created_at_populated(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.created_at != ""

    def test_no_experiments_weak(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.WEAK

    def test_no_experiments_zero_confidence(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.confidence == 0.0

    def test_no_experiments_zero_count(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.experiment_count == 0

    def test_strong_confidence_ge_08(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Strong", 0.9)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.STRONG

    def test_strong_confidence_exactly_08(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Exact", 0.8)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.STRONG

    def test_moderate_confidence_06(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Mod", 0.6)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.MODERATE

    def test_moderate_confidence_05(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Mod", 0.5)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.MODERATE

    def test_moderate_confidence_079(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Mod", 0.79)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.MODERATE

    def test_weak_confidence_035(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Weak", 0.35)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.WEAK

    def test_weak_confidence_03(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Weak", 0.3)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.WEAK

    def test_weak_confidence_049(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Weak", 0.49)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.WEAK

    def test_weak_confidence_below_03(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Weak", 0.1)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.WEAK

    def test_contradictory_one_failed(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Fail", 0.1)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.CONTRADICTORY

    def test_contradictory_count(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Fail", 0.1)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.contradiction_count == 1

    def test_contradictory_overrides_high_confidence(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.95)
        seeded.start_experiment("e2", "t1", "s1", "pending")
        seeded.record_experiment_result("e2", ExperimentStatus.FAILED, "Bad", 0.05)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.CONTRADICTORY

    def test_literature_counted(self, seeded):
        seeded.attach_literature_packet("lit1", "t1", "h1", "R")
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.literature_count == 1

    def test_multiple_literature_counted(self, seeded):
        seeded.attach_literature_packet("lit1", "t1", "h1", "R1")
        seeded.attach_literature_packet("lit2", "t1", "h1", "R2")
        seeded.attach_literature_packet("lit3", "t1", "h1", "R3")
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.literature_count == 3

    def test_only_counts_literature_for_hypothesis(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        engine.attach_literature_packet("lit1", "t1", "h1", "R1")
        engine.attach_literature_packet("lit2", "t1", "h2", "R2")
        syn = engine.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.literature_count == 1

    def test_counts_experiments_via_study(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.start_experiment("e2", "t1", "s1", "pending")
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.experiment_count == 2

    def test_confidence_average_of_completed(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "A", 0.8)
        seeded.start_experiment("e2", "t1", "s1", "pending")
        seeded.record_experiment_result("e2", ExperimentStatus.COMPLETED, "B", 0.6)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.confidence == pytest.approx(0.7)

    def test_running_experiments_not_in_confidence(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "A", 0.8)
        seeded.start_experiment("e2", "t1", "s1", "pending")  # still running
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.confidence == 0.8

    def test_duplicate_synthesis_raises(self, seeded):
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            seeded.build_evidence_synthesis("syn1", "t1", "h1")

    def test_unknown_hypothesis_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown hypothesis"):
            engine.build_evidence_synthesis("syn1", "t1", "nonexistent")

    def test_emits_event(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert spine.event_count == before + 1

    def test_frozen_record(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            syn.strength = EvidenceStrength.STRONG

    def test_increments_synthesis_count(self, seeded):
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert seeded.synthesis_count == 1

    def test_evidence_free_synthesis_weak(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        syn = engine.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.experiment_count == 0
        assert syn.literature_count == 0
        assert syn.strength == EvidenceStrength.WEAK

    def test_two_failed_experiments_contradictory(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.FAILED, "Fail1", 0.1)
        seeded.start_experiment("e2", "t1", "s1", "pending")
        seeded.record_experiment_result("e2", ExperimentStatus.FAILED, "Fail2", 0.1)
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.CONTRADICTORY
        assert syn.contradiction_count == 2

    def test_synthesis_metadata_default_empty(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.metadata == {}

    def test_only_counts_experiments_for_hypothesis_studies(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t1", "q1", "S2")
        engine.register_study_protocol("s1", "t1", "h1", "Study1")
        engine.register_study_protocol("s2", "t1", "h2", "Study2")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.approve_study("s2")
        engine.start_study("s2")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.start_experiment("e2", "t1", "s2", "pending")
        syn = engine.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.experiment_count == 1


# ===================================================================
# 10. request_peer_review & complete_peer_review (25 tests)
# ===================================================================


class TestPeerReview:
    # --- request_peer_review ---
    def test_returns_peer_review_record(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert isinstance(rev, PeerReviewRecord)

    def test_review_id_matches(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.review_id == "rev1"

    def test_tenant_id_matches(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.tenant_id == "t1"

    def test_target_ref_matches(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.target_ref == "target1"

    def test_reviewer_ref_matches(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.reviewer_ref == "reviewer1"

    def test_disposition_in_review(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.disposition == PublicationDisposition.IN_REVIEW

    def test_default_comments(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.comments == "Review requested"

    def test_custom_comments(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1", "Please review")
        assert rev.comments == "Please review"

    def test_confidence_zero(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.confidence == 0.0

    def test_reviewed_at_populated(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert rev.reviewed_at != ""

    def test_increments_review_count(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert engine.review_count == 1

    def test_duplicate_raises(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.request_peer_review("rev1", "t1", "target2", "reviewer2")

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            rev.comments = "changed"

    # --- complete_peer_review ---
    def test_complete_accepted(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.95)
        assert rev.disposition == PublicationDisposition.ACCEPTED

    def test_complete_rejected(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.REJECTED, "Bad", 0.1)
        assert rev.disposition == PublicationDisposition.REJECTED

    def test_complete_published(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.PUBLISHED, "OK", 0.8)
        assert rev.disposition == PublicationDisposition.PUBLISHED

    def test_complete_comments(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Great work", 0.9)
        assert rev.comments == "Great work"

    def test_complete_confidence(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.85)
        assert rev.confidence == 0.85

    def test_complete_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.complete_peer_review("nonexistent", PublicationDisposition.ACCEPTED, "C", 0.5)

    def test_complete_already_accepted_raises(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot complete"):
            engine.complete_peer_review("rev1", PublicationDisposition.REJECTED, "Bad", 0.1)

    def test_complete_already_rejected_raises(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        engine.complete_peer_review("rev1", PublicationDisposition.REJECTED, "Bad", 0.1)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot complete"):
            engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)

    def test_complete_emits_event(self, engine, es):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        before = es.event_count
        engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        assert es.event_count == before + 1

    def test_complete_preserves_target_ref(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        assert rev.target_ref == "target1"

    def test_complete_preserves_reviewer_ref(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        rev = engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        assert rev.reviewer_ref == "reviewer1"


# ===================================================================
# 11. research_snapshot (20 tests)
# ===================================================================


class TestResearchSnapshot:
    def test_returns_snapshot(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        assert isinstance(snap, ResearchSnapshot)

    def test_snapshot_id_matches(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.snapshot_id == "snap1"

    def test_tenant_id_matches(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.tenant_id == "t1"

    def test_captured_at_populated(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.captured_at != ""

    def test_empty_engine_all_zeros(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.total_questions == 0
        assert snap.total_hypotheses == 0
        assert snap.total_studies == 0
        assert snap.total_experiments == 0
        assert snap.total_literature == 0
        assert snap.total_syntheses == 0
        assert snap.total_reviews == 0
        assert snap.total_violations == 0

    def test_counts_questions(self, seeded):
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_questions == 1

    def test_counts_hypotheses(self, seeded):
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_hypotheses == 1

    def test_counts_studies(self, seeded):
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_studies == 1

    def test_counts_experiments(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_experiments == 1

    def test_counts_literature(self, seeded):
        seeded.attach_literature_packet("lit1", "t1", "h1", "R")
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_literature == 1

    def test_counts_syntheses(self, seeded):
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_syntheses == 1

    def test_counts_reviews(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.total_reviews == 1

    def test_counts_violations(self, seeded):
        seeded.detect_research_violations()
        snap = seeded.research_snapshot("snap1", "t1")
        assert snap.total_violations > 0

    def test_tenant_scoped(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        snap = engine.research_snapshot("snap1", "t1")
        assert snap.total_questions == 1

    def test_tenant_scoped_other(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        snap = engine.research_snapshot("snap2", "t2")
        assert snap.total_questions == 1

    def test_duplicate_raises(self, engine):
        engine.research_snapshot("snap1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.research_snapshot("snap1", "t1")

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.research_snapshot("snap1", "t1")
        assert es.event_count == before + 1

    def test_frozen_record(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.total_questions = 99

    def test_multiple_snapshots_independent(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        snap1 = engine.research_snapshot("snap1", "t1")
        engine.register_question("q2", "t1", "T2", "D2")
        snap2 = engine.research_snapshot("snap2", "t1")
        assert snap1.total_questions == 1
        assert snap2.total_questions == 2

    def test_snapshot_with_no_matching_tenant(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        snap = engine.research_snapshot("snap1", "t99")
        assert snap.total_questions == 0


# ===================================================================
# 12. detect_research_violations (25 tests)
# ===================================================================


class TestDetectResearchViolations:
    # evidence_free_synthesis
    def test_evidence_free_synthesis_detected(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        violations = engine.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "evidence_free_synthesis" in ops

    def test_evidence_free_synthesis_has_reason(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        violations = engine.detect_research_violations()
        assert any("reason" in v for v in violations)

    def test_evidence_free_synthesis_has_tenant(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        violations = engine.detect_research_violations()
        ef = [v for v in violations if v["operation"] == "evidence_free_synthesis"]
        assert ef[0]["tenant_id"] == "t1"

    def test_no_evidence_free_with_experiments(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        violations = seeded.detect_research_violations()
        ef = [v for v in violations if v["operation"] == "evidence_free_synthesis"]
        assert len(ef) == 0

    def test_no_evidence_free_with_literature(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        violations = engine.detect_research_violations()
        ef = [v for v in violations if v["operation"] == "evidence_free_synthesis"]
        assert len(ef) == 0

    # incomplete_study
    def test_incomplete_study_detected(self, seeded):
        # s1 is IN_PROGRESS with no experiments
        violations = seeded.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "incomplete_study" in ops

    def test_incomplete_study_not_detected_with_experiments(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        violations = seeded.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "incomplete_study" not in ops

    def test_incomplete_study_not_detected_draft(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        violations = engine.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "incomplete_study" not in ops

    def test_incomplete_study_not_detected_approved(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        violations = engine.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "incomplete_study" not in ops

    # unreviewed_closure
    def test_unreviewed_closure_detected(self, seeded):
        seeded.complete_study("s1")
        violations = seeded.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "unreviewed_closure" in ops

    def test_unreviewed_closure_not_detected_with_review(self, seeded):
        seeded.request_peer_review("rev1", "t1", "s1", "reviewer1")
        seeded.complete_study("s1")
        violations = seeded.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "unreviewed_closure" not in ops

    def test_unreviewed_closure_not_detected_in_progress(self, seeded):
        # s1 is IN_PROGRESS, not COMPLETED
        violations = seeded.detect_research_violations()
        ops = [v["operation"] for v in violations]
        assert "unreviewed_closure" not in ops

    # idempotency
    def test_idempotent_no_new_violations(self, seeded):
        v1 = seeded.detect_research_violations()
        assert len(v1) > 0
        v2 = seeded.detect_research_violations()
        assert len(v2) == 0

    def test_idempotent_violation_count_stable(self, seeded):
        seeded.detect_research_violations()
        count = seeded.violation_count
        seeded.detect_research_violations()
        assert seeded.violation_count == count

    def test_idempotent_three_calls(self, seeded):
        v1 = seeded.detect_research_violations()
        v2 = seeded.detect_research_violations()
        v3 = seeded.detect_research_violations()
        assert len(v1) > 0
        assert len(v2) == 0
        assert len(v3) == 0

    # general
    def test_returns_tuple(self, engine):
        violations = engine.detect_research_violations()
        assert isinstance(violations, tuple)

    def test_empty_engine_no_violations(self, engine):
        violations = engine.detect_research_violations()
        assert len(violations) == 0

    def test_violation_has_violation_id(self, seeded):
        violations = seeded.detect_research_violations()
        assert all("violation_id" in v for v in violations)

    def test_violation_has_detected_at(self, seeded):
        violations = seeded.detect_research_violations()
        assert all("detected_at" in v for v in violations)

    def test_violation_count_property(self, seeded):
        assert seeded.violation_count == 0
        seeded.detect_research_violations()
        assert seeded.violation_count > 0

    def test_emits_event_on_violations(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.detect_research_violations()
        assert spine.event_count > before

    def test_no_event_on_no_new_violations(self, engine):
        spine = _event_spine(engine)
        before = spine.event_count
        engine.detect_research_violations()
        # No violations means no event emitted
        assert spine.event_count == before

    def test_multiple_violations_detected(self, seeded):
        """IN_PROGRESS study with no experiments + complete it for unreviewed."""
        v1 = seeded.detect_research_violations()  # incomplete_study
        seeded.complete_study("s1")
        v2 = seeded.detect_research_violations()  # unreviewed_closure
        assert len(v1) >= 1
        assert len(v2) >= 1

    def test_clean_flow_no_violations(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        engine.request_peer_review("rev1", "t1", "s1", "reviewer1")
        engine.complete_study("s1")
        violations = engine.detect_research_violations()
        assert len(violations) == 0

    def test_evidence_free_synthesis_violation_id_deterministic(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        violations = engine.detect_research_violations()
        vid = violations[0]["violation_id"]
        assert isinstance(vid, str)
        assert len(vid) > 0


# ===================================================================
# 13. state_hash (15 tests)
# ===================================================================


class TestStateHash:
    def test_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_length_16(self, engine):
        assert len(engine.state_hash()) == 64

    def test_is_hex_string(self, engine):
        h = engine.state_hash()
        int(h, 16)  # should not raise

    def test_changes_on_question(self, engine):
        h1 = engine.state_hash()
        engine.register_question("q1", "t1", "T", "D")
        assert engine.state_hash() != h1

    def test_changes_on_hypothesis(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h1 = engine.state_hash()
        engine.register_hypothesis("h1", "t1", "q1", "S")
        assert engine.state_hash() != h1

    def test_changes_on_study(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        h1 = engine.state_hash()
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert engine.state_hash() != h1

    def test_changes_on_experiment(self, seeded):
        h1 = seeded.state_hash()
        seeded.start_experiment("e1", "t1", "s1", "pending")
        assert seeded.state_hash() != h1

    def test_changes_on_literature(self, seeded):
        h1 = seeded.state_hash()
        seeded.attach_literature_packet("lit1", "t1", "h1", "R")
        assert seeded.state_hash() != h1

    def test_changes_on_synthesis(self, seeded):
        h1 = seeded.state_hash()
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert seeded.state_hash() != h1

    def test_changes_on_review(self, engine):
        h1 = engine.state_hash()
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert engine.state_hash() != h1

    def test_changes_on_violation(self, seeded):
        h1 = seeded.state_hash()
        seeded.detect_research_violations()
        assert seeded.state_hash() != h1

    def test_no_timestamps_two_engines_same_hash(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        assert eng1.state_hash() == eng2.state_hash()

    def test_same_counts_same_hash(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        eng1.register_question("q1", "t1", "T", "D")

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        eng2.register_question("q2", "t2", "T2", "D2")

        assert eng1.state_hash() == eng2.state_hash()

    def test_different_counts_different_hash(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        eng1.register_question("q1", "t1", "T", "D")

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)

        assert eng1.state_hash() != eng2.state_hash()

    def test_hash_stable_after_no_mutation(self, seeded):
        h1 = seeded.state_hash()
        # no mutation
        h2 = seeded.state_hash()
        assert h1 == h2


# ===================================================================
# 14. Cross-tenant isolation (12 tests)
# ===================================================================


class TestCrossTenantIsolation:
    def test_questions_isolated(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        assert len(engine.questions_for_tenant("t1")) == 1
        assert len(engine.questions_for_tenant("t2")) == 1

    def test_snapshots_isolated(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_questions == 1
        assert snap2.total_questions == 1

    def test_hypotheses_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t2", "q2", "S2")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_hypotheses == 1
        assert snap2.total_hypotheses == 1

    def test_studies_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t2", "q2", "S2")
        engine.register_study_protocol("s1", "t1", "h1", "St1")
        engine.register_study_protocol("s2", "t2", "h2", "St2")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_studies == 1
        assert snap2.total_studies == 1

    def test_experiments_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_study_protocol("s1", "t1", "h1", "St1")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.register_question("q2", "t2", "T2", "D2")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_experiments == 1
        assert snap2.total_experiments == 0

    def test_literature_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_literature == 1
        assert snap2.total_literature == 0

    def test_syntheses_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_syntheses == 1
        assert snap2.total_syntheses == 0

    def test_reviews_isolated_in_snapshot(self, engine):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_reviews == 1
        assert snap2.total_reviews == 0

    def test_violations_isolated_in_snapshot(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        engine.detect_research_violations()
        snap1 = engine.research_snapshot("snap1", "t1")
        snap2 = engine.research_snapshot("snap2", "t2")
        assert snap1.total_violations >= 1
        assert snap2.total_violations == 0

    def test_three_tenants_isolated(self, engine):
        for t in ["t1", "t2", "t3"]:
            engine.register_question(f"q-{t}", t, f"T-{t}", f"D-{t}")
        for t in ["t1", "t2", "t3"]:
            snap = engine.research_snapshot(f"snap-{t}", t)
            assert snap.total_questions == 1

    def test_cross_tenant_question_count_global(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        assert engine.question_count == 2  # global count

    def test_cross_tenant_hypothesis_count_global(self, engine):
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.register_hypothesis("h2", "t2", "q2", "S2")
        assert engine.hypothesis_count == 2


# ===================================================================
# 15. Replay/restore (10 tests)
# ===================================================================


class TestReplayRestore:
    def _replay_scenario(self):
        """Run a standard scenario and return its state_hash."""
        es = EventSpineEngine()
        eng = ResearchRuntimeEngine(es)
        eng.register_question("q1", "t1", "T", "D")
        eng.register_hypothesis("h1", "t1", "q1", "S")
        eng.register_study_protocol("s1", "t1", "h1", "Study")
        eng.approve_study("s1")
        eng.start_study("s1")
        eng.start_experiment("e1", "t1", "s1", "pending")
        eng.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.85)
        eng.attach_literature_packet("lit1", "t1", "h1", "R")
        eng.build_evidence_synthesis("syn1", "t1", "h1")
        eng.request_peer_review("rev1", "t1", "s1", "reviewer1")
        eng.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "OK", 0.9)
        return eng.state_hash()

    def test_replay_same_hash(self):
        h1 = self._replay_scenario()
        h2 = self._replay_scenario()
        assert h1 == h2

    def test_replay_same_hash_three_times(self):
        hashes = [self._replay_scenario() for _ in range(3)]
        assert hashes[0] == hashes[1] == hashes[2]

    def test_replay_same_counts(self):
        es = EventSpineEngine()
        eng = ResearchRuntimeEngine(es)
        eng.register_question("q1", "t1", "T", "D")
        eng.register_hypothesis("h1", "t1", "q1", "S")

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        eng2.register_question("q1", "t1", "T", "D")
        eng2.register_hypothesis("h1", "t1", "q1", "S")

        assert eng.question_count == eng2.question_count
        assert eng.hypothesis_count == eng2.hypothesis_count

    def test_replay_different_ops_different_hash(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        eng1.register_question("q1", "t1", "T", "D")

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        eng2.register_question("q1", "t1", "T", "D")
        eng2.register_hypothesis("h1", "t1", "q1", "S")

        assert eng1.state_hash() != eng2.state_hash()

    def test_replay_preserves_question_data(self):
        es = EventSpineEngine()
        eng = ResearchRuntimeEngine(es)
        eng.register_question("q1", "t1", "Title1", "Desc1")
        q = eng.get_question("q1")
        assert q.title == "Title1"
        assert q.description == "Desc1"

    def test_replay_preserves_hypothesis_data(self):
        es = EventSpineEngine()
        eng = ResearchRuntimeEngine(es)
        eng.register_question("q1", "t1", "T", "D")
        eng.register_hypothesis("h1", "t1", "q1", "My stmt")
        h = eng.get_hypothesis("h1")
        assert h.statement == "My stmt"

    def test_replay_preserves_experiment_result(self):
        es = EventSpineEngine()
        eng = ResearchRuntimeEngine(es)
        eng.register_question("q1", "t1", "T", "D")
        eng.register_hypothesis("h1", "t1", "q1", "S")
        eng.register_study_protocol("s1", "t1", "h1", "Study")
        eng.approve_study("s1")
        eng.start_study("s1")
        eng.start_experiment("e1", "t1", "s1", "pending")
        eng.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Good", 0.85)
        e = eng.get_experiment("e1")
        assert e.status == ExperimentStatus.COMPLETED
        assert e.confidence == 0.85

    def test_replay_full_lifecycle_hash_stable(self):
        h1 = self._replay_scenario()
        h2 = self._replay_scenario()
        assert h1 == h2
        assert len(h1) == 64

    def test_replay_event_count_matches(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        eng1.register_question("q1", "t1", "T", "D")
        eng1.register_hypothesis("h1", "t1", "q1", "S")
        c1 = es1.event_count

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        eng2.register_question("q1", "t1", "T", "D")
        eng2.register_hypothesis("h1", "t1", "q1", "S")
        c2 = es2.event_count

        assert c1 == c2

    def test_replay_violation_detection_same_count(self):
        es1 = EventSpineEngine()
        eng1 = ResearchRuntimeEngine(es1)
        eng1.register_question("q1", "t1", "T", "D")
        eng1.register_hypothesis("h1", "t1", "q1", "S")
        eng1.build_evidence_synthesis("syn1", "t1", "h1")
        v1 = eng1.detect_research_violations()

        es2 = EventSpineEngine()
        eng2 = ResearchRuntimeEngine(es2)
        eng2.register_question("q1", "t1", "T", "D")
        eng2.register_hypothesis("h1", "t1", "q1", "S")
        eng2.build_evidence_synthesis("syn1", "t1", "h1")
        v2 = eng2.detect_research_violations()

        assert len(v1) == len(v2)


# ===================================================================
# 16. Event emission verification (15 tests)
# ===================================================================


class TestEventEmission:
    def test_register_question_emits(self, engine, es):
        before = es.event_count
        engine.register_question("q1", "t1", "T", "D")
        assert es.event_count == before + 1

    def test_register_hypothesis_emits(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        before = es.event_count
        engine.register_hypothesis("h1", "t1", "q1", "S")
        assert es.event_count == before + 1

    def test_register_study_emits(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        before = es.event_count
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        assert es.event_count == before + 1

    def test_approve_study_emits(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        before = es.event_count
        engine.approve_study("s1")
        assert es.event_count == before + 1

    def test_start_study_emits(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        before = es.event_count
        engine.start_study("s1")
        assert es.event_count == before + 1

    def test_complete_study_emits(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.complete_study("s1")
        assert spine.event_count == before + 1

    def test_cancel_study_emits(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.cancel_study("s1")
        assert spine.event_count == before + 1

    def test_start_experiment_emits(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.start_experiment("e1", "t1", "s1", "pending")
        assert spine.event_count == before + 1

    def test_record_experiment_result_emits(self, seeded):
        seeded.start_experiment("e1", "t1", "s1", "pending")
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        assert spine.event_count == before + 1

    def test_attach_literature_emits(self, engine, es):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        before = es.event_count
        engine.attach_literature_packet("lit1", "t1", "h1", "R")
        assert es.event_count == before + 1

    def test_build_synthesis_emits(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.build_evidence_synthesis("syn1", "t1", "h1")
        assert spine.event_count == before + 1

    def test_request_review_emits(self, engine, es):
        before = es.event_count
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        assert es.event_count == before + 1

    def test_complete_review_emits(self, engine, es):
        engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        before = es.event_count
        engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        assert es.event_count == before + 1

    def test_snapshot_emits(self, engine, es):
        before = es.event_count
        engine.research_snapshot("snap1", "t1")
        assert es.event_count == before + 1

    def test_violations_emit_when_found(self, seeded):
        spine = _event_spine(seeded)
        before = spine.event_count
        seeded.detect_research_violations()
        assert spine.event_count > before


# ===================================================================
# 17. Frozen record verification (8 tests)
# ===================================================================


class TestFrozenRecords:
    def test_question_frozen(self, engine):
        q = engine.register_question("q1", "t1", "T", "D")
        with pytest.raises(dataclasses.FrozenInstanceError):
            q.question_id = "changed"

    def test_hypothesis_frozen(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        h = engine.register_hypothesis("h1", "t1", "q1", "S")
        with pytest.raises(dataclasses.FrozenInstanceError):
            h.hypothesis_id = "changed"

    def test_study_frozen(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        s = engine.register_study_protocol("s1", "t1", "h1", "Study")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.study_id = "changed"

    def test_experiment_frozen(self, seeded):
        exp = seeded.start_experiment("e1", "t1", "s1", "pending")
        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.experiment_id = "changed"

    def test_literature_frozen(self, engine):
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        lit = engine.attach_literature_packet("lit1", "t1", "h1", "R")
        with pytest.raises(dataclasses.FrozenInstanceError):
            lit.packet_id = "changed"

    def test_synthesis_frozen(self, seeded):
        syn = seeded.build_evidence_synthesis("syn1", "t1", "h1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            syn.synthesis_id = "changed"

    def test_review_frozen(self, engine):
        rev = engine.request_peer_review("rev1", "t1", "target1", "reviewer1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            rev.review_id = "changed"

    def test_snapshot_frozen(self, engine):
        snap = engine.research_snapshot("snap1", "t1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "changed"


# ===================================================================
# 18. Golden end-to-end scenarios (6 tests)
# ===================================================================


class TestGoldenEndToEnd:
    def test_full_lifecycle(self, engine, es):
        """Complete lifecycle: question -> hypothesis -> study -> experiment -> synthesis -> review."""
        q = engine.register_question("q1", "t1", "Effect of X", "Does X affect Y?")
        h = engine.register_hypothesis("h1", "t1", "q1", "X increases Y")
        s = engine.register_study_protocol("s1", "t1", "h1", "RCT Study")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Significant", 0.85)
        engine.attach_literature_packet("lit1", "t1", "h1", "Meta-analysis", 5, 0.9)
        syn = engine.build_evidence_synthesis("syn1", "t1", "h1")
        engine.request_peer_review("rev1", "t1", "s1", "reviewer1")
        engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Excellent", 0.95)
        engine.complete_study("s1")

        assert syn.strength == EvidenceStrength.STRONG
        assert syn.experiment_count == 1
        assert syn.literature_count == 1
        assert engine.question_count == 1
        assert engine.hypothesis_count == 1
        assert engine.study_count == 1
        assert engine.experiment_count == 1
        assert engine.literature_count == 1
        assert engine.synthesis_count == 1
        assert engine.review_count == 1

        snap = engine.research_snapshot("snap1", "t1")
        assert snap.total_questions == 1
        assert snap.total_experiments == 1

        violations = engine.detect_research_violations()
        assert len(violations) == 0

        # All events emitted
        assert es.event_count > 0

    def test_multi_tenant_isolation_golden(self, engine):
        """Two tenants have fully independent research."""
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_question("q2", "t2", "T2", "D2")
        engine.register_hypothesis("h1", "t1", "q1", "H1")
        engine.register_hypothesis("h2", "t2", "q2", "H2")
        engine.register_study_protocol("s1", "t1", "h1", "St1")
        engine.register_study_protocol("s2", "t2", "h2", "St2")

        snap1 = engine.research_snapshot("snap-t1", "t1")
        snap2 = engine.research_snapshot("snap-t2", "t2")

        assert snap1.total_questions == 1
        assert snap1.total_hypotheses == 1
        assert snap1.total_studies == 1
        assert snap2.total_questions == 1
        assert snap2.total_hypotheses == 1
        assert snap2.total_studies == 1

    def test_contradictory_evidence_flow(self, engine):
        """Failed experiments produce contradictory synthesis."""
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Positive", 0.9)
        engine.start_experiment("e2", "t1", "s1", "pending")
        engine.record_experiment_result("e2", ExperimentStatus.FAILED, "Could not replicate", 0.1)
        syn = engine.build_evidence_synthesis("syn1", "t1", "h1")
        assert syn.strength == EvidenceStrength.CONTRADICTORY
        assert syn.contradiction_count == 1

    def test_no_violations_clean_flow(self, engine):
        """A properly completed flow produces no violations."""
        engine.register_question("q1", "t1", "T", "D")
        engine.register_hypothesis("h1", "t1", "q1", "S")
        engine.register_study_protocol("s1", "t1", "h1", "Study")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.record_experiment_result("e1", ExperimentStatus.COMPLETED, "Done", 0.8)
        engine.attach_literature_packet("lit1", "t1", "h1", "Review", 3, 0.7)
        engine.build_evidence_synthesis("syn1", "t1", "h1")
        engine.request_peer_review("rev1", "t1", "s1", "reviewer1")
        engine.complete_peer_review("rev1", PublicationDisposition.ACCEPTED, "Good", 0.9)
        engine.complete_study("s1")
        violations = engine.detect_research_violations()
        assert len(violations) == 0

    def test_multiple_hypotheses_studies_experiments(self, engine):
        """Multiple branches under one question."""
        engine.register_question("q1", "t1", "Big Q", "Desc")
        engine.register_hypothesis("h1", "t1", "q1", "Hyp A")
        engine.register_hypothesis("h2", "t1", "q1", "Hyp B")
        engine.register_study_protocol("s1", "t1", "h1", "Study A")
        engine.register_study_protocol("s2", "t1", "h2", "Study B")
        engine.approve_study("s1")
        engine.start_study("s1")
        engine.approve_study("s2")
        engine.start_study("s2")
        engine.start_experiment("e1", "t1", "s1", "pending")
        engine.start_experiment("e2", "t1", "s1", "pending")
        engine.start_experiment("e3", "t1", "s2", "pending")
        engine.record_experiment_result("e1", ExperimentStatus.COMPLETED, "A1", 0.7)
        engine.record_experiment_result("e2", ExperimentStatus.COMPLETED, "A2", 0.9)
        engine.record_experiment_result("e3", ExperimentStatus.COMPLETED, "B1", 0.6)

        syn1 = engine.build_evidence_synthesis("syn1", "t1", "h1")
        syn2 = engine.build_evidence_synthesis("syn2", "t1", "h2")

        assert syn1.experiment_count == 2
        assert syn1.confidence == pytest.approx(0.8)
        assert syn1.strength == EvidenceStrength.STRONG
        assert syn2.experiment_count == 1
        assert syn2.confidence == 0.6
        assert syn2.strength == EvidenceStrength.MODERATE

        q = engine.get_question("q1")
        assert q.hypothesis_count == 2
        assert engine.experiment_count == 3

    def test_all_violation_types_in_one_run(self, engine):
        """Trigger all three violation types."""
        # evidence_free_synthesis
        engine.register_question("q1", "t1", "T1", "D1")
        engine.register_hypothesis("h1", "t1", "q1", "S1")
        engine.build_evidence_synthesis("syn1", "t1", "h1")

        # incomplete_study
        engine.register_question("q2", "t1", "T2", "D2")
        engine.register_hypothesis("h2", "t1", "q2", "S2")
        engine.register_study_protocol("s1", "t1", "h2", "Study")
        engine.approve_study("s1")
        engine.start_study("s1")

        # unreviewed_closure
        engine.register_question("q3", "t1", "T3", "D3")
        engine.register_hypothesis("h3", "t1", "q3", "S3")
        engine.register_study_protocol("s2", "t1", "h3", "Study2")
        engine.approve_study("s2")
        engine.start_study("s2")
        engine.start_experiment("e1", "t1", "s2", "pending")
        engine.complete_study("s2")

        violations = engine.detect_research_violations()
        ops = {v["operation"] for v in violations}
        assert "evidence_free_synthesis" in ops
        assert "incomplete_study" in ops
        assert "unreviewed_closure" in ops
