"""Comprehensive tests for AutonomousImprovementEngine.

Covers: constructor, policy management, candidate evaluation, session
management, learning windows, rollback triggers, suppression, outcome
assessment, properties, state hash, event emission, and 8 golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.autonomous_improvement import AutonomousImprovementEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.autonomous_improvement import (
    AutonomyLevel,
    AutonomyPolicy,
    ImprovementCandidate,
    ImprovementDisposition,
    ImprovementOutcome,
    ImprovementOutcomeVerdict,
    ImprovementSession,
    LearningWindow,
    LearningWindowStatus,
    RollbackTrigger,
    SuppressionReason,
    SuppressionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> tuple[AutonomousImprovementEngine, EventSpineEngine]:
    es = EventSpineEngine()
    engine = AutonomousImprovementEngine(event_spine=es)
    return engine, es


def _register_default_policy(
    engine: AutonomousImprovementEngine,
    policy_id: str = "pol-1",
    change_type: str = "",
    **kwargs,
) -> AutonomyPolicy:
    defaults = dict(
        min_confidence=0.8,
        max_risk_score=0.3,
        max_cost_delta=100.0,
        max_auto_changes_per_window=5,
        require_approval_above_cost=500.0,
        require_approval_above_risk=0.5,
        failure_suppression_threshold=3,
        learning_window_seconds=3600.0,
        rollback_tolerance_pct=5.0,
        enabled=True,
    )
    defaults.update(kwargs)
    return engine.register_policy(policy_id, change_type, **defaults)


def _auto_promote_candidate(
    engine: AutonomousImprovementEngine,
    candidate_id: str = "cand-1",
    change_type: str = "",
    scope_ref_id: str = "scope-1",
) -> ImprovementCandidate:
    """Evaluate a candidate that should pass all policy checks."""
    return engine.evaluate_candidate(
        candidate_id,
        "rec-1",
        "Auto-promote test",
        change_type=change_type,
        scope_ref_id=scope_ref_id,
        confidence=0.95,
        estimated_improvement_pct=10.0,
        estimated_cost_delta=50.0,
        risk_score=0.1,
    )


# =========================================================================
# TestConstructor
# =========================================================================


class TestConstructor:
    def test_valid_construction(self):
        engine, es = _make_engine()
        assert engine.candidate_count == 0
        assert engine.session_count == 0

    def test_invalid_event_spine_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementEngine(event_spine="not-an-engine")  # type: ignore


# =========================================================================
# TestPolicyManagement
# =========================================================================


class TestPolicyManagement:
    def test_register_and_get_policy(self):
        engine, _ = _make_engine()
        policy = _register_default_policy(engine, "pol-1")
        assert isinstance(policy, AutonomyPolicy)
        assert policy.policy_id == "pol-1"
        assert engine.get_policy("pol-1") is policy

    def test_duplicate_policy_raises(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, "pol-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            _register_default_policy(engine, "pol-1")
        assert "pol-1" not in str(exc_info.value)

    def test_get_missing_policy_returns_none(self):
        engine, _ = _make_engine()
        assert engine.get_policy("nonexistent") is None

    def test_find_policy_for_type_specific_match(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, "pol-default", change_type="")
        _register_default_policy(engine, "pol-deploy", change_type="deploy")
        found = engine.find_policy_for_type("deploy")
        assert found is not None
        assert found.policy_id == "pol-deploy"

    def test_find_policy_for_type_fallback_to_default(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, "pol-default", change_type="")
        found = engine.find_policy_for_type("unknown-type")
        assert found is not None
        assert found.policy_id == "pol-default"

    def test_find_policy_for_type_no_match(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, "pol-deploy", change_type="deploy")
        found = engine.find_policy_for_type("config")
        assert found is None


# =========================================================================
# TestCandidateEvaluation
# =========================================================================


class TestCandidateEvaluation:
    def test_auto_promote_high_confidence_low_risk_low_cost(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Good change",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=50.0,
        )
        assert c.disposition is ImprovementDisposition.AUTO_PROMOTED
        assert c.autonomy_level is AutonomyLevel.BOUNDED_AUTO

    def test_approval_required_low_confidence(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, min_confidence=0.8)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Low conf",
            confidence=0.5, risk_score=0.1, estimated_cost_delta=10.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert c.autonomy_level is AutonomyLevel.APPROVAL_REQUIRED

    def test_approval_required_high_risk(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_risk_score=0.3)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "High risk",
            confidence=0.9, risk_score=0.4, estimated_cost_delta=10.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED

    def test_approval_required_high_cost(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_cost_delta=100.0)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "High cost",
            confidence=0.9, risk_score=0.1, estimated_cost_delta=200.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED

    def test_suppressed_pattern_blocks_auto_promotion(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.MANUAL_BLOCK)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Suppressed change",
            change_type="deploy", scope_ref_id="svc-1",
            confidence=0.99, risk_score=0.0, estimated_cost_delta=0.0,
        )
        assert c.disposition is ImprovementDisposition.SUPPRESSED
        assert c.autonomy_level is AutonomyLevel.FULL_HUMAN

    def test_no_policy_yields_approval_required(self):
        engine, _ = _make_engine()
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "No policy",
            confidence=0.99, risk_score=0.0, estimated_cost_delta=0.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert c.autonomy_level is AutonomyLevel.APPROVAL_REQUIRED

    def test_disabled_policy_yields_approval_required(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, enabled=False)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Disabled",
            confidence=0.99, risk_score=0.0, estimated_cost_delta=0.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED

    def test_auto_change_limit_reached(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_auto_changes_per_window=2)
        # Promote two candidates to fill the window
        for i in range(2):
            engine.evaluate_candidate(
                f"cand-{i}", f"rec-{i}", f"Auto {i}",
                confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
            )
        assert engine.auto_change_count == 2
        # Third should be blocked
        c = engine.evaluate_candidate(
            "cand-blocked", "rec-b", "Blocked",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert "limit reached" in c.reason

    def test_risk_above_require_approval_above_risk_yields_full_human(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_risk_score=0.3, require_approval_above_risk=0.5)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Very risky",
            confidence=0.95, risk_score=0.6, estimated_cost_delta=10.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert c.autonomy_level is AutonomyLevel.FULL_HUMAN

    def test_cost_above_require_approval_above_cost_yields_full_human(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_cost_delta=100.0, require_approval_above_cost=500.0)
        c = engine.evaluate_candidate(
            "cand-1", "rec-1", "Very expensive",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=600.0,
        )
        assert c.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert c.autonomy_level is AutonomyLevel.FULL_HUMAN

    def test_duplicate_candidate_raises(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            _auto_promote_candidate(engine, "cand-1")
        assert "cand-1" not in str(exc_info.value)


# =========================================================================
# TestSessionManagement
# =========================================================================


class TestSessionManagement:
    def test_start_and_get_session(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        session = engine.start_session("sess-1", "cand-1", change_id="chg-1")
        assert isinstance(session, ImprovementSession)
        assert session.session_id == "sess-1"
        assert session.candidate_id == "cand-1"
        assert engine.get_session("sess-1") is session

    def test_get_missing_session_returns_none(self):
        engine, _ = _make_engine()
        assert engine.get_session("nonexistent") is None

    def test_duplicate_session_raises(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            engine.start_session("sess-1", "cand-1")
        assert "sess-1" not in str(exc_info.value)

    def test_missing_candidate_raises(self):
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            engine.start_session("sess-1", "no-such-candidate")
        assert "no-such-candidate" not in str(exc_info.value)


# =========================================================================
# TestLearningWindows
# =========================================================================


class TestLearningWindows:
    def test_open_learning_window(self):
        engine, _ = _make_engine()
        w = engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        assert isinstance(w, LearningWindow)
        assert w.window_id == "win-1"
        assert w.baseline_value == 100.0
        assert w.current_value == 100.0
        assert w.status is LearningWindowStatus.ACTIVE
        assert w.samples_collected == 0

    def test_record_observation_improvement_pct(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        w = engine.record_observation("win-1", 110.0)
        assert w.current_value == 110.0
        assert w.improvement_pct == pytest.approx(10.0)
        assert w.samples_collected == 1

    def test_record_observation_samples_increment(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        engine.record_observation("win-1", 105.0)
        w = engine.record_observation("win-1", 110.0)
        assert w.samples_collected == 2

    def test_multiple_observations(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "throughput", 200.0)
        engine.record_observation("win-1", 210.0)
        engine.record_observation("win-1", 220.0)
        w = engine.record_observation("win-1", 230.0)
        assert w.samples_collected == 3
        # improvement_pct based on baseline and latest observation
        assert w.improvement_pct == pytest.approx(15.0)

    def test_close_learning_window(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        engine.record_observation("win-1", 110.0)
        w = engine.close_learning_window("win-1")
        assert w.status is LearningWindowStatus.COMPLETED
        assert w.completed_at != ""

    def test_duplicate_window_raises(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            engine.open_learning_window("win-1", "chg-2", "latency_ms", 100.0)
        assert "win-1" not in str(exc_info.value)

    def test_observe_non_active_window_raises(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "latency_ms", 100.0)
        engine.close_learning_window("win-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active") as exc_info:
            engine.record_observation("win-1", 110.0)
        assert "win-1" not in str(exc_info.value)

    def test_observe_missing_window_raises(self):
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.record_observation("no-window", 110.0)

    def test_baseline_zero_improvement_calc(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-1", "chg-1", "errors", 0.0)
        w = engine.record_observation("win-1", 5.0)
        assert w.improvement_pct == 0.0


# =========================================================================
# TestRollbackTriggers
# =========================================================================


class TestRollbackTriggers:
    def test_trigger_fires_on_degradation(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, rollback_tolerance_pct=5.0)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        # 20% degradation (100 -> 80) exceeds 5% tolerance
        trigger = engine.check_rollback_trigger(
            "chg-1", "sess-1", "throughput", 100.0, 80.0,
        )
        assert trigger is not None
        assert isinstance(trigger, RollbackTrigger)
        assert trigger.degradation_pct == pytest.approx(20.0)

    def test_no_trigger_below_tolerance(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, rollback_tolerance_pct=5.0)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        # 2% degradation (100 -> 98) is below 5% tolerance
        trigger = engine.check_rollback_trigger(
            "chg-1", "sess-1", "throughput", 100.0, 98.0,
        )
        assert trigger is None

    def test_custom_tolerance_pct(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, rollback_tolerance_pct=5.0)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        # 3% degradation with custom tolerance of 2% should fire
        trigger = engine.check_rollback_trigger(
            "chg-1", "sess-1", "throughput", 100.0, 97.0, tolerance_pct=2.0,
        )
        assert trigger is not None

    def test_baseline_zero_returns_none(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        trigger = engine.check_rollback_trigger(
            "chg-1", "sess-1", "errors", 0.0, 5.0,
        )
        assert trigger is None

    def test_get_rollback_triggers_returns_tuple(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, rollback_tolerance_pct=5.0)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        engine.check_rollback_trigger("chg-1", "sess-1", "tp", 100.0, 70.0)
        triggers = engine.get_rollback_triggers()
        assert isinstance(triggers, tuple)
        assert len(triggers) == 1


# =========================================================================
# TestSuppression
# =========================================================================


class TestSuppression:
    def test_record_failure_below_threshold_returns_none(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, failure_suppression_threshold=3)
        result = engine.record_failure("deploy", "svc-1")
        assert result is None

    def test_record_failure_at_threshold_suppresses(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, failure_suppression_threshold=3)
        engine.record_failure("deploy", "svc-1")
        engine.record_failure("deploy", "svc-1")
        result = engine.record_failure("deploy", "svc-1")
        assert result is not None
        assert isinstance(result, SuppressionRecord)
        assert result.reason is SuppressionReason.REPEATED_FAILURE
        assert engine.is_suppressed("deploy", "svc-1")

    def test_is_suppressed_true_false(self):
        engine, _ = _make_engine()
        assert engine.is_suppressed("deploy", "svc-1") is False
        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.MANUAL_BLOCK)
        assert engine.is_suppressed("deploy", "svc-1") is True

    def test_suppress_pattern_manual(self):
        engine, _ = _make_engine()
        rec = engine.suppress_pattern("config", "db-1", SuppressionReason.COST_EXCEEDED)
        assert isinstance(rec, SuppressionRecord)
        assert rec.change_type == "config"
        assert rec.reason is SuppressionReason.COST_EXCEEDED

    def test_get_suppressions(self):
        engine, _ = _make_engine()
        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.MANUAL_BLOCK)
        engine.suppress_pattern("config", "db-1", SuppressionReason.DEGRADED_KPI)
        supps = engine.get_suppressions()
        assert isinstance(supps, tuple)
        assert len(supps) == 2


# =========================================================================
# TestOutcomeAssessment
# =========================================================================


class TestOutcomeAssessment:
    def _setup_session(self, engine):
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        engine.start_session("sess-1", "cand-1", change_id="chg-1")

    def test_improved_outcome(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        outcome = engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=110.0, confidence=0.9,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert outcome.improvement_pct == pytest.approx(10.0)
        assert outcome.reinforcement_applied is True
        assert outcome.rollback_triggered is False

    def test_degraded_outcome_triggers_rollback_and_failure(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        outcome = engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=80.0, confidence=0.9,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.DEGRADED
        assert outcome.rollback_triggered is True

    def test_neutral_outcome(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        outcome = engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=100.5, confidence=0.9,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.NEUTRAL
        assert outcome.rollback_triggered is False
        assert outcome.reinforcement_applied is False

    def test_inconclusive_low_confidence(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        outcome = engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=100.0, confidence=0.3,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.INCONCLUSIVE

    def test_missing_session_raises(self):
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            engine.assess_outcome("out-1", "no-session")
        assert "no-session" not in str(exc_info.value)

    def test_session_updated_after_assessment(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=110.0, confidence=0.9,
        )
        session = engine.get_session("sess-1")
        assert session is not None
        assert session.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert session.disposition is ImprovementDisposition.COMPLETED
        assert session.completed_at != ""

    def test_degraded_session_is_rolled_back(self):
        engine, _ = _make_engine()
        self._setup_session(engine)
        engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=80.0, confidence=0.9,
        )
        session = engine.get_session("sess-1")
        assert session is not None
        assert session.disposition is ImprovementDisposition.ROLLED_BACK
        assert session.rollback_triggered is True


# =========================================================================
# TestProperties
# =========================================================================


class TestProperties:
    def test_counts_after_operations(self):
        engine, _ = _make_engine()
        assert engine.candidate_count == 0
        assert engine.session_count == 0
        assert engine.outcome_count == 0
        assert engine.suppression_count == 0
        assert engine.auto_change_count == 0

        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        assert engine.candidate_count == 1
        assert engine.auto_change_count == 1

        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        assert engine.session_count == 1

        engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=110.0, confidence=0.9,
        )
        assert engine.outcome_count == 1

        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.MANUAL_BLOCK)
        assert engine.suppression_count == 1


# =========================================================================
# TestStateHash
# =========================================================================


class TestStateHash:
    def test_deterministic(self):
        engine, _ = _make_engine()
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_mutation(self):
        engine, _ = _make_engine()
        h1 = engine.state_hash()
        _register_default_policy(engine)
        _auto_promote_candidate(engine, "cand-1")
        h2 = engine.state_hash()
        assert h1 != h2


# =========================================================================
# TestEventEmission
# =========================================================================


class TestEventEmission:
    def test_events_emitted_for_all_mutations(self):
        engine, es = _make_engine()
        initial_count = len(es.list_events())

        # register_policy emits 1 event
        _register_default_policy(engine)
        after_policy = len(es.list_events())
        assert after_policy > initial_count

        # evaluate_candidate emits 1 event
        _auto_promote_candidate(engine, "cand-1")
        after_candidate = len(es.list_events())
        assert after_candidate > after_policy

        # start_session emits 1 event
        engine.start_session("sess-1", "cand-1", change_id="chg-1")
        after_session = len(es.list_events())
        assert after_session > after_candidate

        # open_learning_window emits 1 event
        engine.open_learning_window("win-1", "chg-1", "latency", 100.0)
        after_window = len(es.list_events())
        assert after_window > after_session

        # close_learning_window emits 1 event
        engine.close_learning_window("win-1")
        after_close = len(es.list_events())
        assert after_close > after_window

        # assess_outcome emits 1 event
        engine.assess_outcome(
            "out-1", "sess-1",
            baseline_value=100.0, final_value=110.0, confidence=0.9,
        )
        after_outcome = len(es.list_events())
        assert after_outcome > after_close

        # suppress_pattern emits 1 event
        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.MANUAL_BLOCK)
        after_suppress = len(es.list_events())
        assert after_suppress > after_outcome


# =========================================================================
# Golden Scenarios
# =========================================================================


class TestGoldenScenario1HappyPath:
    """register policy -> evaluate (auto-promote) -> session -> window ->
    observe -> close -> assess (improved) -> reinforcement"""

    def test_full_happy_path(self):
        engine, es = _make_engine()

        # Step 1: register policy
        policy = _register_default_policy(engine)
        assert policy.enabled is True

        # Step 2: evaluate candidate (auto-promote)
        candidate = engine.evaluate_candidate(
            "cand-hp", "rec-hp", "Happy path change",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=50.0,
            change_type="", scope_ref_id="svc-hp",
        )
        assert candidate.disposition is ImprovementDisposition.AUTO_PROMOTED
        assert candidate.autonomy_level is AutonomyLevel.BOUNDED_AUTO

        # Step 3: start session
        session = engine.start_session("sess-hp", "cand-hp", change_id="chg-hp")
        assert session.candidate_id == "cand-hp"

        # Step 4: open learning window
        window = engine.open_learning_window(
            "win-hp", "chg-hp", "response_time_ms", 200.0,
        )
        assert window.baseline_value == 200.0

        # Step 5: observe improvements
        w = engine.record_observation("win-hp", 190.0)
        assert w.improvement_pct == pytest.approx(-5.0)
        w = engine.record_observation("win-hp", 180.0)
        assert w.improvement_pct == pytest.approx(-10.0)

        # Step 6: close learning window
        w = engine.close_learning_window("win-hp")
        assert w.status is LearningWindowStatus.COMPLETED

        # Step 7: assess outcome (improved -- lower latency is better,
        # use higher final for positive improvement direction)
        outcome = engine.assess_outcome(
            "out-hp", "sess-hp",
            baseline_value=100.0, final_value=115.0, confidence=0.95,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert outcome.reinforcement_applied is True
        assert outcome.rollback_triggered is False

        # Session updated
        sess = engine.get_session("sess-hp")
        assert sess is not None
        assert sess.verdict is ImprovementOutcomeVerdict.IMPROVED

        # Events emitted
        assert len(es.list_events()) > 0


class TestGoldenScenario2LowConfidenceApproval:
    """Low confidence -> approval required -> session -> assess (neutral)"""

    def test_low_confidence_path(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, min_confidence=0.8)

        candidate = engine.evaluate_candidate(
            "cand-lc", "rec-lc", "Low confidence change",
            confidence=0.5, risk_score=0.1, estimated_cost_delta=10.0,
        )
        assert candidate.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert candidate.autonomy_level is AutonomyLevel.APPROVAL_REQUIRED

        session = engine.start_session("sess-lc", "cand-lc")
        outcome = engine.assess_outcome(
            "out-lc", "sess-lc",
            baseline_value=100.0, final_value=100.3, confidence=0.9,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.NEUTRAL


class TestGoldenScenario3HighRiskFullHuman:
    """High risk above approval threshold -> FULL_HUMAN"""

    def test_high_risk_full_human(self):
        engine, _ = _make_engine()
        _register_default_policy(
            engine, max_risk_score=0.3, require_approval_above_risk=0.5,
        )

        candidate = engine.evaluate_candidate(
            "cand-hr", "rec-hr", "Very risky change",
            confidence=0.95, risk_score=0.7, estimated_cost_delta=10.0,
        )
        assert candidate.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert candidate.autonomy_level is AutonomyLevel.FULL_HUMAN


class TestGoldenScenario4SuppressedBlocks:
    """Suppressed pattern blocks auto-promotion"""

    def test_suppressed_blocks(self):
        engine, _ = _make_engine()
        _register_default_policy(engine)

        engine.suppress_pattern("deploy", "svc-1", SuppressionReason.REPEATED_FAILURE)
        assert engine.is_suppressed("deploy", "svc-1") is True

        candidate = engine.evaluate_candidate(
            "cand-sup", "rec-sup", "Suppressed deploy",
            change_type="deploy", scope_ref_id="svc-1",
            confidence=0.99, risk_score=0.0, estimated_cost_delta=0.0,
        )
        assert candidate.disposition is ImprovementDisposition.SUPPRESSED
        assert candidate.autonomy_level is AutonomyLevel.FULL_HUMAN


class TestGoldenScenario5AutoChangeLimitReached:
    """Auto-change limit reached -> approval required"""

    def test_auto_change_limit(self):
        engine, _ = _make_engine()
        _register_default_policy(engine, max_auto_changes_per_window=3)

        for i in range(3):
            c = engine.evaluate_candidate(
                f"cand-al-{i}", f"rec-al-{i}", f"Auto {i}",
                confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
            )
            assert c.disposition is ImprovementDisposition.AUTO_PROMOTED

        assert engine.auto_change_count == 3

        blocked = engine.evaluate_candidate(
            "cand-al-blocked", "rec-al-b", "Should be blocked",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
        )
        assert blocked.disposition is ImprovementDisposition.APPROVAL_REQUIRED
        assert "limit reached" in blocked.reason


class TestGoldenScenario6DegradedRollbackSuppression:
    """Degraded outcome -> rollback + failure recorded -> suppression at threshold"""

    def test_degraded_chain(self):
        engine, _ = _make_engine()
        _register_default_policy(
            engine, change_type="deploy", failure_suppression_threshold=2,
        )

        # First degraded outcome
        engine.evaluate_candidate(
            "cand-d1", "rec-d1", "Degraded change 1",
            change_type="deploy", scope_ref_id="svc-d",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
        )
        engine.start_session("sess-d1", "cand-d1", change_id="chg-d1")
        out1 = engine.assess_outcome(
            "out-d1", "sess-d1",
            baseline_value=100.0, final_value=80.0, confidence=0.9,
        )
        assert out1.verdict is ImprovementOutcomeVerdict.DEGRADED
        assert out1.rollback_triggered is True
        # First failure, threshold is 2, so not yet suppressed
        assert out1.suppression_triggered is False
        assert engine.is_suppressed("deploy", "svc-d") is False

        # Second degraded outcome for same pattern
        engine.evaluate_candidate(
            "cand-d2", "rec-d2", "Degraded change 2",
            change_type="deploy", scope_ref_id="svc-d",
            confidence=0.95, risk_score=0.1, estimated_cost_delta=10.0,
        )
        engine.start_session("sess-d2", "cand-d2", change_id="chg-d2")
        out2 = engine.assess_outcome(
            "out-d2", "sess-d2",
            baseline_value=100.0, final_value=75.0, confidence=0.9,
        )
        assert out2.verdict is ImprovementOutcomeVerdict.DEGRADED
        assert out2.rollback_triggered is True
        assert out2.suppression_triggered is True
        assert engine.is_suppressed("deploy", "svc-d") is True


class TestGoldenScenario7LearningWindowMultipleObservations:
    """Learning window with multiple observations"""

    def test_multiple_observations(self):
        engine, _ = _make_engine()
        engine.open_learning_window("win-mo", "chg-mo", "qps", 1000.0)

        observations = [1050.0, 1100.0, 1080.0, 1120.0, 1150.0]
        for val in observations:
            w = engine.record_observation("win-mo", val)

        assert w.samples_collected == 5
        # Last observation: (1150 - 1000) / 1000 * 100 = 15%
        assert w.improvement_pct == pytest.approx(15.0)
        assert w.current_value == 1150.0

        closed = engine.close_learning_window("win-mo")
        assert closed.status is LearningWindowStatus.COMPLETED
        assert closed.samples_collected == 5


class TestGoldenScenario8FullLifecycle:
    """Full lifecycle: policy -> candidate -> session -> window -> rollback
    trigger check -> assess"""

    def test_full_lifecycle(self):
        engine, es = _make_engine()

        # Policy
        policy = _register_default_policy(
            engine, "pol-lc", change_type="scaling",
            rollback_tolerance_pct=10.0,
        )
        assert policy.change_type == "scaling"

        # Candidate
        candidate = engine.evaluate_candidate(
            "cand-lc", "rec-lc", "Scale up workers",
            change_type="scaling", scope_ref_id="worker-pool",
            confidence=0.9, risk_score=0.2, estimated_cost_delta=80.0,
        )
        assert candidate.disposition is ImprovementDisposition.AUTO_PROMOTED

        # Session
        session = engine.start_session("sess-lc", "cand-lc", change_id="chg-lc")
        assert session.session_id == "sess-lc"

        # Learning window
        window = engine.open_learning_window(
            "win-lc", "chg-lc", "p99_latency_ms", 500.0,
            candidate_id="cand-lc",
        )
        engine.record_observation("win-lc", 480.0)
        engine.record_observation("win-lc", 460.0)
        engine.close_learning_window("win-lc")

        # Rollback trigger check -- no trigger expected (improvement)
        trigger = engine.check_rollback_trigger(
            "chg-lc", "sess-lc", "p99_latency_ms", 500.0, 460.0,
        )
        # 8% degradation is < 10% tolerance -- actually 460 < 500, so
        # degradation = (500-460)/500*100 = 8%, which is < 10%
        assert trigger is None

        # Now check with degradation exceeding tolerance
        trigger2 = engine.check_rollback_trigger(
            "chg-lc", "sess-lc", "error_rate", 100.0, 80.0,
        )
        # 20% degradation > 10% tolerance
        assert trigger2 is not None
        assert trigger2.degradation_pct == pytest.approx(20.0)

        # Assess outcome (improved overall)
        outcome = engine.assess_outcome(
            "out-lc", "sess-lc",
            baseline_value=500.0, final_value=520.0, confidence=0.85,
        )
        assert outcome.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert outcome.reinforcement_applied is True

        # Verify counts
        assert engine.candidate_count == 1
        assert engine.session_count == 1
        assert engine.outcome_count == 1
        assert len(engine.get_rollback_triggers()) == 1

        # Events emitted throughout
        assert len(es.list_events()) >= 7
