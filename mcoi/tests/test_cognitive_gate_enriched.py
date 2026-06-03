"""Stage E - safety-positive cognitive gate enrichment.

Covers:
  - pure monotone enrichment helpers;
  - bad-input degradation;
  - CognitiveExecutionGate enriched ON/OFF behavior;
  - fail-open behavior for broken episodic reads;
  - env composition through build_execution_gate.
"""

from __future__ import annotations

from itertools import product

import pytest

from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_ENFORCE_ENV,
    COGNITIVE_LOOP_GATE_ENRICHED_ENV,
    build_execution_gate,
    validate_gate_enriched_config,
)
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.core.cognitive_gate_enrichment import (
    VERDICT_RANK,
    enrich_verdict,
    more_restrictive_verdict,
)
from mcoi_runtime.core.cognitive_live import CognitiveExecutionGate
from mcoi_runtime.core.cognitive_loop import DecisionVerdict
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine


def _clock() -> str:
    return "2026-06-03T12:00:00Z"


def _meta_with_confidence(capability_id: str, confidence: float) -> MetaReasoningEngine:
    """Build meta confidence records whose overall_confidence equals confidence."""
    meta = MetaReasoningEngine(clock=_clock)
    meta.update_confidence(
        CapabilityConfidence(
            capability_id=capability_id,
            success_rate=confidence,
            verification_pass_rate=1.0,
            timeout_rate=0.0,
            error_rate=0.0,
            sample_count=1,
            assessed_at=_clock(),
        )
    )
    return meta


def _episodic_with_outcomes(capability_id: str, outcomes: tuple[bool, ...]) -> EpisodicMemory:
    episodic = EpisodicMemory()
    for index, succeeded in enumerate(outcomes):
        episodic.admit(
            MemoryEntry(
                entry_id=f"outcome-{capability_id}-{index}",
                tier=MemoryTier.EPISODIC,
                category="cognitive_loop_outcome",
                content={
                    "capability_id": capability_id,
                    "route": capability_id,
                    "succeeded": succeeded,
                    "verified": True,
                    "source_ref": f"wf-{index}",
                },
                source_ids=(f"wf-{index}",),
            )
        )
    return episodic


class _Organs:
    def __init__(self, *, meta, episodic=None) -> None:
        self.meta_reasoning = meta
        if episodic is not None:
            self.episodic_memory = episodic


class _RaisingEpisodic:
    def list_entries(self, *, category=None):  # noqa: ARG002
        raise RuntimeError("synthetic episodic failure")


# ---------- pure helper tests ----------


@pytest.mark.parametrize("verdict", tuple(DecisionVerdict))
def test_more_restrictive_verdict_tie_returns_left(verdict):
    assert more_restrictive_verdict(verdict, verdict) is verdict


@pytest.mark.parametrize("left,right", product(tuple(DecisionVerdict), repeat=2))
def test_more_restrictive_verdict_is_commutative_by_rank(left, right):
    a = more_restrictive_verdict(left, right)
    b = more_restrictive_verdict(right, left)
    assert VERDICT_RANK[a] == VERDICT_RANK[b]
    assert VERDICT_RANK[a] == max(VERDICT_RANK[left], VERDICT_RANK[right])


def test_more_restrictive_verdict_rejects_non_verdict():
    with pytest.raises(RuntimeCoreInvariantError):
        more_restrictive_verdict(DecisionVerdict.PROCEED, "replan")


def test_enrich_e1_caution_with_no_evidence_defers_to_review():
    assert (
        enrich_verdict(
            DecisionVerdict.PROCEED_WITH_CAUTION,
            prior_outcomes_count=0,
            prior_success_count=0,
        )
        is DecisionVerdict.DEFER_TO_REVIEW
    )


def test_enrich_e1_caution_with_evidence_stays_caution():
    assert (
        enrich_verdict(
            DecisionVerdict.PROCEED_WITH_CAUTION,
            prior_outcomes_count=1,
            prior_success_count=1,
        )
        is DecisionVerdict.PROCEED_WITH_CAUTION
    )


def test_enrich_e2_replan_with_bad_track_record_defers_to_review():
    assert (
        enrich_verdict(
            DecisionVerdict.REPLAN,
            prior_outcomes_count=3,
            prior_success_count=1,
        )
        is DecisionVerdict.DEFER_TO_REVIEW
    )


def test_enrich_e2_replan_with_good_track_record_stays_replan():
    assert (
        enrich_verdict(
            DecisionVerdict.REPLAN,
            prior_outcomes_count=3,
            prior_success_count=2,
        )
        is DecisionVerdict.REPLAN
    )


