"""Comprehensive tests for research runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, and to_dict() serialization.
"""

from __future__ import annotations

import dataclasses
import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.research_runtime import *


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================


def _make_hypothesis(**overrides):
    base = dict(
        hypothesis_id="h-1", tenant_id="t-1", question_ref="q-1",
        statement="Plants grow faster with light",
        status=HypothesisStatus.PROPOSED, confidence=0.5,
        evidence_count=3, created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_question(**overrides):
    base = dict(
        question_id="q-1", tenant_id="t-1",
        title="Growth factors", description="What factors affect growth?",
        status=ResearchStatus.DRAFT, hypothesis_count=2,
        created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_study(**overrides):
    base = dict(
        study_id="s-1", tenant_id="t-1",
        title="Light study", hypothesis_ref="h-1",
        status=StudyStatus.DRAFT, experiment_count=5,
        created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_experiment(**overrides):
    base = dict(
        experiment_id="e-1", tenant_id="t-1", study_ref="s-1",
        status=ExperimentStatus.PLANNED,
        result_summary="Positive correlation observed",
        confidence=0.8, created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_literature(**overrides):
    base = dict(
        packet_id="lit-1", tenant_id="t-1", hypothesis_ref="h-1",
        title="Related work survey", source_count=12,
        relevance_score=0.75, created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_synthesis(**overrides):
    base = dict(
        synthesis_id="syn-1", tenant_id="t-1", hypothesis_ref="h-1",
        strength=EvidenceStrength.MODERATE,
        experiment_count=4, literature_count=8,
        contradiction_count=1, confidence=0.7,
        created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_review(**overrides):
    base = dict(
        review_id="rev-1", tenant_id="t-1",
        target_ref="syn-1", reviewer_ref="reviewer-1",
        disposition=PublicationDisposition.IN_REVIEW,
        comments="Needs more evidence",
        confidence=0.6, reviewed_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_assessment(**overrides):
    base = dict(
        assessment_id="assess-1", tenant_id="t-1",
        total_questions=10, total_hypotheses=20,
        total_experiments=15, total_syntheses=5,
        total_reviews=8, completion_rate=0.65,
        assessed_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_snapshot(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_questions=10, total_hypotheses=20,
        total_studies=8, total_experiments=15,
        total_literature=30, total_syntheses=5,
        total_reviews=8, total_violations=2,
        captured_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _make_closure(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_questions=10, total_hypotheses=20,
        total_studies=8, total_experiments=15,
        total_syntheses=5, total_reviews=8,
        total_violations=2, created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


# ===================================================================
# 1. Enum membership tests
# ===================================================================


class TestResearchStatusEnum:
    def test_members(self):
        assert set(ResearchStatus) == {
            ResearchStatus.DRAFT, ResearchStatus.ACTIVE,
            ResearchStatus.COMPLETED, ResearchStatus.ARCHIVED,
            ResearchStatus.CANCELLED,
        }

    @pytest.mark.parametrize("member", list(ResearchStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(ResearchStatus) == 5


class TestHypothesisStatusEnum:
    def test_members(self):
        assert set(HypothesisStatus) == {
            HypothesisStatus.PROPOSED, HypothesisStatus.UNDER_TEST,
            HypothesisStatus.SUPPORTED, HypothesisStatus.REFUTED,
            HypothesisStatus.INCONCLUSIVE,
        }

    @pytest.mark.parametrize("member", list(HypothesisStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(HypothesisStatus) == 5


class TestStudyStatusEnum:
    def test_members(self):
        assert set(StudyStatus) == {
            StudyStatus.DRAFT, StudyStatus.APPROVED,
            StudyStatus.IN_PROGRESS, StudyStatus.COMPLETED,
            StudyStatus.CANCELLED,
        }

    @pytest.mark.parametrize("member", list(StudyStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(StudyStatus) == 5


class TestExperimentStatusEnum:
    def test_members(self):
        assert set(ExperimentStatus) == {
            ExperimentStatus.PLANNED, ExperimentStatus.RUNNING,
            ExperimentStatus.COMPLETED, ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
        }

    @pytest.mark.parametrize("member", list(ExperimentStatus))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(ExperimentStatus) == 5


class TestEvidenceStrengthEnum:
    def test_members(self):
        assert set(EvidenceStrength) == {
            EvidenceStrength.STRONG, EvidenceStrength.MODERATE,
            EvidenceStrength.WEAK, EvidenceStrength.CONTRADICTORY,
        }

    @pytest.mark.parametrize("member", list(EvidenceStrength))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(EvidenceStrength) == 4


class TestPublicationDispositionEnum:
    def test_members(self):
        assert set(PublicationDisposition) == {
            PublicationDisposition.DRAFT,
            PublicationDisposition.IN_REVIEW,
            PublicationDisposition.ACCEPTED,
            PublicationDisposition.PUBLISHED,
            PublicationDisposition.REJECTED,
            PublicationDisposition.RETRACTED,
        }

    @pytest.mark.parametrize("member", list(PublicationDisposition))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(PublicationDisposition) == 6


# ===================================================================
# 2. HypothesisRecord
# ===================================================================


class TestHypothesisRecord:
    def test_valid_construction(self):
        rec = HypothesisRecord(**_make_hypothesis())
        assert rec.hypothesis_id == "h-1"
        assert rec.tenant_id == "t-1"
        assert rec.question_ref == "q-1"
        assert rec.statement == "Plants grow faster with light"
        assert rec.status is HypothesisStatus.PROPOSED
        assert rec.confidence == 0.5
        assert rec.evidence_count == 3

    @pytest.mark.parametrize("member", list(HypothesisStatus))
    def test_all_status_members(self, member):
        rec = HypothesisRecord(**_make_hypothesis(status=member))
        assert rec.status is member

    def test_status_rejects_string(self):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(status="proposed"))

    def test_status_rejects_int(self):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(status=0))

    @pytest.mark.parametrize("field_name", [
        "hypothesis_id", "tenant_id", "question_ref", "statement",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "hypothesis_id", "tenant_id", "question_ref", "statement",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(**{field_name: "   "}))

    @pytest.mark.parametrize("bad_val", [-1, -100])
    def test_evidence_count_negative_rejected(self, bad_val):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(evidence_count=bad_val))

    @pytest.mark.parametrize("bad_val", [True, False])
    def test_evidence_count_bool_rejected(self, bad_val):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(evidence_count=bad_val))

    @pytest.mark.parametrize("bad_val", [1.0, 2.5])
    def test_evidence_count_float_rejected(self, bad_val):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(evidence_count=bad_val))

    @pytest.mark.parametrize("good_val", [0, 1, 100])
    def test_evidence_count_valid(self, good_val):
        rec = HypothesisRecord(**_make_hypothesis(evidence_count=good_val))
        assert rec.evidence_count == good_val

    @pytest.mark.parametrize("bad_val", [-0.1, 1.1, 2.0])
    def test_confidence_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(confidence=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
    def test_confidence_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(confidence=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_confidence_valid_range(self, good_val):
        rec = HypothesisRecord(**_make_hypothesis(confidence=good_val))
        assert rec.confidence == good_val

    def test_confidence_rejects_bool(self):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(confidence=True))

    def test_datetime_valid_iso(self):
        rec = HypothesisRecord(**_make_hypothesis(created_at="2025-06-01T12:30:00Z"))
        assert rec.created_at == "2025-06-01T12:30:00Z"

    def test_datetime_date_only(self):
        rec = HypothesisRecord(**_make_hypothesis(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_empty_rejected(self):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(created_at=""))

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            HypothesisRecord(**_make_hypothesis(created_at="not-a-date"))

    def test_metadata_frozen(self):
        rec = HypothesisRecord(**_make_hypothesis(metadata={"k": "v"}))
        assert isinstance(rec.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            rec.metadata["k2"] = "v2"

    def test_metadata_to_dict_plain(self):
        rec = HypothesisRecord(**_make_hypothesis(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == {"k": "v"}

    def test_frozen_immutability(self):
        rec = HypothesisRecord(**_make_hypothesis())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "hypothesis_id", "x")

    def test_to_dict_preserves_enum(self):
        rec = HypothesisRecord(**_make_hypothesis())
        d = rec.to_dict()
        assert d["status"] is HypothesisStatus.PROPOSED

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(HypothesisRecord)

    def test_metadata_default_empty(self):
        rec = HypothesisRecord(**_make_hypothesis())
        assert rec.metadata == MappingProxyType({})


# ===================================================================
# 3. ResearchQuestion
# ===================================================================


class TestResearchQuestion:
    def test_valid_construction(self):
        rec = ResearchQuestion(**_make_question())
        assert rec.question_id == "q-1"
        assert rec.tenant_id == "t-1"
        assert rec.title == "Growth factors"
        assert rec.status is ResearchStatus.DRAFT
        assert rec.hypothesis_count == 2

    @pytest.mark.parametrize("member", list(ResearchStatus))
    def test_all_status_members(self, member):
        rec = ResearchQuestion(**_make_question(status=member))
        assert rec.status is member

    def test_status_rejects_string(self):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(status="draft"))

    def test_status_rejects_int(self):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(status=0))

    @pytest.mark.parametrize("field_name", [
        "question_id", "tenant_id", "title", "description",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "question_id", "tenant_id", "title", "description",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(**{field_name: "\t\n "}))

    @pytest.mark.parametrize("bad_val", [-1, -5])
    def test_hypothesis_count_negative_rejected(self, bad_val):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(hypothesis_count=bad_val))

    @pytest.mark.parametrize("bad_val", [True, False])
    def test_hypothesis_count_bool_rejected(self, bad_val):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(hypothesis_count=bad_val))

    @pytest.mark.parametrize("bad_val", [1.0, 2.5])
    def test_hypothesis_count_float_rejected(self, bad_val):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(hypothesis_count=bad_val))

    @pytest.mark.parametrize("good_val", [0, 1, 99])
    def test_hypothesis_count_valid(self, good_val):
        rec = ResearchQuestion(**_make_question(hypothesis_count=good_val))
        assert rec.hypothesis_count == good_val

    def test_datetime_valid(self):
        rec = ResearchQuestion(**_make_question(created_at="2025-06-01T12:00:00+05:00"))
        assert rec.created_at == "2025-06-01T12:00:00+05:00"

    def test_datetime_date_only(self):
        rec = ResearchQuestion(**_make_question(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            ResearchQuestion(**_make_question(created_at="xyz"))

    def test_metadata_frozen(self):
        rec = ResearchQuestion(**_make_question(metadata={"a": 1}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = ResearchQuestion(**_make_question())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "title", "x")

    def test_to_dict_preserves_enum(self):
        rec = ResearchQuestion(**_make_question())
        d = rec.to_dict()
        assert d["status"] is ResearchStatus.DRAFT

    def test_to_dict_metadata_plain(self):
        rec = ResearchQuestion(**_make_question(metadata={"k": [1, 2]}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ResearchQuestion)


# ===================================================================
# 4. StudyProtocol
# ===================================================================


class TestStudyProtocol:
    def test_valid_construction(self):
        rec = StudyProtocol(**_make_study())
        assert rec.study_id == "s-1"
        assert rec.tenant_id == "t-1"
        assert rec.title == "Light study"
        assert rec.hypothesis_ref == "h-1"
        assert rec.status is StudyStatus.DRAFT
        assert rec.experiment_count == 5

    @pytest.mark.parametrize("member", list(StudyStatus))
    def test_all_status_members(self, member):
        rec = StudyProtocol(**_make_study(status=member))
        assert rec.status is member

    def test_status_rejects_string(self):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(status="draft"))

    def test_status_rejects_int(self):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(status=1))

    @pytest.mark.parametrize("field_name", [
        "study_id", "tenant_id", "title", "hypothesis_ref",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "study_id", "tenant_id", "title", "hypothesis_ref",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(**{field_name: "  "}))

    @pytest.mark.parametrize("bad_val", [-1, -10])
    def test_experiment_count_negative_rejected(self, bad_val):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(experiment_count=bad_val))

    @pytest.mark.parametrize("bad_val", [True, False])
    def test_experiment_count_bool_rejected(self, bad_val):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(experiment_count=bad_val))

    @pytest.mark.parametrize("bad_val", [1.0, 3.14])
    def test_experiment_count_float_rejected(self, bad_val):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(experiment_count=bad_val))

    @pytest.mark.parametrize("good_val", [0, 1, 50])
    def test_experiment_count_valid(self, good_val):
        rec = StudyProtocol(**_make_study(experiment_count=good_val))
        assert rec.experiment_count == good_val

    def test_datetime_valid(self):
        rec = StudyProtocol(**_make_study(created_at="2025-12-31T23:59:59Z"))
        assert rec.created_at == "2025-12-31T23:59:59Z"

    def test_datetime_date_only(self):
        rec = StudyProtocol(**_make_study(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            StudyProtocol(**_make_study(created_at="nope"))

    def test_metadata_frozen(self):
        rec = StudyProtocol(**_make_study(metadata={"x": "y"}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = StudyProtocol(**_make_study())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "study_id", "x")

    def test_to_dict_preserves_enum(self):
        rec = StudyProtocol(**_make_study())
        d = rec.to_dict()
        assert d["status"] is StudyStatus.DRAFT

    def test_to_dict_metadata_plain(self):
        rec = StudyProtocol(**_make_study(metadata={"nested": {"a": 1}}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(StudyProtocol)


# ===================================================================
# 5. ExperimentRun
# ===================================================================


class TestExperimentRun:
    def test_valid_construction(self):
        rec = ExperimentRun(**_make_experiment())
        assert rec.experiment_id == "e-1"
        assert rec.tenant_id == "t-1"
        assert rec.study_ref == "s-1"
        assert rec.status is ExperimentStatus.PLANNED
        assert rec.result_summary == "Positive correlation observed"
        assert rec.confidence == 0.8

    @pytest.mark.parametrize("member", list(ExperimentStatus))
    def test_all_status_members(self, member):
        rec = ExperimentRun(**_make_experiment(status=member))
        assert rec.status is member

    def test_status_rejects_string(self):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(status="planned"))

    def test_status_rejects_int(self):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(status=0))

    @pytest.mark.parametrize("field_name", [
        "experiment_id", "tenant_id", "study_ref", "result_summary",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "experiment_id", "tenant_id", "study_ref", "result_summary",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(**{field_name: "   "}))

    @pytest.mark.parametrize("bad_val", [-0.01, 1.01, 5.0])
    def test_confidence_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(confidence=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
    def test_confidence_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(confidence=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_confidence_valid_range(self, good_val):
        rec = ExperimentRun(**_make_experiment(confidence=good_val))
        assert rec.confidence == good_val

    def test_confidence_rejects_bool(self):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(confidence=True))

    def test_datetime_valid(self):
        rec = ExperimentRun(**_make_experiment(created_at="2025-06-01T00:00:00Z"))
        assert rec.created_at == "2025-06-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = ExperimentRun(**_make_experiment(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            ExperimentRun(**_make_experiment(created_at="bad"))

    def test_metadata_frozen(self):
        rec = ExperimentRun(**_make_experiment(metadata={"m": 1}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = ExperimentRun(**_make_experiment())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "experiment_id", "x")

    def test_to_dict_preserves_enum(self):
        rec = ExperimentRun(**_make_experiment())
        d = rec.to_dict()
        assert d["status"] is ExperimentStatus.PLANNED

    def test_to_dict_metadata_plain(self):
        rec = ExperimentRun(**_make_experiment(metadata={"z": "w"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ExperimentRun)


# ===================================================================
# 6. LiteraturePacket
# ===================================================================


class TestLiteraturePacket:
    def test_valid_construction(self):
        rec = LiteraturePacket(**_make_literature())
        assert rec.packet_id == "lit-1"
        assert rec.tenant_id == "t-1"
        assert rec.hypothesis_ref == "h-1"
        assert rec.title == "Related work survey"
        assert rec.source_count == 12
        assert rec.relevance_score == 0.75

    @pytest.mark.parametrize("field_name", [
        "packet_id", "tenant_id", "hypothesis_ref", "title",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "packet_id", "tenant_id", "hypothesis_ref", "title",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(**{field_name: "\t"}))

    @pytest.mark.parametrize("bad_val", [-1, -100])
    def test_source_count_negative_rejected(self, bad_val):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(source_count=bad_val))

    @pytest.mark.parametrize("bad_val", [True, False])
    def test_source_count_bool_rejected(self, bad_val):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(source_count=bad_val))

    @pytest.mark.parametrize("bad_val", [1.0, 2.5])
    def test_source_count_float_rejected(self, bad_val):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(source_count=bad_val))

    @pytest.mark.parametrize("good_val", [0, 1, 50])
    def test_source_count_valid(self, good_val):
        rec = LiteraturePacket(**_make_literature(source_count=good_val))
        assert rec.source_count == good_val

    @pytest.mark.parametrize("bad_val", [-0.1, 1.1, 10.0])
    def test_relevance_score_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(relevance_score=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
    def test_relevance_score_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(relevance_score=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_relevance_score_valid_range(self, good_val):
        rec = LiteraturePacket(**_make_literature(relevance_score=good_val))
        assert rec.relevance_score == good_val

    def test_relevance_score_rejects_bool(self):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(relevance_score=True))

    def test_datetime_valid(self):
        rec = LiteraturePacket(**_make_literature(created_at="2025-06-01T00:00:00Z"))
        assert rec.created_at == "2025-06-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = LiteraturePacket(**_make_literature(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            LiteraturePacket(**_make_literature(created_at="nah"))

    def test_metadata_frozen(self):
        rec = LiteraturePacket(**_make_literature(metadata={"p": "q"}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = LiteraturePacket(**_make_literature())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "packet_id", "x")

    def test_to_dict_metadata_plain(self):
        rec = LiteraturePacket(**_make_literature(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(LiteraturePacket)


# ===================================================================
# 7. EvidenceSynthesis
# ===================================================================


class TestEvidenceSynthesis:
    def test_valid_construction(self):
        rec = EvidenceSynthesis(**_make_synthesis())
        assert rec.synthesis_id == "syn-1"
        assert rec.tenant_id == "t-1"
        assert rec.hypothesis_ref == "h-1"
        assert rec.strength is EvidenceStrength.MODERATE
        assert rec.experiment_count == 4
        assert rec.literature_count == 8
        assert rec.contradiction_count == 1
        assert rec.confidence == 0.7

    @pytest.mark.parametrize("member", list(EvidenceStrength))
    def test_all_strength_members(self, member):
        rec = EvidenceSynthesis(**_make_synthesis(strength=member))
        assert rec.strength is member

    def test_strength_rejects_string(self):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(strength="moderate"))

    def test_strength_rejects_int(self):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(strength=2))

    @pytest.mark.parametrize("field_name", [
        "synthesis_id", "tenant_id", "hypothesis_ref",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "synthesis_id", "tenant_id", "hypothesis_ref",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(**{field_name: "  "}))

    @pytest.mark.parametrize("int_field", [
        "experiment_count", "literature_count", "contradiction_count",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "experiment_count", "literature_count", "contradiction_count",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(**{int_field: True}))

    @pytest.mark.parametrize("int_field", [
        "experiment_count", "literature_count", "contradiction_count",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(**{int_field: 1.0}))

    @pytest.mark.parametrize("int_field", [
        "experiment_count", "literature_count", "contradiction_count",
    ])
    def test_int_field_zero_valid(self, int_field):
        rec = EvidenceSynthesis(**_make_synthesis(**{int_field: 0}))
        assert getattr(rec, int_field) == 0

    @pytest.mark.parametrize("bad_val", [-0.1, 1.1])
    def test_confidence_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(confidence=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("nan")])
    def test_confidence_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(confidence=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_confidence_valid_range(self, good_val):
        rec = EvidenceSynthesis(**_make_synthesis(confidence=good_val))
        assert rec.confidence == good_val

    def test_confidence_rejects_bool(self):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(confidence=False))

    def test_datetime_valid(self):
        rec = EvidenceSynthesis(**_make_synthesis(created_at="2025-01-01T00:00:00Z"))
        assert rec.created_at == "2025-01-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = EvidenceSynthesis(**_make_synthesis(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            EvidenceSynthesis(**_make_synthesis(created_at="???"))

    def test_metadata_frozen(self):
        rec = EvidenceSynthesis(**_make_synthesis(metadata={"a": "b"}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = EvidenceSynthesis(**_make_synthesis())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "synthesis_id", "x")

    def test_to_dict_preserves_enum(self):
        rec = EvidenceSynthesis(**_make_synthesis())
        d = rec.to_dict()
        assert d["strength"] is EvidenceStrength.MODERATE

    def test_to_dict_metadata_plain(self):
        rec = EvidenceSynthesis(**_make_synthesis(metadata={"k": 1}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(EvidenceSynthesis)


# ===================================================================
# 8. PeerReviewRecord
# ===================================================================


class TestPeerReviewRecord:
    def test_valid_construction(self):
        rec = PeerReviewRecord(**_make_review())
        assert rec.review_id == "rev-1"
        assert rec.tenant_id == "t-1"
        assert rec.target_ref == "syn-1"
        assert rec.reviewer_ref == "reviewer-1"
        assert rec.disposition is PublicationDisposition.IN_REVIEW
        assert rec.comments == "Needs more evidence"
        assert rec.confidence == 0.6

    @pytest.mark.parametrize("member", list(PublicationDisposition))
    def test_all_disposition_members(self, member):
        rec = PeerReviewRecord(**_make_review(disposition=member))
        assert rec.disposition is member

    def test_disposition_rejects_string(self):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(disposition="in_review"))

    def test_disposition_rejects_int(self):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(disposition=0))

    @pytest.mark.parametrize("field_name", [
        "review_id", "tenant_id", "target_ref", "reviewer_ref", "comments",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "review_id", "tenant_id", "target_ref", "reviewer_ref", "comments",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(**{field_name: "\n\t "}))

    @pytest.mark.parametrize("bad_val", [-0.01, 1.01])
    def test_confidence_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(confidence=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
    def test_confidence_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(confidence=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_confidence_valid_range(self, good_val):
        rec = PeerReviewRecord(**_make_review(confidence=good_val))
        assert rec.confidence == good_val

    def test_confidence_rejects_bool(self):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(confidence=True))

    def test_datetime_valid(self):
        rec = PeerReviewRecord(**_make_review(reviewed_at="2025-06-01T00:00:00Z"))
        assert rec.reviewed_at == "2025-06-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = PeerReviewRecord(**_make_review(reviewed_at="2025-06-01"))
        assert rec.reviewed_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            PeerReviewRecord(**_make_review(reviewed_at="nope"))

    def test_metadata_frozen(self):
        rec = PeerReviewRecord(**_make_review(metadata={"score": 9}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = PeerReviewRecord(**_make_review())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "review_id", "x")

    def test_to_dict_preserves_enum(self):
        rec = PeerReviewRecord(**_make_review())
        d = rec.to_dict()
        assert d["disposition"] is PublicationDisposition.IN_REVIEW

    def test_to_dict_metadata_plain(self):
        rec = PeerReviewRecord(**_make_review(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(PeerReviewRecord)


# ===================================================================
# 9. ResearchAssessment
# ===================================================================


class TestResearchAssessment:
    def test_valid_construction(self):
        rec = ResearchAssessment(**_make_assessment())
        assert rec.assessment_id == "assess-1"
        assert rec.tenant_id == "t-1"
        assert rec.total_questions == 10
        assert rec.total_hypotheses == 20
        assert rec.total_experiments == 15
        assert rec.total_syntheses == 5
        assert rec.total_reviews == 8
        assert rec.completion_rate == 0.65

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(**{field_name: "  "}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_experiments",
        "total_syntheses", "total_reviews",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_experiments",
        "total_syntheses", "total_reviews",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(**{int_field: True}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_experiments",
        "total_syntheses", "total_reviews",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(**{int_field: 1.0}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_experiments",
        "total_syntheses", "total_reviews",
    ])
    def test_int_field_zero_valid(self, int_field):
        rec = ResearchAssessment(**_make_assessment(**{int_field: 0}))
        assert getattr(rec, int_field) == 0

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_experiments",
        "total_syntheses", "total_reviews",
    ])
    def test_int_field_positive_valid(self, int_field):
        rec = ResearchAssessment(**_make_assessment(**{int_field: 42}))
        assert getattr(rec, int_field) == 42

    @pytest.mark.parametrize("bad_val", [-0.01, 1.01, 2.0])
    def test_completion_rate_out_of_range(self, bad_val):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(completion_rate=bad_val))

    @pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
    def test_completion_rate_non_finite(self, bad_val):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(completion_rate=bad_val))

    @pytest.mark.parametrize("good_val", [0.0, 0.5, 1.0])
    def test_completion_rate_valid_range(self, good_val):
        rec = ResearchAssessment(**_make_assessment(completion_rate=good_val))
        assert rec.completion_rate == good_val

    def test_completion_rate_rejects_bool(self):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(completion_rate=True))

    def test_datetime_valid(self):
        rec = ResearchAssessment(**_make_assessment(assessed_at="2025-06-01T12:00:00Z"))
        assert rec.assessed_at == "2025-06-01T12:00:00Z"

    def test_datetime_date_only(self):
        rec = ResearchAssessment(**_make_assessment(assessed_at="2025-06-01"))
        assert rec.assessed_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            ResearchAssessment(**_make_assessment(assessed_at="xxx"))

    def test_metadata_frozen(self):
        rec = ResearchAssessment(**_make_assessment(metadata={"a": 1}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = ResearchAssessment(**_make_assessment())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "assessment_id", "x")

    def test_to_dict_metadata_plain(self):
        rec = ResearchAssessment(**_make_assessment(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ResearchAssessment)


# ===================================================================
# 10. ResearchSnapshot
# ===================================================================


class TestResearchSnapshot:
    def test_valid_construction(self):
        rec = ResearchSnapshot(**_make_snapshot())
        assert rec.snapshot_id == "snap-1"
        assert rec.tenant_id == "t-1"
        assert rec.total_questions == 10
        assert rec.total_hypotheses == 20
        assert rec.total_studies == 8
        assert rec.total_experiments == 15
        assert rec.total_literature == 30
        assert rec.total_syntheses == 5
        assert rec.total_reviews == 8
        assert rec.total_violations == 2

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(**{field_name: "  "}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_literature", "total_syntheses",
        "total_reviews", "total_violations",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_literature", "total_syntheses",
        "total_reviews", "total_violations",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(**{int_field: True}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_literature", "total_syntheses",
        "total_reviews", "total_violations",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(**{int_field: 1.0}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_literature", "total_syntheses",
        "total_reviews", "total_violations",
    ])
    def test_int_field_zero_valid(self, int_field):
        rec = ResearchSnapshot(**_make_snapshot(**{int_field: 0}))
        assert getattr(rec, int_field) == 0

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_literature", "total_syntheses",
        "total_reviews", "total_violations",
    ])
    def test_int_field_positive_valid(self, int_field):
        rec = ResearchSnapshot(**_make_snapshot(**{int_field: 99}))
        assert getattr(rec, int_field) == 99

    def test_datetime_valid(self):
        rec = ResearchSnapshot(**_make_snapshot(captured_at="2025-06-01T00:00:00Z"))
        assert rec.captured_at == "2025-06-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = ResearchSnapshot(**_make_snapshot(captured_at="2025-06-01"))
        assert rec.captured_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            ResearchSnapshot(**_make_snapshot(captured_at="zzz"))

    def test_metadata_frozen(self):
        rec = ResearchSnapshot(**_make_snapshot(metadata={"x": 1}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = ResearchSnapshot(**_make_snapshot())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "snapshot_id", "x")

    def test_to_dict_metadata_plain(self):
        rec = ResearchSnapshot(**_make_snapshot(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ResearchSnapshot)


# ===================================================================
# 11. ResearchClosureReport
# ===================================================================


class TestResearchClosureReport:
    def test_valid_construction(self):
        rec = ResearchClosureReport(**_make_closure())
        assert rec.report_id == "rpt-1"
        assert rec.tenant_id == "t-1"
        assert rec.total_questions == 10
        assert rec.total_hypotheses == 20
        assert rec.total_studies == 8
        assert rec.total_experiments == 15
        assert rec.total_syntheses == 5
        assert rec.total_reviews == 8
        assert rec.total_violations == 2

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(**{field_name: "   "}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_syntheses", "total_reviews",
        "total_violations",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_syntheses", "total_reviews",
        "total_violations",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(**{int_field: True}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_syntheses", "total_reviews",
        "total_violations",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(**{int_field: 1.0}))

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_syntheses", "total_reviews",
        "total_violations",
    ])
    def test_int_field_zero_valid(self, int_field):
        rec = ResearchClosureReport(**_make_closure(**{int_field: 0}))
        assert getattr(rec, int_field) == 0

    @pytest.mark.parametrize("int_field", [
        "total_questions", "total_hypotheses", "total_studies",
        "total_experiments", "total_syntheses", "total_reviews",
        "total_violations",
    ])
    def test_int_field_positive_valid(self, int_field):
        rec = ResearchClosureReport(**_make_closure(**{int_field: 77}))
        assert getattr(rec, int_field) == 77

    def test_datetime_valid(self):
        rec = ResearchClosureReport(**_make_closure(created_at="2025-06-01T00:00:00Z"))
        assert rec.created_at == "2025-06-01T00:00:00Z"

    def test_datetime_date_only(self):
        rec = ResearchClosureReport(**_make_closure(created_at="2025-06-01"))
        assert rec.created_at == "2025-06-01"

    def test_datetime_garbage_rejected(self):
        with pytest.raises(ValueError):
            ResearchClosureReport(**_make_closure(created_at="bad"))

    def test_metadata_frozen(self):
        rec = ResearchClosureReport(**_make_closure(metadata={"z": 9}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        rec = ResearchClosureReport(**_make_closure())
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(rec, "report_id", "x")

    def test_to_dict_metadata_plain(self):
        rec = ResearchClosureReport(**_make_closure(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ResearchClosureReport)


# ===================================================================
# 12. Cross-cutting: to_dict round-trip and field coverage
# ===================================================================


_ALL_FACTORIES = [
    (HypothesisRecord, _make_hypothesis),
    (ResearchQuestion, _make_question),
    (StudyProtocol, _make_study),
    (ExperimentRun, _make_experiment),
    (LiteraturePacket, _make_literature),
    (EvidenceSynthesis, _make_synthesis),
    (PeerReviewRecord, _make_review),
    (ResearchAssessment, _make_assessment),
    (ResearchSnapshot, _make_snapshot),
    (ResearchClosureReport, _make_closure),
]


class TestCrossCutting:
    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_to_dict_keys_match_fields(self, cls, factory):
        rec = cls(**factory())
        d = rec.to_dict()
        field_names = {f.name for f in dataclasses.fields(cls)}
        assert set(d.keys()) == field_names

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_metadata_default_is_empty_proxy(self, cls, factory):
        rec = cls(**factory())
        assert rec.metadata == MappingProxyType({})

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_metadata_nested_dict_frozen(self, cls, factory):
        rec = cls(**factory(metadata={"outer": {"inner": 1}}))
        assert isinstance(rec.metadata, MappingProxyType)
        assert isinstance(rec.metadata["outer"], MappingProxyType)

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_metadata_nested_to_dict_thawed(self, cls, factory):
        rec = cls(**factory(metadata={"outer": {"inner": 1}}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["outer"], dict)

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_frozen_all_fields(self, cls, factory):
        rec = cls(**factory())
        for f in dataclasses.fields(cls):
            with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
                setattr(rec, f.name, "x")

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_is_frozen_dataclass(self, cls, factory):
        assert dataclasses.is_dataclass(cls)
        # slots=True implies __slots__
        assert hasattr(cls, "__slots__")

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_metadata_list_in_dict_frozen_to_tuple(self, cls, factory):
        rec = cls(**factory(metadata={"items": [1, 2, 3]}))
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_metadata_list_thawed_to_list(self, cls, factory):
        rec = cls(**factory(metadata={"items": [1, 2, 3]}))
        d = rec.to_dict()
        assert isinstance(d["metadata"]["items"], list)

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_equality_same_values(self, cls, factory):
        a = cls(**factory())
        b = cls(**factory())
        assert a == b

    @pytest.mark.parametrize("cls,factory", _ALL_FACTORIES,
                             ids=[c.__name__ for c, _ in _ALL_FACTORIES])
    def test_repr_contains_class_name(self, cls, factory):
        rec = cls(**factory())
        assert cls.__name__ in repr(rec)


# ===================================================================
# 13. Edge cases for datetime formats
# ===================================================================


_DATETIME_FACTORIES = [
    (HypothesisRecord, _make_hypothesis, "created_at"),
    (ResearchQuestion, _make_question, "created_at"),
    (StudyProtocol, _make_study, "created_at"),
    (ExperimentRun, _make_experiment, "created_at"),
    (LiteraturePacket, _make_literature, "created_at"),
    (EvidenceSynthesis, _make_synthesis, "created_at"),
    (PeerReviewRecord, _make_review, "reviewed_at"),
    (ResearchAssessment, _make_assessment, "assessed_at"),
    (ResearchSnapshot, _make_snapshot, "captured_at"),
    (ResearchClosureReport, _make_closure, "created_at"),
]


class TestDatetimeEdgeCases:
    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_iso_with_timezone_offset(self, cls, factory, dt_field):
        rec = cls(**factory(**{dt_field: "2025-06-01T12:00:00+05:30"}))
        assert getattr(rec, dt_field) == "2025-06-01T12:00:00+05:30"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_iso_with_z_suffix(self, cls, factory, dt_field):
        rec = cls(**factory(**{dt_field: "2025-06-01T00:00:00Z"}))
        assert getattr(rec, dt_field) == "2025-06-01T00:00:00Z"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_date_only_accepted(self, cls, factory, dt_field):
        rec = cls(**factory(**{dt_field: "2025-06-01"}))
        assert getattr(rec, dt_field) == "2025-06-01"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_empty_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: ""}))

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_whitespace_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: "   "}))

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FACTORIES,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FACTORIES])
    def test_garbage_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: "not-a-date"}))
