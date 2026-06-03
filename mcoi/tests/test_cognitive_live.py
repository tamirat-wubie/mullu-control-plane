"""Tests for the live-acting cognitive components (Stage B gate + Stage C learner).

Verifies the gate is safety-positive (only blocking verdicts block; everything else
is allowed), and the learner is deterministic + rollback-safe (admits an episodic
outcome only on a verified success, keyed on a unique source_ref).
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.cognitive_live import (
    CognitiveExecutionGate,
    CognitiveLearner,
    GateDecision,
)
from mcoi_runtime.core.cognitive_loop import (
    DecisionVerdict,
    HardConstraint,
    ProofState,
    next_capability_confidence,
)
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _FakeConfidence:
    def __init__(self, overall: float) -> None:
        self.overall_confidence = overall


class _FakeMeta:
    def __init__(self, *, confidence: float | None = None, degraded: bool = False) -> None:
        self._confidence = confidence
        self._degraded = degraded

    def get_confidence(self, capability_id: str):
        return _FakeConfidence(self._confidence) if self._confidence is not None else None

    def is_degraded(self, capability_id: str) -> bool:
        return self._degraded


# ---------------- Stage B: CognitiveExecutionGate ----------------

def test_gate_allows_confident_capability():
    gate = CognitiveExecutionGate(meta_reasoning=_FakeMeta(confidence=0.9))
    decision = gate.evaluate(capability_id="research")
    assert isinstance(decision, GateDecision)
    assert decision.decision_verdict is DecisionVerdict.PROCEED
    assert decision.blocked is False


def test_gate_does_not_block_on_replan():
    # Low confidence (no degraded) => REPLAN, which is NOT a block (parity with today).
    gate = CognitiveExecutionGate(meta_reasoning=_FakeMeta(confidence=0.1))
    decision = gate.evaluate(capability_id="research")
    assert decision.decision_verdict is DecisionVerdict.REPLAN
    assert decision.blocked is False


def test_gate_blocks_on_degraded_low_confidence():
    gate = CognitiveExecutionGate(meta_reasoning=_FakeMeta(confidence=0.1, degraded=True))
    decision = gate.evaluate(capability_id="flaky")
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert decision.blocked is True


def test_gate_blocks_on_unknown_hard_constraint():
    gate = CognitiveExecutionGate(meta_reasoning=_FakeMeta(confidence=0.9))
    constraint = HardConstraint(
        constraint_id="c1", description="unproven safety law", proof_state=ProofState.UNKNOWN
    )
    decision = gate.evaluate(capability_id="research", hard_constraints=(constraint,))
    assert decision.decision_verdict is DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT
    assert decision.blocked is True


def test_gate_unseen_capability_is_neutral_and_allowed():
    gate = CognitiveExecutionGate(meta_reasoning=_FakeMeta(confidence=None))
    decision = gate.evaluate(capability_id="never_seen")
    assert decision.confidence == pytest.approx(0.5)
    assert decision.blocked is False


# ---------------- Stage C: CognitiveLearner ----------------

def _learner():
    meta = MetaReasoningEngine(clock=_clock)
    episodic = EpisodicMemory()
    return CognitiveLearner(meta_reasoning=meta, episodic_memory=episodic, clock=_clock), meta, episodic


def test_learner_updates_confidence_and_admits_on_verified_success():
    learner, meta, episodic = _learner()
    record = learner.learn(capability_id="research", succeeded=True, verified=True, source_ref="wf-1")
    conf = meta.get_confidence("research")
    assert conf is not None and conf.success_rate == 1.0
    assert record.admitted_entry_id is not None
    assert len(episodic.list_entries()) == 1


def test_learner_is_rollback_safe_on_failure():
    learner, meta, episodic = _learner()
    record = learner.learn(capability_id="research", succeeded=False, verified=False, source_ref="wf-1")
    # No episodic admission on a non-verified outcome.
    assert record.admitted_entry_id is None
    assert len(episodic.list_entries()) == 0
    conf = meta.get_confidence("research")
    assert conf is not None and conf.success_rate == 0.0


def test_learner_distinct_source_refs_admit_separately():
    learner, _meta, episodic = _learner()
    learner.learn(capability_id="research", succeeded=True, verified=True, source_ref="wf-1")
    learner.learn(capability_id="research", succeeded=True, verified=True, source_ref="wf-2")
    assert len(episodic.list_entries()) == 2


def test_learner_requires_source_ref():
    learner, _meta, _episodic = _learner()
    with pytest.raises(Exception):
        learner.learn(capability_id="research", succeeded=True, verified=True, source_ref="")


def test_next_capability_confidence_is_pure_and_incremental():
    at = "2026-06-03T00:00:00Z"
    c1 = next_capability_confidence(None, capability_id="x", succeeded=True, verified=True, assessed_at=at)
    assert c1.success_rate == 1.0
    assert c1.sample_count == 1
    c2 = next_capability_confidence(c1, capability_id="x", succeeded=False, verified=False, assessed_at=at)
    assert c2.sample_count == 2
    assert c2.success_rate == 0.5
