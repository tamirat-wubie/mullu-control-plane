"""Contract-level tests for optimization_runtime contracts.

Covers all 5 enums and 8 frozen dataclasses with 170+ tests spanning:
  - Enum member existence and count
  - Valid construction with defaults and explicit values
  - Frozen immutability
  - ContractRecord.to_dict() serialization
  - require_non_empty_text, require_unit_float, require_non_negative_int,
    require_datetime_text validation
  - Enum-typed field rejection of wrong types
  - Bool-typed field rejection of non-booleans
  - metadata / recommendation_ids freezing
  - Default values, edge cases (score boundaries, empty metadata)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.optimization_runtime import (
    OptimizationCandidate,
    OptimizationConstraint,
    OptimizationImpactEstimate,
    OptimizationPlan,
    OptimizationRecommendation,
    OptimizationRequest,
    OptimizationResult,
    OptimizationScope,
    OptimizationStrategy,
    OptimizationTarget,
    RecommendationDecision,
    RecommendationDisposition,
    RecommendationSeverity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(y: int = 2025, m: int = 6, d: int = 15, h: int = 10, mi: int = 0) -> str:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc).isoformat()


TS = _ts()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestOptimizationTargetEnum:
    EXPECTED_MEMBERS = [
        "CAMPAIGN_COST",
        "CAMPAIGN_DURATION",
        "CONNECTOR_SELECTION",
        "PORTFOLIO_BALANCE",
        "BUDGET_ALLOCATION",
        "SCHEDULE_EFFICIENCY",
        "ESCALATION_POLICY",
        "DOMAIN_PACK_SELECTION",
        "CHANNEL_ROUTING",
        "FAULT_AVOIDANCE",
    ]

    def test_member_count(self):
        assert len(OptimizationTarget) == 10

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_exists(self, name: str):
        assert hasattr(OptimizationTarget, name)

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_value_matches_lower(self, name: str):
        assert OptimizationTarget[name].value == name.lower()


class TestOptimizationStrategyEnum:
    EXPECTED_MEMBERS = [
        "COST_MINIMIZATION",
        "THROUGHPUT_MAXIMIZATION",
        "LATENCY_MINIMIZATION",
        "RELIABILITY_MAXIMIZATION",
        "BALANCED",
        "CONSTRAINT_SATISFACTION",
    ]

    def test_member_count(self):
        assert len(OptimizationStrategy) == 6

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_exists(self, name: str):
        assert hasattr(OptimizationStrategy, name)

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_value_matches_lower(self, name: str):
        assert OptimizationStrategy[name].value == name.lower()


class TestRecommendationSeverityEnum:
    EXPECTED_MEMBERS = [
        "INFORMATIONAL",
        "ADVISORY",
        "RECOMMENDED",
        "URGENT",
        "CRITICAL",
    ]

    def test_member_count(self):
        assert len(RecommendationSeverity) == 5

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_exists(self, name: str):
        assert hasattr(RecommendationSeverity, name)

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_value_matches_lower(self, name: str):
        assert RecommendationSeverity[name].value == name.lower()


class TestRecommendationDispositionEnum:
    EXPECTED_MEMBERS = [
        "PENDING",
        "ACCEPTED",
        "REJECTED",
        "DEFERRED",
        "PARTIALLY_ACCEPTED",
        "SUPERSEDED",
    ]

    def test_member_count(self):
        assert len(RecommendationDisposition) == 6

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_exists(self, name: str):
        assert hasattr(RecommendationDisposition, name)

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_value_matches_lower(self, name: str):
        assert RecommendationDisposition[name].value == name.lower()


class TestOptimizationScopeEnum:
    EXPECTED_MEMBERS = [
        "GLOBAL",
        "PORTFOLIO",
        "CAMPAIGN",
        "CONNECTOR",
        "TEAM",
        "FUNCTION",
        "CHANNEL",
        "DOMAIN_PACK",
    ]

    def test_member_count(self):
        assert len(OptimizationScope) == 8

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_exists(self, name: str):
        assert hasattr(OptimizationScope, name)

    @pytest.mark.parametrize("name", EXPECTED_MEMBERS)
    def test_member_value_matches_lower(self, name: str):
        assert OptimizationScope[name].value == name.lower()


# ---------------------------------------------------------------------------
# OptimizationRequest
# ---------------------------------------------------------------------------


class TestOptimizationRequest:
    def _make(self, **kw):
        defaults = dict(
            request_id="req-1",
            target=OptimizationTarget.CAMPAIGN_COST,
            strategy=OptimizationStrategy.BALANCED,
            scope=OptimizationScope.GLOBAL,
            max_candidates=10,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationRequest(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.request_id == "req-1"
        assert r.target == OptimizationTarget.CAMPAIGN_COST
        assert r.strategy == OptimizationStrategy.BALANCED
        assert r.scope == OptimizationScope.GLOBAL
        assert r.max_candidates == 10
        assert r.priority == "normal"

    def test_defaults(self):
        r = self._make()
        assert r.scope_ref_id == ""
        assert r.reason == ""

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.request_id = "new"

    def test_to_dict_returns_plain_dict(self):
        d = self._make(metadata={"k": "v"}).to_dict()
        assert isinstance(d, dict)
        assert d["request_id"] == "req-1"
        assert isinstance(d["metadata"], dict)

    def test_to_dict_enum_values(self):
        d = self._make().to_dict()
        assert d["target"] == OptimizationTarget.CAMPAIGN_COST

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    def test_whitespace_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="   ")

    def test_invalid_target_type(self):
        with pytest.raises(ValueError):
            self._make(target="campaign_cost")

    def test_invalid_strategy_type(self):
        with pytest.raises(ValueError):
            self._make(strategy="balanced")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            self._make(scope="global")

    def test_negative_max_candidates_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_candidates=-1)

    def test_max_candidates_zero_accepted(self):
        r = self._make(max_candidates=0)
        assert r.max_candidates == 0

    def test_max_candidates_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_candidates=True)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_metadata_frozen_to_mapping_proxy(self):
        r = self._make(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_empty_metadata(self):
        r = self._make(metadata={})
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    @pytest.mark.parametrize("target", list(OptimizationTarget))
    def test_all_targets_accepted(self, target):
        r = self._make(target=target)
        assert r.target == target

    @pytest.mark.parametrize("strategy", list(OptimizationStrategy))
    def test_all_strategies_accepted(self, strategy):
        r = self._make(strategy=strategy)
        assert r.strategy == strategy

    @pytest.mark.parametrize("scope", list(OptimizationScope))
    def test_all_scopes_accepted(self, scope):
        r = self._make(scope=scope)
        assert r.scope == scope


# ---------------------------------------------------------------------------
# OptimizationConstraint
# ---------------------------------------------------------------------------


class TestOptimizationConstraint:
    def _make(self, **kw):
        defaults = dict(
            constraint_id="con-1",
            request_id="req-1",
            constraint_type="budget_cap",
            hard=True,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationConstraint(**defaults)

    def test_valid_construction(self):
        c = self._make()
        assert c.constraint_id == "con-1"
        assert c.request_id == "req-1"
        assert c.constraint_type == "budget_cap"
        assert c.hard is True

    def test_defaults(self):
        c = self._make()
        assert c.field_name == ""
        assert c.operator == ""
        assert c.value == ""

    def test_frozen(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.constraint_id = "new"

    def test_to_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)
        assert d["constraint_id"] == "con-1"

    def test_empty_constraint_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(constraint_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    def test_empty_constraint_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(constraint_type="")

    def test_hard_non_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(hard=1)

    def test_hard_string_rejected(self):
        with pytest.raises(ValueError):
            self._make(hard="true")

    def test_hard_false_accepted(self):
        c = self._make(hard=False)
        assert c.hard is False

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="nope")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="")


# ---------------------------------------------------------------------------
# OptimizationCandidate
# ---------------------------------------------------------------------------


class TestOptimizationCandidate:
    def _make(self, **kw):
        defaults = dict(
            candidate_id="cand-1",
            request_id="req-1",
            description="Reduce cost by 10%",
            target=OptimizationTarget.CAMPAIGN_COST,
            score=0.85,
            feasible=True,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationCandidate(**defaults)

    def test_valid_construction(self):
        c = self._make()
        assert c.candidate_id == "cand-1"
        assert c.score == 0.85
        assert c.feasible is True

    def test_defaults(self):
        c = self._make()
        assert c.action == ""
        assert c.scope_ref_id == ""
        assert c.estimated_improvement == 0.0
        assert c.estimated_cost_delta == 0.0

    def test_frozen(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.candidate_id = "new"

    def test_to_dict(self):
        d = self._make(metadata={"x": 1}).to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["metadata"], dict)

    def test_empty_candidate_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(candidate_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._make(description="")

    def test_invalid_target_type(self):
        with pytest.raises(ValueError):
            self._make(target="campaign_cost")

    def test_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(score=-0.01)

    def test_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(score=1.01)

    def test_score_zero_accepted(self):
        c = self._make(score=0.0)
        assert c.score == 0.0

    def test_score_one_accepted(self):
        c = self._make(score=1.0)
        assert c.score == 1.0

    def test_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(score=True)

    def test_feasible_non_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(feasible=1)

    def test_feasible_false_accepted(self):
        c = self._make(feasible=False)
        assert c.feasible is False

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="xyz")

    def test_metadata_frozen(self):
        c = self._make(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            c.metadata["new"] = "val"

    def test_empty_metadata_accepted(self):
        c = self._make(metadata={})
        assert len(c.metadata) == 0

    @pytest.mark.parametrize("target", list(OptimizationTarget))
    def test_all_targets_accepted(self, target):
        c = self._make(target=target)
        assert c.target == target


# ---------------------------------------------------------------------------
# OptimizationRecommendation
# ---------------------------------------------------------------------------


class TestOptimizationRecommendation:
    def _make(self, **kw):
        defaults = dict(
            recommendation_id="rec-1",
            request_id="req-1",
            title="Cut campaign cost",
            target=OptimizationTarget.CAMPAIGN_COST,
            severity=RecommendationSeverity.ADVISORY,
            scope=OptimizationScope.CAMPAIGN,
            score=0.9,
            confidence=0.8,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationRecommendation(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.recommendation_id == "rec-1"
        assert r.score == 0.9
        assert r.confidence == 0.8

    def test_defaults(self):
        r = self._make()
        assert r.candidate_id == ""
        assert r.description == ""
        assert r.action == ""
        assert r.scope_ref_id == ""
        assert r.estimated_improvement_pct == 0.0
        assert r.estimated_cost_delta == 0.0
        assert r.rationale == ""

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.recommendation_id = "new"

    def test_to_dict(self):
        d = self._make(metadata={"m": 1}).to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["metadata"], dict)

    def test_empty_recommendation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(recommendation_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_invalid_target_type(self):
        with pytest.raises(ValueError):
            self._make(target="campaign_cost")

    def test_invalid_severity_type(self):
        with pytest.raises(ValueError):
            self._make(severity="advisory")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            self._make(scope="global")

    def test_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(score=-0.1)

    def test_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(score=1.5)

    def test_score_zero_accepted(self):
        r = self._make(score=0.0)
        assert r.score == 0.0

    def test_score_one_accepted(self):
        r = self._make(score=1.0)
        assert r.score == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.01)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.01)

    def test_confidence_zero_accepted(self):
        r = self._make(confidence=0.0)
        assert r.confidence == 0.0

    def test_confidence_one_accepted(self):
        r = self._make(confidence=1.0)
        assert r.confidence == 1.0

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["new"] = "val"

    @pytest.mark.parametrize("severity", list(RecommendationSeverity))
    def test_all_severities_accepted(self, severity):
        r = self._make(severity=severity)
        assert r.severity == severity

    @pytest.mark.parametrize("scope", list(OptimizationScope))
    def test_all_scopes_accepted(self, scope):
        r = self._make(scope=scope)
        assert r.scope == scope


# ---------------------------------------------------------------------------
# OptimizationPlan
# ---------------------------------------------------------------------------


class TestOptimizationPlan:
    def _make(self, **kw):
        defaults = dict(
            plan_id="plan-1",
            request_id="req-1",
            title="Cost reduction plan",
            recommendation_ids=("rec-1", "rec-2"),
            feasible=True,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationPlan(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.plan_id == "plan-1"
        assert p.recommendation_ids == ("rec-1", "rec-2")
        assert p.feasible is True

    def test_defaults(self):
        p = self._make()
        assert p.total_estimated_improvement_pct == 0.0
        assert p.total_estimated_cost_delta == 0.0

    def test_frozen(self):
        p = self._make()
        with pytest.raises(AttributeError):
            p.plan_id = "new"

    def test_to_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)
        # recommendation_ids thawed to list
        assert isinstance(d["recommendation_ids"], list)

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(plan_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_recommendation_ids_frozen_to_tuple(self):
        p = self._make(recommendation_ids=["rec-a", "rec-b"])
        assert isinstance(p.recommendation_ids, tuple)
        assert p.recommendation_ids == ("rec-a", "rec-b")

    def test_recommendation_ids_empty_tuple_accepted(self):
        p = self._make(recommendation_ids=())
        assert p.recommendation_ids == ()

    def test_feasible_non_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(feasible=1)

    def test_feasible_string_rejected(self):
        with pytest.raises(ValueError):
            self._make(feasible="yes")

    def test_feasible_false_accepted(self):
        p = self._make(feasible=False)
        assert p.feasible is False

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="oops")

    def test_metadata_frozen(self):
        p = self._make(metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            p.metadata["new"] = "val"

    def test_empty_metadata(self):
        p = self._make(metadata={})
        assert len(p.metadata) == 0


# ---------------------------------------------------------------------------
# OptimizationResult
# ---------------------------------------------------------------------------


class TestOptimizationResult:
    def _make(self, **kw):
        defaults = dict(
            result_id="res-1",
            request_id="req-1",
            candidates_generated=5,
            recommendations_produced=3,
            constraints_satisfied=2,
            constraints_violated=0,
            best_score=0.95,
            completed_at=TS,
        )
        defaults.update(kw)
        return OptimizationResult(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.result_id == "res-1"
        assert r.candidates_generated == 5
        assert r.recommendations_produced == 3
        assert r.best_score == 0.95

    def test_defaults(self):
        r = self._make()
        assert r.plan_id == ""

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.result_id = "new"

    def test_to_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)
        assert d["result_id"] == "res-1"

    def test_empty_result_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(result_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_id="")

    @pytest.mark.parametrize(
        "field_name",
        ["candidates_generated", "recommendations_produced", "constraints_satisfied", "constraints_violated"],
    )
    def test_negative_int_rejected(self, field_name: str):
        with pytest.raises(ValueError):
            self._make(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        ["candidates_generated", "recommendations_produced", "constraints_satisfied", "constraints_violated"],
    )
    def test_zero_int_accepted(self, field_name: str):
        r = self._make(**{field_name: 0})
        assert getattr(r, field_name) == 0

    @pytest.mark.parametrize(
        "field_name",
        ["candidates_generated", "recommendations_produced", "constraints_satisfied", "constraints_violated"],
    )
    def test_bool_int_field_rejected(self, field_name: str):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    def test_best_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(best_score=-0.01)

    def test_best_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(best_score=1.01)

    def test_best_score_zero_accepted(self):
        r = self._make(best_score=0.0)
        assert r.best_score == 0.0

    def test_best_score_one_accepted(self):
        r = self._make(best_score=1.0)
        assert r.best_score == 1.0

    def test_invalid_completed_at(self):
        with pytest.raises(ValueError):
            self._make(completed_at="garbage")

    def test_empty_completed_at(self):
        with pytest.raises(ValueError):
            self._make(completed_at="")


# ---------------------------------------------------------------------------
# OptimizationImpactEstimate
# ---------------------------------------------------------------------------


class TestOptimizationImpactEstimate:
    def _make(self, **kw):
        defaults = dict(
            estimate_id="est-1",
            recommendation_id="rec-1",
            metric_name="cost_per_lead",
            confidence=0.75,
            created_at=TS,
        )
        defaults.update(kw)
        return OptimizationImpactEstimate(**defaults)

    def test_valid_construction(self):
        e = self._make()
        assert e.estimate_id == "est-1"
        assert e.recommendation_id == "rec-1"
        assert e.metric_name == "cost_per_lead"
        assert e.confidence == 0.75

    def test_defaults(self):
        e = self._make()
        assert e.current_value == 0.0
        assert e.projected_value == 0.0
        assert e.improvement_pct == 0.0
        assert e.risk_level == "low"

    def test_frozen(self):
        e = self._make()
        with pytest.raises(AttributeError):
            e.estimate_id = "new"

    def test_to_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)
        assert d["estimate_id"] == "est-1"

    def test_empty_estimate_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(estimate_id="")

    def test_empty_recommendation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(recommendation_id="")

    def test_empty_metric_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(metric_name="")

    def test_whitespace_metric_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(metric_name="   ")

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.01)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.01)

    def test_confidence_zero_accepted(self):
        e = self._make(confidence=0.0)
        assert e.confidence == 0.0

    def test_confidence_one_accepted(self):
        e = self._make(confidence=1.0)
        assert e.confidence == 1.0

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(confidence=True)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="nah")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_custom_values(self):
        e = self._make(current_value=100.0, projected_value=80.0, improvement_pct=20.0)
        assert e.current_value == 100.0
        assert e.projected_value == 80.0
        assert e.improvement_pct == 20.0


# ---------------------------------------------------------------------------
# RecommendationDecision
# ---------------------------------------------------------------------------


class TestRecommendationDecision:
    def _make(self, **kw):
        defaults = dict(
            decision_id="dec-1",
            recommendation_id="rec-1",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_at=TS,
        )
        defaults.update(kw)
        return RecommendationDecision(**defaults)

    def test_valid_construction(self):
        d = self._make()
        assert d.decision_id == "dec-1"
        assert d.recommendation_id == "rec-1"
        assert d.disposition == RecommendationDisposition.ACCEPTED

    def test_defaults(self):
        d = self._make()
        assert d.decided_by == ""
        assert d.reason == ""

    def test_frozen(self):
        d = self._make()
        with pytest.raises(AttributeError):
            d.decision_id = "new"

    def test_to_dict(self):
        result = self._make().to_dict()
        assert isinstance(result, dict)
        assert result["decision_id"] == "dec-1"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_empty_recommendation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(recommendation_id="")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            self._make(disposition="accepted")

    def test_invalid_disposition_int(self):
        with pytest.raises(ValueError):
            self._make(disposition=1)

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            self._make(decided_at="bad-date")

    def test_empty_decided_at(self):
        with pytest.raises(ValueError):
            self._make(decided_at="")

    @pytest.mark.parametrize("disposition", list(RecommendationDisposition))
    def test_all_dispositions_accepted(self, disposition):
        d = self._make(disposition=disposition)
        assert d.disposition == disposition

    def test_decided_by_and_reason(self):
        d = self._make(decided_by="user-42", reason="Budget approved")
        assert d.decided_by == "user-42"
        assert d.reason == "Budget approved"


# ---------------------------------------------------------------------------
# Cross-cutting / edge-case tests
# ---------------------------------------------------------------------------


class TestDatetimeFormats:
    """Verify various valid ISO 8601 timestamps are accepted."""

    @pytest.mark.parametrize(
        "ts_value",
        [
            "2025-06-15T10:00:00+00:00",
            "2025-06-15T10:00:00Z",
            "2025-01-01T00:00:00+05:30",
            "2025-12-31T23:59:59-08:00",
            "2025-06-15T10:00:00.123456+00:00",
        ],
    )
    def test_valid_iso_timestamps(self, ts_value: str):
        r = OptimizationRequest(request_id="req-1", created_at=ts_value)
        assert r.created_at == ts_value

    @pytest.mark.parametrize(
        "bad_ts",
        [
            "2025-13-01T00:00:00+00:00",
            "not-a-date",
            "2025/06/15",
            "",
            "   ",
        ],
    )
    def test_invalid_timestamps_rejected(self, bad_ts: str):
        with pytest.raises(ValueError):
            OptimizationRequest(request_id="req-1", created_at=bad_ts)


class TestMetadataNestedFreezing:
    """Verify nested metadata structures are recursively frozen."""

    def test_nested_dict_frozen(self):
        r = OptimizationRequest(
            request_id="req-1",
            created_at=TS,
            metadata={"outer": {"inner": "value"}},
        )
        assert isinstance(r.metadata["outer"], MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["outer"]["new_key"] = "fail"

    def test_nested_list_becomes_tuple(self):
        c = OptimizationCandidate(
            candidate_id="cand-1",
            request_id="req-1",
            description="Test",
            score=0.5,
            created_at=TS,
            metadata={"tags": ["a", "b"]},
        )
        assert isinstance(c.metadata["tags"], tuple)
        assert c.metadata["tags"] == ("a", "b")


class TestScoreBoundaryEdgeCases:
    """Boundary values for unit-float fields."""

    def test_candidate_score_int_zero(self):
        c = OptimizationCandidate(
            candidate_id="c-1", request_id="r-1", description="d",
            score=0, created_at=TS,
        )
        assert c.score == 0.0

    def test_candidate_score_int_one(self):
        c = OptimizationCandidate(
            candidate_id="c-1", request_id="r-1", description="d",
            score=1, created_at=TS,
        )
        assert c.score == 1.0

    def test_result_best_score_midpoint(self):
        r = OptimizationResult(
            result_id="res-1", request_id="req-1",
            best_score=0.5, completed_at=TS,
        )
        assert r.best_score == 0.5

    def test_score_nan_rejected(self):
        with pytest.raises(ValueError):
            OptimizationCandidate(
                candidate_id="c-1", request_id="r-1", description="d",
                score=float("nan"), created_at=TS,
            )

    def test_score_inf_rejected(self):
        with pytest.raises(ValueError):
            OptimizationCandidate(
                candidate_id="c-1", request_id="r-1", description="d",
                score=float("inf"), created_at=TS,
            )

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError):
            OptimizationImpactEstimate(
                estimate_id="e-1", recommendation_id="r-1",
                metric_name="m", confidence=float("nan"), created_at=TS,
            )


class TestRecommendationIdsListInput:
    """Verify recommendation_ids accepts list input and freezes to tuple."""

    def test_list_converted_to_tuple(self):
        p = OptimizationPlan(
            plan_id="p-1", request_id="r-1", title="Plan",
            recommendation_ids=["rec-a", "rec-b", "rec-c"],
            created_at=TS,
        )
        assert isinstance(p.recommendation_ids, tuple)
        assert len(p.recommendation_ids) == 3

    def test_single_item(self):
        p = OptimizationPlan(
            plan_id="p-1", request_id="r-1", title="Plan",
            recommendation_ids=("rec-only",),
            created_at=TS,
        )
        assert p.recommendation_ids == ("rec-only",)


class TestImmutabilityAcrossAllDataclasses:
    """Ensure every dataclass rejects attribute mutation."""

    def test_constraint_immutable(self):
        c = OptimizationConstraint(
            constraint_id="c-1", request_id="r-1",
            constraint_type="limit", created_at=TS,
        )
        with pytest.raises(AttributeError):
            c.hard = False

    def test_recommendation_immutable(self):
        r = OptimizationRecommendation(
            recommendation_id="rec-1", request_id="r-1",
            title="Title", score=0.5, confidence=0.5, created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.score = 0.99

    def test_plan_immutable(self):
        p = OptimizationPlan(
            plan_id="p-1", request_id="r-1", title="Plan", created_at=TS,
        )
        with pytest.raises(AttributeError):
            p.feasible = False

    def test_result_immutable(self):
        r = OptimizationResult(
            result_id="res-1", request_id="r-1",
            best_score=0.5, completed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.best_score = 0.0

    def test_impact_estimate_immutable(self):
        e = OptimizationImpactEstimate(
            estimate_id="e-1", recommendation_id="r-1",
            metric_name="m", confidence=0.5, created_at=TS,
        )
        with pytest.raises(AttributeError):
            e.confidence = 0.9

    def test_decision_immutable(self):
        d = RecommendationDecision(
            decision_id="d-1", recommendation_id="r-1",
            disposition=RecommendationDisposition.PENDING, decided_at=TS,
        )
        with pytest.raises(AttributeError):
            d.disposition = RecommendationDisposition.ACCEPTED
