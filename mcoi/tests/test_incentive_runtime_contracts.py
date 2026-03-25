"""Tests for incentive runtime contracts (Phase 115).

Covers: IncentiveRecord, BehaviorObservation, GamingDetection, PolicyEffect,
        IncentiveDecision, ContractIncentiveBinding, IncentiveAssessment,
        IncentiveViolation, IncentiveSnapshot, IncentiveClosureReport,
        and all related enums.
"""

import json
import math

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.incentive_runtime import (
    BehaviorDisposition,
    BehaviorObservation,
    ContractIncentiveBinding,
    GamingDetection,
    IncentiveAssessment,
    IncentiveClosureReport,
    IncentiveDecision,
    IncentiveKind,
    IncentiveRecord,
    IncentiveRiskLevel,
    IncentiveSnapshot,
    IncentiveStatus,
    IncentiveViolation,
    PolicyEffect,
    PolicyEffectKind,
    RiskOfGaming,
)


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _incentive(**kw):
    defaults = dict(
        incentive_id="inc-001", tenant_id="t-1", display_name="Reward A",
        kind=IncentiveKind.REWARD, status=IncentiveStatus.ACTIVE,
        target_actor_ref="actor-1", value=100.0, created_at=TS,
    )
    defaults.update(kw)
    return IncentiveRecord(**defaults)


def _observation(**kw):
    defaults = dict(
        observation_id="obs-001", tenant_id="t-1", actor_ref="actor-1",
        incentive_ref="inc-001", disposition=BehaviorDisposition.ALIGNED,
        created_at=TS,
    )
    defaults.update(kw)
    return BehaviorObservation(**defaults)


def _detection(**kw):
    defaults = dict(
        detection_id="det-001", tenant_id="t-1", actor_ref="actor-1",
        incentive_ref="inc-001", risk=RiskOfGaming.HIGH,
        evidence="pattern match", detected_at=TS,
    )
    defaults.update(kw)
    return GamingDetection(**defaults)


def _effect(**kw):
    defaults = dict(
        effect_id="eff-001", tenant_id="t-1", policy_ref="pol-001",
        kind=PolicyEffectKind.INTENDED, description="Improved compliance",
        measured_at=TS,
    )
    defaults.update(kw)
    return PolicyEffect(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="dec-001", tenant_id="t-1", incentive_ref="inc-001",
        disposition="continue", reason="Working as intended", decided_at=TS,
    )
    defaults.update(kw)
    return IncentiveDecision(**defaults)


def _binding(**kw):
    defaults = dict(
        binding_id="bind-001", tenant_id="t-1", contract_ref="con-001",
        incentive_ref="inc-001", created_at=TS,
    )
    defaults.update(kw)
    return ContractIncentiveBinding(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="a-001", tenant_id="t-1", total_incentives=5,
        total_observations=20, total_gaming_detections=2, alignment_rate=0.7,
        assessed_at=TS,
    )
    defaults.update(kw)
    return IncentiveAssessment(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="viol-001", tenant_id="t-1", operation="gaming_unaddressed",
        reason="Gaming not resolved", detected_at=TS,
    )
    defaults.update(kw)
    return IncentiveViolation(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-001", tenant_id="t-1", total_incentives=5,
        total_observations=20, total_detections=2, total_effects=3,
        total_bindings=4, total_violations=1, captured_at=TS,
    )
    defaults.update(kw)
    return IncentiveSnapshot(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="cr-001", tenant_id="t-1", total_incentives=5,
        total_observations=20, total_detections=2, total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return IncentiveClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================

class TestIncentiveStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in IncentiveStatus) == {
            "active", "suspended", "expired", "retired",
        }
    def test_member_count(self):
        assert len(IncentiveStatus) == 4

class TestIncentiveKindEnum:
    def test_all_values(self):
        assert set(e.value for e in IncentiveKind) == {
            "reward", "penalty", "bonus", "discount", "commission", "threshold",
        }
    def test_member_count(self):
        assert len(IncentiveKind) == 6

class TestBehaviorDispositionEnum:
    def test_all_values(self):
        assert set(e.value for e in BehaviorDisposition) == {
            "aligned", "misaligned", "gaming", "neutral",
        }

