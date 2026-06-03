"""Stage E - safety-positive gate-enrichment for CognitiveExecutionGate.

Covers:
  * more_restrictive_verdict commutativity + tie-handling.
  * enrich_verdict per-rule behaviour (E1 PROCEED_WITH_CAUTION + zero priors,
    E2 REPLAN + bad track record).
  * **The monotone-safety invariant**: for every (today_verdict, prior_total,
    prior_success) input in a representative grid,
    _VERDICT_RANK[enrich_verdict(...)] >= _VERDICT_RANK[today_verdict]. This is
    the by-construction proof that enrichment can ONLY add a refusal, never
    remove one - the safety property that lets Stage E ship behind a single
    env flag without regressing the gate's existing safety-positivity.
  * Bad-input degradation (negative counts, success > total, non-int): always
    returns today_verdict unchanged so a buggy priors read cannot cause a
    spurious refusal.
  * CognitiveExecutionGate evaluate() with enrichment ON and OFF:
    - OFF (default): byte-identical to today; episodic_memory is never read.
    - ON: prior episodic outcomes are read and may escalate the verdict.
    - ON + raising episodic: the read fail-OPENs to (0, 0), so the verdict
      degrades to today's verdict (never spuriously refuses).
  * build_execution_gate composition: both env flags + organs combine to the
    enriched gate; either missing falls back to the unenriched gate or None.
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
from mcoi_runtime.core.cognitive_live import CognitiveExecutionGate
from mcoi_runtime.core.cognitive_loop import (
    DecisionVerdict,
    _VERDICT_RANK,
    enrich_verdict,
    more_restrictive_verdict,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine


def _clock() -> str:
    return "2026-06-03T12:00:00+00:00"


# ---------- more_restrictive_verdict ----------


@pytest.mark.parametrize(
    "a,b",
    list(product(DecisionVerdict, DecisionVerdict)),
)
def test_more_restrictive_verdict_picks_higher_rank(a, b):
    result = more_restrictive_verdict(a, b)
    assert _VERDICT_RANK[result] == max(_VERDICT_RANK[a], _VERDICT_RANK[b])


def test_more_restrictive_verdict_tie_returns_left():
    # Stable tie-breaker so the function is deterministic for snapshot tests.
    assert (
        more_restrictive_verdict(DecisionVerdict.REPLAN, DecisionVerdict.REPLAN)
        is DecisionVerdict.REPLAN
    )


def test_more_restrictive_verdict_rejects_non_enum_input():
    with pytest.raises(RuntimeCoreInvariantError):
        more_restrictive_verdict("proceed", DecisionVerdict.PROCEED)  # type: ignore[arg-type]
    with pytest.raises(RuntimeCoreInvariantError):
        more_restrictive_verdict(DecisionVerdict.PROCEED, None)  # type: ignore[arg-type]


# ---------- enrich_verdict per-rule ----------


def test_enrich_verdict_e1_proceed_with_caution_zero_priors_escalates():
    result = enrich_verdict(
        DecisionVerdict.PROCEED_WITH_CAUTION,
        prior_outcomes_count=0,
        prior_success_count=0,
    )
    assert result is DecisionVerdict.DEFER_TO_REVIEW


def test_enrich_verdict_e1_does_not_fire_when_priors_exist():
    result = enrich_verdict(
        DecisionVerdict.PROCEED_WITH_CAUTION,
        prior_outcomes_count=1,
        prior_success_count=1,
    )
    assert result is DecisionVerdict.PROCEED_WITH_CAUTION


def test_enrich_verdict_e1_does_not_fire_for_proceed():
    # Plain PROCEED with zero priors stays PROCEED -- only the hedged
    # PROCEED_WITH_CAUTION verdict is the target of E1.
    result = enrich_verdict(
        DecisionVerdict.PROCEED,
        prior_outcomes_count=0,
        prior_success_count=0,
    )
    assert result is DecisionVerdict.PROCEED


def test_enrich_verdict_e2_replan_bad_track_record_escalates():
    # 3 priors, 0 success => success_rate 0.0 < 0.5 + sample >= 3 => escalate.
    result = enrich_verdict(
        DecisionVerdict.REPLAN,
        prior_outcomes_count=3,
        prior_success_count=0,
    )
    assert result is DecisionVerdict.DEFER_TO_REVIEW


def test_enrich_verdict_e2_does_not_fire_below_min_sample():
    # 2 priors, 0 success: even though success_rate 0.0 < 0.5, sample < 3
    # so the rule cannot fire (one or two failures is noise, not signal).
    result = enrich_verdict(
        DecisionVerdict.REPLAN,
        prior_outcomes_count=2,
        prior_success_count=0,
    )
    assert result is DecisionVerdict.REPLAN


def test_enrich_verdict_e2_does_not_fire_above_threshold():
    # 4 priors, 2 success => 0.5 success rate; strict < 0.5 so no fire.
    result = enrich_verdict(
        DecisionVerdict.REPLAN,
        prior_outcomes_count=4,
        prior_success_count=2,
    )
    assert result is DecisionVerdict.REPLAN


def test_enrich_verdict_e2_fires_just_below_threshold():
    # 5 priors, 2 success => 0.4 success rate, sample >= 3 => escalate.
    result = enrich_verdict(
        DecisionVerdict.REPLAN,
        prior_outcomes_count=5,
        prior_success_count=2,
    )
    assert result is DecisionVerdict.DEFER_TO_REVIEW


# ---------- the monotone-safety invariant (the by-construction proof) ----------


def _grid_inputs():
    """Representative input grid covering every verdict + each rule's hot zone."""
    counts = [
        (0, 0),
        (1, 0),
        (1, 1),
        (2, 0),
        (2, 1),
        (2, 2),
        (3, 0),
        (3, 1),
        (3, 2),
        (3, 3),
        (5, 0),
        (5, 2),
        (5, 3),
        (5, 5),
        (10, 4),
        (10, 9),
        (10, 10),
        # Edge cases that should fall back to today_verdict:
        (-1, 0),
        (0, -1),
        (1, 2),  # success > total
    ]
    for verdict, (total, success) in product(DecisionVerdict, counts):
        yield verdict, total, success


