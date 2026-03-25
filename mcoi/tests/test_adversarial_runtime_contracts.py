"""Tests for adversarial runtime contracts (~200 tests).

Covers: AttackScenario, VulnerabilityRecord, ExploitPath, DefenseRecord,
    StressTestRecord, AdversarialDecision, AdversarialAssessment,
    AdversarialViolation, AdversarialSnapshot, AdversarialClosureReport, enums.
"""

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.adversarial_runtime import (
    AttackScenario,
    VulnerabilityRecord,
    ExploitPath,
    DefenseRecord,
    StressTestRecord,
    AdversarialDecision,
    AdversarialAssessment,
    AdversarialViolation,
    AdversarialSnapshot,
    AdversarialClosureReport,
    AttackStatus,
    AttackKind,
    VulnerabilityStatus,
    ExploitSeverity,
    DefenseDisposition,
    AdversarialRiskLevel,
)

_NOW = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestAttackStatusEnum:
    def test_values(self):
        assert AttackStatus.PLANNED.value == "planned"
        assert AttackStatus.EXECUTING.value == "executing"
        assert AttackStatus.COMPLETED.value == "completed"
        assert AttackStatus.BLOCKED.value == "blocked"

    def test_member_count(self):
        assert len(AttackStatus) == 4


class TestAttackKindEnum:
    def test_values(self):
        assert AttackKind.POLICY_BYPASS.value == "policy_bypass"
        assert AttackKind.DATA_POISONING.value == "data_poisoning"
        assert AttackKind.PRIVILEGE_ESCALATION.value == "privilege_escalation"
        assert AttackKind.GAMING.value == "gaming"
        assert AttackKind.INJECTION.value == "injection"
        assert AttackKind.DENIAL.value == "denial"

    def test_member_count(self):
        assert len(AttackKind) == 6


class TestVulnerabilityStatusEnum:
    def test_values(self):
        assert VulnerabilityStatus.OPEN.value == "open"
        assert VulnerabilityStatus.MITIGATED.value == "mitigated"
        assert VulnerabilityStatus.ACCEPTED.value == "accepted"
        assert VulnerabilityStatus.FALSE_POSITIVE.value == "false_positive"

    def test_member_count(self):
        assert len(VulnerabilityStatus) == 4


class TestExploitSeverityEnum:
    def test_values(self):
        assert ExploitSeverity.INFORMATIONAL.value == "informational"
        assert ExploitSeverity.LOW.value == "low"
        assert ExploitSeverity.MEDIUM.value == "medium"
        assert ExploitSeverity.HIGH.value == "high"
        assert ExploitSeverity.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(ExploitSeverity) == 5


class TestDefenseDispositionEnum:
    def test_values(self):
        assert DefenseDisposition.EFFECTIVE.value == "effective"
        assert DefenseDisposition.PARTIAL.value == "partial"
        assert DefenseDisposition.INEFFECTIVE.value == "ineffective"
        assert DefenseDisposition.UNTESTED.value == "untested"

    def test_member_count(self):
        assert len(DefenseDisposition) == 4


class TestAdversarialRiskLevelEnum:
    def test_values(self):
        assert AdversarialRiskLevel.LOW.value == "low"
        assert AdversarialRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(AdversarialRiskLevel) == 4


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _scenario(**ov):
    d = dict(scenario_id="sc1", tenant_id="t1", display_name="Attack1",
             kind=AttackKind.POLICY_BYPASS, target_runtime="default",
             status=AttackStatus.PLANNED, created_at=_NOW)
    d.update(ov)
    return AttackScenario(**d)


def _vuln(**ov):
    d = dict(vulnerability_id="v1", tenant_id="t1", target_runtime="default",
             status=VulnerabilityStatus.OPEN, severity=ExploitSeverity.MEDIUM,
             description="vuln desc", detected_at=_NOW)
    d.update(ov)
    return VulnerabilityRecord(**d)


def _exploit(**ov):
    d = dict(path_id="ep1", tenant_id="t1", scenario_ref="sc1",
             step_count=3, success=False, created_at=_NOW)
    d.update(ov)
    return ExploitPath(**d)


def _defense(**ov):
    d = dict(defense_id="def1", tenant_id="t1", vulnerability_ref="v1",
             disposition=DefenseDisposition.EFFECTIVE, mitigation="patched",
             created_at=_NOW)
    d.update(ov)
    return DefenseRecord(**d)


def _stress(**ov):
    d = dict(test_id="st1", tenant_id="t1", target_runtime="default",
             load_factor=1.0, outcome="pass", created_at=_NOW)
    d.update(ov)
    return StressTestRecord(**d)


