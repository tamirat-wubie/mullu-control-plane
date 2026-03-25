"""Tests for simulation engine contracts."""

import math

import pytest

from mcoi_runtime.contracts.simulation import (
    ConsequenceEstimate,
    ObligationProjection,
    RiskEstimate,
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationOutcome,
    SimulationRequest,
    SimulationStatus,
    SimulationVerdict,
    VerdictType,
)


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# --- Helpers ---


def _option(**overrides):
    defaults = dict(
        option_id="opt-001",
        label="Blue-green deployment",
        risk_level=RiskLevel.LOW,
        estimated_cost=200.0,
        estimated_duration_seconds=120.0,
        success_probability=0.92,
    )
    defaults.update(overrides)
    return SimulationOption(**defaults)


def _request(**overrides):
    defaults = dict(
        request_id="req-001",
        context_type="goal",
        context_id="goal-001",
        description="Evaluate deployment options",
        options=(_option(),),
    )
    defaults.update(overrides)
    return SimulationRequest(**defaults)


def _consequence(**overrides):
    defaults = dict(
        estimate_id="ce-001",
        option_id="opt-001",
        affected_node_ids=("node-001", "node-003"),
        new_edges_count=3,
        new_obligations_count=2,
        blocked_nodes_count=1,
        unblocked_nodes_count=4,
    )
    defaults.update(overrides)
    return ConsequenceEstimate(**defaults)


def _risk(**overrides):
    defaults = dict(
        estimate_id="re-001",
        option_id="opt-001",
        risk_level=RiskLevel.LOW,
        incident_probability=0.1,
        review_burden=2,
        provider_exposure_count=1,
        verification_difficulty="moderate",
        rationale="Standard deployment with rollback capability",
    )
    defaults.update(overrides)
    return RiskEstimate(**defaults)


def _obligation_proj(**overrides):
    defaults = dict(
        projection_id="op-001",
        option_id="opt-001",
        new_obligations=("notify stakeholders", "update runbook"),
        fulfilled_obligations=("complete staging test",),
        deadline_pressure=1,
    )
    defaults.update(overrides)
    return ObligationProjection(**defaults)


def _outcome(**overrides):
    defaults = dict(
        outcome_id="out-001",
        option_id="opt-001",
        consequence=_consequence(),
        risk=_risk(),
        obligation_projection=_obligation_proj(),
        simulated_at=TS,
    )
    defaults.update(overrides)
    return SimulationOutcome(**defaults)


def _comparison(**overrides):
    defaults = dict(
        comparison_id="cmp-001",
        request_id="req-001",
        ranked_option_ids=("opt-001",),
        scores={"opt-001": 0.85},
        top_risk_level=RiskLevel.LOW,
        review_burden=0.1,
    )
    defaults.update(overrides)
    return SimulationComparison(**defaults)


def _verdict(**overrides):
    defaults = dict(
        verdict_id="vrd-001",
        comparison_id="cmp-001",
        verdict_type=VerdictType.PROCEED,
        recommended_option_id="opt-001",
        confidence=0.85,
        reasons=("acceptable risk and confidence",),
    )
    defaults.update(overrides)
    return SimulationVerdict(**defaults)


# ===================================================================
# SimulationStatus enum
# ===================================================================


class TestSimulationStatus:
    def test_all_values(self):
        assert set(SimulationStatus) == {
            SimulationStatus.PENDING,
            SimulationStatus.RUNNING,
            SimulationStatus.COMPLETED,
            SimulationStatus.FAILED,
        }

    def test_string_values(self):
        assert SimulationStatus.PENDING == "pending"
        assert SimulationStatus.RUNNING == "running"
        assert SimulationStatus.COMPLETED == "completed"
        assert SimulationStatus.FAILED == "failed"


# ===================================================================
# RiskLevel enum
# ===================================================================


class TestRiskLevel:
    def test_all_values(self):
        assert set(RiskLevel) == {
            RiskLevel.MINIMAL,
            RiskLevel.LOW,
            RiskLevel.MODERATE,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }

    def test_string_values(self):
        assert RiskLevel.MINIMAL == "minimal"
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MODERATE == "moderate"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"


# ===================================================================
# VerdictType enum
# ===================================================================


