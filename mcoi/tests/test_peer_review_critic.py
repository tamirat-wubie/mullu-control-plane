"""Tests for the peer-review-backed inner critic.

Covers: verdict mapping (contradicted=>reject, flagged strict=>reject, flagged
advisory=>accept, consistent=>accept), abstain-on-no-text (defer to mechanical
proof), text-extraction precedence, determinism, and an END-TO-END run through
the real CognitiveLoop proving the critic actually downgrades a mechanically
passing-but-hallucinated outcome (no green-but-unwired). >=3 assertions/test.
"""
from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.cognitive_loop import CognitiveLoop, CriticVerdict, CognitiveStepRequest
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.peer_review_critic import PeerReviewCritic, extract_reviewable_text
from mcoi_runtime.core.world_state import WorldStateEngine


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


def _execution_result(
    *,
    metadata: dict | None = None,
    extensions: dict | None = None,
    effects: tuple[EffectRecord, ...] = (),
    execution_id: str = "exec-1",
) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=effects,
        assumed_effects=(),
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        metadata=metadata or {},
        extensions=extensions or {},
    )


# --------------------------------------------------------------------------
# Verdict mapping
# --------------------------------------------------------------------------


def test_contradiction_marker_is_rejected():
    critic = PeerReviewCritic()
    result = _execution_result(metadata={"response": "Actually, that's not correct, I was wrong about it."})

    verdict = critic.review(
        capability_id="cap", execution_result=result, mechanical_verification_passed=True
    )

    assert isinstance(verdict, CriticVerdict)
    assert verdict.accepted is False
    assert "contradicted" in verdict.reason


def test_hallucination_marker_flagged_is_rejected_when_strict():
    critic = PeerReviewCritic(strict=True)
    result = _execution_result(metadata={"response": "I cannot verify this figure but the total is 42."})

    verdict = critic.review(
        capability_id="cap", execution_result=result, mechanical_verification_passed=True
    )

    assert critic.strict is True
    assert verdict.accepted is False
    assert "flagged (strict)" in verdict.reason


def test_flagged_is_accepted_when_advisory():
    critic = PeerReviewCritic(strict=False)
    result = _execution_result(metadata={"response": "I cannot verify this figure but the total is 42."})

    verdict = critic.review(
        capability_id="cap", execution_result=result, mechanical_verification_passed=True
    )

    assert critic.strict is False
    assert verdict.accepted is True  # advisory: flag recorded but not blocking
    assert "advisory" in verdict.reason


def test_consistent_response_is_accepted():
    critic = PeerReviewCritic()
    result = _execution_result(metadata={"response": "The invoice total is 100 USD, paid in full."})

    verdict = critic.review(
        capability_id="cap", execution_result=result, mechanical_verification_passed=True
    )

    assert verdict.accepted is True
    assert "consistent" in verdict.reason
    assert 0.0 <= verdict.confidence <= 1.0


def test_no_reviewable_text_abstains_and_accepts():
    # Monotone-skeptic + honest scope: with no model text, defer to the proof.
    critic = PeerReviewCritic()
    result = _execution_result(metadata={"rows_written": 3}, effects=(EffectRecord(name="db_write", details={"n": 3}),))

    verdict = critic.review(
        capability_id="cap", execution_result=result, mechanical_verification_passed=True
    )

    assert verdict.accepted is True
    assert "abstain" in verdict.reason
    assert verdict.confidence == 0.5


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------


def test_extract_prefers_metadata_then_extensions_then_effects():
    md = _execution_result(metadata={"response": "from-metadata"}, extensions={"output": "from-ext"})
    _, response_md = extract_reviewable_text(md)
    assert response_md == "from-metadata"

    ext = _execution_result(extensions={"output": "from-ext"})
    _, response_ext = extract_reviewable_text(ext)
    assert response_ext == "from-ext"

    eff = _execution_result(effects=(EffectRecord(name="say", details="from-effect"),))
    _, response_eff = extract_reviewable_text(eff)
    assert response_eff == "from-effect"


def test_extract_returns_empty_when_no_text_surface():
    result = _execution_result(metadata={"count": 1}, effects=(EffectRecord(name="noop", details={"k": 1}),))
    prompt, response = extract_reviewable_text(result)
    assert prompt == ""
    assert response == ""
    assert (prompt, response) == ("", "")


def test_review_is_deterministic():
    critic = PeerReviewCritic()
    result = _execution_result(metadata={"response": "Actually, that's not correct."})
    a = critic.review(capability_id="cap", execution_result=result, mechanical_verification_passed=True)
    b = critic.review(capability_id="cap", execution_result=result, mechanical_verification_passed=True)
    assert a.accepted == b.accepted
    assert a.reason == b.reason
    assert a.confidence == b.confidence


# --------------------------------------------------------------------------
# End-to-end through the real CognitiveLoop (wired, not green-but-unwired)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubVerification:
    passed: bool


@dataclass(frozen=True)
class _StubDispatchResult:
    execution_result: ExecutionResult
    verification: _StubVerification


def _policy_decision() -> PolicyDecision:
    return PolicyDecision(
        decision_id="dec-1",
        subject_id="subject-1",
        goal_id="goal-1",
        status=PolicyDecisionStatus.ALLOW,
        reasons=(DecisionReason(message="allowed", code="ok"),),
        issued_at="2026-01-01T00:00:00Z",
    )


def _request() -> CognitiveStepRequest:
    return CognitiveStepRequest(
        goal_id="goal-1",
        capability_id="noop",
        template={"action_type": "noop"},
        policy_decision=_policy_decision(),
        bindings={},
        hard_constraints=(),
    )


def _loop_with_response_text(response_text: str) -> CognitiveLoop:
    """A loop whose (mechanically passing) dispatch returns the given model text."""

    def _dispatch(governed, request, *, policy_decision, issued_at, actor_id):
        return _StubDispatchResult(
            execution_result=_execution_result(metadata={"response": response_text}),
            verification=_StubVerification(passed=True),  # mechanical proof PASSES
        )

    return CognitiveLoop(
        governed_dispatcher=object(),
        world_state=WorldStateEngine(),
        episodic_memory=EpisodicMemory(),
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        decision_learning=DecisionLearningEngine(clock=_clock),
        clock=_clock,
        inner_critic=PeerReviewCritic(strict=True),
        dispatch_fn=_dispatch,
        max_steps=1,
        step_budget=1,
    )


def test_end_to_end_critic_downgrades_hallucinated_but_passing_outcome():
    # Mechanical proof passes, but the model text contradicts itself => the
    # critic must downgrade SOLVED_VERIFIED to SOLVED_UNVERIFIED and NOT learn.
    loop = _loop_with_response_text("Actually, that's not correct, I was wrong about the total.")
    report = loop.run(_request())

    assert report.terminal_outcome is SolverOutcome.SOLVED_UNVERIFIED
    assert report.steps[0].verification_passed is True  # mechanical proof did pass
    assert report.steps[0].critic_accepted is False  # but the critic refused
    assert report.learning_admission_count == 0  # vetoed => not admitted


def test_end_to_end_clean_text_stays_verified_and_learns():
    loop = _loop_with_response_text("The invoice total is 100 USD, paid in full on 2026-01-01.")
    report = loop.run(_request())

    assert report.terminal_outcome is SolverOutcome.SOLVED_VERIFIED
    assert report.steps[0].critic_accepted is True
    assert report.learning_admission_count == 1