def _adv_decision(**ov):
    d = dict(decision_id="ad1", tenant_id="t1", scenario_ref="sc1",
             disposition="approved", reason="ok", decided_at=_NOW)
    d.update(ov)
    return AdversarialDecision(**d)


def _adv_assessment(**ov):
    d = dict(assessment_id="aa1", tenant_id="t1", total_scenarios=1,
             total_vulnerabilities=1, total_mitigated=0, defense_rate=0.5,
             assessed_at=_NOW)
    d.update(ov)
    return AdversarialAssessment(**d)


def _adv_violation(**ov):
    d = dict(violation_id="av1", tenant_id="t1", operation="open_crit",
             reason="critical vuln open", detected_at=_NOW)
    d.update(ov)
    return AdversarialViolation(**d)


def _adv_snapshot(**ov):
    d = dict(snapshot_id="as1", tenant_id="t1", total_scenarios=1,
             total_vulnerabilities=1, total_exploits=0, total_defenses=0,
             total_stress_tests=0, total_violations=0, captured_at=_NOW)
    d.update(ov)
    return AdversarialSnapshot(**d)


def _adv_closure(**ov):
    d = dict(report_id="ar1", tenant_id="t1", total_scenarios=1,
             total_vulnerabilities=1, total_defenses=0, total_violations=0,
             created_at=_NOW)
    d.update(ov)
    return AdversarialClosureReport(**d)


# ---------------------------------------------------------------------------
# AttackScenario tests
# ---------------------------------------------------------------------------


class TestAttackScenario:
    def test_valid(self):
        s = _scenario()
        assert s.scenario_id == "sc1"
        assert s.kind is AttackKind.POLICY_BYPASS
        assert s.status is AttackStatus.PLANNED

    def test_all_kinds(self):
        for kind in AttackKind:
            s = _scenario(kind=kind)
            assert s.kind is kind

    def test_all_statuses(self):
        for status in AttackStatus:
            s = _scenario(status=status)
            assert s.status is status

    def test_empty_scenario_id_rejected(self):
        with pytest.raises(ValueError, match="scenario_id"):
            _scenario(scenario_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _scenario(tenant_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _scenario(display_name="")

    def test_empty_target_runtime_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _scenario(target_runtime="")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _scenario(kind="unknown")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _scenario(status="running")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _scenario(created_at="bad")

    def test_frozen(self):
        s = _scenario()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "scenario_id", "x")

    def test_to_dict_preserves_enum(self):
        d = _scenario().to_dict()
        assert d["kind"] is AttackKind.POLICY_BYPASS

    def test_to_json_dict_converts_enum(self):
        d = _scenario().to_json_dict()
        assert d["kind"] == "policy_bypass"

    def test_metadata_frozen(self):
        s = _scenario(metadata={"k": "v"})
        with pytest.raises(TypeError):
            s.metadata["new"] = "fail"


# ---------------------------------------------------------------------------
# VulnerabilityRecord tests
# ---------------------------------------------------------------------------


class TestVulnerabilityRecord:
    def test_valid(self):
        v = _vuln()
        assert v.vulnerability_id == "v1"
        assert v.severity is ExploitSeverity.MEDIUM

    def test_all_statuses(self):
        for status in VulnerabilityStatus:
            v = _vuln(status=status)
            assert v.status is status

    def test_all_severities(self):
        for sev in ExploitSeverity:
            v = _vuln(severity=sev)
            assert v.severity is sev

    def test_empty_vulnerability_id_rejected(self):
        with pytest.raises(ValueError, match="vulnerability_id"):
            _vuln(vulnerability_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _vuln(description="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _vuln(status="patched")

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            _vuln(severity="extreme")

    def test_frozen(self):
        v = _vuln()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "vulnerability_id", "x")

    def test_to_dict(self):
        d = _vuln().to_dict()
        assert d["severity"] is ExploitSeverity.MEDIUM


# ---------------------------------------------------------------------------
# ExploitPath tests
# ---------------------------------------------------------------------------


class TestExploitPath:
    def test_valid(self):
        e = _exploit()
        assert e.path_id == "ep1"
        assert e.success is False
        assert e.step_count == 3

    def test_success_true(self):
        e = _exploit(success=True)
        assert e.success is True

    def test_success_non_bool_rejected(self):
        with pytest.raises(ValueError, match="success"):
            _exploit(success=1)

    def test_success_string_rejected(self):
        with pytest.raises(ValueError, match="success"):
            _exploit(success="true")

    def test_step_count_zero(self):
        e = _exploit(step_count=0)
        assert e.step_count == 0

    def test_step_count_negative_rejected(self):
        with pytest.raises(ValueError, match="step_count"):
            _exploit(step_count=-1)

    def test_step_count_bool_rejected(self):
        with pytest.raises(ValueError, match="step_count"):
            _exploit(step_count=True)

    def test_empty_path_id_rejected(self):
        with pytest.raises(ValueError, match="path_id"):
            _exploit(path_id="")

    def test_empty_scenario_ref_rejected(self):
        with pytest.raises(ValueError, match="scenario_ref"):
            _exploit(scenario_ref="")

    def test_frozen(self):
        e = _exploit()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "path_id", "x")

    def test_to_dict(self):
        d = _exploit().to_dict()
        assert d["success"] is False
        assert d["step_count"] == 3


# ---------------------------------------------------------------------------
# DefenseRecord tests
# ---------------------------------------------------------------------------


class TestDefenseRecord:
    def test_valid(self):
        d = _defense()
        assert d.defense_id == "def1"
        assert d.disposition is DefenseDisposition.EFFECTIVE

    def test_all_dispositions(self):
        for disp in DefenseDisposition:
            d = _defense(disposition=disp)
            assert d.disposition is disp

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _defense(disposition="unknown")

    def test_empty_defense_id_rejected(self):
        with pytest.raises(ValueError, match="defense_id"):
            _defense(defense_id="")

    def test_empty_vulnerability_ref_rejected(self):
        with pytest.raises(ValueError, match="vulnerability_ref"):
            _defense(vulnerability_ref="")

    def test_empty_mitigation_rejected(self):
        with pytest.raises(ValueError, match="mitigation"):
            _defense(mitigation="")

    def test_frozen(self):
        d = _defense()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "defense_id", "x")