class TestVerdictType:
    def test_all_values(self):
        assert set(VerdictType) == {
            VerdictType.PROCEED,
            VerdictType.PROCEED_WITH_CAUTION,
            VerdictType.APPROVAL_REQUIRED,
            VerdictType.ESCALATE,
            VerdictType.ABORT,
        }

    def test_string_values(self):
        assert VerdictType.PROCEED == "proceed"
        assert VerdictType.PROCEED_WITH_CAUTION == "proceed_with_caution"
        assert VerdictType.APPROVAL_REQUIRED == "approval_required"
        assert VerdictType.ESCALATE == "escalate"
        assert VerdictType.ABORT == "abort"


# ===================================================================
# SimulationOption
# ===================================================================


class TestSimulationOption:
    def test_valid_construction(self):
        o = _option()
        assert o.option_id == "opt-001"
        assert o.label == "Blue-green deployment"
        assert o.risk_level == RiskLevel.LOW
        assert o.estimated_cost == 200.0
        assert o.estimated_duration_seconds == 120.0
        assert o.success_probability == 0.92

    def test_empty_option_id_rejected(self):
        with pytest.raises(ValueError, match="option_id"):
            _option(option_id="")

    def test_empty_label_rejected(self):
        with pytest.raises(ValueError, match="label"):
            _option(label="")

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValueError, match="risk_level"):
            _option(risk_level="unknown")

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError, match="estimated_cost"):
            _option(estimated_cost=-1.0)

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="estimated_duration_seconds"):
            _option(estimated_duration_seconds=-1.0)

    def test_probability_above_one_rejected(self):
        with pytest.raises(ValueError, match="success_probability"):
            _option(success_probability=1.1)

    def test_probability_below_zero_rejected(self):
        with pytest.raises(ValueError, match="success_probability"):
            _option(success_probability=-0.1)

    def test_probability_nan_rejected(self):
        with pytest.raises(ValueError, match="success_probability"):
            _option(success_probability=float("nan"))

    def test_probability_boundaries(self):
        o0 = _option(success_probability=0.0)
        assert o0.success_probability == 0.0
        o1 = _option(success_probability=1.0)
        assert o1.success_probability == 1.0

    def test_zero_cost_accepted(self):
        o = _option(estimated_cost=0.0)
        assert o.estimated_cost == 0.0

    def test_zero_duration_accepted(self):
        o = _option(estimated_duration_seconds=0.0)
        assert o.estimated_duration_seconds == 0.0

    def test_frozen(self):
        o = _option()
        with pytest.raises(AttributeError):
            o.option_id = "changed"

    def test_to_dict(self):
        o = _option()
        d = o.to_dict()
        assert d["estimated_cost"] == 200.0
        assert d["risk_level"] == "low"


# ===================================================================
# SimulationRequest
# ===================================================================


