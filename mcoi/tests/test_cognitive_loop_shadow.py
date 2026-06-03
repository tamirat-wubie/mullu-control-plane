"""Tests for Stage-A shadow mode (CognitiveLoop.shadow_observe).

The defining invariant of shadow mode is SIDE-EFFECT FREEDOM: judging an
already-produced dispatch outcome must NOT dispatch and must NOT mutate any
engine (episodic memory, meta-reasoning confidence, decision-learning). If that
holds, attaching shadow mode to the live path cannot perturb production.

Covers: side-effect freedom (the key safety property), would-block judgement
(degraded + unknown-hard-constraint), would-downgrade via inner critic,
would_admission disposition, determinism, and that no dispatch_fn is ever called.
>=3 assertions per test.
"""
from __future__ import annotations

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.cognitive_loop import (
    CognitiveLoop,
    CognitiveStepRequest,
    DecisionVerdict,
    HardConstraint,
    ProofState,
    ShadowObservation,
)
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.peer_review_critic import PeerReviewCritic
from mcoi_runtime.core.world_state import WorldStateEngine


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


def _exploding_dispatch(*args, **kwargs):
    raise AssertionError("shadow_observe must NEVER dispatch")


def _execution_result(
    status: ExecutionOutcome = ExecutionOutcome.SUCCEEDED,
    *,
    metadata: dict | None = None,
    governance_blocked: bool = False,
    execution_id: str = "exec-1",
) -> ExecutionResult:
    effects = (
        (EffectRecord(name="governance_blocked", details={"gate": "policy"}),)
        if governance_blocked
        else ()
    )
    md = dict(metadata or {})
    if governance_blocked:
        md["gates_failed"] = ["policy"]
    return ExecutionResult(
        execution_id=execution_id,
        goal_id="goal-1",
        status=status,
        actual_effects=effects,
        assumed_effects=(),
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        metadata=md,
    )


def _policy_decision() -> PolicyDecision:
    return PolicyDecision(
        decision_id="dec-1",
        subject_id="subject-1",
        goal_id="goal-1",
        status=PolicyDecisionStatus.ALLOW,
        reasons=(DecisionReason(message="allowed", code="ok"),),
        issued_at="2026-01-01T00:00:00Z",
    )


def _request(**overrides) -> CognitiveStepRequest:
    base = dict(
        goal_id="goal-1",
        capability_id="noop",
        template={"action_type": "noop"},
        policy_decision=_policy_decision(),
        bindings={},
        hard_constraints=(),
    )
    base.update(overrides)
    return CognitiveStepRequest(**base)


def _loop(*, episodic=None, meta=None, learning=None, critic=None) -> CognitiveLoop:
    return CognitiveLoop(
        governed_dispatcher=object(),
        world_state=WorldStateEngine(),
        episodic_memory=episodic or EpisodicMemory(),
        meta_reasoning=meta or MetaReasoningEngine(clock=_clock),
        decision_learning=learning or DecisionLearningEngine(clock=_clock),
        clock=_clock,
        inner_critic=critic,
        dispatch_fn=_exploding_dispatch,  # proves shadow never dispatches
    )


# --------------------------------------------------------------------------
# THE key invariant: side-effect freedom
# --------------------------------------------------------------------------


def test_shadow_observe_does_not_dispatch_or_mutate_engines():
    episodic = EpisodicMemory()
    meta = MetaReasoningEngine(clock=_clock)
    learning = DecisionLearningEngine(clock=_clock)
    loop = _loop(episodic=episodic, meta=meta, learning=learning)

    before_episodic = episodic.size
    before_conf = meta.get_confidence("noop")
    before_outcomes = learning.outcome_count

    # A clean, verified result that WOULD admit if this were the live path.
    obs = loop.shadow_observe(
        _request(),
        _execution_result(metadata={"response": "all good, total is 100"}),
        mechanical_verification_passed=True,
    )

    assert isinstance(obs, ShadowObservation)
    # Nothing mutated: episodic unchanged, no confidence created, no outcome recorded.
    assert episodic.size == before_episodic
    assert meta.get_confidence("noop") == before_conf  # still None / unchanged
    assert learning.outcome_count == before_outcomes
    # And the dispatch_fn (which raises) was never called - reaching here proves it.
    assert obs.would_admission is LearningAdmissionStatus.ADMIT  # would-, not did-