@pytest.mark.parametrize("today", tuple(DecisionVerdict))
@pytest.mark.parametrize("total", [-1, 0, 1, 2, 3, 4, 10])
@pytest.mark.parametrize("success", [-1, 0, 1, 2, 3, 4, 11])
def test_enrich_verdict_is_monotone_over_input_space(today, total, success):
    enriched = enrich_verdict(
        today,
        prior_outcomes_count=total,
        prior_success_count=success,
    )
    assert VERDICT_RANK[enriched] >= VERDICT_RANK[today]


@pytest.mark.parametrize(
    ("total", "success"),
    [(-1, 0), (0, -1), (1, 2), ("3", 1), (3, "1")],
)
def test_enrich_bad_priors_returns_today_unchanged(total, success):
    assert (
        enrich_verdict(
            DecisionVerdict.PROCEED_WITH_CAUTION,
            prior_outcomes_count=total,
            prior_success_count=success,
        )
        is DecisionVerdict.PROCEED_WITH_CAUTION
    )


# ---------- gate behavior ----------


def test_unenriched_gate_does_not_read_episodic_and_stays_byte_identical():
    gate = CognitiveExecutionGate(
        meta_reasoning=_meta_with_confidence("cap.A", 0.4),
        episodic_memory=_RaisingEpisodic(),
        enriched=False,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.PROCEED_WITH_CAUTION
    assert decision.blocked is False


def test_enriched_gate_uses_zero_evidence_to_defer_caution():
    gate = CognitiveExecutionGate(
        meta_reasoning=_meta_with_confidence("cap.A", 0.4),
        episodic_memory=EpisodicMemory(),
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert decision.blocked is True


def test_enriched_gate_uses_bad_track_record_to_defer_replan():
    gate = CognitiveExecutionGate(
        meta_reasoning=_meta_with_confidence("cap.A", 0.2),
        episodic_memory=_episodic_with_outcomes("cap.A", (False, False, True)),
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert decision.blocked is True


def test_enriched_gate_ignores_other_capability_outcomes():
    episodic = _episodic_with_outcomes("other.cap", (True, True, True))
    gate = CognitiveExecutionGate(
        meta_reasoning=_meta_with_confidence("cap.A", 0.4),
        episodic_memory=episodic,
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    # No outcomes for cap.A specifically => E1 fires.
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW


def test_enriched_gate_read_failure_preserves_today_verdict_not_zero_evidence():
    gate = CognitiveExecutionGate(
        meta_reasoning=_meta_with_confidence("cap.A", 0.4),
        episodic_memory=_RaisingEpisodic(),
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    # Read failure is unknown, not "zero evidence". It must not spuriously defer.
    assert decision.decision_verdict is DecisionVerdict.PROCEED_WITH_CAUTION
    assert decision.blocked is False


def test_enriched_gate_requires_episodic_memory():
    with pytest.raises(RuntimeCoreInvariantError):
        CognitiveExecutionGate(
            meta_reasoning=_meta_with_confidence("cap.A", 0.4),
            enriched=True,
        )


# ---------- integration builder ----------


def test_validate_gate_enriched_config_truthy():
    assert validate_gate_enriched_config({COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"}).enabled is True


def test_validate_gate_enriched_config_malformed_fails_safe():
    report = validate_gate_enriched_config({COGNITIVE_LOOP_GATE_ENRICHED_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None


def test_build_execution_gate_returns_none_when_enforce_off():
    organs = _Organs(meta=_meta_with_confidence("cap.A", 0.4), episodic=EpisodicMemory())
    assert build_execution_gate({COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"}, organs) is None


def test_build_execution_gate_enriched_when_both_flags_on():
    organs = _Organs(meta=_meta_with_confidence("cap.A", 0.4), episodic=EpisodicMemory())
    gate = build_execution_gate(
        {COGNITIVE_LOOP_ENFORCE_ENV: "1", COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"},
        organs,
    )
    assert isinstance(gate, CognitiveExecutionGate)
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW


def test_build_execution_gate_enforce_on_enrichment_off_unenriched():
    organs = _Organs(meta=_meta_with_confidence("cap.A", 0.4), episodic=EpisodicMemory())
    gate = build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "1"}, organs)
    assert isinstance(gate, CognitiveExecutionGate)
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.PROCEED_WITH_CAUTION


def test_build_execution_gate_enrichment_on_missing_episodic_falls_back_unenriched():
    organs = _Organs(meta=_meta_with_confidence("cap.A", 0.4))
    gate = build_execution_gate(
        {COGNITIVE_LOOP_ENFORCE_ENV: "1", COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"},
        organs,
    )
    assert isinstance(gate, CognitiveExecutionGate)
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.PROCEED_WITH_CAUTION
