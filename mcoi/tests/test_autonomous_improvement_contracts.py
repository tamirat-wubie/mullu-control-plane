"""Tests for mcoi_runtime.contracts.autonomous_improvement contracts."""

from __future__ import annotations

import dataclasses
import datetime as _dt
from types import MappingProxyType

import pytest

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

def _ts() -> str:
    """Return a valid ISO-8601 datetime string."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _make_improvement_candidate(**overrides) -> ImprovementCandidate:
    defaults = dict(
        candidate_id="cand-001",
        recommendation_id="rec-001",
        change_type="parameter_tune",
        scope_ref_id="scope-001",
        title="Increase batch size",
        confidence=0.85,
        estimated_improvement_pct=12.5,
        estimated_cost_delta=50.0,
        risk_score=0.2,
        disposition=ImprovementDisposition.PENDING,
        autonomy_level=AutonomyLevel.BOUNDED_AUTO,
        reason="Historical data suggests improvement",
        created_at=_ts(),
        metadata={"source": "auto"},
    )
    defaults.update(overrides)
    return ImprovementCandidate(**defaults)


def _make_autonomy_policy(**overrides) -> AutonomyPolicy:
    defaults = dict(
        policy_id="pol-001",
        change_type="parameter_tune",
        created_at=_ts(),
    )
    defaults.update(overrides)
    return AutonomyPolicy(**defaults)


def _make_learning_window(**overrides) -> LearningWindow:
    defaults = dict(
        window_id="win-001",
        change_id="chg-001",
        candidate_id="cand-001",
        metric_name="latency_p99",
        baseline_value=120.0,
        status=LearningWindowStatus.ACTIVE,
        current_value=110.0,
        improvement_pct=8.3,
        samples_collected=42,
        started_at=_ts(),
    )
    defaults.update(overrides)
    return LearningWindow(**defaults)


def _make_improvement_session(**overrides) -> ImprovementSession:
    defaults = dict(
        session_id="sess-001",
        candidate_id="cand-001",
        change_id="chg-001",
        autonomy_level=AutonomyLevel.BOUNDED_AUTO,
        disposition=ImprovementDisposition.AUTO_PROMOTED,
        verdict=ImprovementOutcomeVerdict.IMPROVED,
        improvement_pct=10.0,
        rollback_triggered=False,
        suppression_applied=False,
        learning_window_ids=("win-001",),
        started_at=_ts(),
        metadata={"run": 1},
    )
    defaults.update(overrides)
    return ImprovementSession(**defaults)


def _make_suppression_record(**overrides) -> SuppressionRecord:
    defaults = dict(
        suppression_id="sup-001",
        change_type="parameter_tune",
        scope_ref_id="scope-001",
        reason=SuppressionReason.REPEATED_FAILURE,
        failure_count=3,
        suppressed_at=_ts(),
    )
    defaults.update(overrides)
    return SuppressionRecord(**defaults)


def _make_improvement_outcome(**overrides) -> ImprovementOutcome:
    defaults = dict(
        outcome_id="out-001",
        session_id="sess-001",
        candidate_id="cand-001",
        change_id="chg-001",
        verdict=ImprovementOutcomeVerdict.IMPROVED,
        baseline_value=120.0,
        final_value=108.0,
        improvement_pct=10.0,
        confidence=0.92,
        rollback_triggered=False,
        suppression_triggered=False,
        reinforcement_applied=True,
        assessed_at=_ts(),
        metadata={"notes": "good"},
    )
    defaults.update(overrides)
    return ImprovementOutcome(**defaults)


def _make_rollback_trigger(**overrides) -> RollbackTrigger:
    defaults = dict(
        trigger_id="rb-001",
        change_id="chg-001",
        session_id="sess-001",
        metric_name="error_rate",
        baseline_value=0.01,
        observed_value=0.08,
        degradation_pct=700.0,
        triggered_at=_ts(),
    )
    defaults.update(overrides)
    return RollbackTrigger(**defaults)


# ---------------------------------------------------------------------------
# Enum membership tests
# ---------------------------------------------------------------------------

class TestEnumMembers:
    def test_improvement_disposition_count(self):
        assert len(ImprovementDisposition) == 8

    def test_improvement_disposition_values(self):
        expected = {
            "PENDING", "AUTO_PROMOTED", "APPROVAL_REQUIRED", "SUPPRESSED",
            "REJECTED", "COMPLETED", "ROLLED_BACK", "FAILED",
        }
        assert {m.name for m in ImprovementDisposition} == expected

    def test_autonomy_level_count(self):
        assert len(AutonomyLevel) == 4

    def test_autonomy_level_values(self):
        expected = {"FULL_HUMAN", "APPROVAL_REQUIRED", "BOUNDED_AUTO", "FULL_AUTO"}
        assert {m.name for m in AutonomyLevel} == expected

    def test_improvement_outcome_verdict_count(self):
        assert len(ImprovementOutcomeVerdict) == 4

    def test_improvement_outcome_verdict_values(self):
        expected = {"IMPROVED", "NEUTRAL", "DEGRADED", "INCONCLUSIVE"}
        assert {m.name for m in ImprovementOutcomeVerdict} == expected

    def test_suppression_reason_count(self):
        assert len(SuppressionReason) == 5

    def test_suppression_reason_values(self):
        expected = {
            "REPEATED_FAILURE", "ROLLBACK_TRIGGERED", "DEGRADED_KPI",
            "COST_EXCEEDED", "MANUAL_BLOCK",
        }
        assert {m.name for m in SuppressionReason} == expected

    def test_learning_window_status_count(self):
        assert len(LearningWindowStatus) == 4

    def test_learning_window_status_values(self):
        expected = {"ACTIVE", "COMPLETED", "ABORTED", "TIMED_OUT"}
        assert {m.name for m in LearningWindowStatus} == expected


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------

class TestImprovementCandidateConstruction:
    def test_valid_construction(self):
        c = _make_improvement_candidate()
        assert c.candidate_id == "cand-001"
        assert c.confidence == 0.85
        assert c.risk_score == 0.2
        assert c.disposition is ImprovementDisposition.PENDING
        assert c.autonomy_level is AutonomyLevel.BOUNDED_AUTO

    def test_to_dict(self):
        c = _make_improvement_candidate()
        d = c.to_dict()
        assert isinstance(d, dict)
        assert d["candidate_id"] == "cand-001"


class TestAutonomyPolicyConstruction:
    def test_valid_construction(self):
        p = _make_autonomy_policy()
        assert p.policy_id == "pol-001"
        assert p.min_confidence == 0.8
        assert p.max_risk_score == 0.3
        assert p.max_cost_delta == 100.0
        assert p.max_auto_changes_per_window == 5
        assert p.require_approval_above_cost == 500.0
        assert p.require_approval_above_risk == 0.5
        assert p.failure_suppression_threshold == 3
        assert p.learning_window_seconds == 3600.0
        assert p.rollback_tolerance_pct == 5.0
        assert p.enabled is True

    def test_to_dict(self):
        p = _make_autonomy_policy()
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["policy_id"] == "pol-001"


class TestLearningWindowConstruction:
    def test_valid_construction(self):
        w = _make_learning_window()
        assert w.window_id == "win-001"
        assert w.status is LearningWindowStatus.ACTIVE
        assert w.samples_collected == 42
        assert w.duration_seconds == 3600.0

    def test_to_dict(self):
        w = _make_learning_window()
        d = w.to_dict()
        assert isinstance(d, dict)
        assert d["window_id"] == "win-001"


class TestImprovementSessionConstruction:
    def test_valid_construction(self):
        s = _make_improvement_session()
        assert s.session_id == "sess-001"
        assert s.autonomy_level is AutonomyLevel.BOUNDED_AUTO
        assert s.disposition is ImprovementDisposition.AUTO_PROMOTED
        assert s.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert s.rollback_triggered is False

    def test_to_dict(self):
        s = _make_improvement_session()
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["session_id"] == "sess-001"


class TestSuppressionRecordConstruction:
    def test_valid_construction(self):
        r = _make_suppression_record()
        assert r.suppression_id == "sup-001"
        assert r.reason is SuppressionReason.REPEATED_FAILURE
        assert r.failure_count == 3

    def test_to_dict(self):
        r = _make_suppression_record()
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["suppression_id"] == "sup-001"


class TestImprovementOutcomeConstruction:
    def test_valid_construction(self):
        o = _make_improvement_outcome()
        assert o.outcome_id == "out-001"
        assert o.verdict is ImprovementOutcomeVerdict.IMPROVED
        assert o.confidence == 0.92
        assert o.reinforcement_applied is True

    def test_to_dict(self):
        o = _make_improvement_outcome()
        d = o.to_dict()
        assert isinstance(d, dict)
        assert d["outcome_id"] == "out-001"


class TestRollbackTriggerConstruction:
    def test_valid_construction(self):
        t = _make_rollback_trigger()
        assert t.trigger_id == "rb-001"
        assert t.degradation_pct == 700.0
        assert t.tolerance_pct == 5.0

    def test_to_dict(self):
        t = _make_rollback_trigger()
        d = t.to_dict()
        assert isinstance(d, dict)
        assert d["trigger_id"] == "rb-001"


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------

class TestFrozenImmutability:
    def test_improvement_candidate_frozen(self):
        c = _make_improvement_candidate()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.candidate_id = "other"

    def test_autonomy_policy_frozen(self):
        p = _make_autonomy_policy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.policy_id = "other"

    def test_learning_window_frozen(self):
        w = _make_learning_window()
        with pytest.raises(dataclasses.FrozenInstanceError):
            w.window_id = "other"

    def test_improvement_session_frozen(self):
        s = _make_improvement_session()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.session_id = "other"

    def test_suppression_record_frozen(self):
        r = _make_suppression_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.suppression_id = "other"

    def test_improvement_outcome_frozen(self):
        o = _make_improvement_outcome()
        with pytest.raises(dataclasses.FrozenInstanceError):
            o.outcome_id = "other"

    def test_rollback_trigger_frozen(self):
        t = _make_rollback_trigger()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.trigger_id = "other"


# ---------------------------------------------------------------------------
# require_non_empty_text validation
# ---------------------------------------------------------------------------

class TestRequireNonEmptyText:
    def test_candidate_empty_candidate_id(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(candidate_id="")

    def test_candidate_empty_recommendation_id(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(recommendation_id="")

    def test_candidate_empty_title(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(title="")

    def test_policy_empty_policy_id(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(policy_id="")

    def test_learning_window_empty_window_id(self):
        with pytest.raises(ValueError):
            _make_learning_window(window_id="")

    def test_learning_window_empty_change_id(self):
        with pytest.raises(ValueError):
            _make_learning_window(change_id="")

    def test_learning_window_empty_metric_name(self):
        with pytest.raises(ValueError):
            _make_learning_window(metric_name="")

    def test_session_empty_session_id(self):
        with pytest.raises(ValueError):
            _make_improvement_session(session_id="")

    def test_session_empty_candidate_id(self):
        with pytest.raises(ValueError):
            _make_improvement_session(candidate_id="")

    def test_suppression_empty_suppression_id(self):
        with pytest.raises(ValueError):
            _make_suppression_record(suppression_id="")

    def test_suppression_empty_change_type(self):
        with pytest.raises(ValueError):
            _make_suppression_record(change_type="")

    def test_outcome_empty_outcome_id(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(outcome_id="")

    def test_outcome_empty_session_id(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(session_id="")

    def test_outcome_empty_candidate_id(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(candidate_id="")

    def test_rollback_empty_trigger_id(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(trigger_id="")

    def test_rollback_empty_change_id(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(change_id="")

    def test_rollback_empty_session_id(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(session_id="")

    def test_rollback_empty_metric_name(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(metric_name="")


# ---------------------------------------------------------------------------
# require_unit_float validation
# ---------------------------------------------------------------------------

class TestRequireUnitFloat:
    def test_candidate_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(confidence=-0.1)

    def test_candidate_confidence_above_one(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(confidence=1.1)

    def test_candidate_risk_score_below_zero(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(risk_score=-0.01)

    def test_candidate_risk_score_above_one(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(risk_score=1.5)

    def test_policy_min_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(min_confidence=-0.1)

    def test_policy_min_confidence_above_one(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(min_confidence=1.01)

    def test_policy_max_risk_score_below_zero(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(max_risk_score=-0.5)

    def test_policy_max_risk_score_above_one(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(max_risk_score=2.0)

    def test_policy_require_approval_above_risk_below_zero(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(require_approval_above_risk=-0.1)

    def test_policy_require_approval_above_risk_above_one(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(require_approval_above_risk=1.1)

    def test_outcome_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(confidence=-0.01)

    def test_outcome_confidence_above_one(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(confidence=1.001)


# ---------------------------------------------------------------------------
# require_non_negative_int validation
# ---------------------------------------------------------------------------

class TestRequireNonNegativeInt:
    def test_policy_max_auto_changes_per_window_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(max_auto_changes_per_window=-1)

    def test_policy_failure_suppression_threshold_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(failure_suppression_threshold=-1)

    def test_learning_window_samples_collected_negative(self):
        with pytest.raises(ValueError):
            _make_learning_window(samples_collected=-1)

    def test_suppression_failure_count_negative(self):
        with pytest.raises(ValueError):
            _make_suppression_record(failure_count=-1)


# ---------------------------------------------------------------------------
# require_non_negative_float validation
# ---------------------------------------------------------------------------

class TestRequireNonNegativeFloat:
    def test_policy_max_cost_delta_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(max_cost_delta=-1.0)

    def test_policy_require_approval_above_cost_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(require_approval_above_cost=-0.01)

    def test_policy_learning_window_seconds_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(learning_window_seconds=-1.0)

    def test_policy_rollback_tolerance_pct_negative(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(rollback_tolerance_pct=-0.5)

    def test_learning_window_duration_seconds_negative(self):
        with pytest.raises(ValueError):
            _make_learning_window(duration_seconds=-1.0)

    def test_rollback_tolerance_pct_negative(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(tolerance_pct=-0.1)


# ---------------------------------------------------------------------------
# require_datetime_text validation
# ---------------------------------------------------------------------------

class TestRequireDatetimeText:
    def test_candidate_invalid_created_at(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(created_at="not-a-date")

    def test_policy_invalid_created_at(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(created_at="nope")

    def test_learning_window_invalid_started_at(self):
        with pytest.raises(ValueError):
            _make_learning_window(started_at="bad-time")

    def test_session_invalid_started_at(self):
        with pytest.raises(ValueError):
            _make_improvement_session(started_at="xxx")

    def test_suppression_invalid_suppressed_at(self):
        with pytest.raises(ValueError):
            _make_suppression_record(suppressed_at="nah")

    def test_outcome_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(assessed_at="wrong")

    def test_rollback_invalid_triggered_at(self):
        with pytest.raises(ValueError):
            _make_rollback_trigger(triggered_at="invalid")


# ---------------------------------------------------------------------------
# Enum type validation
# ---------------------------------------------------------------------------

class TestEnumTypeValidation:
    def test_candidate_bad_disposition(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(disposition="PENDING")

    def test_candidate_bad_autonomy_level(self):
        with pytest.raises(ValueError):
            _make_improvement_candidate(autonomy_level="FULL_AUTO")

    def test_learning_window_bad_status(self):
        with pytest.raises(ValueError):
            _make_learning_window(status="ACTIVE")

    def test_session_bad_autonomy_level(self):
        with pytest.raises(ValueError):
            _make_improvement_session(autonomy_level="BOUNDED_AUTO")

    def test_session_bad_disposition(self):
        with pytest.raises(ValueError):
            _make_improvement_session(disposition="COMPLETED")

    def test_session_bad_verdict(self):
        with pytest.raises(ValueError):
            _make_improvement_session(verdict="IMPROVED")

    def test_suppression_bad_reason(self):
        with pytest.raises(ValueError):
            _make_suppression_record(reason="REPEATED_FAILURE")

    def test_outcome_bad_verdict(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(verdict="NEUTRAL")


# ---------------------------------------------------------------------------
# Bool type validation
# ---------------------------------------------------------------------------

class TestBoolTypeValidation:
    def test_policy_enabled_non_bool(self):
        with pytest.raises(ValueError):
            _make_autonomy_policy(enabled=1)

    def test_session_rollback_triggered_non_bool(self):
        with pytest.raises(ValueError):
            _make_improvement_session(rollback_triggered=1)

    def test_session_suppression_applied_non_bool(self):
        with pytest.raises(ValueError):
            _make_improvement_session(suppression_applied="false")

    def test_outcome_rollback_triggered_non_bool(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(rollback_triggered=0)

    def test_outcome_suppression_triggered_non_bool(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(suppression_triggered=0)

    def test_outcome_reinforcement_applied_non_bool(self):
        with pytest.raises(ValueError):
            _make_improvement_outcome(reinforcement_applied=1)


# ---------------------------------------------------------------------------
# freeze_value checks
# ---------------------------------------------------------------------------

class TestFreezeValue:
    def test_candidate_metadata_is_mapping_proxy(self):
        c = _make_improvement_candidate(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_session_metadata_is_mapping_proxy(self):
        s = _make_improvement_session(metadata={"run": 2})
        assert isinstance(s.metadata, MappingProxyType)

    def test_outcome_metadata_is_mapping_proxy(self):
        o = _make_improvement_outcome(metadata={"x": 1})
        assert isinstance(o.metadata, MappingProxyType)

    def test_session_learning_window_ids_is_tuple(self):
        s = _make_improvement_session(learning_window_ids=["win-a", "win-b"])
        assert isinstance(s.learning_window_ids, tuple)
        assert s.learning_window_ids == ("win-a", "win-b")

    def test_candidate_metadata_dict_frozen(self):
        c = _make_improvement_candidate(metadata={"a": 1})
        with pytest.raises(TypeError):
            c.metadata["a"] = 2  # type: ignore[index]

    def test_session_metadata_dict_frozen(self):
        s = _make_improvement_session(metadata={"a": 1})
        with pytest.raises(TypeError):
            s.metadata["a"] = 2  # type: ignore[index]


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_autonomy_policy_defaults(self):
        p = _make_autonomy_policy()
        assert p.min_confidence == 0.8
        assert p.max_risk_score == 0.3
        assert p.max_cost_delta == 100.0
        assert p.max_auto_changes_per_window == 5
        assert p.require_approval_above_cost == 500.0
        assert p.require_approval_above_risk == 0.5
        assert p.failure_suppression_threshold == 3
        assert p.learning_window_seconds == 3600.0
        assert p.rollback_tolerance_pct == 5.0
        assert p.enabled is True

    def test_learning_window_defaults(self):
        w = _make_learning_window()
        assert w.duration_seconds == 3600.0
        assert w.completed_at == ""

    def test_session_defaults(self):
        s = _make_improvement_session()
        assert s.completed_at == ""

    def test_suppression_defaults(self):
        r = _make_suppression_record()
        assert r.expires_at == ""

    def test_rollback_trigger_tolerance_default(self):
        t = _make_rollback_trigger()
        assert t.tolerance_pct == 5.0


# ---------------------------------------------------------------------------
# Edge case boundary values
# ---------------------------------------------------------------------------

class TestEdgeCaseBoundaries:
    def test_candidate_confidence_zero(self):
        c = _make_improvement_candidate(confidence=0.0)
        assert c.confidence == 0.0

    def test_candidate_confidence_one(self):
        c = _make_improvement_candidate(confidence=1.0)
        assert c.confidence == 1.0

    def test_candidate_risk_score_zero(self):
        c = _make_improvement_candidate(risk_score=0.0)
        assert c.risk_score == 0.0

    def test_candidate_risk_score_one(self):
        c = _make_improvement_candidate(risk_score=1.0)
        assert c.risk_score == 1.0

    def test_policy_min_confidence_zero(self):
        p = _make_autonomy_policy(min_confidence=0.0)
        assert p.min_confidence == 0.0

    def test_policy_min_confidence_one(self):
        p = _make_autonomy_policy(min_confidence=1.0)
        assert p.min_confidence == 1.0

    def test_policy_max_auto_changes_zero(self):
        p = _make_autonomy_policy(max_auto_changes_per_window=0)
        assert p.max_auto_changes_per_window == 0

    def test_policy_failure_suppression_threshold_zero(self):
        p = _make_autonomy_policy(failure_suppression_threshold=0)
        assert p.failure_suppression_threshold == 0

    def test_policy_max_cost_delta_zero(self):
        p = _make_autonomy_policy(max_cost_delta=0.0)
        assert p.max_cost_delta == 0.0

    def test_learning_window_samples_zero(self):
        w = _make_learning_window(samples_collected=0)
        assert w.samples_collected == 0

    def test_learning_window_duration_zero(self):
        w = _make_learning_window(duration_seconds=0.0)
        assert w.duration_seconds == 0.0

    def test_suppression_failure_count_zero(self):
        r = _make_suppression_record(failure_count=0)
        assert r.failure_count == 0

    def test_rollback_tolerance_pct_zero(self):
        t = _make_rollback_trigger(tolerance_pct=0.0)
        assert t.tolerance_pct == 0.0

    def test_outcome_confidence_zero(self):
        o = _make_improvement_outcome(confidence=0.0)
        assert o.confidence == 0.0

    def test_outcome_confidence_one(self):
        o = _make_improvement_outcome(confidence=1.0)
        assert o.confidence == 1.0


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------

class TestToDictSerialization:
    """to_dict() returns a plain dict and preserves enum objects (not .value)."""

    def test_candidate_to_dict_returns_dict(self):
        d = _make_improvement_candidate().to_dict()
        assert isinstance(d, dict)

    def test_candidate_to_dict_preserves_enum(self):
        d = _make_improvement_candidate().to_dict()
        assert d["disposition"] is ImprovementDisposition.PENDING
        assert d["autonomy_level"] is AutonomyLevel.BOUNDED_AUTO

    def test_policy_to_dict_returns_dict(self):
        d = _make_autonomy_policy().to_dict()
        assert isinstance(d, dict)

    def test_learning_window_to_dict_preserves_enum(self):
        d = _make_learning_window().to_dict()
        assert d["status"] is LearningWindowStatus.ACTIVE

    def test_session_to_dict_preserves_enums(self):
        d = _make_improvement_session().to_dict()
        assert d["autonomy_level"] is AutonomyLevel.BOUNDED_AUTO
        assert d["disposition"] is ImprovementDisposition.AUTO_PROMOTED
        assert d["verdict"] is ImprovementOutcomeVerdict.IMPROVED

    def test_suppression_to_dict_preserves_enum(self):
        d = _make_suppression_record().to_dict()
        assert d["reason"] is SuppressionReason.REPEATED_FAILURE

    def test_outcome_to_dict_preserves_enum(self):
        d = _make_improvement_outcome().to_dict()
        assert d["verdict"] is ImprovementOutcomeVerdict.IMPROVED

    def test_rollback_to_dict_returns_dict(self):
        d = _make_rollback_trigger().to_dict()
        assert isinstance(d, dict)

    def test_candidate_to_dict_all_keys(self):
        d = _make_improvement_candidate().to_dict()
        expected_keys = {
            "candidate_id", "recommendation_id", "change_type", "scope_ref_id",
            "title", "confidence", "estimated_improvement_pct",
            "estimated_cost_delta", "risk_score", "disposition",
            "autonomy_level", "reason", "created_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())

    def test_outcome_to_dict_all_keys(self):
        d = _make_improvement_outcome().to_dict()
        expected_keys = {
            "outcome_id", "session_id", "candidate_id", "change_id",
            "verdict", "baseline_value", "final_value", "improvement_pct",
            "confidence", "rollback_triggered", "suppression_triggered",
            "reinforcement_applied", "assessed_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())