class TestSimulationRequest:
    def test_valid_construction(self):
        r = _request()
        assert r.request_id == "req-001"
        assert r.context_type == "goal"
        assert r.context_id == "goal-001"
        assert r.description == "Evaluate deployment options"
        assert len(r.options) == 1

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _request(request_id="")

    def test_empty_context_type_rejected(self):
        with pytest.raises(ValueError, match="context_type"):
            _request(context_type="")

    def test_empty_context_id_rejected(self):
        with pytest.raises(ValueError, match="context_id"):
            _request(context_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _request(description="")

    def test_empty_options_rejected(self):
        with pytest.raises(ValueError, match="options"):
            _request(options=())

    def test_frozen(self):
        r = _request()
        with pytest.raises(AttributeError):
            r.request_id = "changed"

    def test_to_dict_roundtrip(self):
        r = _request()
        d = r.to_dict()
        assert d["request_id"] == "req-001"
        assert d["context_type"] == "goal"

    def test_to_dict_has_options(self):
        r = _request(options=(_option(),))
        d = r.to_dict()
        assert "options" in d
        assert len(d["options"]) == 1

    def test_list_options_coerced(self):
        r = _request(options=[_option()])
        assert isinstance(r.options, tuple)


# ===================================================================
# ConsequenceEstimate
# ===================================================================


class TestConsequenceEstimate:
    def test_valid_construction(self):
        c = _consequence()
        assert c.estimate_id == "ce-001"
        assert c.new_edges_count == 3
        assert c.unblocked_nodes_count == 4

    def test_empty_estimate_id_rejected(self):
        with pytest.raises(ValueError, match="estimate_id"):
            _consequence(estimate_id="")

    def test_empty_option_id_rejected(self):
        with pytest.raises(ValueError, match="option_id"):
            _consequence(option_id="")

    def test_negative_new_edges_rejected(self):
        with pytest.raises(ValueError, match="new_edges_count"):
            _consequence(new_edges_count=-1)

    def test_negative_new_obligations_rejected(self):
        with pytest.raises(ValueError, match="new_obligations_count"):
            _consequence(new_obligations_count=-1)

    def test_negative_blocked_rejected(self):
        with pytest.raises(ValueError, match="blocked_nodes_count"):
            _consequence(blocked_nodes_count=-1)

    def test_negative_unblocked_rejected(self):
        with pytest.raises(ValueError, match="unblocked_nodes_count"):
            _consequence(unblocked_nodes_count=-1)

    def test_zero_counts_accepted(self):
        c = _consequence(
            new_edges_count=0,
            new_obligations_count=0,
            blocked_nodes_count=0,
            unblocked_nodes_count=0,
        )
        assert c.new_edges_count == 0

    def test_empty_affected_node_ids_accepted(self):
        c = _consequence(affected_node_ids=())
        assert c.affected_node_ids == ()

    def test_list_affected_node_ids_coerced(self):
        c = _consequence(affected_node_ids=["a", "b"])
        assert isinstance(c.affected_node_ids, tuple)

    def test_frozen(self):
        c = _consequence()
        with pytest.raises(AttributeError):
            c.estimate_id = "changed"

    def test_to_dict(self):
        c = _consequence()
        d = c.to_dict()
        assert d["new_edges_count"] == 3


# ===================================================================
# RiskEstimate
# ===================================================================


class TestRiskEstimate:
    def test_valid_construction(self):
        r = _risk()
        assert r.risk_level == RiskLevel.LOW
        assert r.incident_probability == 0.1
        assert r.review_burden == 2

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValueError, match="risk_level"):
            _risk(risk_level="unknown")

    def test_incident_probability_above_one_rejected(self):
        with pytest.raises(ValueError, match="incident_probability"):
            _risk(incident_probability=1.1)

    def test_incident_probability_below_zero_rejected(self):
        with pytest.raises(ValueError, match="incident_probability"):
            _risk(incident_probability=-0.1)

    def test_incident_probability_nan_rejected(self):
        with pytest.raises(ValueError, match="incident_probability"):
            _risk(incident_probability=float("nan"))

    def test_incident_probability_inf_rejected(self):
        with pytest.raises(ValueError, match="incident_probability"):
            _risk(incident_probability=float("inf"))

    def test_incident_probability_bool_rejected(self):
        with pytest.raises(ValueError, match="incident_probability"):
            _risk(incident_probability=True)

    def test_incident_probability_boundaries(self):
        r0 = _risk(incident_probability=0.0)
        assert r0.incident_probability == 0.0
        r1 = _risk(incident_probability=1.0)
        assert r1.incident_probability == 1.0

    def test_negative_review_burden_rejected(self):
        with pytest.raises(ValueError, match="review_burden"):
            _risk(review_burden=-1)

    def test_negative_provider_exposure_rejected(self):
        with pytest.raises(ValueError, match="provider_exposure_count"):
            _risk(provider_exposure_count=-1)

    def test_empty_verification_difficulty_rejected(self):
        with pytest.raises(ValueError, match="verification_difficulty"):
            _risk(verification_difficulty="")

    def test_empty_rationale_rejected(self):
        with pytest.raises(ValueError, match="rationale"):
            _risk(rationale="")

    def test_empty_estimate_id_rejected(self):
        with pytest.raises(ValueError, match="estimate_id"):
            _risk(estimate_id="")

    def test_all_risk_levels(self):
        for level in RiskLevel:
            r = _risk(risk_level=level)
            assert r.risk_level == level

    def test_frozen(self):
        r = _risk()
        with pytest.raises(AttributeError):
            r.risk_level = RiskLevel.HIGH

    def test_to_dict(self):
        r = _risk()
        d = r.to_dict()
        assert d["risk_level"] == "low"
        assert d["incident_probability"] == 0.1

    def test_int_coerced_to_float(self):
        r = _risk(incident_probability=0)
        assert r.incident_probability == 0.0
        assert isinstance(r.incident_probability, float)


# ===================================================================
# ObligationProjection
# ===================================================================


