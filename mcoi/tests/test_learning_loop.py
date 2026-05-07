"""Tests for learning feedback loop: lesson recording, confidence updates, promotion suggestions."""

from __future__ import annotations

import math

import pytest

from mcoi_runtime.contracts.knowledge_ingestion import (
    ConfidenceLevel,
    KnowledgeLifecycle,
    KnowledgeSource,
    KnowledgeSourceType,
    LessonRecord,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.knowledge import KnowledgeExtractor, KnowledgeRegistry
from mcoi_runtime.core.learning import LearningEngine


# --- Test helpers ---

FIXED_CLOCK = "2025-01-15T10:00:00+00:00"
_call_count = 0


def _clock() -> str:
    return FIXED_CLOCK


def _make_advancing_clock():
    """Create an advancing clock factory to avoid global state leaks."""
    counter = [0]

    def clock() -> str:
        counter[0] += 1
        return f"2025-01-15T10:{counter[0]:02d}:00+00:00"

    return clock


def _make_source(source_id: str = "src-1") -> KnowledgeSource:
    return KnowledgeSource(
        source_id=source_id,
        source_type=KnowledgeSourceType.DOCUMENT,
        reference_id="ref-1",
        description="test source",
        created_at=FIXED_CLOCK,
    )


def _register_candidate(registry: KnowledgeRegistry) -> str:
    """Register a candidate and return its knowledge_id."""
    extractor = KnowledgeExtractor(clock=_clock)
    source = _make_source()
    candidate = extractor.extract_from_document(source, "1. Step one\n2. Step two")
    registry.register(candidate)
    return candidate.candidate_id


# --- LearningEngine tests ---


class TestLessonRecording:
    def test_record_lesson(self) -> None:
        engine = LearningEngine(clock=_clock)

        record = engine.record_lesson(
            source_id="src-1",
            context="deploying to production",
            action="ran migration script",
            outcome="database updated successfully",
            lesson="always back up before migration",
        )

        assert isinstance(record, LessonRecord)
        assert record.source_id == "src-1"
        assert record.context == "deploying to production"
        assert record.action_taken == "ran migration script"
        assert record.outcome == "database updated successfully"
        assert record.lesson == "always back up before migration"
        assert record.created_at == FIXED_CLOCK

    def test_record_lesson_empty_field_raises(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_lesson(
                source_id="",
                context="context",
                action="action",
                outcome="outcome",
                lesson="lesson",
            )


class TestConfidenceUpdates:
    def test_confidence_increase_on_success(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.set_confidence("k-1", 0.5)

        result = engine.update_confidence("k-1", outcome_success=True, weight=0.1)

        assert isinstance(result, ConfidenceLevel)
        # 0.5 + 0.1 * (1 - 0.5) = 0.5 + 0.05 = 0.55
        assert abs(result.value - 0.55) < 1e-6
        assert result.reason == "outcome-based confidence increase"
        assert "0.1" not in result.reason

    def test_confidence_decrease_on_failure(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.set_confidence("k-1", 0.5)

        result = engine.update_confidence("k-1", outcome_success=False, weight=0.1)

        # 0.5 - 0.1 * 0.5 = 0.5 - 0.05 = 0.45
        assert abs(result.value - 0.45) < 1e-6
        assert result.reason == "outcome-based confidence decrease"
        assert "0.1" not in result.reason

    def test_confidence_clamped_at_upper_bound(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.set_confidence("k-1", 0.99)

        result = engine.update_confidence("k-1", outcome_success=True, weight=0.5)

        # 0.99 + 0.5 * (1 - 0.99) = 0.99 + 0.005 = 0.995
        assert result.value <= 1.0

        # Push to the edge
        engine.set_confidence("k-2", 1.0)
        result2 = engine.update_confidence("k-2", outcome_success=True, weight=1.0)
        assert result2.value == 1.0

    def test_confidence_clamped_at_lower_bound(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.set_confidence("k-1", 0.01)

        result = engine.update_confidence("k-1", outcome_success=False, weight=0.5)

        # 0.01 - 0.5 * 0.01 = 0.01 - 0.005 = 0.005
        assert result.value >= 0.0

        # Push to the edge
        engine.set_confidence("k-2", 0.0)
        result2 = engine.update_confidence("k-2", outcome_success=False, weight=1.0)
        assert result2.value == 0.0

    def test_default_confidence_is_half(self) -> None:
        engine = LearningEngine(clock=_clock)

        result = engine.update_confidence("k-new", outcome_success=True, weight=0.1)

        # Default is 0.5; 0.5 + 0.1 * 0.5 = 0.55
        assert abs(result.value - 0.55) < 1e-6

    def test_invalid_weight_raises(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_confidence("k-1", outcome_success=True, weight=-0.1)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_confidence("k-1", outcome_success=True, weight=1.5)

    def test_nan_weight_rejected(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_confidence("k-1", outcome_success=True, weight=float("nan"))

    def test_infinity_weight_rejected(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_confidence("k-1", outcome_success=True, weight=float("inf"))

        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_confidence("k-1", outcome_success=True, weight=float("-inf"))

    def test_nan_value_rejected_in_set_confidence(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.set_confidence("k-1", float("nan"))

    def test_infinity_value_rejected_in_set_confidence(self) -> None:
        engine = LearningEngine(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.set_confidence("k-1", float("inf"))

        with pytest.raises(RuntimeCoreInvariantError):
            engine.set_confidence("k-1", float("-inf"))


class TestPromotionSuggestions:
    def test_suggest_candidate_to_provisional(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)
        kid = _register_candidate(registry)
        engine.set_confidence(kid, 0.8)

        suggestion = engine.suggest_promotion(kid, registry)
        assert suggestion == "provisional"

    def test_suggest_provisional_to_verified(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)
        kid = _register_candidate(registry)
        registry.promote(kid, KnowledgeLifecycle.PROVISIONAL, "passed", "r1")
        engine.set_confidence(kid, 0.9)

        suggestion = engine.suggest_promotion(kid, registry)
        assert suggestion == "verified"

    def test_suggest_verified_to_trusted(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)
        kid = _register_candidate(registry)
        registry.promote(kid, KnowledgeLifecycle.PROVISIONAL, "passed", "r1")
        registry.promote(kid, KnowledgeLifecycle.VERIFIED, "tested", "r2")
        engine.set_confidence(kid, 0.95)

        suggestion = engine.suggest_promotion(kid, registry)
        assert suggestion == "trusted"

    def test_no_suggestion_below_threshold(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)
        kid = _register_candidate(registry)
        engine.set_confidence(kid, 0.7)

        suggestion = engine.suggest_promotion(kid, registry)
        assert suggestion is None

    def test_no_suggestion_for_trusted(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)
        kid = _register_candidate(registry)
        registry.promote(kid, KnowledgeLifecycle.PROVISIONAL, "passed", "r1")
        registry.promote(kid, KnowledgeLifecycle.VERIFIED, "tested", "r2")
        registry.promote(kid, KnowledgeLifecycle.TRUSTED, "proven", "r3")
        engine.set_confidence(kid, 0.99)

        suggestion = engine.suggest_promotion(kid, registry)
        assert suggestion is None

    def test_no_suggestion_for_unknown_artifact(self) -> None:
        engine = LearningEngine(clock=_clock)
        registry = KnowledgeRegistry(clock=_clock)

        suggestion = engine.suggest_promotion("nonexistent", registry)
        assert suggestion is None


class TestLessonRetrieval:
    def test_find_relevant_lessons_by_keyword(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.record_lesson("s1", "deploying to production", "migrate", "success", "back up first")
        engine.record_lesson("s2", "testing in staging", "run tests", "pass", "use fixtures")
        engine.record_lesson("s3", "deploying to staging", "deploy", "success", "check logs")

        results = engine.find_relevant_lessons(("deploying",))

        assert len(results) == 2
        contexts = [r.context for r in results]
        assert "deploying to production" in contexts
        assert "deploying to staging" in contexts

    def test_no_match_returns_empty(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.record_lesson("s1", "deploying to production", "migrate", "success", "back up first")

        results = engine.find_relevant_lessons(("unrelated",))
        assert results == ()

    def test_empty_keywords_returns_empty(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.record_lesson("s1", "context", "action", "outcome", "lesson")

        results = engine.find_relevant_lessons(())
        assert results == ()

    def test_case_insensitive_matching(self) -> None:
        engine = LearningEngine(clock=_clock)
        engine.record_lesson("s1", "Deploying to Production", "migrate", "success", "back up")

        results = engine.find_relevant_lessons(("deploying",))
        assert len(results) == 1

    def test_find_with_external_lessons_list(self) -> None:
        engine = LearningEngine(clock=_clock)
        external_lesson = LessonRecord(
            lesson_id="ext-1",
            source_id="ext-src",
            context="external deployment context",
            action_taken="deploy",
            outcome="success",
            lesson="verify first",
            created_at=FIXED_CLOCK,
        )

        results = engine.find_relevant_lessons(("deployment",), lessons=[external_lesson])
        assert len(results) == 1
        assert results[0].lesson_id == "ext-1"


class TestClockDeterminism:
    def test_clock_injection_produces_consistent_timestamps(self) -> None:
        engine = LearningEngine(clock=_clock)

        record1 = engine.record_lesson("s1", "ctx", "act", "out", "lesson")
        record2 = engine.record_lesson("s2", "ctx2", "act2", "out2", "lesson2")

        # Both use the fixed clock, so created_at is identical
        assert record1.created_at == FIXED_CLOCK
        assert record2.created_at == FIXED_CLOCK

    def test_advancing_clock_produces_different_ids(self) -> None:
        adv_clock = _make_advancing_clock()
        engine = LearningEngine(clock=adv_clock)

        record1 = engine.record_lesson("s1", "ctx", "act", "out", "lesson")
        record2 = engine.record_lesson("s2", "ctx2", "act2", "out2", "lesson2")

        # The advancing clock increments, so IDs differ (different timestamps in stable_identifier)
        assert record1.lesson_id != record2.lesson_id