class TestRiskOfGamingEnum:
    def test_all_values(self):
        assert set(e.value for e in RiskOfGaming) == {
            "low", "moderate", "high", "critical",
        }

class TestPolicyEffectKindEnum:
    def test_all_values(self):
        assert set(e.value for e in PolicyEffectKind) == {
            "intended", "unintended", "perverse", "neutral",
        }

class TestIncentiveRiskLevelEnum:
    def test_all_values(self):
        assert set(e.value for e in IncentiveRiskLevel) == {
            "low", "medium", "high", "critical",
        }


# ===================================================================
# IncentiveRecord
# ===================================================================

class TestIncentiveRecord:
    def test_happy_path(self):
        i = _incentive()
        assert i.incentive_id == "inc-001"
        assert i.kind == IncentiveKind.REWARD
        assert i.status == IncentiveStatus.ACTIVE
        assert i.value == 100.0

    def test_frozen(self):
        i = _incentive()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(i, "incentive_id", "x")

    def test_to_dict_preserves_enum(self):
        i = _incentive()
        data = i.to_dict()
        assert data["kind"] is IncentiveKind.REWARD
        assert data["status"] is IncentiveStatus.ACTIVE

    def test_to_json_dict_serializes_enum(self):
        i = _incentive()
        data = i.to_json_dict()
        assert data["kind"] == "reward"
        assert data["status"] == "active"

    def test_to_json_roundtrip(self):
        i = _incentive()
        parsed = json.loads(i.to_json())
        assert parsed["incentive_id"] == "inc-001"

    def test_metadata_frozen(self):
        i = _incentive(metadata={"k": "v"})
        with pytest.raises(TypeError):
            i.metadata["k2"] = "v2"

    @pytest.mark.parametrize("field,val", [
        ("incentive_id", ""), ("tenant_id", "  "), ("display_name", ""),
        ("target_actor_ref", ""),
    ])
    def test_empty_text_rejected(self, field, val):
        with pytest.raises(ValueError):
            _incentive(**{field: val})

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            _incentive(kind="not_a_kind")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _incentive(status="not_a_status")

    def test_negative_value_rejected(self):
        with pytest.raises(ValueError):
            _incentive(value=-1.0)

    def test_bool_value_rejected(self):
        with pytest.raises(ValueError):
            _incentive(value=True)

    def test_inf_value_rejected(self):
        with pytest.raises(ValueError):
            _incentive(value=float("inf"))

    def test_bad_created_at(self):
        with pytest.raises(ValueError):
            _incentive(created_at="not-a-date")

    @pytest.mark.parametrize("kind", list(IncentiveKind))
    def test_all_kinds_accepted(self, kind):
        i = _incentive(kind=kind)
        assert i.kind is kind

    @pytest.mark.parametrize("status", list(IncentiveStatus))
    def test_all_statuses_accepted(self, status):
        i = _incentive(status=status)
        assert i.status is status

    def test_zero_value(self):
        i = _incentive(value=0.0)
        assert i.value == 0.0

    def test_two_records_equal(self):
        assert _incentive() == _incentive()

    def test_different_ids_not_equal(self):
        assert _incentive() != _incentive(incentive_id="inc-002")


# ===================================================================
# BehaviorObservation
# ===================================================================