class TestObligationProjection:
    def test_valid_construction(self):
        o = _obligation_proj()
        assert o.projection_id == "op-001"
        assert o.new_obligations == ("notify stakeholders", "update runbook")
        assert o.fulfilled_obligations == ("complete staging test",)
        assert o.deadline_pressure == 1

    def test_empty_projection_id_rejected(self):
        with pytest.raises(ValueError, match="projection_id"):
            _obligation_proj(projection_id="")

    def test_empty_option_id_rejected(self):
        with pytest.raises(ValueError, match="option_id"):
            _obligation_proj(option_id="")

    def test_negative_deadline_pressure_rejected(self):
        with pytest.raises(ValueError, match="deadline_pressure"):
            _obligation_proj(deadline_pressure=-1)

    def test_empty_tuples_accepted(self):
        o = _obligation_proj(new_obligations=(), fulfilled_obligations=())
        assert o.new_obligations == ()
        assert o.fulfilled_obligations == ()

    def test_list_coerced_to_tuple(self):
        o = _obligation_proj(new_obligations=["a"], fulfilled_obligations=["b"])
        assert isinstance(o.new_obligations, tuple)
        assert isinstance(o.fulfilled_obligations, tuple)

    def test_frozen(self):
        o = _obligation_proj()
        with pytest.raises(AttributeError):
            o.deadline_pressure = 99

    def test_to_dict(self):
        o = _obligation_proj()
        d = o.to_dict()
        assert d["deadline_pressure"] == 1
        assert isinstance(d["new_obligations"], list)


# ===================================================================
# SimulationOutcome
# ===================================================================


class TestSimulationOutcome:
    def test_valid_construction(self):
        o = _outcome()
        assert o.outcome_id == "out-001"
        assert isinstance(o.consequence, ConsequenceEstimate)
        assert isinstance(o.risk, RiskEstimate)
        assert isinstance(o.obligation_projection, ObligationProjection)

    def test_empty_outcome_id_rejected(self):
        with pytest.raises(ValueError, match="outcome_id"):
            _outcome(outcome_id="")

    def test_empty_option_id_rejected(self):
        with pytest.raises(ValueError, match="option_id"):
            _outcome(option_id="")

    def test_bad_consequence_type_rejected(self):
        with pytest.raises(ValueError, match="consequence"):
            _outcome(consequence="not a consequence")

    def test_bad_risk_type_rejected(self):
        with pytest.raises(ValueError, match="risk"):
            _outcome(risk="not a risk")

    def test_bad_obligation_projection_type_rejected(self):
        with pytest.raises(ValueError, match="obligation_projection"):
            _outcome(obligation_projection="not a projection")

    def test_bad_simulated_at_rejected(self):
        with pytest.raises(ValueError, match="simulated_at"):
            _outcome(simulated_at="bad")

    def test_frozen(self):
        o = _outcome()
        with pytest.raises(AttributeError):
            o.outcome_id = "changed"

    def test_to_dict_nested(self):
        o = _outcome()
        d = o.to_dict()
        assert "consequence" in d
        assert "risk" in d
        assert "obligation_projection" in d


# ===================================================================
# SimulationComparison
# ===================================================================


class TestSimulationComparison:
    def test_valid_construction(self):
        c = _comparison()
        assert c.comparison_id == "cmp-001"
        assert c.ranked_option_ids == ("opt-001",)
        assert c.top_risk_level == RiskLevel.LOW
        assert c.review_burden == 0.1

    def test_empty_comparison_id_rejected(self):
        with pytest.raises(ValueError, match="comparison_id"):
            _comparison(comparison_id="")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _comparison(request_id="")

    def test_empty_ranked_option_ids_rejected(self):
        with pytest.raises(ValueError, match="ranked_option_ids"):
            _comparison(ranked_option_ids=())

    def test_invalid_top_risk_level_rejected(self):
        with pytest.raises(ValueError, match="top_risk_level"):
            _comparison(top_risk_level="unknown")

    def test_review_burden_above_one_rejected(self):
        with pytest.raises(ValueError, match="review_burden"):
            _comparison(review_burden=1.1)

    def test_review_burden_below_zero_rejected(self):
        with pytest.raises(ValueError, match="review_burden"):
            _comparison(review_burden=-0.1)

    def test_frozen(self):
        c = _comparison()
        with pytest.raises(AttributeError):
            c.comparison_id = "changed"

    def test_multiple_ranked_ids(self):
        c = _comparison(
            ranked_option_ids=("opt-002", "opt-001"),
            scores={"opt-001": 0.7, "opt-002": 0.9},
        )
        assert len(c.ranked_option_ids) == 2
        assert c.ranked_option_ids[0] == "opt-002"

    def test_to_dict(self):
        c = _comparison()
        d = c.to_dict()
        assert d["comparison_id"] == "cmp-001"


