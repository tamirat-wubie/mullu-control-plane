"""Tests for knowledge extraction engine and knowledge registry."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.knowledge_ingestion import (
    ConfidenceLevel,
    FailurePattern,
    KnowledgeLifecycle,
    KnowledgeSource,
    KnowledgeSourceType,
    MethodPattern,
    ProcedureCandidate,
    ProcedureStep,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.knowledge import KnowledgeExtractor, KnowledgeRegistry


# --- Test helpers ---

FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _clock() -> str:
    return FIXED_CLOCK


def _make_source(source_id: str = "src-1") -> KnowledgeSource:
    return KnowledgeSource(
        source_id=source_id,
        source_type=KnowledgeSourceType.DOCUMENT,
        reference_id="ref-1",
        description="test source",
        created_at=FIXED_CLOCK,
    )


# --- KnowledgeExtractor tests ---


class TestDocumentExtraction:
    def test_extract_produces_procedure_with_steps(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        document = "1. Open the terminal\n2. Run the command\n3. Check the output"

        result = extractor.extract_from_document(source, document)

        assert isinstance(result, ProcedureCandidate)
        assert len(result.steps) == 3
        assert result.steps[0].description == "Open the terminal"
        assert result.steps[1].description == "Run the command"
        assert result.steps[2].description == "Check the output"
        assert result.steps[0].step_order == 0
        assert result.steps[2].step_order == 2
        assert result.confidence is not None
        assert result.confidence.value > 0.0

    def test_extract_with_bullet_list(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        document = "- First step\n- Second step"

        result = extractor.extract_from_document(source, document)

        assert len(result.steps) == 2
        assert result.steps[0].description == "First step"
        assert result.steps[1].description == "Second step"

    def test_incomplete_extraction_marks_missing_parts(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        # No preconditions, postconditions, or warnings mentioned
        document = "1. Do the thing\n2. Done"

        result = extractor.extract_from_document(source, document)

        assert len(result.missing_parts) > 0
        missing_text = " ".join(result.missing_parts).lower()
        assert "precondition" in missing_text
        assert "postcondition" in missing_text
        assert "warning" in missing_text

    def test_document_with_preconditions_reduces_missing_parts(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        document = "Precondition: system is running\n1. Open the terminal\n2. Run command"

        result = extractor.extract_from_document(source, document)

        missing_text = " ".join(result.missing_parts).lower()
        assert "precondition" not in missing_text

    def test_empty_document_raises(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()

        with pytest.raises(RuntimeCoreInvariantError):
            extractor.extract_from_document(source, "")

    def test_extract_sanitizes_null_bytes_and_control_chars(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        # Document with null bytes and control characters embedded
        document = "1. Open\x00 the terminal\x01\n2. Run\x02 command\x7f\n3. Check output"

        result = extractor.extract_from_document(source, document)

        assert len(result.steps) == 3
        # Null bytes and control chars should be stripped
        assert "\x00" not in result.steps[0].description
        assert "\x01" not in result.steps[0].description
        assert "\x02" not in result.steps[1].description
        assert "\x7f" not in result.steps[1].description
        assert result.steps[0].description == "Open the terminal"
        assert result.steps[1].description == "Run command"

    def test_extract_preserves_tabs_and_newlines_in_content(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        # Tabs and newlines should survive sanitization (they're valid whitespace)
        document = "1. Open the terminal\n2. Run the command"

        result = extractor.extract_from_document(source, document)

        assert len(result.steps) == 2

    def test_extract_multi_digit_numbered_steps(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        # Build a document with steps 1 through 15
        lines = [f"{i}. Step number {i}" for i in range(1, 16)]
        document = "\n".join(lines)

        result = extractor.extract_from_document(source, document)

        assert len(result.steps) == 15
        for i, step in enumerate(result.steps):
            assert step.step_order == i
            assert step.description == f"Step number {i + 1}"

    def test_extract_multi_digit_with_paren_separator(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        document = "10) First multi-digit\n11) Second multi-digit\n12) Third multi-digit"

        result = extractor.extract_from_document(source, document)

        assert len(result.steps) == 3
        assert result.steps[0].description == "First multi-digit"
        assert result.steps[2].description == "Third multi-digit"

    def test_confidence_based_on_completeness(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()

        # Fewer missing parts = higher confidence
        full_doc = (
            "Precondition: ready\nPostcondition: done\nWarning: careful\n"
            "1. Step one\n2. Step two\n3. Step three"
        )
        sparse_doc = "1. Do something"

        full_result = extractor.extract_from_document(source, full_doc)
        sparse_result = extractor.extract_from_document(source, sparse_doc)

        assert full_result.confidence is not None
        assert sparse_result.confidence is not None
        assert full_result.confidence.value > sparse_result.confidence.value


class TestFailurePatternExtraction:
    def test_extract_failure_pattern_from_incidents(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        incidents = [
            {"trigger": "timeout", "failure_mode": "service_down", "response": "restart"},
            {"trigger": "timeout", "failure_mode": "service_down", "response": "restart"},
            {"trigger": "oom", "failure_mode": "crash", "response": "scale_up"},
        ]

        result = extractor.extract_failure_pattern(source, incidents)

        assert isinstance(result, FailurePattern)
        assert "timeout" in result.trigger_conditions
        assert result.failure_mode == "service_down"
        assert result.recommended_response == "restart"
        assert result.confidence is not None
        assert result.confidence.value > 0.5

    def test_empty_incidents_raises(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()

        with pytest.raises(RuntimeCoreInvariantError):
            extractor.extract_failure_pattern(source, [])

    def test_single_incident(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        incidents = [{"trigger": "disk_full", "failure_mode": "write_error", "response": "cleanup"}]

        result = extractor.extract_failure_pattern(source, incidents)

        assert "disk_full" in result.trigger_conditions
        assert result.confidence is not None
        assert result.confidence.value == 1.0


class TestMethodPatternExtraction:
    def test_extract_method_pattern_from_runs(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        runs = [
            {"steps": ["init", "process", "finalize"]},
            {"steps": ["init", "process", "finalize"]},
            {"steps": ["setup", "run"]},
        ]

        result = extractor.extract_method_pattern(source, runs)

        assert isinstance(result, MethodPattern)
        assert result.steps == ("init", "process", "finalize")
        assert result.confidence is not None
        assert result.confidence.value > 0.5

    def test_empty_runs_raises(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()

        with pytest.raises(RuntimeCoreInvariantError):
            extractor.extract_method_pattern(source, [])

    def test_all_runs_match(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        runs = [
            {"steps": ["a", "b", "c"]},
            {"steps": ["a", "b", "c"]},
        ]

        result = extractor.extract_method_pattern(source, runs)

        assert result.confidence is not None
        assert result.confidence.value == 1.0


# --- KnowledgeRegistry tests ---


class TestKnowledgeRegistry:
    def test_register_and_lookup(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one\n2. Step two")

        registry.register(candidate)
        found = registry.lookup(candidate.candidate_id)

        assert found is candidate

    def test_lookup_missing_returns_none(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        assert registry.lookup("nonexistent-id") is None

    def test_duplicate_registration_raises(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")

        registry.register(candidate)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            registry.register(candidate)

    def test_list_by_lifecycle(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        results = registry.list_by_lifecycle(KnowledgeLifecycle.CANDIDATE)
        assert len(results) == 1
        assert results[0] is candidate

        empty = registry.list_by_lifecycle(KnowledgeLifecycle.VERIFIED)
        assert len(empty) == 0

    def test_list_by_source(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source("src-alpha")
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        results = registry.list_by_source("src-alpha")
        assert len(results) == 1

        empty = registry.list_by_source("src-other")
        assert len(empty) == 0


class TestLifecyclePromotion:
    def test_valid_promotion_candidate_to_provisional(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        decision = registry.promote(
            candidate.candidate_id,
            KnowledgeLifecycle.PROVISIONAL,
            reason="passed review",
            decided_by="reviewer-1",
        )

        assert decision.from_lifecycle == KnowledgeLifecycle.CANDIDATE
        assert decision.to_lifecycle == KnowledgeLifecycle.PROVISIONAL
        assert registry.get_lifecycle(candidate.candidate_id) == KnowledgeLifecycle.PROVISIONAL

    def test_valid_promotion_chain(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)
        kid = candidate.candidate_id

        registry.promote(kid, KnowledgeLifecycle.PROVISIONAL, "review", "r1")
        registry.promote(kid, KnowledgeLifecycle.VERIFIED, "tested", "r2")
        decision = registry.promote(kid, KnowledgeLifecycle.TRUSTED, "proven", "r3")

        assert decision.to_lifecycle == KnowledgeLifecycle.TRUSTED
        assert registry.get_lifecycle(kid) == KnowledgeLifecycle.TRUSTED

    def test_invalid_transition_rejected(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        # Cannot skip from candidate to verified
        with pytest.raises(RuntimeCoreInvariantError, match="invalid lifecycle transition"):
            registry.promote(
                candidate.candidate_id,
                KnowledgeLifecycle.VERIFIED,
                reason="skip",
                decided_by="reviewer-1",
            )

    def test_blocked_cannot_be_promoted(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)
        kid = candidate.candidate_id

        registry.promote(kid, KnowledgeLifecycle.BLOCKED, "unsafe", "r1")

        with pytest.raises(RuntimeCoreInvariantError, match="invalid lifecycle transition"):
            registry.promote(kid, KnowledgeLifecycle.CANDIDATE, "retry", "r2")

    def test_any_to_deprecated(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        decision = registry.promote(
            candidate.candidate_id,
            KnowledgeLifecycle.DEPRECATED,
            reason="outdated",
            decided_by="reviewer-1",
        )

        assert decision.to_lifecycle == KnowledgeLifecycle.DEPRECATED

    def test_promote_nonexistent_raises(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError, match="knowledge not found"):
            registry.promote("no-such-id", KnowledgeLifecycle.PROVISIONAL, "reason", "reviewer")


class TestVerification:
    def test_verification_recording(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source()
        candidate = extractor.extract_from_document(source, "1. Step one")
        registry.register(candidate)

        result = registry.verify(
            knowledge_id=candidate.candidate_id,
            verifier_id="verifier-1",
            method="manual_review",
            notes="Looks good",
        )

        assert result.knowledge_id == candidate.candidate_id
        assert result.verifier_id == "verifier-1"
        assert result.verification_method == "manual_review"
        assert result.verified_at == FIXED_CLOCK
        assert result.verified is True

    def test_verify_nonexistent_raises(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError, match="knowledge not found"):
            registry.verify("no-such-id", "verifier-1", "method", "notes")


class TestBoundedContracts:
    def test_document_extraction_redacts_source_and_counts(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source("source-secret")
        result = extractor.extract_from_document(source, "1. Do the thing\n2. Done")

        assert result.name == "procedure candidate"
        assert result.confidence.reason == "completeness-based extraction assessment"
        assert "source-secret" not in result.name
        assert "2 steps" not in result.confidence.reason

    def test_failure_pattern_redacts_trigger_and_frequency(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source("source-secret")
        incidents = [
            {"trigger": "trigger-secret", "failure_mode": "service_down", "response": "restart"},
            {"trigger": "trigger-secret", "failure_mode": "service_down", "response": "restart"},
            {"trigger": "other-trigger", "failure_mode": "degraded", "response": "retry"},
        ]

        result = extractor.extract_failure_pattern(source, incidents)

        assert result.name == "failure pattern"
        assert result.confidence.reason == "trigger frequency assessment"
        assert "trigger-secret" not in result.name
        assert "2/3" not in result.confidence.reason

    def test_method_pattern_redacts_source_and_run_counts(self) -> None:
        extractor = KnowledgeExtractor(clock=_clock)
        source = _make_source("source-secret")
        runs = [
            {"steps": ["init", "process", "finalize"]},
            {"steps": ["init", "process", "finalize"]},
            {"steps": ["setup", "run"]},
        ]

        result = extractor.extract_method_pattern(source, runs)

        assert result.name == "method pattern"
        assert result.description == "common steps across successful runs"
        assert result.confidence.reason == "step match assessment"
        assert "source-secret" not in result.name
        assert "3 runs" not in result.description
        assert "2/3" not in result.confidence.reason

    def test_duplicate_registration_redacts_knowledge_id(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        candidate = extractor.extract_from_document(_make_source(), "1. Step one")

        registry.register(candidate)
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            registry.register(candidate)

        assert "knowledge already registered" in str(excinfo.value)
        assert candidate.candidate_id not in str(excinfo.value)

    def test_promote_missing_redacts_knowledge_id(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            registry.promote("knowledge-secret", KnowledgeLifecycle.PROVISIONAL, "reason", "reviewer")

        assert "knowledge not found" in str(excinfo.value)
        assert "knowledge-secret" not in str(excinfo.value)

    def test_verify_missing_redacts_knowledge_id(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            registry.verify("knowledge-secret", "verifier-1", "method", "notes")

        assert "knowledge not found" in str(excinfo.value)
        assert "knowledge-secret" not in str(excinfo.value)

    def test_invalid_transition_redacts_lifecycle_values(self) -> None:
        registry = KnowledgeRegistry(clock=_clock)
        extractor = KnowledgeExtractor(clock=_clock)
        candidate = extractor.extract_from_document(_make_source(), "1. Step one")
        registry.register(candidate)

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            registry.promote(candidate.candidate_id, KnowledgeLifecycle.VERIFIED, "skip", "reviewer-1")

        assert "invalid lifecycle transition" in str(excinfo.value)
        assert "candidate" not in str(excinfo.value).lower()
        assert "verified" not in str(excinfo.value).lower()
