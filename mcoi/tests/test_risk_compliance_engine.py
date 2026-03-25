"""Comprehensive tests for RiskComplianceEngine.

Covers: risk management, requirement registration, control lifecycle,
    control bindings, control testing with auto-status transitions,
    exception lifecycle, control failure recording, risk assessment,
    compliance snapshots, assurance reports, query helpers, properties,
    state_hash, event emission, and invariant-violation error paths.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.risk_compliance import RiskComplianceEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.risk_compliance import (
    RiskSeverity,
    RiskCategory,
    ControlStatus,
    ControlTestStatus,
    ExceptionStatus,
    ComplianceDisposition,
    EvidenceSourceKind,
    RiskRecord,
    ControlRecord,
    ControlBinding,
    ControlTestRecord,
    ComplianceRequirement,
    ExceptionRequest,
    RiskAssessment,
    ComplianceSnapshot,
    ControlFailure,
    AssuranceReport,
)


# ======================================================================
# Fixture
# ======================================================================


@pytest.fixture
def env():
    es = EventSpineEngine()
    eng = RiskComplianceEngine(es)
    return es, eng


# ======================================================================
# Helpers
# ======================================================================


def _register_risk(eng, risk_id="r1", title="Risk One", **kw):
    defaults = dict(
        severity=RiskSeverity.MEDIUM,
        category=RiskCategory.OPERATIONAL,
        likelihood=0.5,
        impact=0.5,
        scope_ref_id="scope-1",
        owner="owner-1",
        mitigations=["m1"],
    )
    defaults.update(kw)
    return eng.register_risk(risk_id, title, **defaults)


def _register_control(eng, control_id="c1", title="Control One", **kw):
    defaults = dict(requirement_id="req-1", test_frequency_seconds=3600.0, owner="owner-1")
    defaults.update(kw)
    return eng.register_control(control_id, title, **defaults)


def _register_requirement(eng, requirement_id="req-1", title="Req One", **kw):
    defaults = dict(
        category=RiskCategory.COMPLIANCE,
        mandatory=True,
        control_ids=["c1"],
        evidence_source_kinds=["artifact"],
    )
    defaults.update(kw)
    return eng.register_requirement(requirement_id, title, **defaults)


def _bind_control(eng, binding_id="b1", control_id="c1", scope_ref_id="scope-1", **kw):
    return eng.bind_control(binding_id, control_id, scope_ref_id, **kw)


# ======================================================================
# 1  Risk management
# ======================================================================


class TestRegisterRisk:
    def test_basic_registration(self, env):
        es, eng = env
        r = _register_risk(eng)
        assert isinstance(r, RiskRecord)
        assert r.risk_id == "r1"
        assert r.title == "Risk One"
        assert r.severity == RiskSeverity.MEDIUM
        assert r.category == RiskCategory.OPERATIONAL
        assert r.likelihood == 0.5
        assert r.impact == 0.5
        assert r.scope_ref_id == "scope-1"
        assert r.owner == "owner-1"
        assert r.mitigations == ("m1",)
        assert r.created_at != ""

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        _register_risk(eng)
        assert len(es.list_events()) > before

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate risk_id"):
            _register_risk(eng, risk_id="r1")

    def test_risk_count_property(self, env):
        _, eng = env
        assert eng.risk_count == 0
        _register_risk(eng, risk_id="r1")
        assert eng.risk_count == 1
        _register_risk(eng, risk_id="r2")
        assert eng.risk_count == 2

    def test_no_mitigations_defaults_empty(self, env):
        _, eng = env
        r = eng.register_risk(
            "r1", "Risk", severity=RiskSeverity.LOW,
            category=RiskCategory.SECURITY, likelihood=0.1, impact=0.1,
            scope_ref_id="s", owner="o",
        )
        assert r.mitigations == ()

    def test_severity_values(self, env):
        _, eng = env
        for i, sev in enumerate(RiskSeverity):
            r = _register_risk(eng, risk_id=f"r-{i}", severity=sev)
            assert r.severity == sev


class TestUpdateRiskSeverity:
    def test_basic_update(self, env):
        _, eng = env
        _register_risk(eng)
        updated = eng.update_risk_severity("r1", RiskSeverity.CRITICAL)
        assert updated.severity == RiskSeverity.CRITICAL
        assert updated.risk_id == "r1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown risk_id"):
            eng.update_risk_severity("nope", RiskSeverity.LOW)

    def test_emits_event(self, env):
        es, eng = env
        _register_risk(eng)
        before = len(es.list_events())
        eng.update_risk_severity("r1", RiskSeverity.HIGH)
        assert len(es.list_events()) > before

    def test_preserves_other_fields(self, env):
        _, eng = env
        _register_risk(eng, owner="alice")
        updated = eng.update_risk_severity("r1", RiskSeverity.LOW)
        assert updated.owner == "alice"
        assert updated.title == "Risk One"


class TestRiskQueries:
    def test_risks_by_severity(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", severity=RiskSeverity.HIGH)
        _register_risk(eng, risk_id="r2", severity=RiskSeverity.LOW)
        _register_risk(eng, risk_id="r3", severity=RiskSeverity.HIGH)
        result = eng.risks_by_severity(RiskSeverity.HIGH)
        assert len(result) == 2
        assert all(r.severity == RiskSeverity.HIGH for r in result)

    def test_risks_by_severity_empty(self, env):
        _, eng = env
        assert eng.risks_by_severity(RiskSeverity.CRITICAL) == ()

    def test_risks_for_scope(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1")
        _register_risk(eng, risk_id="r2", scope_ref_id="s2")
        _register_risk(eng, risk_id="r3", scope_ref_id="s1")
        result = eng.risks_for_scope("s1")
        assert len(result) == 2

    def test_risks_for_scope_empty(self, env):
        _, eng = env
        assert eng.risks_for_scope("nonexistent") == ()


# ======================================================================
# 2  Requirement management
# ======================================================================


class TestRegisterRequirement:
    def test_basic_registration(self, env):
        _, eng = env
        req = _register_requirement(eng)
        assert isinstance(req, ComplianceRequirement)
        assert req.requirement_id == "req-1"
        assert req.title == "Req One"
        assert req.mandatory is True
        assert req.control_ids == ("c1",)

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_requirement(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate requirement_id"):
            _register_requirement(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        _register_requirement(eng)
        assert len(es.list_events()) > before

    def test_requirement_count(self, env):
        _, eng = env
        assert eng.requirement_count == 0
        _register_requirement(eng, requirement_id="req-1")
        _register_requirement(eng, requirement_id="req-2")
        assert eng.requirement_count == 2


# ======================================================================
# 3  Control management
# ======================================================================


class TestRegisterControl:
    def test_basic_registration(self, env):
        _, eng = env
        ctrl = _register_control(eng)
        assert isinstance(ctrl, ControlRecord)
        assert ctrl.control_id == "c1"
        assert ctrl.status == ControlStatus.ACTIVE
        assert ctrl.requirement_id == "req-1"

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_control(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate control_id"):
            _register_control(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        _register_control(eng)
        assert len(es.list_events()) > before

    def test_control_count(self, env):
        _, eng = env
        assert eng.control_count == 0
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        assert eng.control_count == 2


class TestSetControlStatus:
    def test_basic_update(self, env):
        _, eng = env
        _register_control(eng)
        updated = eng.set_control_status("c1", ControlStatus.TESTING)
        assert updated.status == ControlStatus.TESTING

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown control_id"):
            eng.set_control_status("nope", ControlStatus.ACTIVE)

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        before = len(es.list_events())
        eng.set_control_status("c1", ControlStatus.INACTIVE)
        assert len(es.list_events()) > before

    def test_all_statuses(self, env):
        _, eng = env
        _register_control(eng)
        for st in ControlStatus:
            updated = eng.set_control_status("c1", st)
            assert updated.status == st


class TestControlQueries:
    def test_failed_controls(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        eng.set_control_status("c1", ControlStatus.FAILED)
        result = eng.failed_controls()
        assert len(result) == 1
        assert result[0].control_id == "c1"

    def test_failed_controls_empty(self, env):
        _, eng = env
        _register_control(eng)
        assert eng.failed_controls() == ()

    def test_controls_for_requirement(self, env):
        _, eng = env
        _register_control(eng, control_id="c1", requirement_id="req-1")
        _register_control(eng, control_id="c2", requirement_id="req-2")
        _register_control(eng, control_id="c3", requirement_id="req-1")
        result = eng.controls_for_requirement("req-1")
        assert len(result) == 2

    def test_controls_for_requirement_empty(self, env):
        _, eng = env
        assert eng.controls_for_requirement("nope") == ()


# ======================================================================
# 4  Control binding
# ======================================================================


class TestBindControl:
    def test_basic_binding(self, env):
        _, eng = env
        _register_control(eng)
        b = _bind_control(eng)
        assert isinstance(b, ControlBinding)
        assert b.binding_id == "b1"
        assert b.control_id == "c1"
        assert b.scope_ref_id == "scope-1"
        assert b.enforced is True

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_control(eng)
        _bind_control(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate binding_id"):
            _bind_control(eng)

    def test_unknown_control_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown control_id"):
            eng.bind_control("b1", "nonexistent", "scope-1")

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        before = len(es.list_events())
        _bind_control(eng)
        assert len(es.list_events()) > before

    def test_binding_count(self, env):
        _, eng = env
        _register_control(eng)
        assert eng.binding_count == 0
        _bind_control(eng, binding_id="b1")
        _bind_control(eng, binding_id="b2", scope_ref_id="scope-2")
        assert eng.binding_count == 2

    def test_non_enforced_binding(self, env):
        _, eng = env
        _register_control(eng)
        b = _bind_control(eng, enforced=False)
        assert b.enforced is False


class TestBindingQueries:
    def test_bindings_for_scope(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c2", "s1")
        eng.bind_control("b3", "c1", "s2")
        assert len(eng.bindings_for_scope("s1")) == 2
        assert len(eng.bindings_for_scope("s2")) == 1

    def test_bindings_for_control(self, env):
        _, eng = env
        _register_control(eng)
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c1", "s2")
        assert len(eng.bindings_for_control("c1")) == 2

    def test_bindings_for_scope_empty(self, env):
        _, eng = env
        assert eng.bindings_for_scope("none") == ()

    def test_bindings_for_control_empty(self, env):
        _, eng = env
        assert eng.bindings_for_control("none") == ()


# ======================================================================
# 5  Control testing
# ======================================================================


class TestRecordControlTest:
    def test_basic_test(self, env):
        _, eng = env
        _register_control(eng)
        t = eng.record_control_test(
            "t1", "c1", ControlTestStatus.PASSED,
            evidence_refs=["ev1"], tester="alice", notes="ok",
        )
        assert isinstance(t, ControlTestRecord)
        assert t.test_id == "t1"
        assert t.status == ControlTestStatus.PASSED

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate test_id"):
            eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)

    def test_unknown_control_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown control_id"):
            eng.record_control_test("t1", "nope", ControlTestStatus.PASSED)

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        before = len(es.list_events())
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        assert len(es.list_events()) > before

    def test_test_count(self, env):
        _, eng = env
        _register_control(eng)
        assert eng.test_count == 0
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        eng.record_control_test("t2", "c1", ControlTestStatus.FAILED)
        assert eng.test_count == 2

    def test_failed_test_sets_control_failed(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)
        ctrl = eng.failed_controls()
        assert len(ctrl) == 1
        assert ctrl[0].control_id == "c1"

    def test_passed_test_on_failed_control_sets_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)
        assert eng.failed_controls()[0].control_id == "c1"
        eng.record_control_test("t2", "c1", ControlTestStatus.PASSED)
        assert eng.failed_controls() == ()

    def test_passed_test_on_testing_control_sets_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.TESTING)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE

    def test_passed_test_on_remediation_control_sets_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.REMEDIATION)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE

    def test_passed_test_on_active_control_stays_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE

    def test_partial_test_does_not_change_status(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PARTIAL)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE

    def test_skipped_test_does_not_change_status(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.SKIPPED)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE

    def test_error_test_does_not_change_active_status(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.ERROR)
        ctrl = eng.controls_for_requirement("req-1")
        assert ctrl[0].status == ControlStatus.ACTIVE


class TestControlTestQueries:
    def test_tests_for_control(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        eng.record_control_test("t2", "c1", ControlTestStatus.FAILED)
        assert len(eng.tests_for_control("c1")) == 2

    def test_tests_for_control_empty(self, env):
        _, eng = env
        assert eng.tests_for_control("c1") == ()

    def test_latest_test_for_control(self, env):
        _, eng = env
        _register_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        eng.record_control_test("t2", "c1", ControlTestStatus.FAILED)
        latest = eng.latest_test_for_control("c1")
        assert latest is not None
        assert latest.test_id == "t2"

    def test_latest_test_for_control_none(self, env):
        _, eng = env
        assert eng.latest_test_for_control("c1") is None


# ======================================================================
# 6  Exception management
# ======================================================================


class TestRequestException:
    def test_basic_request(self, env):
        _, eng = env
        _register_control(eng)
        exc = eng.request_exception(
            "ex1", "c1", scope_ref_id="scope-1",
            reason="testing", requested_by="alice", expires_at="2099-01-01T00:00:00+00:00",
        )
        assert isinstance(exc, ExceptionRequest)
        assert exc.exception_id == "ex1"
        assert exc.status == ExceptionStatus.REQUESTED

    def test_duplicate_raises(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate exception_id"):
            eng.request_exception("ex1", "c1")

    def test_unknown_control_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown control_id"):
            eng.request_exception("ex1", "nope")

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        before = len(es.list_events())
        eng.request_exception("ex1", "c1")
        assert len(es.list_events()) > before

    def test_exception_count(self, env):
        _, eng = env
        _register_control(eng)
        assert eng.exception_count == 0
        eng.request_exception("ex1", "c1")
        assert eng.exception_count == 1


class TestApproveException:
    def test_basic_approve(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        approved = eng.approve_exception("ex1", approved_by="bob")
        assert approved.status == ExceptionStatus.APPROVED
        assert approved.approved_by == "bob"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown exception_id"):
            eng.approve_exception("nope")

    def test_not_requested_raises(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.approve_exception("ex1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot approve"):
            eng.approve_exception("ex1")

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        before = len(es.list_events())
        eng.approve_exception("ex1")
        assert len(es.list_events()) > before


class TestDenyException:
    def test_basic_deny(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        denied = eng.deny_exception("ex1")
        assert denied.status == ExceptionStatus.DENIED

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown exception_id"):
            eng.deny_exception("nope")

    def test_not_requested_raises(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.deny_exception("ex1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            eng.deny_exception("ex1")

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        before = len(es.list_events())
        eng.deny_exception("ex1")
        assert len(es.list_events()) > before


class TestRevokeException:
    def test_basic_revoke(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.approve_exception("ex1")
        revoked = eng.revoke_exception("ex1")
        assert revoked.status == ExceptionStatus.REVOKED

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown exception_id"):
            eng.revoke_exception("nope")

    def test_not_approved_raises(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            eng.revoke_exception("ex1")

    def test_denied_cannot_revoke(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.deny_exception("ex1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            eng.revoke_exception("ex1")

    def test_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.approve_exception("ex1")
        before = len(es.list_events())
        eng.revoke_exception("ex1")
        assert len(es.list_events()) > before


class TestExceptionQueries:
    def test_active_exceptions_for_control(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        eng.approve_exception("ex1")
        eng.request_exception("ex2", "c1")
        # ex2 still REQUESTED, not active
        result = eng.active_exceptions_for_control("c1")
        assert len(result) == 1
        assert result[0].exception_id == "ex1"

    def test_active_exceptions_for_control_empty(self, env):
        _, eng = env
        assert eng.active_exceptions_for_control("c1") == ()

    def test_active_exceptions_for_scope(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1", scope_ref_id="s1")
        eng.approve_exception("ex1")
        eng.request_exception("ex2", "c1", scope_ref_id="s2")
        eng.approve_exception("ex2")
        assert len(eng.active_exceptions_for_scope("s1")) == 1
        assert len(eng.active_exceptions_for_scope("s2")) == 1

    def test_revoked_not_in_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1", scope_ref_id="s1")
        eng.approve_exception("ex1")
        eng.revoke_exception("ex1")
        assert eng.active_exceptions_for_control("c1") == ()
        assert eng.active_exceptions_for_scope("s1") == ()


# ======================================================================
# 7  Control failure recording
# ======================================================================


class TestRecordControlFailure:
    def test_basic_failure(self, env):
        _, eng = env
        f = eng.record_control_failure(
            "f1", "c1", test_id="t1", scope_ref_id="s1",
            severity=RiskSeverity.HIGH, action_taken="escalated",
            escalated=True, blocked=False,
        )
        assert isinstance(f, ControlFailure)
        assert f.failure_id == "f1"
        assert f.severity == RiskSeverity.HIGH
        assert f.escalated is True
        assert f.blocked is False

    def test_duplicate_raises(self, env):
        _, eng = env
        eng.record_control_failure("f1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate failure_id"):
            eng.record_control_failure("f1", "c1")

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        eng.record_control_failure("f1", "c1")
        assert len(es.list_events()) > before

    def test_failure_count(self, env):
        _, eng = env
        assert eng.failure_count == 0
        eng.record_control_failure("f1", "c1")
        eng.record_control_failure("f2", "c2")
        assert eng.failure_count == 2


class TestFailureQueries:
    def test_failures_for_control(self, env):
        _, eng = env
        eng.record_control_failure("f1", "c1")
        eng.record_control_failure("f2", "c1")
        eng.record_control_failure("f3", "c2")
        assert len(eng.failures_for_control("c1")) == 2

    def test_failures_for_control_empty(self, env):
        _, eng = env
        assert eng.failures_for_control("c1") == ()

    def test_failures_for_scope(self, env):
        _, eng = env
        eng.record_control_failure("f1", "c1", scope_ref_id="s1")
        eng.record_control_failure("f2", "c2", scope_ref_id="s1")
        eng.record_control_failure("f3", "c1", scope_ref_id="s2")
        assert len(eng.failures_for_scope("s1")) == 2

    def test_failures_for_scope_empty(self, env):
        _, eng = env
        assert eng.failures_for_scope("none") == ()


# ======================================================================
# 8  Risk assessment
# ======================================================================


class TestAssessScope:
    def test_basic_assessment(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", severity=RiskSeverity.MEDIUM,
                        likelihood=0.5, impact=0.6, mitigations=["m1"])
        a = eng.assess_scope("a1", "s1")
        assert isinstance(a, RiskAssessment)
        assert a.assessment_id == "a1"
        assert a.risk_count == 1
        assert a.overall_severity == RiskSeverity.MEDIUM

    def test_duplicate_raises(self, env):
        _, eng = env
        eng.assess_scope("a1", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assessment_id"):
            eng.assess_scope("a1", "s1")

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        eng.assess_scope("a1", "s1")
        assert len(es.list_events()) > before

    def test_assessment_count(self, env):
        _, eng = env
        assert eng.assessment_count == 0
        eng.assess_scope("a1", "s1")
        assert eng.assessment_count == 1

    def test_no_risks_yields_low(self, env):
        _, eng = env
        a = eng.assess_scope("a1", "empty-scope")
        assert a.overall_severity == RiskSeverity.LOW
        assert a.risk_count == 0
        assert a.risk_score == 0.0

    def test_critical_risk_yields_critical(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", severity=RiskSeverity.CRITICAL,
                        likelihood=0.9, impact=0.9)
        a = eng.assess_scope("a1", "s1")
        assert a.overall_severity == RiskSeverity.CRITICAL
        assert a.critical_risks == 1

    def test_high_risk_yields_high(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", severity=RiskSeverity.HIGH,
                        likelihood=0.7, impact=0.8)
        a = eng.assess_scope("a1", "s1")
        assert a.overall_severity == RiskSeverity.HIGH
        assert a.high_risks == 1

    def test_unmitigated_count(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", mitigations=[])
        _register_risk(eng, risk_id="r2", scope_ref_id="s1", mitigations=["m1"])
        a = eng.assess_scope("a1", "s1")
        assert a.unmitigated_risks == 1

    def test_risk_score_computation(self, env):
        _, eng = env
        # r1: 0.5*0.5 = 0.25, r2: 0.8*1.0 = 0.8 => avg = 0.525
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", likelihood=0.5, impact=0.5)
        _register_risk(eng, risk_id="r2", scope_ref_id="s1", likelihood=0.8, impact=1.0)
        a = eng.assess_scope("a1", "s1")
        assert abs(a.risk_score - 0.525) < 1e-9

    def test_risk_score_capped_at_one(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", likelihood=1.0, impact=1.0)
        a = eng.assess_scope("a1", "s1")
        assert a.risk_score <= 1.0


# ======================================================================
# 9  Compliance snapshot
# ======================================================================


class TestCaptureComplianceSnapshot:
    def test_basic_snapshot_compliant(self, env):
        _, eng = env
        _register_control(eng)
        _bind_control(eng, scope_ref_id="s1")
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert isinstance(snap, ComplianceSnapshot)
        assert snap.disposition == ComplianceDisposition.COMPLIANT
        assert snap.total_controls == 1
        assert snap.passing_controls == 1
        assert snap.failing_controls == 0
        assert snap.compliance_pct == 100.0

    def test_duplicate_raises(self, env):
        _, eng = env
        eng.capture_compliance_snapshot("snap1", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            eng.capture_compliance_snapshot("snap1", "s1")

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        eng.capture_compliance_snapshot("snap1", "s1")
        assert len(es.list_events()) > before

    def test_snapshot_count(self, env):
        _, eng = env
        assert eng.snapshot_count == 0
        eng.capture_compliance_snapshot("snap1", "s1")
        assert eng.snapshot_count == 1

    def test_no_controls_not_assessed(self, env):
        _, eng = env
        snap = eng.capture_compliance_snapshot("snap1", "empty-scope")
        assert snap.disposition == ComplianceDisposition.NOT_ASSESSED
        assert snap.total_controls == 0

    def test_partially_compliant(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c2", "s1")
        eng.set_control_status("c2", ControlStatus.FAILED)
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.disposition == ComplianceDisposition.PARTIALLY_COMPLIANT
        assert snap.passing_controls == 1
        assert snap.failing_controls == 1
        assert snap.compliance_pct == 50.0

    def test_non_compliant_all_failed(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        eng.bind_control("b1", "c1", "s1")
        eng.set_control_status("c1", ControlStatus.FAILED)
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.disposition == ComplianceDisposition.NON_COMPLIANT

    def test_exception_granted(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        eng.bind_control("b1", "c1", "s1")
        # Set control to TESTING (not ACTIVE, not FAILED)
        eng.set_control_status("c1", ControlStatus.TESTING)
        # Approve an exception for the scope
        eng.request_exception("ex1", "c1", scope_ref_id="s1")
        eng.approve_exception("ex1")
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.disposition == ComplianceDisposition.EXCEPTION_GRANTED
        assert snap.exceptions_active == 1

    def test_non_enforced_bindings_excluded(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        eng.bind_control("b1", "c1", "s1", enforced=True)
        eng.bind_control("b2", "c2", "s1", enforced=False)
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.total_controls == 1  # only enforced


# ======================================================================
# 10  Assurance report
# ======================================================================


class TestAssuranceReport:
    def test_basic_report(self, env):
        _, eng = env
        _register_requirement(eng, requirement_id="req-1", control_ids=["c1"])
        _register_control(eng, control_id="c1", requirement_id="req-1")
        eng.bind_control("b1", "c1", "s1")
        rpt = eng.assurance_report("rpt1", "s1")
        assert isinstance(rpt, AssuranceReport)
        assert rpt.report_id == "rpt1"
        assert rpt.total_requirements == 1
        assert rpt.met_requirements == 1
        assert rpt.total_controls == 1
        assert rpt.passing_controls == 1
        assert rpt.overall_disposition == ComplianceDisposition.COMPLIANT

    def test_duplicate_raises(self, env):
        _, eng = env
        eng.assurance_report("rpt1", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate report_id"):
            eng.assurance_report("rpt1", "s1")

    def test_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        eng.assurance_report("rpt1", "s1")
        assert len(es.list_events()) > before

    def test_report_count(self, env):
        _, eng = env
        assert eng.report_count == 0
        eng.assurance_report("rpt1", "s1")
        assert eng.report_count == 1

    def test_unmet_requirement(self, env):
        _, eng = env
        _register_requirement(eng, requirement_id="req-1", control_ids=["c1"])
        _register_control(eng, control_id="c1", requirement_id="req-1")
        eng.set_control_status("c1", ControlStatus.FAILED)
        eng.bind_control("b1", "c1", "s1")
        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.met_requirements == 0
        assert rpt.failing_controls == 1

    def test_requirement_no_controls_is_met(self, env):
        _, eng = env
        _register_requirement(eng, requirement_id="req-1", control_ids=[])
        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.met_requirements == 1

    def test_risk_severity_in_report(self, env):
        _, eng = env
        _register_risk(eng, risk_id="r1", scope_ref_id="s1", severity=RiskSeverity.CRITICAL,
                        likelihood=1.0, impact=1.0)
        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.overall_risk_severity == RiskSeverity.CRITICAL
        assert rpt.risk_score == 1.0

    def test_no_risks_low_severity(self, env):
        _, eng = env
        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.overall_risk_severity == RiskSeverity.LOW
        assert rpt.risk_score == 0.0

    def test_failures_in_report(self, env):
        _, eng = env
        eng.record_control_failure("f1", "c1", scope_ref_id="s1")
        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.total_failures == 1


# ======================================================================
# 11  State hash
# ======================================================================


class TestStateHash:
    def test_returns_16_chars(self, env):
        _, eng = env
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_changes_on_mutation(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _register_risk(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_deterministic_for_same_state(self, env):
        _, eng = env
        _register_risk(eng)
        assert eng.state_hash() == eng.state_hash()


# ======================================================================
# 12  Properties (comprehensive)
# ======================================================================


class TestProperties:
    def test_all_counts_start_at_zero(self, env):
        _, eng = env
        assert eng.risk_count == 0
        assert eng.requirement_count == 0
        assert eng.control_count == 0
        assert eng.binding_count == 0
        assert eng.test_count == 0
        assert eng.exception_count == 0
        assert eng.assessment_count == 0
        assert eng.snapshot_count == 0
        assert eng.failure_count == 0
        assert eng.report_count == 0

    def test_counts_after_full_setup(self, env):
        _, eng = env
        _register_risk(eng)
        _register_requirement(eng)
        _register_control(eng)
        _bind_control(eng)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        eng.request_exception("ex1", "c1")
        eng.assess_scope("a1", "scope-1")
        eng.capture_compliance_snapshot("snap1", "scope-1")
        eng.record_control_failure("f1", "c1")
        eng.assurance_report("rpt1", "scope-1")
        assert eng.risk_count == 1
        assert eng.requirement_count == 1
        assert eng.control_count == 1
        assert eng.binding_count == 1
        assert eng.test_count == 1
        assert eng.exception_count == 1
        assert eng.assessment_count == 1
        assert eng.snapshot_count == 1
        assert eng.failure_count == 1
        assert eng.report_count == 1


# ======================================================================
# 13  Constructor invariant
# ======================================================================


class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            RiskComplianceEngine("not-an-event-spine")

    def test_requires_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            RiskComplianceEngine(None)


# ======================================================================
# 14  Event emission (cumulative)
# ======================================================================


class TestEventEmission:
    def test_every_mutation_emits(self, env):
        es, eng = env
        counts = []
        counts.append(len(es.list_events()))

        _register_risk(eng)
        counts.append(len(es.list_events()))

        eng.update_risk_severity("r1", RiskSeverity.HIGH)
        counts.append(len(es.list_events()))

        _register_requirement(eng)
        counts.append(len(es.list_events()))

        _register_control(eng)
        counts.append(len(es.list_events()))

        eng.set_control_status("c1", ControlStatus.TESTING)
        counts.append(len(es.list_events()))

        _bind_control(eng)
        counts.append(len(es.list_events()))

        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        counts.append(len(es.list_events()))

        eng.request_exception("ex1", "c1")
        counts.append(len(es.list_events()))

        eng.approve_exception("ex1")
        counts.append(len(es.list_events()))

        eng.revoke_exception("ex1")
        counts.append(len(es.list_events()))

        eng.record_control_failure("f1", "c1")
        counts.append(len(es.list_events()))

        eng.assess_scope("a1", "scope-1")
        counts.append(len(es.list_events()))

        eng.capture_compliance_snapshot("snap1", "scope-1")
        counts.append(len(es.list_events()))

        eng.assurance_report("rpt1", "scope-1")
        counts.append(len(es.list_events()))

        # Each step must have strictly more events than the previous
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1], f"Step {i} did not emit an event"

    def test_deny_emits_event(self, env):
        es, eng = env
        _register_control(eng)
        eng.request_exception("ex1", "c1")
        before = len(es.list_events())
        eng.deny_exception("ex1")
        assert len(es.list_events()) > before


# ======================================================================
# Golden Scenario 1: Full lifecycle
#   register risk -> register control -> bind -> test pass -> snapshot COMPLIANT
# ======================================================================


class TestGoldenScenario1FullLifecycle:
    def test_full_lifecycle_compliant(self, env):
        es, eng = env
        # Register risk
        risk = _register_risk(eng, scope_ref_id="proj-1")
        assert risk.severity == RiskSeverity.MEDIUM

        # Register requirement and control
        _register_requirement(eng, control_ids=["c1"])
        ctrl = _register_control(eng)
        assert ctrl.status == ControlStatus.ACTIVE

        # Bind control to scope
        binding = _bind_control(eng, scope_ref_id="proj-1")
        assert binding.enforced is True

        # Pass control test
        test = eng.record_control_test("t1", "c1", ControlTestStatus.PASSED,
                                        evidence_refs=["evidence-1"])
        assert test.status == ControlTestStatus.PASSED

        # Capture compliance snapshot
        snap = eng.capture_compliance_snapshot("snap1", "proj-1")
        assert snap.disposition == ComplianceDisposition.COMPLIANT
        assert snap.compliance_pct == 100.0
        assert snap.total_controls == 1
        assert snap.passing_controls == 1
        assert snap.failing_controls == 0

        # Events were emitted
        assert len(es.list_events()) >= 5


# ======================================================================
# Golden Scenario 2: Failed test degrades control -> snapshot PARTIALLY_COMPLIANT
# ======================================================================


class TestGoldenScenario2FailedTest:
    def test_failed_test_partially_compliant(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        eng.bind_control("b1", "c1", "proj-1")
        eng.bind_control("b2", "c2", "proj-1")

        # c1 passes, c2 fails
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        eng.record_control_test("t2", "c2", ControlTestStatus.FAILED)

        snap = eng.capture_compliance_snapshot("snap1", "proj-1")
        assert snap.disposition == ComplianceDisposition.PARTIALLY_COMPLIANT
        assert snap.passing_controls == 1
        assert snap.failing_controls == 1
        assert snap.compliance_pct == 50.0


# ======================================================================
# Golden Scenario 3: Exception lifecycle: request -> approve -> active -> revoke
# ======================================================================


class TestGoldenScenario3ExceptionLifecycle:
    def test_exception_lifecycle(self, env):
        es, eng = env
        _register_control(eng)

        # Request
        exc = eng.request_exception("ex1", "c1", scope_ref_id="s1",
                                     reason="maintenance", requested_by="alice",
                                     expires_at="2099-12-31T00:00:00+00:00")
        assert exc.status == ExceptionStatus.REQUESTED
        assert eng.active_exceptions_for_control("c1") == ()

        # Approve
        exc = eng.approve_exception("ex1", approved_by="bob")
        assert exc.status == ExceptionStatus.APPROVED
        assert len(eng.active_exceptions_for_control("c1")) == 1
        assert len(eng.active_exceptions_for_scope("s1")) == 1

        # Revoke
        exc = eng.revoke_exception("ex1")
        assert exc.status == ExceptionStatus.REVOKED
        assert eng.active_exceptions_for_control("c1") == ()
        assert eng.active_exceptions_for_scope("s1") == ()

        assert len(es.list_events()) >= 4


# ======================================================================
# Golden Scenario 4: Exception deny: request -> deny (must be REQUESTED)
# ======================================================================


class TestGoldenScenario4ExceptionDeny:
    def test_exception_deny(self, env):
        _, eng = env
        _register_control(eng)

        exc = eng.request_exception("ex1", "c1")
        assert exc.status == ExceptionStatus.REQUESTED

        denied = eng.deny_exception("ex1")
        assert denied.status == ExceptionStatus.DENIED

        # Cannot approve after deny
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot approve"):
            eng.approve_exception("ex1")

        # Cannot revoke after deny
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            eng.revoke_exception("ex1")

        # Cannot deny again
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            eng.deny_exception("ex1")


# ======================================================================
# Golden Scenario 5: Control failure escalation
#   failed test -> record failure -> assess -> CRITICAL
# ======================================================================


class TestGoldenScenario5ControlFailureEscalation:
    def test_failure_escalation_critical(self, env):
        _, eng = env
        # Register a critical risk for the scope
        _register_risk(eng, risk_id="r1", scope_ref_id="s1",
                        severity=RiskSeverity.CRITICAL, likelihood=0.9, impact=1.0,
                        mitigations=[])

        # Register control, bind, and fail it
        _register_control(eng, control_id="c1")
        eng.bind_control("b1", "c1", "s1")
        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)

        # Record failure
        failure = eng.record_control_failure(
            "f1", "c1", test_id="t1", scope_ref_id="s1",
            severity=RiskSeverity.CRITICAL, action_taken="escalated to CISO",
            escalated=True, blocked=True,
        )
        assert failure.escalated is True
        assert failure.blocked is True

        # Assess
        assessment = eng.assess_scope("a1", "s1")
        assert assessment.overall_severity == RiskSeverity.CRITICAL
        assert assessment.critical_risks == 1
        assert assessment.unmitigated_risks == 1
        assert assessment.risk_score == pytest.approx(0.9)


# ======================================================================
# Golden Scenario 6: Assurance report with mixed passing/failing controls
# ======================================================================


class TestGoldenScenario6MixedAssuranceReport:
    def test_mixed_controls_report(self, env):
        _, eng = env
        # Two requirements
        _register_requirement(eng, requirement_id="req-1", control_ids=["c1", "c2"])
        _register_requirement(eng, requirement_id="req-2", control_ids=["c3"])

        # Three controls
        _register_control(eng, control_id="c1", requirement_id="req-1")
        _register_control(eng, control_id="c2", requirement_id="req-1")
        _register_control(eng, control_id="c3", requirement_id="req-2")

        # Bind all to scope
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c2", "s1")
        eng.bind_control("b3", "c3", "s1")

        # c1 ACTIVE, c2 FAILED, c3 ACTIVE
        eng.record_control_test("t2", "c2", ControlTestStatus.FAILED)

        # Record a failure for scope
        eng.record_control_failure("f1", "c2", scope_ref_id="s1")

        rpt = eng.assurance_report("rpt1", "s1")
        assert rpt.total_requirements == 2
        # req-1 not met (c2 is FAILED), req-2 met (c3 ACTIVE)
        assert rpt.met_requirements == 1
        assert rpt.total_controls == 3
        assert rpt.passing_controls == 2  # c1, c3
        assert rpt.failing_controls == 1  # c2
        assert rpt.total_failures == 1
        assert rpt.overall_disposition == ComplianceDisposition.PARTIALLY_COMPLIANT
        assert rpt.compliance_pct == pytest.approx(200.0 / 3.0)


# ======================================================================
# Golden Scenario 7: Risk assessment: scope with critical + low risks
# ======================================================================


class TestGoldenScenario7RiskAssessment:
    def test_critical_plus_low_risks(self, env):
        _, eng = env
        # Critical risk: likelihood=0.9, impact=1.0 => 0.9
        _register_risk(eng, risk_id="r1", scope_ref_id="s1",
                        severity=RiskSeverity.CRITICAL, likelihood=0.9, impact=1.0,
                        mitigations=["m1"])
        # Low risk: likelihood=0.1, impact=0.2 => 0.02
        _register_risk(eng, risk_id="r2", scope_ref_id="s1",
                        severity=RiskSeverity.LOW, likelihood=0.1, impact=0.2,
                        mitigations=[])

        a = eng.assess_scope("a1", "s1")
        assert a.overall_severity == RiskSeverity.CRITICAL
        assert a.risk_count == 2
        assert a.critical_risks == 1
        assert a.high_risks == 0
        assert a.unmitigated_risks == 1  # r2 has no mitigations
        # score = (0.9 + 0.02) / 2 = 0.46
        assert a.risk_score == pytest.approx(0.46)


# ======================================================================
# Golden Scenario 8: Control test auto-status transitions
# ======================================================================


class TestGoldenScenario8AutoStatusTransitions:
    def test_passed_on_failed_to_active(self, env):
        _, eng = env
        _register_control(eng)
        # Fail it
        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)
        ctrls = eng.failed_controls()
        assert len(ctrls) == 1

        # Pass it — should revert to ACTIVE
        eng.record_control_test("t2", "c1", ControlTestStatus.PASSED)
        assert eng.failed_controls() == ()
        ctrl = eng.controls_for_requirement("req-1")[0]
        assert ctrl.status == ControlStatus.ACTIVE

    def test_failed_on_active_to_failed(self, env):
        _, eng = env
        _register_control(eng)
        assert eng.failed_controls() == ()

        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)
        ctrls = eng.failed_controls()
        assert len(ctrls) == 1
        assert ctrls[0].status == ControlStatus.FAILED

    def test_passed_on_testing_to_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.TESTING)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")[0]
        assert ctrl.status == ControlStatus.ACTIVE

    def test_passed_on_remediation_to_active(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.REMEDIATION)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")[0]
        assert ctrl.status == ControlStatus.ACTIVE

    def test_passed_on_inactive_stays_inactive(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.INACTIVE)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")[0]
        # INACTIVE is not in (TESTING, FAILED, REMEDIATION) so stays INACTIVE
        assert ctrl.status == ControlStatus.INACTIVE

    def test_passed_on_retired_stays_retired(self, env):
        _, eng = env
        _register_control(eng)
        eng.set_control_status("c1", ControlStatus.RETIRED)
        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        ctrl = eng.controls_for_requirement("req-1")[0]
        assert ctrl.status == ControlStatus.RETIRED

    def test_multiple_transitions(self, env):
        _, eng = env
        _register_control(eng)
        # ACTIVE -> fail -> FAILED -> pass -> ACTIVE -> fail -> FAILED
        eng.record_control_test("t1", "c1", ControlTestStatus.FAILED)
        assert eng.controls_for_requirement("req-1")[0].status == ControlStatus.FAILED
        eng.record_control_test("t2", "c1", ControlTestStatus.PASSED)
        assert eng.controls_for_requirement("req-1")[0].status == ControlStatus.ACTIVE
        eng.record_control_test("t3", "c1", ControlTestStatus.FAILED)
        assert eng.controls_for_requirement("req-1")[0].status == ControlStatus.FAILED


# ======================================================================
# Additional edge cases
# ======================================================================


class TestEdgeCases:
    def test_multiple_bindings_same_control_same_scope(self, env):
        _, eng = env
        _register_control(eng)
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c1", "s1")
        # Two bindings but same control_id — snapshot should count unique controls
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.total_controls == 1

    def test_snapshot_compliance_pct_rounding(self, env):
        _, eng = env
        _register_control(eng, control_id="c1")
        _register_control(eng, control_id="c2")
        _register_control(eng, control_id="c3")
        eng.bind_control("b1", "c1", "s1")
        eng.bind_control("b2", "c2", "s1")
        eng.bind_control("b3", "c3", "s1")
        eng.set_control_status("c3", ControlStatus.FAILED)
        snap = eng.capture_compliance_snapshot("snap1", "s1")
        assert snap.compliance_pct == pytest.approx(200.0 / 3.0)

    def test_state_hash_changes_with_each_entity_type(self, env):
        _, eng = env
        hashes = [eng.state_hash()]

        _register_risk(eng)
        hashes.append(eng.state_hash())

        _register_requirement(eng)
        hashes.append(eng.state_hash())

        _register_control(eng)
        hashes.append(eng.state_hash())

        _bind_control(eng)
        hashes.append(eng.state_hash())

        eng.record_control_test("t1", "c1", ControlTestStatus.PASSED)
        hashes.append(eng.state_hash())

        eng.request_exception("ex1", "c1")
        hashes.append(eng.state_hash())

        eng.assess_scope("a1", "scope-1")
        hashes.append(eng.state_hash())

        eng.capture_compliance_snapshot("snap1", "scope-1")
        hashes.append(eng.state_hash())

        eng.record_control_failure("f1", "c1")
        hashes.append(eng.state_hash())

        eng.assurance_report("rpt1", "scope-1")
        hashes.append(eng.state_hash())

        # All hashes should be unique
        assert len(set(hashes)) == len(hashes)

    def test_return_types_are_tuples(self, env):
        _, eng = env
        assert isinstance(eng.risks_by_severity(RiskSeverity.LOW), tuple)
        assert isinstance(eng.risks_for_scope("x"), tuple)
        assert isinstance(eng.bindings_for_scope("x"), tuple)
        assert isinstance(eng.bindings_for_control("x"), tuple)
        assert isinstance(eng.tests_for_control("x"), tuple)
        assert isinstance(eng.active_exceptions_for_control("x"), tuple)
        assert isinstance(eng.active_exceptions_for_scope("x"), tuple)
        assert isinstance(eng.failures_for_control("x"), tuple)
        assert isinstance(eng.failures_for_scope("x"), tuple)
        assert isinstance(eng.failed_controls(), tuple)
        assert isinstance(eng.controls_for_requirement("x"), tuple)

    def test_risk_record_is_frozen(self, env):
        _, eng = env
        r = _register_risk(eng)
        with pytest.raises(AttributeError):
            r.title = "changed"

    def test_control_record_is_frozen(self, env):
        _, eng = env
        c = _register_control(eng)
        with pytest.raises(AttributeError):
            c.title = "changed"

    def test_binding_is_frozen(self, env):
        _, eng = env
        _register_control(eng)
        b = _bind_control(eng)
        with pytest.raises(AttributeError):
            b.enforced = False

    def test_assess_empty_scope_then_add_risk_and_reassess(self, env):
        _, eng = env
        a1 = eng.assess_scope("a1", "s1")
        assert a1.risk_count == 0
        assert a1.overall_severity == RiskSeverity.LOW

        _register_risk(eng, risk_id="r1", scope_ref_id="s1",
                        severity=RiskSeverity.HIGH, likelihood=0.7, impact=0.8)
        a2 = eng.assess_scope("a2", "s1")
        assert a2.risk_count == 1
        assert a2.overall_severity == RiskSeverity.HIGH

    def test_assurance_report_no_controls_not_assessed(self, env):
        _, eng = env
        rpt = eng.assurance_report("rpt1", "empty-scope")
        assert rpt.overall_disposition == ComplianceDisposition.NOT_ASSESSED
        assert rpt.total_controls == 0
        assert rpt.compliance_pct == 0.0