# ===================================================================
# SimulationVerdict
# ===================================================================


class TestSimulationVerdict:
    def test_valid_construction(self):
        v = _verdict()
        assert v.verdict_id == "vrd-001"
        assert v.verdict_type == VerdictType.PROCEED
        assert v.confidence == 0.85
        assert v.reasons == ("acceptable risk and confidence",)

    def test_empty_verdict_id_rejected(self):
        with pytest.raises(ValueError, match="verdict_id"):
            _verdict(verdict_id="")

    def test_empty_comparison_id_rejected(self):
        with pytest.raises(ValueError, match="comparison_id"):
            _verdict(comparison_id="")

    def test_empty_recommended_option_id_rejected(self):
        with pytest.raises(ValueError, match="recommended_option_id"):
            _verdict(recommended_option_id="")

    def test_invalid_verdict_type_rejected(self):
        with pytest.raises(ValueError, match="verdict_type"):
            _verdict(verdict_type="unknown")

    def test_empty_reasons_rejected(self):
        with pytest.raises(ValueError, match="reasons"):
            _verdict(reasons=())

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=1.01)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=-0.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=float("inf"))

    def test_confidence_neg_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=float("-inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verdict(confidence=True)

    def test_confidence_boundaries(self):
        v0 = _verdict(confidence=0.0)
        assert v0.confidence == 0.0
        v1 = _verdict(confidence=1.0)
        assert v1.confidence == 1.0

    def test_all_verdict_types(self):
        for vt in VerdictType:
            v = _verdict(verdict_type=vt)
            assert v.verdict_type == vt

    def test_frozen(self):
        v = _verdict()
        with pytest.raises(AttributeError):
            v.verdict_id = "changed"

    def test_to_dict(self):
        v = _verdict()
        d = v.to_dict()
        assert d["verdict_type"] == "proceed"
        assert d["confidence"] == 0.85

    def test_to_json(self):
        v = _verdict()
        j = v.to_json()
        assert '"vrd-001"' in j

    def test_int_confidence_coerced(self):
        v = _verdict(confidence=1)
        assert v.confidence == 1.0
        assert isinstance(v.confidence, float)


# ===================================================================
# Serialization round-trip tests
# ===================================================================


class TestSerializationRoundTrip:
    def test_request_dict_deterministic(self):
        r = _request()
        assert r.to_dict() == r.to_dict()

    def test_option_json_deterministic(self):
        o = _option()
        assert o.to_json() == o.to_json()

    def test_consequence_json_deterministic(self):
        c = _consequence()
        assert c.to_json() == c.to_json()

    def test_risk_json_deterministic(self):
        r = _risk()
        assert r.to_json() == r.to_json()

    def test_obligation_proj_json_deterministic(self):
        o = _obligation_proj()
        assert o.to_json() == o.to_json()

    def test_verdict_json_deterministic(self):
        v = _verdict()
        assert v.to_json() == v.to_json()


# ---------------------------------------------------------------------------
# Audit #10 — element validation in tuple fields
# ---------------------------------------------------------------------------


class TestConsequenceEstimateElementValidation:
    """ConsequenceEstimate must reject non-string or empty affected_node_ids."""

    def test_empty_string_node_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            ConsequenceEstimate(
                estimate_id="est-1",
                option_id="opt-1",
                affected_node_ids=("n1", ""),
                new_edges_count=0,
                new_obligations_count=0,
                blocked_nodes_count=0,
                unblocked_nodes_count=0,
            )

    def test_valid_node_ids_accepted(self):
        ce = ConsequenceEstimate(
            estimate_id="est-1",
            option_id="opt-1",
            affected_node_ids=("n1", "n2"),
            new_edges_count=1,
            new_obligations_count=0,
            blocked_nodes_count=0,
            unblocked_nodes_count=0,
        )
        assert ce.affected_node_ids == ("n1", "n2")


class TestObligationProjectionElementValidation:
    """ObligationProjection must reject empty-string obligation IDs."""

    def test_empty_new_obligation_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            ObligationProjection(
                projection_id="proj-1",
                option_id="opt-1",
                new_obligations=("obl-1", ""),
                fulfilled_obligations=(),
                deadline_pressure=0,
            )

    def test_empty_fulfilled_obligation_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            ObligationProjection(
                projection_id="proj-1",
                option_id="opt-1",
                new_obligations=(),
                fulfilled_obligations=("", "obl-2"),
                deadline_pressure=0,
            )
