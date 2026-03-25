"""Comprehensive tests for constitutional governance contracts.

Covers all 6 enums and 10 frozen dataclasses in
mcoi.mcoi_runtime.contracts.constitutional_governance.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.constitutional_governance import (
    ConstitutionAssessment,
    ConstitutionBundle,
    ConstitutionClosureReport,
    ConstitutionDecision,
    ConstitutionRule,
    ConstitutionRuleKind,
    ConstitutionSnapshot,
    ConstitutionStatus,
    ConstitutionViolation,
    EmergencyGovernanceRecord,
    EmergencyMode,
    GlobalOverrideRecord,
    GlobalPolicyDisposition,
    OverrideDisposition,
    PrecedenceLevel,
    PrecedenceResolution,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T00:00:00+00:00"
TS2 = "2025-07-15T12:30:00+00:00"


# ===================================================================
# Section 1 -- Enum tests
# ===================================================================


class TestConstitutionStatus:
    def test_member_count(self):
        assert len(ConstitutionStatus) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (ConstitutionStatus.DRAFT, "draft"),
            (ConstitutionStatus.ACTIVE, "active"),
            (ConstitutionStatus.SUSPENDED, "suspended"),
            (ConstitutionStatus.RETIRED, "retired"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["draft", "active", "suspended", "retired"])
    def test_lookup_by_value(self, value):
        assert ConstitutionStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ConstitutionStatus("invalid")


class TestConstitutionRuleKind:
    def test_member_count(self):
        assert len(ConstitutionRuleKind) == 5

    @pytest.mark.parametrize(
        "member, value",
        [
            (ConstitutionRuleKind.HARD_DENY, "hard_deny"),
            (ConstitutionRuleKind.SOFT_DENY, "soft_deny"),
            (ConstitutionRuleKind.ALLOW, "allow"),
            (ConstitutionRuleKind.RESTRICT, "restrict"),
            (ConstitutionRuleKind.REQUIRE, "require"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize(
        "value", ["hard_deny", "soft_deny", "allow", "restrict", "require"]
    )
    def test_lookup_by_value(self, value):
        assert ConstitutionRuleKind(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ConstitutionRuleKind("nope")


class TestPrecedenceLevel:
    def test_member_count(self):
        assert len(PrecedenceLevel) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (PrecedenceLevel.CONSTITUTIONAL, "constitutional"),
            (PrecedenceLevel.PLATFORM, "platform"),
            (PrecedenceLevel.TENANT, "tenant"),
            (PrecedenceLevel.RUNTIME, "runtime"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize(
        "value", ["constitutional", "platform", "tenant", "runtime"]
    )
    def test_lookup_by_value(self, value):
        assert PrecedenceLevel(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            PrecedenceLevel("x")


class TestOverrideDisposition:
    def test_member_count(self):
        assert len(OverrideDisposition) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (OverrideDisposition.APPLIED, "applied"),
            (OverrideDisposition.DENIED, "denied"),
            (OverrideDisposition.RECORDED, "recorded"),
            (OverrideDisposition.EXPIRED, "expired"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["applied", "denied", "recorded", "expired"])
    def test_lookup_by_value(self, value):
        assert OverrideDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            OverrideDisposition("bad")


class TestEmergencyMode:
    def test_member_count(self):
        assert len(EmergencyMode) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (EmergencyMode.NORMAL, "normal"),
            (EmergencyMode.LOCKDOWN, "lockdown"),
            (EmergencyMode.DEGRADED, "degraded"),
            (EmergencyMode.RESTRICTED, "restricted"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["normal", "lockdown", "degraded", "restricted"])
    def test_lookup_by_value(self, value):
        assert EmergencyMode(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            EmergencyMode("panic")


class TestGlobalPolicyDisposition:
    def test_member_count(self):
        assert len(GlobalPolicyDisposition) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (GlobalPolicyDisposition.ALLOWED, "allowed"),
            (GlobalPolicyDisposition.DENIED, "denied"),
            (GlobalPolicyDisposition.RESTRICTED, "restricted"),
            (GlobalPolicyDisposition.ESCALATED, "escalated"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize(
        "value", ["allowed", "denied", "restricted", "escalated"]
    )
    def test_lookup_by_value(self, value):
        assert GlobalPolicyDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            GlobalPolicyDisposition("nah")


# ===================================================================
# Section 2 -- Dataclass tests
# ===================================================================


# --- helpers ---

def _make_rule(**overrides):
    defaults = dict(
        rule_id="rule-1",
        tenant_id="t-1",
        display_name="Block All",
        kind=ConstitutionRuleKind.HARD_DENY,
        precedence=PrecedenceLevel.CONSTITUTIONAL,
        status=ConstitutionStatus.ACTIVE,
        target_runtime="rt-1",
        target_action="act-1",
        created_at=TS,
        metadata={"k": "v"},
    )
    defaults.update(overrides)
    return ConstitutionRule(**defaults)


def _make_bundle(**overrides):
    defaults = dict(
        bundle_id="bun-1",
        tenant_id="t-1",
        display_name="Core Bundle",
        rule_count=5,
        status=ConstitutionStatus.ACTIVE,
        created_at=TS,
        metadata={"x": 1},
    )
    defaults.update(overrides)
    return ConstitutionBundle(**defaults)


def _make_override(**overrides):
    defaults = dict(
        override_id="ovr-1",
        rule_id="rule-1",
        tenant_id="t-1",
        authority_ref="auth-1",
        disposition=OverrideDisposition.APPLIED,
        reason="emergency",
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return GlobalOverrideRecord(**defaults)


def _make_emergency(**overrides):
    defaults = dict(
        emergency_id="em-1",
        tenant_id="t-1",
        mode=EmergencyMode.LOCKDOWN,
        previous_mode=EmergencyMode.NORMAL,
        authority_ref="auth-1",
        reason="incident",
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return EmergencyGovernanceRecord(**defaults)


def _make_decision(**overrides):
    defaults = dict(
        decision_id="dec-1",
        tenant_id="t-1",
        target_runtime="rt-1",
        target_action="act-1",
        disposition=GlobalPolicyDisposition.ALLOWED,
        matched_rule_id="rule-1",
        emergency_mode=EmergencyMode.NORMAL,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ConstitutionDecision(**defaults)


def _make_violation(**overrides):
    defaults = dict(
        violation_id="viol-1",
        tenant_id="t-1",
        operation="op-bad",
        reason="violated rule X",
        detected_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ConstitutionViolation(**defaults)


def _make_precedence(**overrides):
    defaults = dict(
        resolution_id="res-1",
        tenant_id="t-1",
        winning_rule_id="rule-1",
        losing_rule_id="rule-2",
        winning_precedence=PrecedenceLevel.CONSTITUTIONAL,
        losing_precedence=PrecedenceLevel.RUNTIME,
        resolved_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return PrecedenceResolution(**defaults)


def _make_snapshot(**overrides):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id="t-1",
        total_rules=10,
        active_rules=8,
        total_bundles=2,
        total_overrides=1,
        total_decisions=50,
        total_violations=3,
        emergency_mode=EmergencyMode.NORMAL,
        captured_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ConstitutionSnapshot(**defaults)


def _make_assessment(**overrides):
    defaults = dict(
        assessment_id="assess-1",
        tenant_id="t-1",
        total_rules=10,
        active_rules=8,
        compliance_score=0.95,
        override_count=1,
        violation_count=2,
        assessed_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ConstitutionAssessment(**defaults)


def _make_closure(**overrides):
    defaults = dict(
        report_id="rpt-1",
        tenant_id="t-1",
        total_rules=10,
        total_bundles=2,
        total_overrides=1,
        total_decisions=50,
        total_violations=3,
        total_resolutions=7,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ConstitutionClosureReport(**defaults)


# ===================================================================
# ConstitutionRule
# ===================================================================


class TestConstitutionRule:
    def test_valid_construction(self):
        r = _make_rule()
        assert r.rule_id == "rule-1"
        assert r.tenant_id == "t-1"
        assert r.kind == ConstitutionRuleKind.HARD_DENY
        assert r.precedence == PrecedenceLevel.CONSTITUTIONAL
        assert r.status == ConstitutionStatus.ACTIVE

    def test_frozen(self):
        r = _make_rule()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.rule_id = "other"

    def test_metadata_is_mapping_proxy(self):
        r = _make_rule(metadata={"a": "b"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_immutable(self):
        r = _make_rule(metadata={"a": "b"})
        with pytest.raises(TypeError):
            r.metadata["a"] = "c"

    def test_to_dict_preserves_enums(self):
        r = _make_rule()
        d = r.to_dict()
        assert d["kind"] is ConstitutionRuleKind.HARD_DENY
        assert d["precedence"] is PrecedenceLevel.CONSTITUTIONAL
        assert d["status"] is ConstitutionStatus.ACTIVE

    def test_to_dict_metadata_is_plain_dict(self):
        r = _make_rule(metadata={"k": "v"})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize(
        "field_name",
        ["rule_id", "tenant_id", "display_name", "target_runtime", "target_action"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_rule(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["rule_id", "tenant_id", "display_name", "target_runtime", "target_action"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_rule(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_rule(created_at="not-a-date")

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_rule(created_at="")

    def test_all_enum_kinds(self):
        for kind in ConstitutionRuleKind:
            r = _make_rule(kind=kind)
            assert r.kind is kind

    def test_all_precedence_levels(self):
        for p in PrecedenceLevel:
            r = _make_rule(precedence=p)
            assert r.precedence is p

    def test_all_statuses(self):
        for s in ConstitutionStatus:
            r = _make_rule(status=s)
            assert r.status is s

    def test_nested_metadata_frozen(self):
        r = _make_rule(metadata={"inner": {"deep": 1}})
        assert isinstance(r.metadata["inner"], MappingProxyType)

    def test_list_in_metadata_becomes_tuple(self):
        r = _make_rule(metadata={"items": [1, 2, 3]})
        assert r.metadata["items"] == (1, 2, 3)

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ConstitutionRule)

    def test_has_slots(self):
        assert hasattr(ConstitutionRule, "__slots__")


# ===================================================================
# ConstitutionBundle
# ===================================================================


class TestConstitutionBundle:
    def test_valid_construction(self):
        b = _make_bundle()
        assert b.bundle_id == "bun-1"
        assert b.rule_count == 5

    def test_frozen(self):
        b = _make_bundle()
        with pytest.raises(dataclasses.FrozenInstanceError):
            b.bundle_id = "x"

    def test_metadata_is_mapping_proxy(self):
        b = _make_bundle()
        assert isinstance(b.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        b = _make_bundle()
        d = b.to_dict()
        assert d["status"] is ConstitutionStatus.ACTIVE

    @pytest.mark.parametrize("field_name", ["bundle_id", "tenant_id", "display_name"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_bundle(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["bundle_id", "tenant_id", "display_name"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_bundle(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_bundle(created_at="xyz")

    def test_negative_rule_count_rejected(self):
        with pytest.raises(ValueError):
            _make_bundle(rule_count=-1)

    def test_zero_rule_count_accepted(self):
        b = _make_bundle(rule_count=0)
        assert b.rule_count == 0

    def test_positive_rule_count(self):
        b = _make_bundle(rule_count=100)
        assert b.rule_count == 100

    def test_all_statuses(self):
        for s in ConstitutionStatus:
            b = _make_bundle(status=s)
            assert b.status is s


# ===================================================================
# GlobalOverrideRecord
# ===================================================================


class TestGlobalOverrideRecord:
    def test_valid_construction(self):
        o = _make_override()
        assert o.override_id == "ovr-1"
        assert o.disposition is OverrideDisposition.APPLIED

    def test_frozen(self):
        o = _make_override()
        with pytest.raises(dataclasses.FrozenInstanceError):
            o.override_id = "x"

    def test_metadata_is_mapping_proxy(self):
        o = _make_override(metadata={"z": 1})
        assert isinstance(o.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_override().to_dict()
        assert d["disposition"] is OverrideDisposition.APPLIED

    @pytest.mark.parametrize(
        "field_name", ["override_id", "rule_id", "tenant_id", "authority_ref"]
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_override(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name", ["override_id", "rule_id", "tenant_id", "authority_ref"]
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_override(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_override(created_at="nope")

    def test_all_dispositions(self):
        for d in OverrideDisposition:
            o = _make_override(disposition=d)
            assert o.disposition is d


# ===================================================================
# EmergencyGovernanceRecord
# ===================================================================


class TestEmergencyGovernanceRecord:
    def test_valid_construction(self):
        e = _make_emergency()
        assert e.emergency_id == "em-1"
        assert e.mode is EmergencyMode.LOCKDOWN
        assert e.previous_mode is EmergencyMode.NORMAL

    def test_frozen(self):
        e = _make_emergency()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.emergency_id = "x"

    def test_metadata_is_mapping_proxy(self):
        e = _make_emergency(metadata={"a": 1})
        assert isinstance(e.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_emergency().to_dict()
        assert d["mode"] is EmergencyMode.LOCKDOWN
        assert d["previous_mode"] is EmergencyMode.NORMAL

    @pytest.mark.parametrize(
        "field_name", ["emergency_id", "tenant_id", "authority_ref"]
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_emergency(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name", ["emergency_id", "tenant_id", "authority_ref"]
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_emergency(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_emergency(created_at="bad")

    def test_all_modes(self):
        for m in EmergencyMode:
            e = _make_emergency(mode=m)
            assert e.mode is m

    def test_all_previous_modes(self):
        for m in EmergencyMode:
            e = _make_emergency(previous_mode=m)
            assert e.previous_mode is m


# ===================================================================
# ConstitutionDecision
# ===================================================================


class TestConstitutionDecision:
    def test_valid_construction(self):
        d = _make_decision()
        assert d.decision_id == "dec-1"
        assert d.disposition is GlobalPolicyDisposition.ALLOWED
        assert d.emergency_mode is EmergencyMode.NORMAL

    def test_frozen(self):
        d = _make_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.decision_id = "x"

    def test_metadata_is_mapping_proxy(self):
        d = _make_decision(metadata={"r": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        dd = _make_decision().to_dict()
        assert dd["disposition"] is GlobalPolicyDisposition.ALLOWED
        assert dd["emergency_mode"] is EmergencyMode.NORMAL

    @pytest.mark.parametrize(
        "field_name",
        ["decision_id", "tenant_id", "target_runtime", "target_action"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_decision(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["decision_id", "tenant_id", "target_runtime", "target_action"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_decision(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_decision(created_at="oops")

    def test_all_dispositions(self):
        for dp in GlobalPolicyDisposition:
            d = _make_decision(disposition=dp)
            assert d.disposition is dp

    def test_all_emergency_modes(self):
        for m in EmergencyMode:
            d = _make_decision(emergency_mode=m)
            assert d.emergency_mode is m


# ===================================================================
# ConstitutionViolation
# ===================================================================


class TestConstitutionViolation:
    def test_valid_construction(self):
        v = _make_violation()
        assert v.violation_id == "viol-1"
        assert v.operation == "op-bad"

    def test_frozen(self):
        v = _make_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.violation_id = "x"

    def test_metadata_is_mapping_proxy(self):
        v = _make_violation(metadata={"q": 2})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _make_violation().to_dict()
        expected_keys = {
            "violation_id", "tenant_id", "operation", "reason",
            "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize(
        "field_name", ["violation_id", "tenant_id", "operation", "reason"]
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_violation(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name", ["violation_id", "tenant_id", "operation", "reason"]
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_violation(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_violation(detected_at="abc")

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_violation(detected_at="")


# ===================================================================
# PrecedenceResolution
# ===================================================================


class TestPrecedenceResolution:
    def test_valid_construction(self):
        p = _make_precedence()
        assert p.resolution_id == "res-1"
        assert p.winning_precedence is PrecedenceLevel.CONSTITUTIONAL
        assert p.losing_precedence is PrecedenceLevel.RUNTIME

    def test_frozen(self):
        p = _make_precedence()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.resolution_id = "x"

    def test_metadata_is_mapping_proxy(self):
        p = _make_precedence(metadata={"w": 3})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_precedence().to_dict()
        assert d["winning_precedence"] is PrecedenceLevel.CONSTITUTIONAL
        assert d["losing_precedence"] is PrecedenceLevel.RUNTIME

    @pytest.mark.parametrize(
        "field_name",
        ["resolution_id", "tenant_id", "winning_rule_id", "losing_rule_id"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_precedence(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["resolution_id", "tenant_id", "winning_rule_id", "losing_rule_id"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_precedence(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_precedence(resolved_at="nope")

    def test_all_winning_precedences(self):
        for p in PrecedenceLevel:
            r = _make_precedence(winning_precedence=p)
            assert r.winning_precedence is p

    def test_all_losing_precedences(self):
        for p in PrecedenceLevel:
            r = _make_precedence(losing_precedence=p)
            assert r.losing_precedence is p


# ===================================================================
# ConstitutionSnapshot
# ===================================================================


class TestConstitutionSnapshot:
    def test_valid_construction(self):
        s = _make_snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.total_rules == 10
        assert s.emergency_mode is EmergencyMode.NORMAL

    def test_frozen(self):
        s = _make_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "x"

    def test_metadata_is_mapping_proxy(self):
        s = _make_snapshot(metadata={"m": 9})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_snapshot().to_dict()
        assert d["emergency_mode"] is EmergencyMode.NORMAL

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_snapshot(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_snapshot(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_snapshot(captured_at="bad")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_rules", "active_rules", "total_bundles",
            "total_overrides", "total_decisions", "total_violations",
        ],
    )
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_snapshot(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_rules", "active_rules", "total_bundles",
            "total_overrides", "total_decisions", "total_violations",
        ],
    )
    def test_zero_accepted(self, field_name):
        s = _make_snapshot(**{field_name: 0})
        assert getattr(s, field_name) == 0

    def test_all_emergency_modes(self):
        for m in EmergencyMode:
            s = _make_snapshot(emergency_mode=m)
            assert s.emergency_mode is m


# ===================================================================
# ConstitutionAssessment
# ===================================================================


class TestConstitutionAssessment:
    def test_valid_construction(self):
        a = _make_assessment()
        assert a.assessment_id == "assess-1"
        assert a.compliance_score == 0.95

    def test_frozen(self):
        a = _make_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.assessment_id = "x"

    def test_metadata_is_mapping_proxy(self):
        a = _make_assessment(metadata={"p": 0})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _make_assessment().to_dict()
        expected = {
            "assessment_id", "tenant_id", "total_rules", "active_rules",
            "compliance_score", "override_count", "violation_count",
            "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_assessment(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_assessment(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(assessed_at="nah")

    # --- compliance_score unit_float boundary tests ---

    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_compliance_score_valid(self, score):
        a = _make_assessment(compliance_score=score)
        assert a.compliance_score == score

    def test_compliance_score_negative_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=-0.1)

    def test_compliance_score_over_one_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=1.1)

    @pytest.mark.parametrize(
        "field_name",
        ["total_rules", "active_rules", "override_count", "violation_count"],
    )
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_assessment(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        ["total_rules", "active_rules", "override_count", "violation_count"],
    )
    def test_zero_accepted(self, field_name):
        a = _make_assessment(**{field_name: 0})
        assert getattr(a, field_name) == 0

    @pytest.mark.parametrize(
        "field_name",
        ["total_rules", "active_rules", "override_count", "violation_count"],
    )
    def test_positive_int_accepted(self, field_name):
        a = _make_assessment(**{field_name: 1})
        assert getattr(a, field_name) == 1


# ===================================================================
# ConstitutionClosureReport
# ===================================================================


class TestConstitutionClosureReport:
    def test_valid_construction(self):
        c = _make_closure()
        assert c.report_id == "rpt-1"
        assert c.total_resolutions == 7

    def test_frozen(self):
        c = _make_closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.report_id = "x"

    def test_metadata_is_mapping_proxy(self):
        c = _make_closure(metadata={"f": 5})
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _make_closure().to_dict()
        expected = {
            "report_id", "tenant_id", "total_rules", "total_bundles",
            "total_overrides", "total_decisions", "total_violations",
            "total_resolutions", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_closure(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_closure(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_closure(created_at="bad")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_rules", "total_bundles", "total_overrides",
            "total_decisions", "total_violations", "total_resolutions",
        ],
    )
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_closure(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_rules", "total_bundles", "total_overrides",
            "total_decisions", "total_violations", "total_resolutions",
        ],
    )
    def test_zero_accepted(self, field_name):
        c = _make_closure(**{field_name: 0})
        assert getattr(c, field_name) == 0

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_rules", "total_bundles", "total_overrides",
            "total_decisions", "total_violations", "total_resolutions",
        ],
    )
    def test_positive_int_accepted(self, field_name):
        c = _make_closure(**{field_name: 1})
        assert getattr(c, field_name) == 1


# ===================================================================
# Section 3 -- Cross-cutting parametrized tests
# ===================================================================


class TestUnitFloatBoundaries:
    """Parametrized boundary tests for unit_float via ConstitutionAssessment."""

    @pytest.mark.parametrize("val", [0.0, 1.0, 0.5, 0.001, 0.999])
    def test_valid_unit_float(self, val):
        a = _make_assessment(compliance_score=val)
        assert a.compliance_score == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.1, -1.0, -0.001])
    def test_below_zero_rejected(self, val):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=val)

    @pytest.mark.parametrize("val", [1.1, 2.0, 1.001])
    def test_above_one_rejected(self, val):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=val)

    def test_int_zero_accepted(self):
        a = _make_assessment(compliance_score=0)
        assert a.compliance_score == 0.0

    def test_int_one_accepted(self):
        a = _make_assessment(compliance_score=1)
        assert a.compliance_score == 1.0

    def test_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=True)

    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=float("inf"))

    def test_neg_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_assessment(compliance_score=float("-inf"))


class TestNonNegativeIntBoundaries:
    """Parametrized boundary tests for non_negative_int across multiple classes."""

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_bundle, "rule_count"),
            (_make_snapshot, "total_rules"),
            (_make_snapshot, "active_rules"),
            (_make_snapshot, "total_bundles"),
            (_make_snapshot, "total_overrides"),
            (_make_snapshot, "total_decisions"),
            (_make_snapshot, "total_violations"),
            (_make_assessment, "total_rules"),
            (_make_assessment, "active_rules"),
            (_make_assessment, "override_count"),
            (_make_assessment, "violation_count"),
            (_make_closure, "total_rules"),
            (_make_closure, "total_bundles"),
            (_make_closure, "total_overrides"),
            (_make_closure, "total_decisions"),
            (_make_closure, "total_violations"),
            (_make_closure, "total_resolutions"),
        ],
    )
    def test_zero_accepted(self, factory, field_name):
        obj = factory(**{field_name: 0})
        assert getattr(obj, field_name) == 0

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_bundle, "rule_count"),
            (_make_snapshot, "total_rules"),
            (_make_snapshot, "active_rules"),
            (_make_assessment, "total_rules"),
            (_make_assessment, "override_count"),
            (_make_closure, "total_rules"),
            (_make_closure, "total_resolutions"),
        ],
    )
    def test_negative_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: -1})

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_bundle, "rule_count"),
            (_make_snapshot, "total_rules"),
            (_make_assessment, "total_rules"),
            (_make_closure, "total_rules"),
        ],
    )
    def test_positive_accepted(self, factory, field_name):
        obj = factory(**{field_name: 1})
        assert getattr(obj, field_name) == 1


class TestDatetimeTextValidation:
    """Datetime text validation across all dataclasses."""

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_rule, "created_at"),
            (_make_bundle, "created_at"),
            (_make_override, "created_at"),
            (_make_emergency, "created_at"),
            (_make_decision, "created_at"),
            (_make_violation, "detected_at"),
            (_make_precedence, "resolved_at"),
            (_make_snapshot, "captured_at"),
            (_make_assessment, "assessed_at"),
            (_make_closure, "created_at"),
        ],
    )
    def test_valid_iso_datetime(self, factory, field_name):
        obj = factory(**{field_name: "2025-06-01T12:00:00+00:00"})
        assert getattr(obj, field_name) == "2025-06-01T12:00:00+00:00"

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_rule, "created_at"),
            (_make_bundle, "created_at"),
            (_make_override, "created_at"),
            (_make_emergency, "created_at"),
            (_make_decision, "created_at"),
            (_make_violation, "detected_at"),
            (_make_precedence, "resolved_at"),
            (_make_snapshot, "captured_at"),
            (_make_assessment, "assessed_at"),
            (_make_closure, "created_at"),
        ],
    )
    def test_empty_datetime_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: ""})

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_rule, "created_at"),
            (_make_bundle, "created_at"),
            (_make_override, "created_at"),
            (_make_emergency, "created_at"),
            (_make_decision, "created_at"),
            (_make_violation, "detected_at"),
            (_make_precedence, "resolved_at"),
            (_make_snapshot, "captured_at"),
            (_make_assessment, "assessed_at"),
            (_make_closure, "created_at"),
        ],
    )
    def test_garbage_datetime_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: "not-a-date"})

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_rule, "created_at"),
            (_make_bundle, "created_at"),
            (_make_violation, "detected_at"),
        ],
    )
    def test_zulu_datetime_accepted(self, factory, field_name):
        obj = factory(**{field_name: "2025-06-01T00:00:00Z"})
        assert getattr(obj, field_name) == "2025-06-01T00:00:00Z"


class TestMetadataFreezing:
    """Metadata freezing behaviour across all dataclasses."""

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_metadata_is_mapping_proxy(self, factory):
        obj = factory(metadata={"a": 1})
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_metadata_immutable(self, factory):
        obj = factory(metadata={"a": 1})
        with pytest.raises(TypeError):
            obj.metadata["a"] = 2

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_empty_metadata_accepted(self, factory):
        obj = factory(metadata={})
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_nested_dict_in_metadata_frozen(self, factory):
        obj = factory(metadata={"inner": {"deep": 1}})
        assert isinstance(obj.metadata["inner"], MappingProxyType)

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_list_in_metadata_becomes_tuple(self, factory):
        obj = factory(metadata={"items": [1, 2]})
        assert obj.metadata["items"] == (1, 2)


class TestToDictMetadataThawed:
    """to_dict() returns plain dicts for metadata."""

    @pytest.mark.parametrize(
        "factory",
        [
            _make_rule, _make_bundle, _make_override, _make_emergency,
            _make_decision, _make_violation, _make_precedence,
            _make_snapshot, _make_assessment, _make_closure,
        ],
    )
    def test_metadata_is_dict_in_to_dict(self, factory):
        obj = factory(metadata={"k": "v"})
        d = obj.to_dict()
        assert isinstance(d["metadata"], dict)


class TestFrozenImmutability:
    """All dataclasses raise FrozenInstanceError on attribute assignment."""

    @pytest.mark.parametrize(
        "factory, field_name",
        [
            (_make_rule, "rule_id"),
            (_make_bundle, "bundle_id"),
            (_make_override, "override_id"),
            (_make_emergency, "emergency_id"),
            (_make_decision, "decision_id"),
            (_make_violation, "violation_id"),
            (_make_precedence, "resolution_id"),
            (_make_snapshot, "snapshot_id"),
            (_make_assessment, "assessment_id"),
            (_make_closure, "report_id"),
        ],
    )
    def test_frozen_raises(self, factory, field_name):
        obj = factory()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field_name, "mutated")


class TestIsDataclassAndSlots:
    """All 10 dataclasses have __dataclass_fields__ and __slots__."""

    @pytest.mark.parametrize(
        "cls",
        [
            ConstitutionRule, ConstitutionBundle, GlobalOverrideRecord,
            EmergencyGovernanceRecord, ConstitutionDecision, ConstitutionViolation,
            PrecedenceResolution, ConstitutionSnapshot, ConstitutionAssessment,
            ConstitutionClosureReport,
        ],
    )
    def test_is_dataclass(self, cls):
        assert dataclasses.is_dataclass(cls)

    @pytest.mark.parametrize(
        "cls",
        [
            ConstitutionRule, ConstitutionBundle, GlobalOverrideRecord,
            EmergencyGovernanceRecord, ConstitutionDecision, ConstitutionViolation,
            PrecedenceResolution, ConstitutionSnapshot, ConstitutionAssessment,
            ConstitutionClosureReport,
        ],
    )
    def test_has_slots(self, cls):
        assert hasattr(cls, "__slots__")


class TestAlternateDatetimeFormats:
    """Additional datetime format acceptance tests."""

    def test_date_only_accepted(self):
        # Python 3.11+ accepts date-only strings via fromisoformat
        r = _make_rule(created_at="2025-06-01")
        assert r.created_at == "2025-06-01"

    def test_datetime_with_offset(self):
        r = _make_rule(created_at="2025-06-01T12:30:00-05:00")
        assert r.created_at == "2025-06-01T12:30:00-05:00"

    def test_datetime_zulu(self):
        r = _make_rule(created_at="2025-06-01T00:00:00Z")
        assert r.created_at == "2025-06-01T00:00:00Z"

    def test_datetime_microseconds(self):
        r = _make_rule(created_at="2025-06-01T12:00:00.123456+00:00")
        assert r.created_at == "2025-06-01T12:00:00.123456+00:00"
