"""Tests for adversarial runtime engine (~200 tests).

Covers: AdversarialRuntimeEngine lifecycle, attack scenarios, vulnerabilities,
    exploit paths, defenses, stress tests, assessment, snapshot, closure,
    violation detection, terminal state blocking, state_hash, golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.adversarial_runtime import (
    AttackScenario,
    VulnerabilityRecord,
    ExploitPath,
    DefenseRecord,
    StressTestRecord,
    AdversarialAssessment,
    AdversarialViolation,
    AdversarialSnapshot,
    AdversarialClosureReport,
    AttackStatus,
    AttackKind,
    VulnerabilityStatus,
    ExploitSeverity,
    DefenseDisposition,
)
from mcoi_runtime.core.adversarial_runtime import AdversarialRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

_T1 = "t1"
_T2 = "t2"


def _make_engine(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    eng = AdversarialRuntimeEngine(es, clock=clk)
    return eng, es


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_valid(self):
        eng, _ = _make_engine()
        assert eng.scenario_count == 0
        assert eng.vulnerability_count == 0
        assert eng.exploit_count == 0
        assert eng.defense_count == 0
        assert eng.stress_test_count == 0
        assert eng.violation_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeEngine("bad")

    def test_none_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeEngine(None)

    def test_custom_clock(self):
        clk = FixedClock("2026-06-01T00:00:00+00:00")
        eng, _ = _make_engine(clock=clk)
        s = eng.create_attack_scenario("sc1", _T1, "A1")
        assert s.created_at == "2026-06-01T00:00:00+00:00"

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = AdversarialRuntimeEngine(es, clock=None)
        assert eng.scenario_count == 0


# ---------------------------------------------------------------------------
# Attack scenarios
# ---------------------------------------------------------------------------


class TestAttackScenarios:
    def test_create(self):
        eng, _ = _make_engine()
        s = eng.create_attack_scenario("sc1", _T1, "Attack1")
        assert s.scenario_id == "sc1"
        assert s.status is AttackStatus.PLANNED

    def test_create_with_kind(self):
        eng, _ = _make_engine()
        s = eng.create_attack_scenario("sc1", _T1, "A1", kind=AttackKind.INJECTION)
        assert s.kind is AttackKind.INJECTION

    def test_all_kinds(self):
        eng, _ = _make_engine()
        for i, kind in enumerate(AttackKind):
            s = eng.create_attack_scenario(f"sc{i}", _T1, f"A{i}", kind=kind)
            assert s.kind is kind

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            eng.create_attack_scenario("sc1", _T1, "A1")
        assert "sc1" not in str(exc_info.value)

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.scenario_count == 0
        eng.create_attack_scenario("sc1", _T1, "A1")
        assert eng.scenario_count == 1

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        assert es.event_count >= 1


class TestScenarioTransitions:
    def test_execute(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        s = eng.execute_scenario("sc1")
        assert s.status is AttackStatus.EXECUTING

    def test_complete(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.execute_scenario("sc1")
        s = eng.complete_scenario("sc1")
        assert s.status is AttackStatus.COMPLETED

    def test_block(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        s = eng.block_scenario("sc1")
        assert s.status is AttackStatus.BLOCKED

    def test_terminal_completed_blocks_transition(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.execute_scenario("sc1")
        eng.complete_scenario("sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.execute_scenario("sc1")

    def test_terminal_blocked_blocks_transition(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.block_scenario("sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.execute_scenario("sc1")

    def test_terminal_blocked_blocks_complete(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.block_scenario("sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.complete_scenario("sc1")

    def test_unknown_scenario_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown") as exc_info:
            eng.execute_scenario("missing")
        assert "missing" not in str(exc_info.value)

    def test_transition_emits_event(self):
        eng, es = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        before = es.event_count
        eng.execute_scenario("sc1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Vulnerabilities
# ---------------------------------------------------------------------------


class TestVulnerabilities:
    def test_register(self):
        eng, _ = _make_engine()
        v = eng.register_vulnerability("v1", _T1, "default")
        assert v.vulnerability_id == "v1"
        assert v.status is VulnerabilityStatus.OPEN

    def test_register_with_severity(self):
        eng, _ = _make_engine()
        v = eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        assert v.severity is ExploitSeverity.CRITICAL

    def test_all_severities(self):
        eng, _ = _make_engine()
        for i, sev in enumerate(ExploitSeverity):
            v = eng.register_vulnerability(f"v{i}", _T1, "default", severity=sev)
            assert v.severity is sev

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            eng.register_vulnerability("v1", _T1, "default")
        assert "v1" not in str(exc_info.value)

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.vulnerability_count == 0
        eng.register_vulnerability("v1", _T1, "default")
        assert eng.vulnerability_count == 1


class TestVulnerabilityTransitions:
    def test_mitigate(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        v = eng.mitigate_vulnerability("v1")
        assert v.status is VulnerabilityStatus.MITIGATED

    def test_accept(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        v = eng.accept_vulnerability("v1")
        assert v.status is VulnerabilityStatus.ACCEPTED

    def test_false_positive(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        v = eng.mark_false_positive("v1")
        assert v.status is VulnerabilityStatus.FALSE_POSITIVE

    def test_terminal_mitigated_blocks_transition(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        eng.mitigate_vulnerability("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.accept_vulnerability("v1")

    def test_terminal_accepted_blocks_transition(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        eng.accept_vulnerability("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.mitigate_vulnerability("v1")

    def test_terminal_false_positive_blocks_transition(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default")
        eng.mark_false_positive("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.mitigate_vulnerability("v1")

    def test_unknown_vulnerability_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown") as exc_info:
            eng.mitigate_vulnerability("missing")
        assert "missing" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Exploit paths
# ---------------------------------------------------------------------------


class TestExploitPaths:
    def test_record(self):
        eng, _ = _make_engine()
        ep = eng.record_exploit_path("ep1", _T1, "sc1")
        assert ep.path_id == "ep1"
        assert ep.success is False

    def test_record_success(self):
        eng, _ = _make_engine()
        ep = eng.record_exploit_path("ep1", _T1, "sc1", success=True)
        assert ep.success is True

    def test_record_step_count(self):
        eng, _ = _make_engine()
        ep = eng.record_exploit_path("ep1", _T1, "sc1", step_count=5)
        assert ep.step_count == 5

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_exploit_path("ep1", _T1, "sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_exploit_path("ep1", _T1, "sc1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.exploit_count == 0
        eng.record_exploit_path("ep1", _T1, "sc1")
        assert eng.exploit_count == 1


# ---------------------------------------------------------------------------
# Defenses
# ---------------------------------------------------------------------------


class TestDefenses:
    def test_record(self):
        eng, _ = _make_engine()
        d = eng.record_defense("def1", _T1, "v1")
        assert d.defense_id == "def1"
        assert d.disposition is DefenseDisposition.EFFECTIVE

    def test_record_with_disposition(self):
        eng, _ = _make_engine()
        d = eng.record_defense("def1", _T1, "v1", disposition=DefenseDisposition.PARTIAL)
        assert d.disposition is DefenseDisposition.PARTIAL

    def test_all_dispositions(self):
        eng, _ = _make_engine()
        for i, disp in enumerate(DefenseDisposition):
            d = eng.record_defense(f"def{i}", _T1, "v1", disposition=disp)
            assert d.disposition is disp

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_defense("def1", _T1, "v1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_defense("def1", _T1, "v1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.defense_count == 0
        eng.record_defense("def1", _T1, "v1")
        assert eng.defense_count == 1


# ---------------------------------------------------------------------------
# Stress tests
# ---------------------------------------------------------------------------


class TestStressTests:
    def test_record(self):
        eng, _ = _make_engine()
        st = eng.record_stress_test("st1", _T1, "default")
        assert st.test_id == "st1"
        assert st.load_factor == 1.0

    def test_record_load_factor(self):
        eng, _ = _make_engine()
        st = eng.record_stress_test("st1", _T1, "default", load_factor=5.0)
        assert st.load_factor == 5.0

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_stress_test("st1", _T1, "default")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_stress_test("st1", _T1, "default")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.stress_test_count == 0
        eng.record_stress_test("st1", _T1, "default")
        assert eng.stress_test_count == 1


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class TestAdversarialAssessmentEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        a = eng.adversarial_assessment("aa1", _T1)
        assert a.total_scenarios == 0
        assert a.total_vulnerabilities == 0
        assert a.defense_rate == 0.0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.register_vulnerability("v1", _T1, "default")
        eng.mitigate_vulnerability("v1")
        a = eng.adversarial_assessment("aa1", _T1)
        assert a.total_scenarios == 1
        assert a.total_vulnerabilities == 1
        assert a.total_mitigated == 1
        assert a.defense_rate == 1.0

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.create_attack_scenario("sc2", _T2, "A2")
        a = eng.adversarial_assessment("aa1", _T1)
        assert a.total_scenarios == 1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestAdversarialSnapshotEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        s = eng.adversarial_snapshot("as1", _T1)
        assert s.total_scenarios == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.register_vulnerability("v1", _T1, "default")
        s = eng.adversarial_snapshot("as1", _T1)
        assert s.total_scenarios == 1
        assert s.total_vulnerabilities == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        snap = eng.snapshot()
        assert "scenarios" in snap
        assert "_state_hash" in snap


# ---------------------------------------------------------------------------
# Closure report
# ---------------------------------------------------------------------------


class TestAdversarialClosureEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        r = eng.adversarial_closure_report("ar1", _T1)
        assert r.total_scenarios == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        r = eng.adversarial_closure_report("ar1", _T1)
        assert r.total_scenarios == 1


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


class TestAdversarialViolations:
    def test_no_violations_clean(self):
        eng, _ = _make_engine()
        viols = eng.detect_adversarial_violations(_T1)
        assert len(viols) == 0

    def test_open_critical_vulnerability_violation(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        viols = eng.detect_adversarial_violations(_T1)
        assert any(v.operation == "open_critical_vulnerability" for v in viols)

    def test_unmitigated_exploit_violation(self):
        eng, _ = _make_engine()
        eng.record_exploit_path("ep1", _T1, "sc1", success=True)
        viols = eng.detect_adversarial_violations(_T1)
        assert any(v.operation == "unmitigated_exploit" for v in viols)

    def test_untested_defense_violation(self):
        eng, _ = _make_engine()
        eng.record_defense("def1", _T1, "v1", disposition=DefenseDisposition.UNTESTED)
        viols = eng.detect_adversarial_violations(_T1)
        assert any(v.operation == "untested_defense" for v in viols)

    def test_violation_idempotent(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        first = eng.detect_adversarial_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_adversarial_violations(_T1)
        assert len(second) == 0

    def test_violation_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        viols = eng.detect_adversarial_violations(_T2)
        assert len(viols) == 0

    def test_violation_count_increments(self):
        eng, _ = _make_engine()
        assert eng.violation_count == 0
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        eng.detect_adversarial_violations(_T1)
        assert eng.violation_count >= 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestAdversarialStateHash:
    def test_empty_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_on_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.create_attack_scenario("sc1", _T1, "A1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_64_chars(self):
        eng, _ = _make_engine()
        assert len(eng.state_hash()) == 64

    def test_deterministic_same_ops(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        eng1.create_attack_scenario("sc1", _T1, "A1")
        eng2.create_attack_scenario("sc1", _T1, "A1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_includes_vulnerabilities(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_vulnerability("v1", _T1, "default")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_exploits(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.record_exploit_path("ep1", _T1, "sc1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_defenses(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.record_defense("def1", _T1, "v1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_stress_tests(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.record_stress_test("st1", _T1, "default")
        h2 = eng.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        eng, es = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "Attack1", kind=AttackKind.INJECTION)
        eng.execute_scenario("sc1")
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.HIGH)
        eng.record_exploit_path("ep1", _T1, "sc1", step_count=3, success=True)
        eng.record_defense("def1", _T1, "v1", disposition=DefenseDisposition.EFFECTIVE)
        eng.mitigate_vulnerability("v1")
        eng.complete_scenario("sc1")
        a = eng.adversarial_assessment("aa1", _T1)
        assert a.total_scenarios == 1
        assert a.total_mitigated == 1
        assert a.defense_rate == 1.0
        snap = eng.adversarial_snapshot("as1", _T1)
        assert snap.total_exploits == 1
        assert es.event_count > 0

    def test_attack_blocked_golden(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.block_scenario("sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.execute_scenario("sc1")

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.create_attack_scenario("sc2", _T2, "A2")
        snap1 = eng.adversarial_snapshot("as1", _T1)
        snap2 = eng.adversarial_snapshot("as2", _T2)
        assert snap1.total_scenarios == 1
        assert snap2.total_scenarios == 1

    def test_violation_detection_idempotency_golden(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v1", _T1, "default", severity=ExploitSeverity.CRITICAL)
        first = eng.detect_adversarial_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_adversarial_violations(_T1)
        assert len(second) == 0

    def test_state_hash_determinism_golden(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        for eng in (eng1, eng2):
            eng.create_attack_scenario("sc1", _T1, "A1")
            eng.register_vulnerability("v1", _T1, "default")
            eng.record_exploit_path("ep1", _T1, "sc1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_terminal_state_blocking_golden(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("sc1", _T1, "A1")
        eng.execute_scenario("sc1")
        eng.complete_scenario("sc1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.block_scenario("sc1")
        eng.register_vulnerability("v1", _T1, "default")
        eng.mitigate_vulnerability("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.accept_vulnerability("v1")


class TestBoundedAdversarialContracts:
    def test_terminal_scenario_message_is_bounded(self):
        eng, _ = _make_engine()
        eng.create_attack_scenario("scenario-secret", _T1, "Attack")
        eng.execute_scenario("scenario-secret")
        eng.complete_scenario("scenario-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="scenario is in terminal state") as exc:
            eng.block_scenario("scenario-secret")
        assert "scenario-secret" not in str(exc.value)
        assert "completed" not in str(exc.value).lower()

    def test_terminal_vulnerability_message_is_bounded(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("vuln-secret", _T1, "default")
        eng.mitigate_vulnerability("vuln-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="vulnerability is in terminal state") as exc:
            eng.accept_vulnerability("vuln-secret")
        assert "vuln-secret" not in str(exc.value)
        assert "mitigated" not in str(exc.value).lower()

    def test_violation_reasons_are_bounded(self):
        eng, _ = _make_engine()
        eng.register_vulnerability("v-critical", _T1, "default", severity=ExploitSeverity.CRITICAL)
        eng.record_exploit_path("path-secret", _T1, "scenario-secret", success=True)
        eng.record_defense("defense-secret", _T1, "v-critical", disposition=DefenseDisposition.UNTESTED)
        reasons = {v.reason for v in eng.detect_adversarial_violations(_T1)}
        assert "critical vulnerability remains open" in reasons
        assert "exploit path succeeded without effective defense" in reasons
        assert "defense is untested" in reasons
        assert all("secret" not in reason for reason in reasons)