@pytest.mark.parametrize("today,total,success", list(_grid_inputs()))
def test_enrich_verdict_is_monotone_over_input_space(today, total, success):
    """Stage E's central safety guarantee.

    For every input in the representative grid, the enriched verdict must be
    at least as restrictive as today's. If this test ever fails, the
    enrichment can REMOVE a refusal (= regress safety), and Stage E must not
    ship until the offending rule is corrected.
    """
    enriched = enrich_verdict(
        today, prior_outcomes_count=total, prior_success_count=success
    )
    assert _VERDICT_RANK[enriched] >= _VERDICT_RANK[today], (
        f"enrich_verdict({today}, total={total}, success={success}) = "
        f"{enriched} (rank {_VERDICT_RANK[enriched]}) is LESS restrictive "
        f"than today (rank {_VERDICT_RANK[today]}). Safety-positive invariant "
        f"VIOLATED - the enrichment rule that produced this must be fixed "
        f"before Stage E can ship."
    )


# ---------- bad-input degradation ----------


@pytest.mark.parametrize(
    "total,success",
    [(-1, 0), (0, -1), (-5, -5), (1, 2), (10, 11)],
)
def test_enrich_verdict_bad_priors_return_today(total, success):
    # A buggy priors read must never cause enrichment to refuse; the function
    # treats bad inputs as "no usable evidence" and returns today_verdict.
    for today in DecisionVerdict:
        assert (
            enrich_verdict(today, prior_outcomes_count=total, prior_success_count=success)
            is today
        )


def test_enrich_verdict_rejects_non_enum_today():
    with pytest.raises(RuntimeCoreInvariantError):
        enrich_verdict("proceed", prior_outcomes_count=0, prior_success_count=0)  # type: ignore[arg-type]


def test_enrich_verdict_non_int_counts_return_today():
    for today in DecisionVerdict:
        assert (
            enrich_verdict(today, prior_outcomes_count="3", prior_success_count=1)  # type: ignore[arg-type]
            is today
        )
        assert (
            enrich_verdict(today, prior_outcomes_count=3, prior_success_count=None)  # type: ignore[arg-type]
            is today
        )


# ---------- CognitiveExecutionGate evaluate(): enrichment OFF (default) ----------


def _episodic_with_outcomes(capability_id: str, total: int, success: int) -> EpisodicMemory:
    episodic = EpisodicMemory()
    for i in range(total):
        succeeded = i < success
        episodic.admit(
            MemoryEntry(
                entry_id=f"{capability_id}-e{i}",
                tier=MemoryTier.EPISODIC,
                category="cognitive_loop_outcome",
                content={
                    "capability_id": capability_id,
                    "succeeded": succeeded,
                    "verified": True,
                },
                source_ids=(f"{capability_id}-e{i}",),
            )
        )
    return episodic


def test_gate_byte_identical_when_enriched_false():
    """Default-OFF gate is byte-identical to the pre-Stage-E behaviour."""
    meta = MetaReasoningEngine(clock=_clock)
    # An episodic engine with a damning track record must NOT affect the
    # verdict when enrichment is off.
    episodic = _episodic_with_outcomes("cap.A", total=10, success=0)
    gate_off = CognitiveExecutionGate(meta_reasoning=meta)
    gate_off_with_episodic = CognitiveExecutionGate(
        meta_reasoning=meta, episodic_memory=episodic, enriched=False
    )
    a = gate_off.evaluate(capability_id="cap.A")
    b = gate_off_with_episodic.evaluate(capability_id="cap.A")
    assert a == b


def test_gate_enriched_rejects_construction_without_episodic():
    meta = MetaReasoningEngine(clock=_clock)
    with pytest.raises(RuntimeCoreInvariantError):
        CognitiveExecutionGate(meta_reasoning=meta, enriched=True)


# ---------- gate evaluate() with enrichment ON ----------


class _DegradedMeta:
    """Force degraded=True so today_verdict in {DEFER_TO_REVIEW, REPLAN}."""

    def get_confidence(self, capability_id):  # noqa: ARG002 - protocol shape
        return None

    def is_degraded(self, capability_id):  # noqa: ARG002 - protocol shape
        return True