# ---------------------------------------------------------------------------
# StressTestRecord tests
# ---------------------------------------------------------------------------


class TestStressTestRecord:
    def test_valid(self):
        s = _stress()
        assert s.test_id == "st1"
        assert s.load_factor == 1.0

    def test_load_factor_zero(self):
        s = _stress(load_factor=0.0)
        assert s.load_factor == 0.0

    def test_load_factor_negative_rejected(self):
        with pytest.raises(ValueError, match="load_factor"):
            _stress(load_factor=-1.0)

    def test_load_factor_nan_rejected(self):
        with pytest.raises(ValueError, match="load_factor"):
            _stress(load_factor=float("nan"))

    def test_load_factor_inf_rejected(self):
        with pytest.raises(ValueError, match="load_factor"):
            _stress(load_factor=float("inf"))

    def test_empty_test_id_rejected(self):
        with pytest.raises(ValueError, match="test_id"):
            _stress(test_id="")

    def test_empty_outcome_rejected(self):
        with pytest.raises(ValueError, match="outcome"):
            _stress(outcome="")

    def test_frozen(self):
        s = _stress()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "test_id", "x")


# ---------------------------------------------------------------------------
# AdversarialDecision tests
# ---------------------------------------------------------------------------


class TestAdversarialDecision:
    def test_valid(self):
        d = _adv_decision()
        assert d.decision_id == "ad1"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _adv_decision(decision_id="")

    def test_empty_scenario_ref_rejected(self):
        with pytest.raises(ValueError, match="scenario_ref"):
            _adv_decision(scenario_ref="")

    def test_empty_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _adv_decision(disposition="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _adv_decision(reason="")

    def test_frozen(self):
        d = _adv_decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")


# ---------------------------------------------------------------------------
# AdversarialAssessment tests
# ---------------------------------------------------------------------------


class TestAdversarialAssessment:
    def test_valid(self):
        a = _adv_assessment()
        assert a.defense_rate == 0.5

    def test_defense_rate_zero(self):
        a = _adv_assessment(defense_rate=0.0)
        assert a.defense_rate == 0.0

    def test_defense_rate_one(self):
        a = _adv_assessment(defense_rate=1.0)
        assert a.defense_rate == 1.0

    def test_defense_rate_negative_rejected(self):
        with pytest.raises(ValueError, match="defense_rate"):
            _adv_assessment(defense_rate=-0.1)

    def test_defense_rate_above_one_rejected(self):
        with pytest.raises(ValueError, match="defense_rate"):
            _adv_assessment(defense_rate=1.1)

    def test_total_scenarios_negative_rejected(self):
        with pytest.raises(ValueError, match="total_scenarios"):
            _adv_assessment(total_scenarios=-1)

    def test_total_vulnerabilities_negative_rejected(self):
        with pytest.raises(ValueError, match="total_vulnerabilities"):
            _adv_assessment(total_vulnerabilities=-1)

    def test_total_mitigated_negative_rejected(self):
        with pytest.raises(ValueError, match="total_mitigated"):
            _adv_assessment(total_mitigated=-1)

    def test_frozen(self):
        a = _adv_assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")


# ---------------------------------------------------------------------------
# AdversarialViolation tests
# ---------------------------------------------------------------------------


class TestAdversarialViolation:
    def test_valid(self):
        v = _adv_violation()
        assert v.violation_id == "av1"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _adv_violation(violation_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _adv_violation(operation="")

    def test_frozen(self):
        v = _adv_violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")


# ---------------------------------------------------------------------------
# AdversarialSnapshot tests
# ---------------------------------------------------------------------------


class TestAdversarialSnapshot:
    def test_valid(self):
        s = _adv_snapshot()
        assert s.snapshot_id == "as1"

    def test_all_counts_zero(self):
        s = _adv_snapshot(total_scenarios=0, total_vulnerabilities=0,
                          total_exploits=0, total_defenses=0,
                          total_stress_tests=0, total_violations=0)
        assert s.total_scenarios == 0

    def test_negative_counts_rejected(self):
        for field in ["total_scenarios", "total_vulnerabilities", "total_exploits",
                      "total_defenses", "total_stress_tests", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _adv_snapshot(**{field: -1})

    def test_frozen(self):
        s = _adv_snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")


# ---------------------------------------------------------------------------
# AdversarialClosureReport tests
# ---------------------------------------------------------------------------


class TestAdversarialClosureReport:
    def test_valid(self):
        r = _adv_closure()
        assert r.report_id == "ar1"

    def test_negative_counts_rejected(self):
        for field in ["total_scenarios", "total_vulnerabilities",
                      "total_defenses", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _adv_closure(**{field: -1})

    def test_frozen(self):
        r = _adv_closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "x")

    def test_to_json_roundtrip(self):
        import json
        r = _adv_closure()
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["report_id"] == "ar1"


# ---------------------------------------------------------------------------
# Cross-cutting tests
# ---------------------------------------------------------------------------


class TestAdversarialCrossCutting:
    def test_all_contracts_have_to_dict(self):
        objs = [_scenario(), _vuln(), _exploit(), _defense(), _stress(),
                _adv_decision(), _adv_assessment(), _adv_violation(),
                _adv_snapshot(), _adv_closure()]
        for obj in objs:
            assert isinstance(obj.to_dict(), dict)

    def test_all_contracts_frozen(self):
        objs = [_scenario(), _vuln(), _exploit(), _defense(), _stress(),
                _adv_decision(), _adv_assessment(), _adv_violation(),
                _adv_snapshot(), _adv_closure()]
        for obj in objs:
            with pytest.raises((FrozenInstanceError, AttributeError)):
                setattr(obj, "tenant_id", "x")

    def test_all_invalid_datetime(self):
        with pytest.raises(ValueError):
            _scenario(created_at="bad")
        with pytest.raises(ValueError):
            _vuln(detected_at="bad")
        with pytest.raises(ValueError):
            _exploit(created_at="bad")
        with pytest.raises(ValueError):
            _defense(created_at="bad")
        with pytest.raises(ValueError):
            _stress(created_at="bad")
        with pytest.raises(ValueError):
            _adv_decision(decided_at="bad")
        with pytest.raises(ValueError):
            _adv_assessment(assessed_at="bad")
        with pytest.raises(ValueError):
            _adv_violation(detected_at="bad")
        with pytest.raises(ValueError):
            _adv_snapshot(captured_at="bad")
        with pytest.raises(ValueError):
            _adv_closure(created_at="bad")

    def test_all_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _scenario(tenant_id="")
        with pytest.raises(ValueError):
            _vuln(tenant_id="")
        with pytest.raises(ValueError):
            _exploit(tenant_id="")
        with pytest.raises(ValueError):
            _defense(tenant_id="")
        with pytest.raises(ValueError):
            _stress(tenant_id="")
        with pytest.raises(ValueError):
            _adv_decision(tenant_id="")
        with pytest.raises(ValueError):
            _adv_assessment(tenant_id="")
        with pytest.raises(ValueError):
            _adv_violation(tenant_id="")
        with pytest.raises(ValueError):
            _adv_snapshot(tenant_id="")
        with pytest.raises(ValueError):
            _adv_closure(tenant_id="")

    def test_all_to_json(self):
        import json
        objs = [_scenario(), _vuln(), _exploit(), _defense(), _stress(),
                _adv_decision(), _adv_assessment(), _adv_violation(),
                _adv_snapshot(), _adv_closure()]
        for obj in objs:
            j = obj.to_json()
            assert isinstance(json.loads(j), dict)