# --------------------------------------------------------------------------
# would-block judgement (what Stage B would enforce)
# --------------------------------------------------------------------------


def test_unknown_hard_constraint_would_block():
    loop = _loop()
    obs = loop.shadow_observe(
        _request(
            hard_constraints=(
                HardConstraint(constraint_id="safety-1", description="hard law", proof_state=ProofState.UNKNOWN),
            )
        ),
        _execution_result(),
        mechanical_verification_passed=True,
    )
    assert obs.would_block_dispatch is True
    assert obs.decision_verdict is DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT
    assert "unknown" in obs.block_reason.lower()


def test_degraded_capability_would_block():
    meta = MetaReasoningEngine(clock=_clock)
    meta.update_confidence(
        CapabilityConfidence(
            capability_id="noop",
            success_rate=0.05,
            verification_pass_rate=0.05,
            timeout_rate=0.0,
            error_rate=0.9,
            sample_count=20,
            assessed_at=_clock(),
        )
    )
    assert meta.is_degraded("noop") is True
    loop = _loop(meta=meta)

    obs = loop.shadow_observe(_request(), _execution_result(), mechanical_verification_passed=True)

    assert obs.capability_was_degraded is True
    assert obs.would_block_dispatch is True
    assert obs.decision_verdict in (DecisionVerdict.DEFER_TO_REVIEW, DecisionVerdict.REPLAN)


def test_healthy_capability_would_proceed():
    loop = _loop()
    obs = loop.shadow_observe(_request(), _execution_result(), mechanical_verification_passed=True)
    assert obs.would_block_dispatch is False
    assert obs.decision_verdict in (DecisionVerdict.PROCEED, DecisionVerdict.PROCEED_WITH_CAUTION)
    assert obs.capability_was_degraded is False


# --------------------------------------------------------------------------
# would-downgrade via inner critic (what Stage C would refuse to learn)
# --------------------------------------------------------------------------


def test_critic_would_downgrade_hallucinated_but_passing_result():
    loop = _loop(critic=PeerReviewCritic(strict=True))
    obs = loop.shadow_observe(
        _request(),
        _execution_result(metadata={"response": "Actually, that's not correct, I was wrong about the total."}),
        mechanical_verification_passed=True,
    )
    assert obs.mechanical_verification_passed is True  # mechanical proof DID pass
    assert obs.critic_accepted is False  # but the critic would refuse
    assert obs.would_be_verified is False
    assert obs.would_admission is LearningAdmissionStatus.DEFER  # not learned


def test_governance_blocked_result_would_reject():
    loop = _loop()
    obs = loop.shadow_observe(
        _request(),
        _execution_result(status=ExecutionOutcome.FAILED, governance_blocked=True),
        mechanical_verification_passed=False,
    )
    assert obs.would_be_verified is False
    assert obs.would_admission is LearningAdmissionStatus.REJECT
    assert obs.critic_accepted is None  # critic not consulted on a non-passing proof


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------


def test_shadow_observe_is_deterministic():
    obs_a = _loop().shadow_observe(_request(), _execution_result(), mechanical_verification_passed=True)
    obs_b = _loop().shadow_observe(_request(), _execution_result(), mechanical_verification_passed=True)
    assert obs_a.observation_hash == obs_b.observation_hash
    assert obs_a.decision_verdict == obs_b.decision_verdict
    assert obs_a.would_admission == obs_b.would_admission


def test_shadow_observation_is_frozen():
    obs = _loop().shadow_observe(_request(), _execution_result(), mechanical_verification_passed=True)
    import dataclasses

    assert dataclasses.is_dataclass(obs)
    try:
        obs.would_block_dispatch = True  # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised is True
    assert isinstance(obs.observation_hash, str) and obs.observation_hash
