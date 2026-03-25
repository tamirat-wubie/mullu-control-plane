"""Comprehensive contract tests for knowledge ingestion types.

Proves construction, validation, immutability, confidence bounds, lifecycle
enforcement, source provenance, and promotion decision rules for all
knowledge ingestion contract types.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.knowledge_ingestion import (
    BestPracticeRecord,
    ConfidenceLevel,
    FailurePattern,
    KnowledgeLifecycle,
    KnowledgePromotionDecision,
    KnowledgeScope,
    KnowledgeSource,
    KnowledgeSourceType,
    KnowledgeVerificationResult,
    LessonRecord,
    MethodPattern,
    ProcedureCandidate,
    ProcedureStep,
)


NOW = "2026-03-19T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence(value: float = 0.8) -> ConfidenceLevel:
    return ConfidenceLevel(value=value, reason="test reason", assessed_at=NOW)


def _source() -> KnowledgeSource:
    return KnowledgeSource(
        source_id="src-1",
        source_type=KnowledgeSourceType.DOCUMENT,
        reference_id="doc-42",
        description="A test source",
        created_at=NOW,
    )


def _step(order: int = 0, desc: str = "Do something") -> ProcedureStep:
    return ProcedureStep(step_order=order, description=desc)


def _procedure(**overrides) -> ProcedureCandidate:
    defaults = dict(
        candidate_id="proc-1",
        source_id="src-1",
        name="Test procedure",
        steps=(_step(0, "Step one"),),
        created_at=NOW,
    )
    defaults.update(overrides)
    return ProcedureCandidate(**defaults)


# ===========================================================================
# ConfidenceLevel
# ===========================================================================


class TestConfidenceLevel:
    def test_valid_construction(self):
        c = ConfidenceLevel(value=0.75, reason="solid evidence", assessed_at=NOW)
        assert c.value == 0.75
        assert c.reason == "solid evidence"

    def test_zero_confidence(self):
        c = ConfidenceLevel(value=0.0, reason="no evidence", assessed_at=NOW)
        assert c.value == 0.0

    def test_max_confidence(self):
        c = ConfidenceLevel(value=1.0, reason="perfect evidence", assessed_at=NOW)
        assert c.value == 1.0

    def test_negative_value_rejected(self):
        with pytest.raises(ValueError, match="value must be"):
            ConfidenceLevel(value=-0.1, reason="bad", assessed_at=NOW)

    def test_above_one_rejected(self):
        with pytest.raises(ValueError, match="value must be"):
            ConfidenceLevel(value=1.01, reason="bad", assessed_at=NOW)

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            ConfidenceLevel(value=0.5, reason="", assessed_at=NOW)

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError, match="assessed_at"):
            ConfidenceLevel(value=0.5, reason="ok", assessed_at="not-a-date")

    def test_frozen(self):
        c = _confidence()
        with pytest.raises(AttributeError):
            c.value = 0.5  # type: ignore[misc]

    def test_int_coerced_to_float(self):
        c = ConfidenceLevel(value=1, reason="ok", assessed_at=NOW)
        assert isinstance(c.value, float)
        assert c.value == 1.0

    def test_nan_value_rejected(self):
        with pytest.raises(ValueError, match="value must be"):
            ConfidenceLevel(value=float("nan"), reason="bad", assessed_at=NOW)

    def test_infinity_value_rejected(self):
        with pytest.raises(ValueError, match="value must be"):
            ConfidenceLevel(value=float("inf"), reason="bad", assessed_at=NOW)

        with pytest.raises(ValueError, match="value must be"):
            ConfidenceLevel(value=float("-inf"), reason="bad", assessed_at=NOW)

    def test_serialization_roundtrip(self):
        c = _confidence(0.42)
        d = c.to_dict()
        assert d["value"] == 0.42
        assert d["reason"] == "test reason"


# ===========================================================================
# ProcedureStep
# ===========================================================================


class TestProcedureStep:
    def test_valid_construction(self):
        s = ProcedureStep(step_order=0, description="Do it")
        assert s.step_order == 0
        assert s.description == "Do it"
        assert s.skill_id is None
        assert s.requires_approval is False
        assert s.verification_point is False

    def test_with_skill_id(self):
        s = ProcedureStep(step_order=1, description="Run skill", skill_id="sk-1")
        assert s.skill_id == "sk-1"

    def test_negative_step_order_rejected(self):
        with pytest.raises(ValueError, match="step_order"):
            ProcedureStep(step_order=-1, description="bad")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            ProcedureStep(step_order=0, description="")

    def test_empty_skill_id_rejected(self):
        with pytest.raises(ValueError, match="skill_id"):
            ProcedureStep(step_order=0, description="ok", skill_id="")

    def test_frozen(self):
        s = _step()
        with pytest.raises(AttributeError):
            s.step_order = 5  # type: ignore[misc]

    def test_approval_flag(self):
        s = ProcedureStep(step_order=0, description="needs approval", requires_approval=True)
        assert s.requires_approval is True

    def test_verification_flag(self):
        s = ProcedureStep(step_order=0, description="check", verification_point=True)
        assert s.verification_point is True


# ===========================================================================
# KnowledgeSource
# ===========================================================================


class TestKnowledgeSource:
    def test_valid_construction(self):
        src = _source()
        assert src.source_id == "src-1"
        assert src.source_type is KnowledgeSourceType.DOCUMENT

    def test_all_source_types(self):
        for st in KnowledgeSourceType:
            src = KnowledgeSource(
                source_id="s", source_type=st,
                reference_id="ref", description="d", created_at=NOW,
            )
            assert src.source_type is st

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValueError, match="source_type"):
            KnowledgeSource(
                source_id="s", source_type="invalid",  # type: ignore[arg-type]
                reference_id="r", description="d", created_at=NOW,
            )

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            KnowledgeSource(
                source_id="", source_type=KnowledgeSourceType.RUNBOOK,
                reference_id="r", description="d", created_at=NOW,
            )

    def test_empty_reference_id_rejected(self):
        with pytest.raises(ValueError, match="reference_id"):
            KnowledgeSource(
                source_id="s", source_type=KnowledgeSourceType.RUNBOOK,
                reference_id="", description="d", created_at=NOW,
            )

    def test_metadata_frozen(self):
        src = KnowledgeSource(
            source_id="s", source_type=KnowledgeSourceType.INCIDENT,
            reference_id="r", description="d", created_at=NOW,
            metadata={"key": [1, 2]},
        )
        assert isinstance(src.metadata["key"], tuple)

    def test_frozen(self):
        src = _source()
        with pytest.raises(AttributeError):
            src.source_id = "new"  # type: ignore[misc]


# ===========================================================================
# ProcedureCandidate
# ===========================================================================


class TestProcedureCandidate:
    def test_valid_construction(self):
        p = _procedure()
        assert p.candidate_id == "proc-1"
        assert len(p.steps) == 1

    def test_empty_steps_rejected(self):
        with pytest.raises(ValueError, match="steps must contain"):
            _procedure(steps=())

    def test_multiple_steps(self):
        p = _procedure(steps=(_step(0, "A"), _step(1, "B"), _step(2, "C")))
        assert len(p.steps) == 3

    def test_preconditions_and_postconditions(self):
        p = _procedure(
            preconditions=("system is up",),
            postconditions=("file exists",),
        )
        assert p.preconditions == ("system is up",)
        assert p.postconditions == ("file exists",)

    def test_missing_parts_tracked(self):
        p = _procedure(missing_parts=("step 3 unclear", "approval chain unknown"))
        assert len(p.missing_parts) == 2

    def test_default_lifecycle_is_candidate(self):
        p = _procedure()
        assert p.lifecycle is KnowledgeLifecycle.CANDIDATE

    def test_explicit_lifecycle(self):
        p = _procedure(lifecycle=KnowledgeLifecycle.PROVISIONAL)
        assert p.lifecycle is KnowledgeLifecycle.PROVISIONAL

    def test_invalid_lifecycle_rejected(self):
        with pytest.raises(ValueError, match="lifecycle"):
            _procedure(lifecycle="invalid")  # type: ignore[arg-type]

    def test_with_confidence(self):
        p = _procedure(confidence=_confidence(0.6))
        assert p.confidence.value == 0.6

    def test_frozen(self):
        p = _procedure()
        with pytest.raises(AttributeError):
            p.name = "new"  # type: ignore[misc]

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _procedure(name="")

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            _procedure(source_id="")

    def test_serialization(self):
        p = _procedure()
        d = p.to_dict()
        assert d["candidate_id"] == "proc-1"
        assert isinstance(d["steps"], list)


# ===========================================================================
# MethodPattern
# ===========================================================================


class TestMethodPattern:
    def test_valid_construction(self):
        mp = MethodPattern(
            pattern_id="mp-1", source_ids=("src-1",), name="Pattern A",
            description="Desc", applicability="Web services",
            steps=("step 1", "step 2"), created_at=NOW,
        )
        assert mp.pattern_id == "mp-1"
        assert len(mp.steps) == 2

    def test_empty_source_ids_rejected(self):
        with pytest.raises(ValueError, match="source_ids"):
            MethodPattern(
                pattern_id="mp-1", source_ids=(), name="P",
                description="D", applicability="A", steps=("s",), created_at=NOW,
            )

    def test_empty_steps_rejected(self):
        with pytest.raises(ValueError, match="steps"):
            MethodPattern(
                pattern_id="mp-1", source_ids=("src-1",), name="P",
                description="D", applicability="A", steps=(), created_at=NOW,
            )

    def test_frozen(self):
        mp = MethodPattern(
            pattern_id="mp-1", source_ids=("src-1",), name="P",
            description="D", applicability="A", steps=("s",), created_at=NOW,
        )
        with pytest.raises(AttributeError):
            mp.name = "new"  # type: ignore[misc]


# ===========================================================================
# BestPracticeRecord
# ===========================================================================


class TestBestPracticeRecord:
    def test_valid_construction(self):
        bp = BestPracticeRecord(
            practice_id="bp-1", source_ids=("src-1",), name="BP",
            description="Desc", conditions=("condition A",),
            recommendations=("rec A",), created_at=NOW,
        )
        assert bp.practice_id == "bp-1"

    def test_empty_conditions_rejected(self):
        with pytest.raises(ValueError, match="conditions"):
            BestPracticeRecord(
                practice_id="bp-1", source_ids=("src-1",), name="BP",
                description="Desc", conditions=(),
                recommendations=("rec A",), created_at=NOW,
            )

    def test_empty_recommendations_rejected(self):
        with pytest.raises(ValueError, match="recommendations"):
            BestPracticeRecord(
                practice_id="bp-1", source_ids=("src-1",), name="BP",
                description="Desc", conditions=("c",),
                recommendations=(), created_at=NOW,
            )

    def test_frozen(self):
        bp = BestPracticeRecord(
            practice_id="bp-1", source_ids=("src-1",), name="BP",
            description="Desc", conditions=("c",),
            recommendations=("r",), created_at=NOW,
        )
        with pytest.raises(AttributeError):
            bp.name = "new"  # type: ignore[misc]


# ===========================================================================
# FailurePattern
# ===========================================================================


class TestFailurePattern:
    def test_valid_construction(self):
        fp = FailurePattern(
            pattern_id="fp-1", source_ids=("src-1",), name="FP",
            trigger_conditions=("high load",), failure_mode="OOM",
            recommended_response="Scale up", created_at=NOW,
        )
        assert fp.pattern_id == "fp-1"
        assert fp.failure_mode == "OOM"

    def test_empty_trigger_conditions_rejected(self):
        with pytest.raises(ValueError, match="trigger_conditions"):
            FailurePattern(
                pattern_id="fp-1", source_ids=("src-1",), name="FP",
                trigger_conditions=(), failure_mode="OOM",
                recommended_response="Scale up", created_at=NOW,
            )

    def test_empty_failure_mode_rejected(self):
        with pytest.raises(ValueError, match="failure_mode"):
            FailurePattern(
                pattern_id="fp-1", source_ids=("src-1",), name="FP",
                trigger_conditions=("c",), failure_mode="",
                recommended_response="Scale up", created_at=NOW,
            )

    def test_frozen(self):
        fp = FailurePattern(
            pattern_id="fp-1", source_ids=("src-1",), name="FP",
            trigger_conditions=("c",), failure_mode="OOM",
            recommended_response="Scale up", created_at=NOW,
        )
        with pytest.raises(AttributeError):
            fp.failure_mode = "new"  # type: ignore[misc]


# ===========================================================================
# LessonRecord
# ===========================================================================


class TestLessonRecord:
    def test_valid_construction(self):
        lr = LessonRecord(
            lesson_id="ls-1", source_id="src-1",
            context="During deploy", action_taken="Rolled back",
            outcome="Service restored", lesson="Always have rollback plan",
            created_at=NOW,
        )
        assert lr.lesson_id == "ls-1"

    def test_empty_context_rejected(self):
        with pytest.raises(ValueError, match="context"):
            LessonRecord(
                lesson_id="ls-1", source_id="src-1",
                context="", action_taken="A", outcome="O", lesson="L",
                created_at=NOW,
            )

    def test_empty_lesson_rejected(self):
        with pytest.raises(ValueError, match="lesson"):
            LessonRecord(
                lesson_id="ls-1", source_id="src-1",
                context="C", action_taken="A", outcome="O", lesson="",
                created_at=NOW,
            )

    def test_with_confidence(self):
        lr = LessonRecord(
            lesson_id="ls-1", source_id="src-1",
            context="C", action_taken="A", outcome="O", lesson="L",
            confidence=_confidence(0.9), created_at=NOW,
        )
        assert lr.confidence.value == 0.9

    def test_frozen(self):
        lr = LessonRecord(
            lesson_id="ls-1", source_id="src-1",
            context="C", action_taken="A", outcome="O", lesson="L",
            created_at=NOW,
        )
        with pytest.raises(AttributeError):
            lr.lesson = "new"  # type: ignore[misc]


# ===========================================================================
# KnowledgeVerificationResult
# ===========================================================================


class TestKnowledgeVerificationResult:
    def test_valid_construction(self):
        vr = KnowledgeVerificationResult(
            knowledge_id="k-1", verified=True, verifier_id="user-1",
            verification_method="manual review", notes="Looks good",
            verified_at=NOW,
        )
        assert vr.verified is True

    def test_failed_verification(self):
        vr = KnowledgeVerificationResult(
            knowledge_id="k-1", verified=False, verifier_id="user-1",
            verification_method="automated check", notes="Missing step 3",
            verified_at=NOW,
        )
        assert vr.verified is False

    def test_empty_knowledge_id_rejected(self):
        with pytest.raises(ValueError, match="knowledge_id"):
            KnowledgeVerificationResult(
                knowledge_id="", verified=True, verifier_id="u",
                verification_method="m", notes="n", verified_at=NOW,
            )

    def test_empty_verifier_id_rejected(self):
        with pytest.raises(ValueError, match="verifier_id"):
            KnowledgeVerificationResult(
                knowledge_id="k", verified=True, verifier_id="",
                verification_method="m", notes="n", verified_at=NOW,
            )

    def test_empty_method_rejected(self):
        with pytest.raises(ValueError, match="verification_method"):
            KnowledgeVerificationResult(
                knowledge_id="k", verified=True, verifier_id="u",
                verification_method="", notes="n", verified_at=NOW,
            )

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError, match="verified_at"):
            KnowledgeVerificationResult(
                knowledge_id="k", verified=True, verifier_id="u",
                verification_method="m", notes="n", verified_at="bad",
            )

    def test_empty_notes_allowed(self):
        vr = KnowledgeVerificationResult(
            knowledge_id="k", verified=True, verifier_id="u",
            verification_method="m", notes="", verified_at=NOW,
        )
        assert vr.notes == ""

    def test_frozen(self):
        vr = KnowledgeVerificationResult(
            knowledge_id="k", verified=True, verifier_id="u",
            verification_method="m", notes="n", verified_at=NOW,
        )
        with pytest.raises(AttributeError):
            vr.verified = False  # type: ignore[misc]


# ===========================================================================
# KnowledgePromotionDecision
# ===========================================================================


class TestKnowledgePromotionDecision:
    def test_valid_promotion(self):
        pd = KnowledgePromotionDecision(
            knowledge_id="k-1",
            from_lifecycle=KnowledgeLifecycle.VERIFIED,
            to_lifecycle=KnowledgeLifecycle.TRUSTED,
            reason="Passed all checks", decided_by="admin-1",
            decided_at=NOW,
        )
        assert pd.from_lifecycle is KnowledgeLifecycle.VERIFIED
        assert pd.to_lifecycle is KnowledgeLifecycle.TRUSTED

    def test_same_lifecycle_rejected(self):
        with pytest.raises(ValueError, match="must be different"):
            KnowledgePromotionDecision(
                knowledge_id="k-1",
                from_lifecycle=KnowledgeLifecycle.CANDIDATE,
                to_lifecycle=KnowledgeLifecycle.CANDIDATE,
                reason="no change", decided_by="admin-1", decided_at=NOW,
            )

    def test_invalid_from_lifecycle_rejected(self):
        with pytest.raises(ValueError, match="from_lifecycle"):
            KnowledgePromotionDecision(
                knowledge_id="k-1",
                from_lifecycle="invalid",  # type: ignore[arg-type]
                to_lifecycle=KnowledgeLifecycle.TRUSTED,
                reason="r", decided_by="a", decided_at=NOW,
            )

    def test_invalid_to_lifecycle_rejected(self):
        with pytest.raises(ValueError, match="to_lifecycle"):
            KnowledgePromotionDecision(
                knowledge_id="k-1",
                from_lifecycle=KnowledgeLifecycle.CANDIDATE,
                to_lifecycle="invalid",  # type: ignore[arg-type]
                reason="r", decided_by="a", decided_at=NOW,
            )

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            KnowledgePromotionDecision(
                knowledge_id="k-1",
                from_lifecycle=KnowledgeLifecycle.CANDIDATE,
                to_lifecycle=KnowledgeLifecycle.PROVISIONAL,
                reason="", decided_by="a", decided_at=NOW,
            )

    def test_empty_decided_by_rejected(self):
        with pytest.raises(ValueError, match="decided_by"):
            KnowledgePromotionDecision(
                knowledge_id="k-1",
                from_lifecycle=KnowledgeLifecycle.CANDIDATE,
                to_lifecycle=KnowledgeLifecycle.PROVISIONAL,
                reason="r", decided_by="", decided_at=NOW,
            )

    def test_frozen(self):
        pd = KnowledgePromotionDecision(
            knowledge_id="k-1",
            from_lifecycle=KnowledgeLifecycle.CANDIDATE,
            to_lifecycle=KnowledgeLifecycle.PROVISIONAL,
            reason="r", decided_by="a", decided_at=NOW,
        )
        with pytest.raises(AttributeError):
            pd.reason = "new"  # type: ignore[misc]

    def test_deprecation_decision(self):
        pd = KnowledgePromotionDecision(
            knowledge_id="k-1",
            from_lifecycle=KnowledgeLifecycle.TRUSTED,
            to_lifecycle=KnowledgeLifecycle.DEPRECATED,
            reason="Superseded", decided_by="admin-1", decided_at=NOW,
        )
        assert pd.to_lifecycle is KnowledgeLifecycle.DEPRECATED

    def test_blocking_decision(self):
        pd = KnowledgePromotionDecision(
            knowledge_id="k-1",
            from_lifecycle=KnowledgeLifecycle.DEPRECATED,
            to_lifecycle=KnowledgeLifecycle.BLOCKED,
            reason="Harmful", decided_by="admin-1", decided_at=NOW,
        )
        assert pd.to_lifecycle is KnowledgeLifecycle.BLOCKED


# ===========================================================================
# Enum coverage
# ===========================================================================


class TestEnums:
    def test_knowledge_source_type_values(self):
        expected = {
            "document", "runbook", "skill_run", "workflow_run",
            "incident", "email_thread", "code_review", "operator_note",
        }
        assert {v.value for v in KnowledgeSourceType} == expected

    def test_knowledge_lifecycle_values(self):
        expected = {
            "candidate", "provisional", "verified",
            "trusted", "deprecated", "blocked",
        }
        assert {v.value for v in KnowledgeLifecycle} == expected

    def test_knowledge_scope_values(self):
        expected = {"local", "team", "organization"}
        assert {v.value for v in KnowledgeScope} == expected
