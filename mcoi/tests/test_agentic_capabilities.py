"""Agentic Capabilities Tests — Adaptive reasoning + peer review."""

import pytest
from mcoi_runtime.core.adaptive_reasoning import (
    AdaptiveRouter,
    ComplexityAssessment,
    ComplexityLevel,
    classify_complexity,
    DEFAULT_MODEL_TIERS,
)
from mcoi_runtime.core.peer_review import (
    PeerReviewEngine,
    PeerReviewResult,
    VerificationVerdict,
    verify_response,
)


# ═══ Adaptive Reasoning ═══


class TestComplexityClassification:
    def test_simple_greeting(self):
        result = classify_complexity("Hello, how are you?")
        assert result.level == ComplexityLevel.LOW

    def test_simple_question(self):
        result = classify_complexity("What time is it?")
        assert result.level == ComplexityLevel.LOW

    def test_moderate_question(self):
        result = classify_complexity(
            "Can you explain the difference between TCP and UDP protocols? "
            "What are the trade-offs for real-time applications?"
        )
        assert result.level in (ComplexityLevel.MEDIUM, ComplexityLevel.HIGH)

    def test_complex_coding_task(self):
        result = classify_complexity(
            "Implement a binary search tree with balanced insertion, deletion, "
            "and in-order traversal. Write a complete Python class with tests."
        )
        assert result.level in (ComplexityLevel.HIGH, ComplexityLevel.MAX)

    def test_max_complexity(self):
        result = classify_complexity(
            "Perform a comprehensive security audit of the authentication system. "
            "Provide a detailed analysis of all attack vectors and end-to-end fixes."
        )
        assert result.level == ComplexityLevel.MAX

    def test_code_detection(self):
        result = classify_complexity("```python\ndef foo(): pass\n```")
        assert result.level >= ComplexityLevel.HIGH

    def test_empty_prompt(self):
        result = classify_complexity("")
        assert result.level == ComplexityLevel.LOW
        assert result.confidence == 1.0

    def test_assessment_has_model(self):
        result = classify_complexity("Hello")
        assert result.suggested_model != "" or result.level == ComplexityLevel.LOW

    def test_assessment_has_max_tokens(self):
        result = classify_complexity("Design a microservices architecture")
        assert result.suggested_max_tokens > 0


class TestAdaptiveRouter:
    def test_select_model(self):
        router = AdaptiveRouter()
        assessment = router.select_model("Hello")
        assert assessment.level == ComplexityLevel.LOW

    def test_override_model(self):
        router = AdaptiveRouter(override_model="custom-model")
        assessment = router.select_model("complex analysis task")
        assert assessment.suggested_model == "custom-model"

    def test_routing_count(self):
        router = AdaptiveRouter()
        assert router.routing_count == 0
        router.select_model("hi")
        router.select_model("analyze this")
        assert router.routing_count == 2

    def test_summary(self):
        router = AdaptiveRouter()
        router.select_model("hello")
        router.select_model("implement a database")
        summary = router.summary()
        assert summary["total_routings"] == 2
        assert "level_distribution" in summary


class TestModelTiers:
    def test_all_levels_have_tiers(self):
        for level in ComplexityLevel:
            assert level in DEFAULT_MODEL_TIERS

    def test_max_tokens_increase_with_complexity(self):
        low = DEFAULT_MODEL_TIERS[ComplexityLevel.LOW].max_tokens
        high = DEFAULT_MODEL_TIERS[ComplexityLevel.HIGH].max_tokens
        maxx = DEFAULT_MODEL_TIERS[ComplexityLevel.MAX].max_tokens
        assert low < high < maxx


# ═══ Peer Review ═══


class TestVerifyResponse:
    def test_consistent_response(self):
        result = verify_response("What is 2+2?", "The answer is 4.")
        assert result.verdict == VerificationVerdict.CONSISTENT

    def test_uncertainty_flagged(self):
        result = verify_response(
            "What happened yesterday?",
            "I don't have access to real-time information, but generally...",
        )
        assert result.verdict == VerificationVerdict.FLAGGED
        assert len(result.issues) >= 1

    def test_contradiction_detected(self):
        result = verify_response(
            "Tell me about X",
            "X is blue. Actually, that's not correct — X is red.",
        )
        assert result.verdict == VerificationVerdict.CONTRADICTED

    def test_empty_response_consistent(self):
        result = verify_response("test", "")
        assert result.verdict == VerificationVerdict.CONSISTENT

    def test_disproportionate_response_flagged(self):
        result = verify_response("Hi", "word " * 600)
        assert result.verdict == VerificationVerdict.FLAGGED
        assert any("disproportionate" in i for i in result.issues)


class TestPeerReviewEngine:
    def test_enabled_reviews(self):
        engine = PeerReviewEngine(enabled=True)
        result = engine.review("prompt", "response")
        assert result.verdict == VerificationVerdict.CONSISTENT
        assert engine.review_count == 1

    def test_disabled_skips(self):
        engine = PeerReviewEngine(enabled=False)
        result = engine.review("prompt", "I'm not sure if this is right")
        assert result.verdict == VerificationVerdict.CONSISTENT
        assert result.verification_model == "disabled"

    def test_flagged_count(self):
        engine = PeerReviewEngine()
        engine.review("q", "I don't have access to real-time data")
        engine.review("q", "This is fine")
        assert engine.flagged_count == 1
        assert engine.review_count == 2

    def test_summary(self):
        engine = PeerReviewEngine()
        engine.review("q", "ok")
        summary = engine.summary()
        assert summary["reviews"] == 1
        assert "flag_rate" in summary
