"""Tests for the record-only cognitive shadow observer.

Verifies the observer (1) maps engine signals to the SAME DECIDE verdicts the live
loop uses, (2) is strictly read-only (never writes back to any engine), (3) is
deterministic (identical inputs -> identical report hash), and (4) flags divergence
between the live outcome and what the cognitive DECIDE gate would have done.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.cognitive_loop import (
    DecisionVerdict,
    HardConstraint,
    ProofState,
    decide_verdict,
)
from mcoi_runtime.core.cognitive_shadow import (
    CognitiveShadowReport,
    ShadowCognitiveObserver,
)


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _FakeConfidence:
    def __init__(self, overall: float) -> None:
        self.overall_confidence = overall


class _FakeMeta:
    """Read-only meta-reasoning fake that records any (forbidden) writes."""

    def __init__(self, *, confidence: float | None = None, degraded: bool = False) -> None:
        self._confidence = confidence
        self._degraded = degraded
        self.update_calls = 0

    def get_confidence(self, capability_id: str):
        if self._confidence is None:
            return None
        return _FakeConfidence(self._confidence)

    def is_degraded(self, capability_id: str) -> bool:
        return self._degraded

    def update_confidence(self, confidence) -> None:  # must never be called
        self.update_calls += 1


class _FakeWorldState:
    def __init__(self, entity_count: int = 0) -> None:
        self._entities = tuple(range(entity_count))

    def list_entities(self):
        return self._entities


class _FakeEntry:
    def __init__(self, content: dict) -> None:
        self.content = content


class _FakeEpisodic:
    def __init__(self, entries=()) -> None:
        self._entries = tuple(entries)
        self.admit_calls = 0

    def list_entries(self):
        return self._entries

    def admit(self, entry):  # must never be called by the observer
        self.admit_calls += 1
        return entry


def _observer(*, confidence=None, degraded=False, entity_count=0, entries=()):
    return ShadowCognitiveObserver(
        meta_reasoning=_FakeMeta(confidence=confidence, degraded=degraded),
        world_state=_FakeWorldState(entity_count),
        episodic_memory=_FakeEpisodic(entries),
        clock=_clock,
    )


def test_confident_capability_proceeds_no_block():
    obs = _observer(confidence=0.9)
    report = obs.observe(capability_id="research", live_succeeded=True)
    assert isinstance(report, CognitiveShadowReport)
    assert report.decision_verdict is DecisionVerdict.PROCEED
    assert report.would_have_blocked is False
    assert report.diverged is False


def test_caution_band_does_not_block():
    obs = _observer(confidence=0.4)
    report = obs.observe(capability_id="research", live_succeeded=True)
    assert report.decision_verdict is DecisionVerdict.PROCEED_WITH_CAUTION
    assert report.would_have_blocked is False


def test_unseen_capability_is_neutral_and_proceeds():
    obs = _observer(confidence=None)  # get_confidence -> None -> neutral 0.5
    report = obs.observe(capability_id="never_seen", live_succeeded=True)
    assert report.confidence == pytest.approx(0.5)
    assert report.decision_verdict is DecisionVerdict.PROCEED


def test_degraded_low_confidence_defers_and_diverges():
    obs = _observer(confidence=0.1, degraded=True)
    report = obs.observe(capability_id="flaky", live_succeeded=True)
    assert report.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert report.would_have_blocked is True
    # Live path succeeded but DECIDE would have withheld dispatch -> divergence.
    assert report.diverged is True


def test_unknown_hard_constraint_blocks():
    obs = _observer(confidence=0.9)
    constraint = HardConstraint(
        constraint_id="c1", description="unproven safety law", proof_state=ProofState.UNKNOWN
    )
    report = obs.observe(
        capability_id="research", live_succeeded=False, hard_constraints=(constraint,)
    )
    assert report.decision_verdict is DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT
    assert report.would_have_blocked is True
    # Live did not succeed, so a block is not a divergence.
    assert report.diverged is False


def test_observer_never_writes_back_to_engines():
    meta = _FakeMeta(confidence=0.2, degraded=True)
    episodic = _FakeEpisodic()
    obs = ShadowCognitiveObserver(
        meta_reasoning=meta,
        world_state=_FakeWorldState(3),
        episodic_memory=episodic,
        clock=_clock,
    )
    obs.observe(capability_id="research", live_succeeded=True)
    # Strictly read-only: no confidence update, no episodic admission.
    assert meta.update_calls == 0
    assert episodic.admit_calls == 0


def test_prior_outcomes_counted_by_capability_key():
    entries = (
        _FakeEntry({"capability_id": "research"}),
        _FakeEntry({"route": "research"}),
        _FakeEntry({"capability_id": "other"}),
    )
    obs = _observer(confidence=0.9, entries=entries)
    report = obs.observe(capability_id="research", live_succeeded=True)
    assert report.observed_prior_outcomes == 2
    assert report.observed_planning_entities == 0


def test_planning_entities_counted():
    obs = _observer(confidence=0.9, entity_count=5)
    report = obs.observe(capability_id="research", live_succeeded=True)
    assert report.observed_planning_entities == 5


def test_deterministic_report_hash_for_identical_inputs():
    a = _observer(confidence=0.9, entity_count=2)
    b = _observer(confidence=0.9, entity_count=2)
    ra = a.observe(capability_id="research", live_succeeded=True)
    rb = b.observe(capability_id="research", live_succeeded=True)
    assert ra.report_hash == rb.report_hash


def test_recent_reports_are_bounded():
    obs = ShadowCognitiveObserver(
        meta_reasoning=_FakeMeta(confidence=0.9),
        world_state=_FakeWorldState(),
        episodic_memory=_FakeEpisodic(),
        clock=_clock,
        max_recent=2,
    )
    for _ in range(3):
        obs.observe(capability_id="research", live_succeeded=True)
    assert len(obs.recent_reports()) == 2


def test_observe_requires_capability_id():
    obs = _observer(confidence=0.9)
    with pytest.raises(Exception):
        obs.observe(capability_id="", live_succeeded=True)


def test_decide_verdict_pure_function_matches_bands():
    # Direct coverage of the shared pure DECIDE logic.
    assert decide_verdict(confidence=0.9, degraded=False)[0] is DecisionVerdict.PROCEED
    assert decide_verdict(confidence=0.4, degraded=False)[0] is DecisionVerdict.PROCEED_WITH_CAUTION
    assert decide_verdict(confidence=0.1, degraded=False)[0] is DecisionVerdict.REPLAN
    assert decide_verdict(confidence=0.1, degraded=True)[0] is DecisionVerdict.DEFER_TO_REVIEW
    assert decide_verdict(confidence=0.9, degraded=True)[0] is DecisionVerdict.REPLAN