def test_gate_enriched_e2_escalates_replan_to_defer():
    # Degraded + neutral confidence (0.5) >= replan_threshold 0.3 => REPLAN.
    # With 4 priors / 0 success: E2 fires => DEFER_TO_REVIEW.
    episodic = _episodic_with_outcomes("cap.A", total=4, success=0)
    gate = CognitiveExecutionGate(
        meta_reasoning=_DegradedMeta(),
        episodic_memory=episodic,
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert decision.blocked is True


def test_gate_enriched_replan_with_good_track_record_stays_replan():
    # 4 priors / 4 success: E2 cannot fire => stays REPLAN (not blocking).
    episodic = _episodic_with_outcomes("cap.A", total=4, success=4)
    gate = CognitiveExecutionGate(
        meta_reasoning=_DegradedMeta(),
        episodic_memory=episodic,
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.REPLAN
    assert decision.blocked is False


def test_gate_enriched_filters_priors_by_capability_id():
    # Many bad priors for cap.OTHER must not affect cap.A's verdict.
    episodic = _episodic_with_outcomes("cap.OTHER", total=10, success=0)
    gate = CognitiveExecutionGate(
        meta_reasoning=_DegradedMeta(),
        episodic_memory=episodic,
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.REPLAN  # no priors for cap.A


class _RaisingEpisodic:
    def list_entries(self, *, category=None):  # noqa: ARG002 - protocol shape
        raise RuntimeError("synthetic-episodic-failure")


def test_gate_enriched_fail_open_when_episodic_raises():
    # A buggy episodic read must NEVER cause a spurious refusal; the gate
    # degrades to today's verdict (here REPLAN), never escalates blindly.
    gate = CognitiveExecutionGate(
        meta_reasoning=_DegradedMeta(),
        episodic_memory=_RaisingEpisodic(),
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    assert decision.decision_verdict is DecisionVerdict.REPLAN
    assert decision.blocked is False


def test_gate_enriched_fail_open_on_malformed_entries():
    """An entry missing 'capability_id' is skipped, not counted as zero-priors."""

    class _SparseEpisodic:
        def list_entries(self, *, category=None):  # noqa: ARG002
            return (object(),)  # no .content; iteration must swallow it

    gate = CognitiveExecutionGate(
        meta_reasoning=_DegradedMeta(),
        episodic_memory=_SparseEpisodic(),
        enriched=True,
    )
    decision = gate.evaluate(capability_id="cap.A")
    # Malformed entries treated as no usable evidence; today's REPLAN stands.
    assert decision.decision_verdict is DecisionVerdict.REPLAN


# ---------- validate_gate_enriched_config + build_execution_gate ----------


@pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "TRUE"])
def test_validate_gate_enriched_config_truthy(raw):
    assert validate_gate_enriched_config({COGNITIVE_LOOP_GATE_ENRICHED_ENV: raw}).enabled is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", ""])
def test_validate_gate_enriched_config_falsy(raw):
    assert validate_gate_enriched_config({COGNITIVE_LOOP_GATE_ENRICHED_ENV: raw}).enabled is False


def test_validate_gate_enriched_config_malformed_fail_safe():
    report = validate_gate_enriched_config({COGNITIVE_LOOP_GATE_ENRICHED_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None


class _Organs:
    def __init__(self, *, meta_reasoning, episodic_memory=None):
        self.meta_reasoning = meta_reasoning
        self.episodic_memory = episodic_memory


def test_build_execution_gate_enforce_off_returns_none():
    organs = _Organs(meta_reasoning=MetaReasoningEngine(clock=_clock))
    assert build_execution_gate({}, organs) is None


def test_build_execution_gate_enforce_on_enrichment_off_builds_unenriched():
    organs = _Organs(
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        episodic_memory=EpisodicMemory(),
    )
    gate = build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "1"}, organs)
    assert isinstance(gate, CognitiveExecutionGate)
    # Default-OFF enrichment: episodic isn't consulted even though present.
    assert gate._enriched is False


def test_build_execution_gate_both_flags_on_episodic_present_builds_enriched():
    organs = _Organs(
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        episodic_memory=EpisodicMemory(),
    )
    gate = build_execution_gate(
        {COGNITIVE_LOOP_ENFORCE_ENV: "1", COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"},
        organs,
    )
    assert isinstance(gate, CognitiveExecutionGate)
    assert gate._enriched is True


def test_build_execution_gate_enrichment_on_episodic_missing_builds_unenriched():
    # Enrichment requested but no episodic engine -> degrade to unenriched
    # gate (still active under ENFORCE) rather than raising at startup.
    organs = _Organs(meta_reasoning=MetaReasoningEngine(clock=_clock))
    gate = build_execution_gate(
        {COGNITIVE_LOOP_ENFORCE_ENV: "1", COGNITIVE_LOOP_GATE_ENRICHED_ENV: "1"},
        organs,
    )
    assert isinstance(gate, CognitiveExecutionGate)
    assert gate._enriched is False