class TestBehaviorObservation:
    def test_happy_path(self):
        o = _observation()
        assert o.observation_id == "obs-001"
        assert o.disposition == BehaviorDisposition.ALIGNED

    def test_frozen(self):
        o = _observation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(o, "observation_id", "x")

    @pytest.mark.parametrize("disp", list(BehaviorDisposition))
    def test_all_dispositions(self, disp):
        o = _observation(disposition=disp)
        assert o.disposition is disp

    def test_invalid_disposition(self):
        with pytest.raises(ValueError):
            _observation(disposition="bad")

    @pytest.mark.parametrize("field", ["observation_id", "tenant_id", "actor_ref", "incentive_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _observation(**{field: ""})

    def test_to_dict(self):
        data = _observation().to_dict()
        assert data["disposition"] is BehaviorDisposition.ALIGNED

    def test_to_json(self):
        parsed = json.loads(_observation().to_json())
        assert parsed["disposition"] == "aligned"


# ===================================================================
# GamingDetection
# ===================================================================

class TestGamingDetection:
    def test_happy_path(self):
        d = _detection()
        assert d.detection_id == "det-001"
        assert d.risk == RiskOfGaming.HIGH

    def test_frozen(self):
        d = _detection()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "detection_id", "x")

    @pytest.mark.parametrize("risk", list(RiskOfGaming))
    def test_all_risks(self, risk):
        d = _detection(risk=risk)
        assert d.risk is risk

    def test_invalid_risk(self):
        with pytest.raises(ValueError):
            _detection(risk="bad")

    @pytest.mark.parametrize("field", ["detection_id", "tenant_id", "actor_ref", "incentive_ref", "evidence"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _detection(**{field: ""})

    def test_to_dict(self):
        data = _detection().to_dict()
        assert data["risk"] is RiskOfGaming.HIGH


# ===================================================================
# PolicyEffect
# ===================================================================

class TestPolicyEffect:
    def test_happy_path(self):
        e = _effect()
        assert e.effect_id == "eff-001"
        assert e.kind == PolicyEffectKind.INTENDED

    def test_frozen(self):
        e = _effect()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "effect_id", "x")

    @pytest.mark.parametrize("kind", list(PolicyEffectKind))
    def test_all_kinds(self, kind):
        e = _effect(kind=kind)
        assert e.kind is kind

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            _effect(kind="bad")

    @pytest.mark.parametrize("field", ["effect_id", "tenant_id", "policy_ref", "description"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _effect(**{field: ""})


# ===================================================================
# IncentiveDecision
# ===================================================================

class TestIncentiveDecision:
    def test_happy_path(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.disposition == "continue"

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    @pytest.mark.parametrize("field", ["decision_id", "tenant_id", "incentive_ref", "disposition", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _decision(**{field: ""})

    def test_bad_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="bad")


# ===================================================================
# ContractIncentiveBinding
# ===================================================================

class TestContractIncentiveBinding:
    def test_happy_path(self):
        b = _binding()
        assert b.binding_id == "bind-001"
        assert b.contract_ref == "con-001"

    def test_frozen(self):
        b = _binding()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "binding_id", "x")

    @pytest.mark.parametrize("field", ["binding_id", "tenant_id", "contract_ref", "incentive_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _binding(**{field: ""})

    def test_to_dict(self):
        data = _binding().to_dict()
        assert data["contract_ref"] == "con-001"


# ===================================================================
# IncentiveAssessment
# ===================================================================

class TestIncentiveAssessment:
    def test_happy_path(self):
        a = _assessment()
        assert a.assessment_id == "a-001"
        assert a.alignment_rate == 0.7

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")

    def test_alignment_rate_bounds(self):
        _assessment(alignment_rate=0.0)
        _assessment(alignment_rate=1.0)

    def test_alignment_rate_over_rejected(self):
        with pytest.raises(ValueError):
            _assessment(alignment_rate=1.1)

    def test_alignment_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(alignment_rate=-0.1)

    def test_negative_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_incentives=-1)

    def test_bool_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_incentives=True)


# ===================================================================
# IncentiveViolation
# ===================================================================

class TestIncentiveViolation:
    def test_happy_path(self):
        v = _violation()
        assert v.violation_id == "viol-001"
        assert v.operation == "gaming_unaddressed"

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "operation", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: ""})


# ===================================================================
# IncentiveSnapshot
# ===================================================================

class TestIncentiveSnapshot:
    def test_happy_path(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_incentives == 5

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")

    @pytest.mark.parametrize("field", [
        "total_incentives", "total_observations", "total_detections",
        "total_effects", "total_bindings", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})


# ===================================================================
# IncentiveClosureReport
# ===================================================================

class TestIncentiveClosureReport:
    def test_happy_path(self):
        c = _closure()
        assert c.report_id == "cr-001"
        assert c.total_violations == 1

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "report_id", "x")

    @pytest.mark.parametrize("field", [
        "total_incentives", "total_observations", "total_detections", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    def test_to_json(self):
        parsed = json.loads(_closure().to_json())
        assert parsed["report_id"] == "cr-001"
