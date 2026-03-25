"""Comprehensive tests for ContractRuntimeEngine.

Covers: contract CRUD and lifecycle, clause registration, commitment management,
SLA evaluation (HEALTHY/AT_RISK/BREACHED with auto-breach), breach recording,
remedy recording, renewal scheduling/completion/decline, assessment, violation
detection, snapshots, state hashing, and six golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.contract_runtime import (
    BreachRecord,
    BreachSeverity,
    CommitmentKind,
    CommitmentRecord,
    ContractAssessment,
    ContractClause,
    ContractSnapshot,
    ContractStatus,
    GovernanceContractRecord,
    RemedyDisposition,
    RemedyRecord,
    RenewalStatus,
    RenewalWindow,
    SLAStatus,
    SLAWindow,
)
from mcoi_runtime.core.contract_runtime import ContractRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_T0 = "2025-06-01T00:00:00+00:00"
_T1 = "2025-06-01T01:00:00+00:00"
_T2 = "2025-06-01T02:00:00+00:00"
_T3 = "2025-06-01T03:00:00+00:00"
_T4 = "2025-06-01T04:00:00+00:00"
_FUTURE = "2099-01-01T00:00:00+00:00"
_PAST = "2020-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es):
    return ContractRuntimeEngine(es)


@pytest.fixture()
def active_contract(engine):
    """Register and activate a contract, returning the engine."""
    engine.register_contract("c1", "t1", "vendor-a", "Contract One", expires_at=_FUTURE)
    engine.activate_contract("c1")
    return engine


@pytest.fixture()
def full_stack(engine):
    """Engine with contract, clause, commitment ready for SLA evaluation."""
    engine.register_contract("c1", "t1", "vendor-a", "Contract One", expires_at=_FUTURE)
    engine.activate_contract("c1")
    engine.register_clause("cl1", "c1", "SLA Clause")
    engine.register_commitment("cm1", "c1", "cl1", "t1", "99.9%")
    return engine


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_valid_construction(self, es):
        eng = ContractRuntimeEngine(es)
        assert eng.contract_count == 0

    def test_invalid_event_spine_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ContractRuntimeEngine("not-an-engine")

    def test_initial_properties_zero(self, engine):
        assert engine.contract_count == 0
        assert engine.active_contract_count == 0
        assert engine.clause_count == 0
        assert engine.commitment_count == 0
        assert engine.sla_window_count == 0
        assert engine.breach_count == 0
        assert engine.remedy_count == 0
        assert engine.renewal_count == 0
        assert engine.assessment_count == 0
        assert engine.violation_count == 0


# ===================================================================
# 2. Contract registration
# ===================================================================


class TestRegisterContract:
    def test_register_returns_record(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert isinstance(rec, GovernanceContractRecord)
        assert rec.contract_id == "c1"
        assert rec.tenant_id == "t1"
        assert rec.counterparty == "vendor-a"
        assert rec.title == "Title"

    def test_default_status_is_draft(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert rec.status == ContractStatus.DRAFT

    def test_effective_at_defaults_to_now(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert rec.effective_at != ""

    def test_explicit_effective_at(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title", effective_at=_T0)
        assert rec.effective_at == _T0

    def test_explicit_expires_at(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title", expires_at=_FUTURE)
        assert rec.expires_at == _FUTURE

    def test_description_kwarg(self, engine):
        rec = engine.register_contract("c1", "t1", "vendor-a", "Title", description="desc")
        assert rec.description == "desc"

    def test_duplicate_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_contract("c1", "t1", "vendor-a", "Title")

    def test_contract_count_increments(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.contract_count == 1
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        assert engine.contract_count == 2

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert es.event_count > before


# ===================================================================
# 3. Get contract
# ===================================================================


class TestGetContract:
    def test_get_existing(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        rec = engine.get_contract("c1")
        assert rec.contract_id == "c1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_contract("nope")


# ===================================================================
# 4. Activate contract
# ===================================================================


class TestActivateContract:
    def test_draft_to_active(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        rec = engine.activate_contract("c1")
        assert rec.status == ContractStatus.ACTIVE

    def test_active_contract_count_updates(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.active_contract_count == 0
        engine.activate_contract("c1")
        assert engine.active_contract_count == 1

    def test_activate_expired_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        engine.expire_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.activate_contract("c1")

    def test_activate_terminated_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        engine.terminate_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.activate_contract("c1")

    def test_activate_suspended_ok(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        engine.suspend_contract("c1")
        rec = engine.activate_contract("c1")
        assert rec.status == ContractStatus.ACTIVE

    def test_activate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.activate_contract("nope")


# ===================================================================
# 5. Suspend contract
# ===================================================================


class TestSuspendContract:
    def test_suspend_active(self, active_contract):
        rec = active_contract.suspend_contract("c1")
        assert rec.status == ContractStatus.SUSPENDED

    def test_suspend_draft_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        with pytest.raises(RuntimeCoreInvariantError, match="ACTIVE"):
            engine.suspend_contract("c1")

    def test_suspend_with_reason(self, active_contract):
        rec = active_contract.suspend_contract("c1", reason="maintenance")
        assert rec.status == ContractStatus.SUSPENDED

    def test_suspend_suspended_raises(self, active_contract):
        active_contract.suspend_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            active_contract.suspend_contract("c1")

    def test_suspend_terminated_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        engine.terminate_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.suspend_contract("c1")


# ===================================================================
# 6. Terminate contract
# ===================================================================


class TestTerminateContract:
    def test_terminate_active(self, active_contract):
        rec = active_contract.terminate_contract("c1")
        assert rec.status == ContractStatus.TERMINATED

    def test_terminate_draft(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        rec = engine.terminate_contract("c1")
        assert rec.status == ContractStatus.TERMINATED

    def test_terminate_already_terminated_raises(self, active_contract):
        active_contract.terminate_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            active_contract.terminate_contract("c1")

    def test_terminate_expired_raises(self, active_contract):
        active_contract.expire_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            active_contract.terminate_contract("c1")

    def test_terminate_with_reason(self, active_contract):
        rec = active_contract.terminate_contract("c1", reason="breach")
        assert rec.status == ContractStatus.TERMINATED


# ===================================================================
# 7. Expire contract
# ===================================================================


class TestExpireContract:
    def test_expire_active(self, active_contract):
        rec = active_contract.expire_contract("c1")
        assert rec.status == ContractStatus.EXPIRED

    def test_expire_draft(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        rec = engine.expire_contract("c1")
        assert rec.status == ContractStatus.EXPIRED

    def test_expire_already_expired_raises(self, active_contract):
        active_contract.expire_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            active_contract.expire_contract("c1")

    def test_expire_terminated_raises(self, active_contract):
        active_contract.terminate_contract("c1")
        with pytest.raises(RuntimeCoreInvariantError):
            active_contract.expire_contract("c1")


# ===================================================================
# 8. Contracts for tenant
# ===================================================================


class TestContractsForTenant:
    def test_empty(self, engine):
        assert engine.contracts_for_tenant("t1") == ()

    def test_returns_tuple(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        result = engine.contracts_for_tenant("t1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_tenant(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t2", "vendor-b", "Title2")
        engine.register_contract("c3", "t1", "vendor-c", "Title3")
        assert len(engine.contracts_for_tenant("t1")) == 2
        assert len(engine.contracts_for_tenant("t2")) == 1
        assert len(engine.contracts_for_tenant("t3")) == 0


# ===================================================================
# 9. Clause registration
# ===================================================================


class TestRegisterClause:
    def test_register_returns_clause(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        clause = engine.register_clause("cl1", "c1", "SLA Clause")
        assert isinstance(clause, ContractClause)
        assert clause.clause_id == "cl1"
        assert clause.contract_id == "c1"

    def test_default_commitment_kind(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        clause = engine.register_clause("cl1", "c1", "SLA Clause")
        assert clause.commitment_kind == CommitmentKind.SLA

    def test_custom_commitment_kind(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        clause = engine.register_clause("cl1", "c1", "Avail", commitment_kind=CommitmentKind.AVAILABILITY)
        assert clause.commitment_kind == CommitmentKind.AVAILABILITY

    def test_description_kwarg(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        clause = engine.register_clause("cl1", "c1", "Clause", description="desc")
        assert clause.description == "desc"

    def test_duplicate_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_clause("cl1", "c1", "Clause2")

    def test_unknown_contract_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.register_clause("cl1", "nope", "Clause")

    def test_clause_count(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.clause_count == 0
        engine.register_clause("cl1", "c1", "Clause")
        assert engine.clause_count == 1

    def test_emits_event(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.register_clause("cl1", "c1", "Clause")
        assert es.event_count > before


# ===================================================================
# 10. Clauses for contract
# ===================================================================


class TestClausesForContract:
    def test_empty(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.clauses_for_contract("c1") == ()

    def test_returns_tuple(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause1")
        result = engine.clauses_for_contract("c1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        engine.register_clause("cl1", "c1", "Clause1")
        engine.register_clause("cl2", "c2", "Clause2")
        assert len(engine.clauses_for_contract("c1")) == 1
        assert len(engine.clauses_for_contract("c2")) == 1


# ===================================================================
# 11. Commitment registration
# ===================================================================


class TestRegisterCommitment:
    def test_register_returns_record(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        rec = engine.register_commitment("cm1", "c1", "cl1", "t1", "99.9%")
        assert isinstance(rec, CommitmentRecord)
        assert rec.commitment_id == "cm1"
        assert rec.contract_id == "c1"
        assert rec.clause_id == "cl1"
        assert rec.tenant_id == "t1"
        assert rec.target_value == "99.9%"

    def test_default_kind(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        rec = engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        assert rec.kind == CommitmentKind.SLA

    def test_custom_kind(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        rec = engine.register_commitment("cm1", "c1", "cl1", "t1", "99%", kind=CommitmentKind.AVAILABILITY)
        assert rec.kind == CommitmentKind.AVAILABILITY

    def test_scope_ref_kwargs(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        rec = engine.register_commitment(
            "cm1", "c1", "cl1", "t1", "99%",
            scope_ref_id="svc-1", scope_ref_type="service",
        )
        assert rec.scope_ref_id == "svc-1"
        assert rec.scope_ref_type == "service"

    def test_created_at_populated(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        rec = engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        assert rec.created_at != ""

    def test_duplicate_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")

    def test_unknown_contract_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown contract"):
            engine.register_commitment("cm1", "nope", "cl1", "t1", "99%")

    def test_unknown_clause_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown clause"):
            engine.register_commitment("cm1", "c1", "nope", "t1", "99%")

    def test_commitment_count(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        assert engine.commitment_count == 0
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        assert engine.commitment_count == 1


# ===================================================================
# 12. Commitments for contract
# ===================================================================


class TestCommitmentsForContract:
    def test_empty(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.commitments_for_contract("c1") == ()

    def test_returns_correct_commitments(self, full_stack):
        result = full_stack.commitments_for_contract("c1")
        assert len(result) == 1
        assert result[0].commitment_id == "cm1"


# ===================================================================
# 13. SLA evaluation
# ===================================================================


class TestEvaluateSLA:
    def test_healthy_compliance(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.99)
        assert isinstance(w, SLAWindow)
        assert w.status == SLAStatus.HEALTHY
        assert w.compliance == 0.99

    def test_healthy_at_threshold(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.95)
        assert w.status == SLAStatus.HEALTHY

    def test_at_risk_below_95(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.94)
        assert w.status == SLAStatus.AT_RISK

    def test_at_risk_at_80(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.80)
        assert w.status == SLAStatus.AT_RISK

    def test_breached_below_80(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.79)
        assert w.status == SLAStatus.BREACHED

    def test_breached_at_zero(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.0)
        assert w.status == SLAStatus.BREACHED

    def test_breach_auto_creates_breach_record(self, full_stack):
        assert full_stack.breach_count == 0
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.5)
        assert full_stack.breach_count == 1

    def test_auto_breach_major_when_compliance_ge_05(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.5)
        breaches = full_stack.breaches_for_commitment("cm1")
        assert breaches[0].severity == BreachSeverity.MAJOR

    def test_auto_breach_critical_when_compliance_lt_05(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.49)
        breaches = full_stack.breaches_for_commitment("cm1")
        assert breaches[0].severity == BreachSeverity.CRITICAL

    def test_auto_breach_critical_at_zero(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.0)
        breaches = full_stack.breaches_for_commitment("cm1")
        assert breaches[0].severity == BreachSeverity.CRITICAL

    def test_auto_breach_major_at_079(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.79)
        breaches = full_stack.breaches_for_commitment("cm1")
        assert breaches[0].severity == BreachSeverity.MAJOR

    def test_auto_breach_fills_contract_and_tenant(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.3)
        breaches = full_stack.breaches_for_commitment("cm1")
        assert breaches[0].contract_id == "c1"
        assert breaches[0].tenant_id == "t1"

    def test_healthy_does_not_create_breach(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.95)
        assert full_stack.breach_count == 0

    def test_at_risk_does_not_create_breach(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.90)
        assert full_stack.breach_count == 0

    def test_actual_value_kwarg(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, actual_value="99.5%")
        assert w.actual_value == "99.5%"

    def test_duplicate_raises(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            full_stack.evaluate_sla("w1", "cm1", _T0, _T1)

    def test_unknown_commitment_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.evaluate_sla("w1", "nope", _T0, _T1)

    def test_sla_window_count(self, full_stack):
        assert full_stack.sla_window_count == 0
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        assert full_stack.sla_window_count == 1

    def test_default_compliance_is_healthy(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        assert w.compliance == 1.0
        assert w.status == SLAStatus.HEALTHY


# ===================================================================
# 14. Get SLA window
# ===================================================================


class TestGetSLAWindow:
    def test_get_existing(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        w = full_stack.get_sla_window("w1")
        assert w.window_id == "w1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_sla_window("nope")


# ===================================================================
# 15. SLA windows for commitment
# ===================================================================


class TestSLAWindowsForCommitment:
    def test_empty(self, full_stack):
        assert full_stack.sla_windows_for_commitment("cm1") == ()

    def test_returns_correct_windows(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        full_stack.evaluate_sla("w2", "cm1", _T1, _T2, compliance=0.90)
        result = full_stack.sla_windows_for_commitment("cm1")
        assert len(result) == 2

    def test_returns_tuple(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        assert isinstance(full_stack.sla_windows_for_commitment("cm1"), tuple)


# ===================================================================
# 16. Record breach
# ===================================================================


class TestRecordBreach:
    def test_record_returns_breach(self, full_stack):
        b = full_stack.record_breach("b1", "cm1")
        assert isinstance(b, BreachRecord)
        assert b.breach_id == "b1"
        assert b.commitment_id == "cm1"

    def test_default_severity_minor(self, full_stack):
        b = full_stack.record_breach("b1", "cm1")
        assert b.severity == BreachSeverity.MINOR

    def test_custom_severity(self, full_stack):
        b = full_stack.record_breach("b1", "cm1", severity=BreachSeverity.CRITICAL)
        assert b.severity == BreachSeverity.CRITICAL

    def test_description_kwarg(self, full_stack):
        b = full_stack.record_breach("b1", "cm1", description="SLA miss")
        assert b.description == "SLA miss"

    def test_auto_fills_contract_and_tenant(self, full_stack):
        b = full_stack.record_breach("b1", "cm1")
        assert b.contract_id == "c1"
        assert b.tenant_id == "t1"

    def test_detected_at_populated(self, full_stack):
        b = full_stack.record_breach("b1", "cm1")
        assert b.detected_at != ""

    def test_duplicate_raises(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            full_stack.record_breach("b1", "cm1")

    def test_unknown_commitment_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_breach("b1", "nope")

    def test_breach_count(self, full_stack):
        assert full_stack.breach_count == 0
        full_stack.record_breach("b1", "cm1")
        assert full_stack.breach_count == 1


# ===================================================================
# 17. Breaches for commitment / contract
# ===================================================================


class TestBreachesForCommitment:
    def test_empty(self, full_stack):
        assert full_stack.breaches_for_commitment("cm1") == ()

    def test_returns_correct(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        result = full_stack.breaches_for_commitment("cm1")
        assert len(result) == 1
        assert result[0].breach_id == "b1"


class TestBreachesForContract:
    def test_empty(self, full_stack):
        assert full_stack.breaches_for_contract("c1") == ()

    def test_returns_correct(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        result = full_stack.breaches_for_contract("c1")
        assert len(result) == 1

    def test_filters_by_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        engine.register_clause("cl1", "c1", "Clause1")
        engine.register_clause("cl2", "c2", "Clause2")
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        engine.register_commitment("cm2", "c2", "cl2", "t1", "99%")
        engine.record_breach("b1", "cm1")
        engine.record_breach("b2", "cm2")
        assert len(engine.breaches_for_contract("c1")) == 1
        assert len(engine.breaches_for_contract("c2")) == 1


# ===================================================================
# 18. Record remedy
# ===================================================================


class TestRecordRemedy:
    def test_record_returns_remedy(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1")
        assert isinstance(r, RemedyRecord)
        assert r.remedy_id == "r1"
        assert r.breach_id == "b1"

    def test_default_disposition_pending(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1")
        assert r.disposition == RemedyDisposition.PENDING

    def test_custom_disposition(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1", disposition=RemedyDisposition.CREDIT_ISSUED)
        assert r.disposition == RemedyDisposition.CREDIT_ISSUED

    def test_amount_and_description(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1", amount="500", description="credit")
        assert r.amount == "500"
        assert r.description == "credit"

    def test_auto_fills_tenant(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1")
        assert r.tenant_id == "t1"

    def test_applied_at_populated(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        r = full_stack.record_remedy("r1", "b1")
        assert r.applied_at != ""

    def test_duplicate_raises(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        full_stack.record_remedy("r1", "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            full_stack.record_remedy("r1", "b1")

    def test_unknown_breach_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_remedy("r1", "nope")

    def test_remedy_count(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        assert full_stack.remedy_count == 0
        full_stack.record_remedy("r1", "b1")
        assert full_stack.remedy_count == 1


# ===================================================================
# 19. Remedies for breach
# ===================================================================


class TestRemediesForBreach:
    def test_empty(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        assert full_stack.remedies_for_breach("b1") == ()

    def test_returns_correct(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        full_stack.record_remedy("r1", "b1")
        result = full_stack.remedies_for_breach("b1")
        assert len(result) == 1
        assert result[0].remedy_id == "r1"

    def test_multiple_remedies(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        full_stack.record_remedy("r1", "b1")
        full_stack.record_remedy("r2", "b1", disposition=RemedyDisposition.ESCALATED)
        assert len(full_stack.remedies_for_breach("b1")) == 2


# ===================================================================
# 20. Schedule renewal
# ===================================================================


class TestScheduleRenewal:
    def test_schedule_returns_window(self, active_contract):
        w = active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        assert isinstance(w, RenewalWindow)
        assert w.window_id == "rw1"
        assert w.contract_id == "c1"
        assert w.status == RenewalStatus.SCHEDULED

    def test_duplicate_raises(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)

    def test_unknown_contract_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.schedule_renewal("rw1", "nope", _T0, _FUTURE)

    def test_renewal_count(self, active_contract):
        assert active_contract.renewal_count == 0
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        assert active_contract.renewal_count == 1


# ===================================================================
# 21. Complete renewal
# ===================================================================


class TestCompleteRenewal:
    def test_complete_sets_completed(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        w = active_contract.complete_renewal("rw1")
        assert w.status == RenewalStatus.COMPLETED
        assert w.completed_at != ""

    def test_complete_updates_contract_to_renewed(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        active_contract.complete_renewal("rw1")
        c = active_contract.get_contract("c1")
        assert c.status == ContractStatus.RENEWED

    def test_complete_does_not_renew_terminal_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        engine.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        engine.terminate_contract("c1")
        engine.complete_renewal("rw1")
        c = engine.get_contract("c1")
        assert c.status == ContractStatus.TERMINATED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.complete_renewal("nope")


# ===================================================================
# 22. Decline renewal
# ===================================================================


class TestDeclineRenewal:
    def test_decline_sets_declined(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        w = active_contract.decline_renewal("rw1")
        assert w.status == RenewalStatus.DECLINED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.decline_renewal("nope")


# ===================================================================
# 23. Renewals for contract
# ===================================================================


class TestRenewalsForContract:
    def test_empty(self, active_contract):
        assert active_contract.renewals_for_contract("c1") == ()

    def test_returns_correct(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        result = active_contract.renewals_for_contract("c1")
        assert len(result) == 1
        assert result[0].window_id == "rw1"


# ===================================================================
# 24. Assess contract
# ===================================================================


class TestAssessContract:
    def test_assess_no_commitments(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        a = engine.assess_contract("a1", "c1")
        assert isinstance(a, ContractAssessment)
        assert a.total_commitments == 0
        assert a.overall_compliance == 1.0

    def test_assess_all_healthy(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.99)
        a = full_stack.assess_contract("a1", "c1")
        assert a.healthy_commitments == 1
        assert a.at_risk_commitments == 0
        assert a.breached_commitments == 0
        assert a.overall_compliance == 1.0

    def test_assess_at_risk(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.90)
        a = full_stack.assess_contract("a1", "c1")
        assert a.at_risk_commitments == 1
        assert a.overall_compliance == 0.0

    def test_assess_breached(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.5)
        a = full_stack.assess_contract("a1", "c1")
        assert a.breached_commitments == 1
        assert a.overall_compliance == 0.0

    def test_assess_no_sla_windows_counts_healthy(self, full_stack):
        a = full_stack.assess_contract("a1", "c1")
        assert a.healthy_commitments == 1
        assert a.total_commitments == 1
        assert a.overall_compliance == 1.0

    def test_assess_uses_latest_window(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.5)
        full_stack.evaluate_sla("w2", "cm1", _T1, _T2, compliance=0.99)
        a = full_stack.assess_contract("a1", "c1")
        assert a.healthy_commitments == 1
        assert a.breached_commitments == 0

    def test_assess_multiple_commitments(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause1")
        engine.register_clause("cl2", "c1", "Clause2")
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        engine.register_commitment("cm2", "c1", "cl2", "t1", "99%")
        engine.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.99)
        engine.evaluate_sla("w2", "cm2", _T0, _T1, compliance=0.5)
        a = engine.assess_contract("a1", "c1")
        assert a.total_commitments == 2
        assert a.healthy_commitments == 1
        assert a.breached_commitments == 1
        assert a.overall_compliance == 0.5

    def test_duplicate_assessment_raises(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.assess_contract("a1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.assess_contract("a1", "c1")

    def test_assessment_count(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert engine.assessment_count == 0
        engine.assess_contract("a1", "c1")
        assert engine.assessment_count == 1

    def test_assessment_fills_tenant(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        a = engine.assess_contract("a1", "c1")
        assert a.tenant_id == "t1"


# ===================================================================
# 25. Violation detection
# ===================================================================


class TestDetectContractViolations:
    def test_no_violations_returns_empty(self, engine):
        result = engine.detect_contract_violations()
        assert result == ()

    def test_overdue_renewal_window(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _PAST, _PAST)
        violations = active_contract.detect_contract_violations()
        assert len(violations) >= 1
        assert any(v["operation"] == "overdue_renewal" for v in violations)

    def test_active_past_expires_at(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c1", "t1", "vendor-a", "Title", expires_at=_PAST)
        eng.activate_contract("c1")
        violations = eng.detect_contract_violations()
        assert len(violations) >= 1
        assert any(v["operation"] == "expired_active_contract" for v in violations)

    def test_idempotent(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _PAST, _PAST)
        v1 = active_contract.detect_contract_violations()
        v2 = active_contract.detect_contract_violations()
        assert len(v1) >= 1
        assert len(v2) == 0

    def test_violation_count_increments(self, active_contract):
        assert active_contract.violation_count == 0
        active_contract.schedule_renewal("rw1", "c1", _PAST, _PAST)
        active_contract.detect_contract_violations()
        assert active_contract.violation_count >= 1

    def test_future_renewal_not_overdue(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        violations = active_contract.detect_contract_violations()
        assert len(violations) == 0

    def test_completed_renewal_not_overdue(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _PAST, _PAST)
        active_contract.complete_renewal("rw1")
        violations = active_contract.detect_contract_violations()
        overdue = [v for v in violations if v.get("operation") == "overdue_renewal"]
        assert len(overdue) == 0


# ===================================================================
# 26. Contract snapshot
# ===================================================================


class TestContractSnapshot:
    def test_snapshot_empty_engine(self, engine):
        snap = engine.contract_snapshot("snap1")
        assert isinstance(snap, ContractSnapshot)
        assert snap.snapshot_id == "snap1"
        assert snap.total_contracts == 0
        assert snap.active_contracts == 0
        assert snap.total_commitments == 0

    def test_snapshot_populated_engine(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.5)
        full_stack.record_remedy("r1",
            list(full_stack.breaches_for_commitment("cm1"))[0].breach_id)
        full_stack.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        snap = full_stack.contract_snapshot("snap1")
        assert snap.total_contracts == 1
        assert snap.active_contracts == 1
        assert snap.total_commitments == 1
        assert snap.total_sla_windows == 1
        assert snap.total_breaches >= 1
        assert snap.total_remedies == 1
        assert snap.total_renewals == 1

    def test_duplicate_raises(self, engine):
        engine.contract_snapshot("snap1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.contract_snapshot("snap1")

    def test_captured_at_populated(self, engine):
        snap = engine.contract_snapshot("snap1")
        assert snap.captured_at != ""


# ===================================================================
# 27. State hash
# ===================================================================


class TestStateHash:
    def test_hash_returns_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_hash_length_16(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_hash_changes_after_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_same_counts_same_hash(self, es):
        e1 = ContractRuntimeEngine(es)
        e2 = ContractRuntimeEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# 28. Contract status transitions — comprehensive
# ===================================================================


class TestStatusTransitions:
    def test_draft_to_active(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        c = engine.activate_contract("c1")
        assert c.status == ContractStatus.ACTIVE

    def test_active_to_suspended(self, active_contract):
        c = active_contract.suspend_contract("c1")
        assert c.status == ContractStatus.SUSPENDED

    def test_suspended_to_active(self, active_contract):
        active_contract.suspend_contract("c1")
        c = active_contract.activate_contract("c1")
        assert c.status == ContractStatus.ACTIVE

    def test_active_to_terminated(self, active_contract):
        c = active_contract.terminate_contract("c1")
        assert c.status == ContractStatus.TERMINATED

    def test_active_to_expired(self, active_contract):
        c = active_contract.expire_contract("c1")
        assert c.status == ContractStatus.EXPIRED

    def test_draft_to_terminated(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        c = engine.terminate_contract("c1")
        assert c.status == ContractStatus.TERMINATED

    def test_draft_to_expired(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        c = engine.expire_contract("c1")
        assert c.status == ContractStatus.EXPIRED

    def test_renewed_can_activate(self, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        active_contract.complete_renewal("rw1")
        c = active_contract.get_contract("c1")
        assert c.status == ContractStatus.RENEWED
        c2 = active_contract.activate_contract("c1")
        assert c2.status == ContractStatus.ACTIVE


# ===================================================================
# 29. Event emission
# ===================================================================


class TestEventEmission:
    def test_register_contract_emits(self, es, engine):
        before = es.event_count
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        assert es.event_count == before + 1

    def test_activate_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.activate_contract("c1")
        assert es.event_count == before + 1

    def test_suspend_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.activate_contract("c1")
        before = es.event_count
        engine.suspend_contract("c1")
        assert es.event_count == before + 1

    def test_terminate_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.terminate_contract("c1")
        assert es.event_count == before + 1

    def test_expire_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.expire_contract("c1")
        assert es.event_count == before + 1

    def test_clause_registration_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.register_clause("cl1", "c1", "Clause")
        assert es.event_count == before + 1

    def test_commitment_registration_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        before = es.event_count
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        assert es.event_count == before + 1

    def test_sla_evaluation_emits(self, es, full_stack):
        before = es.event_count
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1)
        assert es.event_count > before

    def test_breach_recording_emits(self, es, full_stack):
        before = es.event_count
        full_stack.record_breach("b1", "cm1")
        assert es.event_count > before

    def test_remedy_recording_emits(self, es, full_stack):
        full_stack.record_breach("b1", "cm1")
        before = es.event_count
        full_stack.record_remedy("r1", "b1")
        assert es.event_count > before

    def test_renewal_scheduling_emits(self, es, active_contract):
        before = es.event_count
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        assert es.event_count > before

    def test_renewal_completion_emits(self, es, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        before = es.event_count
        active_contract.complete_renewal("rw1")
        assert es.event_count > before

    def test_renewal_decline_emits(self, es, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        before = es.event_count
        active_contract.decline_renewal("rw1")
        assert es.event_count > before

    def test_assessment_emits(self, es, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        before = es.event_count
        engine.assess_contract("a1", "c1")
        assert es.event_count > before

    def test_snapshot_emits(self, es, engine):
        before = es.event_count
        engine.contract_snapshot("snap1")
        assert es.event_count > before

    def test_violation_detection_emits_when_found(self, es, active_contract):
        active_contract.schedule_renewal("rw1", "c1", _PAST, _PAST)
        before = es.event_count
        active_contract.detect_contract_violations()
        assert es.event_count > before


# ===================================================================
# 30. Multiple contracts isolation
# ===================================================================


class TestMultiContractIsolation:
    def test_clauses_isolated_per_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        engine.register_clause("cl1", "c1", "Clause1")
        engine.register_clause("cl2", "c2", "Clause2")
        assert len(engine.clauses_for_contract("c1")) == 1
        assert len(engine.clauses_for_contract("c2")) == 1

    def test_commitments_isolated_per_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        engine.register_clause("cl1", "c1", "Clause1")
        engine.register_clause("cl2", "c2", "Clause2")
        engine.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        engine.register_commitment("cm2", "c2", "cl2", "t1", "99%")
        assert len(engine.commitments_for_contract("c1")) == 1
        assert len(engine.commitments_for_contract("c2")) == 1

    def test_renewals_isolated_per_contract(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title1")
        engine.register_contract("c2", "t1", "vendor-b", "Title2")
        engine.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        engine.schedule_renewal("rw2", "c2", _T0, _FUTURE)
        assert len(engine.renewals_for_contract("c1")) == 1
        assert len(engine.renewals_for_contract("c2")) == 1


# ===================================================================
# 31. Edge cases
# ===================================================================


class TestEdgeCases:
    def test_compliance_boundary_095(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.95)
        assert w.status == SLAStatus.HEALTHY

    def test_compliance_boundary_094999(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.9499)
        assert w.status == SLAStatus.AT_RISK

    def test_compliance_boundary_080(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.80)
        assert w.status == SLAStatus.AT_RISK

    def test_compliance_boundary_079999(self, full_stack):
        w = full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.7999)
        assert w.status == SLAStatus.BREACHED

    def test_multiple_sla_windows_same_commitment(self, full_stack):
        full_stack.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.99)
        full_stack.evaluate_sla("w2", "cm1", _T1, _T2, compliance=0.90)
        full_stack.evaluate_sla("w3", "cm1", _T2, _T3, compliance=0.50)
        assert full_stack.sla_window_count == 3
        windows = full_stack.sla_windows_for_commitment("cm1")
        assert len(windows) == 3

    def test_multiple_breaches_same_commitment(self, full_stack):
        full_stack.record_breach("b1", "cm1", severity=BreachSeverity.MINOR)
        full_stack.record_breach("b2", "cm1", severity=BreachSeverity.MAJOR)
        assert len(full_stack.breaches_for_commitment("cm1")) == 2

    def test_multiple_remedies_same_breach(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        full_stack.record_remedy("r1", "b1")
        full_stack.record_remedy("r2", "b1", disposition=RemedyDisposition.ESCALATED)
        assert len(full_stack.remedies_for_breach("b1")) == 2

    def test_all_commitment_kinds(self, engine):
        engine.register_contract("c1", "t1", "vendor-a", "Title")
        engine.register_clause("cl1", "c1", "Clause")
        for i, kind in enumerate(CommitmentKind):
            engine.register_commitment(f"cm{i}", "c1", "cl1", "t1", "99%", kind=kind)
        assert engine.commitment_count == len(CommitmentKind)

    def test_all_breach_severities(self, full_stack):
        for i, sev in enumerate(BreachSeverity):
            full_stack.record_breach(f"b{i}", "cm1", severity=sev)
        assert full_stack.breach_count == len(BreachSeverity)

    def test_all_remedy_dispositions(self, full_stack):
        full_stack.record_breach("b1", "cm1")
        for i, disp in enumerate(RemedyDisposition):
            full_stack.record_remedy(f"r{i}", "b1", disposition=disp)
        assert full_stack.remedy_count == len(RemedyDisposition)


# ===================================================================
# 32. Properties reflect state
# ===================================================================


class TestProperties:
    def test_active_contract_count_after_suspend(self, active_contract):
        assert active_contract.active_contract_count == 1
        active_contract.suspend_contract("c1")
        assert active_contract.active_contract_count == 0

    def test_active_contract_count_after_terminate(self, active_contract):
        active_contract.terminate_contract("c1")
        assert active_contract.active_contract_count == 0

    def test_active_contract_count_after_expire(self, active_contract):
        active_contract.expire_contract("c1")
        assert active_contract.active_contract_count == 0

    def test_contract_count_stable_after_status_change(self, active_contract):
        assert active_contract.contract_count == 1
        active_contract.suspend_contract("c1")
        assert active_contract.contract_count == 1

    def test_multiple_active_contracts(self, engine):
        for i in range(5):
            engine.register_contract(f"c{i}", "t1", f"vendor-{i}", f"Title{i}")
            engine.activate_contract(f"c{i}")
        assert engine.active_contract_count == 5
        engine.suspend_contract("c0")
        assert engine.active_contract_count == 4


# ===================================================================
# GOLDEN SCENARIOS
# ===================================================================


class TestGoldenScenario1CampaignDelayCreatesBreachRisk:
    """Campaign delay creates SLA breach risk (AT_RISK status)."""

    def test_campaign_delay_at_risk(self, es):
        eng = ContractRuntimeEngine(es)
        # Contract with campaign delivery SLA
        eng.register_contract("c-campaign", "tenant-acme", "agency-x",
                              "Campaign Delivery Agreement", expires_at=_FUTURE)
        eng.activate_contract("c-campaign")
        eng.register_clause("cl-delivery", "c-campaign", "Delivery Timeline",
                            commitment_kind=CommitmentKind.SLA)
        eng.register_commitment("cm-delivery", "c-campaign", "cl-delivery",
                                "tenant-acme", "14 days",
                                kind=CommitmentKind.SLA,
                                scope_ref_id="campaign-q1",
                                scope_ref_type="campaign")

        # First window: healthy
        w1 = eng.evaluate_sla("w-week1", "cm-delivery", _T0, _T1, compliance=0.98)
        assert w1.status == SLAStatus.HEALTHY
        assert eng.breach_count == 0

        # Delay causes compliance to slip into AT_RISK
        w2 = eng.evaluate_sla("w-week2", "cm-delivery", _T1, _T2,
                              compliance=0.88, actual_value="18 days projected")
        assert w2.status == SLAStatus.AT_RISK

        # No auto-breach for AT_RISK
        assert eng.breach_count == 0

        # Assessment shows the risk
        a = eng.assess_contract("assess-1", "c-campaign")
        assert a.at_risk_commitments == 1
        assert a.overall_compliance == 0.0  # 0 healthy / 1 total


class TestGoldenScenario2AvailabilityFailureTriggersBreach:
    """Availability failure triggers breach (BREACHED + auto-created BreachRecord)."""

    def test_availability_failure_breach(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-hosting", "tenant-corp", "cloud-provider",
                              "Hosting Agreement", expires_at=_FUTURE)
        eng.activate_contract("c-hosting")
        eng.register_clause("cl-uptime", "c-hosting", "Uptime SLA",
                            commitment_kind=CommitmentKind.AVAILABILITY)
        eng.register_commitment("cm-uptime", "c-hosting", "cl-uptime",
                                "tenant-corp", "99.95%",
                                kind=CommitmentKind.AVAILABILITY)

        # Major outage: compliance drops below 0.80
        w = eng.evaluate_sla("w-outage", "cm-uptime", _T0, _T1,
                             compliance=0.60, actual_value="99.0%")
        assert w.status == SLAStatus.BREACHED

        # Auto-created breach record
        assert eng.breach_count == 1
        breaches = eng.breaches_for_commitment("cm-uptime")
        assert len(breaches) == 1
        b = breaches[0]
        assert b.severity == BreachSeverity.MAJOR  # 0.60 >= 0.5
        assert b.contract_id == "c-hosting"
        assert b.tenant_id == "tenant-corp"
        assert "compliance=0.60" in b.description

    def test_critical_severity_at_very_low_compliance(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-hosting", "tenant-corp", "cloud-provider",
                              "Hosting Agreement", expires_at=_FUTURE)
        eng.activate_contract("c-hosting")
        eng.register_clause("cl-uptime", "c-hosting", "Uptime SLA")
        eng.register_commitment("cm-uptime", "c-hosting", "cl-uptime",
                                "tenant-corp", "99.95%")

        # Complete failure: compliance < 0.5
        w = eng.evaluate_sla("w-outage", "cm-uptime", _T0, _T1,
                             compliance=0.10)
        assert w.status == SLAStatus.BREACHED
        breaches = eng.breaches_for_commitment("cm-uptime")
        assert breaches[0].severity == BreachSeverity.CRITICAL


class TestGoldenScenario3BreachCreatesRemedyObligation:
    """Breach creates remedy obligation."""

    def test_breach_then_remedy(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-svc", "tenant-a", "provider-b",
                              "Service Agreement", expires_at=_FUTURE)
        eng.activate_contract("c-svc")
        eng.register_clause("cl-resp", "c-svc", "Response Time")
        eng.register_commitment("cm-resp", "c-svc", "cl-resp", "tenant-a",
                                "2 hours")

        # Record a breach
        b = eng.record_breach("b-resp", "cm-resp",
                              severity=BreachSeverity.MAJOR,
                              description="Response time exceeded")
        assert b.contract_id == "c-svc"
        assert b.tenant_id == "tenant-a"

        # Record a remedy for the breach
        r = eng.record_remedy("rem-credit", "b-resp",
                              disposition=RemedyDisposition.CREDIT_ISSUED,
                              amount="1000",
                              description="Service credit for SLA breach")
        assert r.breach_id == "b-resp"
        assert r.tenant_id == "tenant-a"
        assert r.disposition == RemedyDisposition.CREDIT_ISSUED
        assert r.amount == "1000"

        # Verify linkage
        remedies = eng.remedies_for_breach("b-resp")
        assert len(remedies) == 1
        assert remedies[0].remedy_id == "rem-credit"


class TestGoldenScenario4RemediationClosesBreachRisk:
    """Remediation completion closes breach risk (assessment shows improvement)."""

    def test_remediation_closes_risk(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-ops", "tenant-x", "ops-vendor",
                              "Operations Contract", expires_at=_FUTURE)
        eng.activate_contract("c-ops")
        eng.register_clause("cl-perf", "c-ops", "Performance SLA")
        eng.register_commitment("cm-perf", "c-ops", "cl-perf", "tenant-x", "99%")

        # Initial breach
        eng.evaluate_sla("w-breach", "cm-perf", _T0, _T1, compliance=0.50)
        a1 = eng.assess_contract("a-before", "c-ops")
        assert a1.breached_commitments == 1
        assert a1.overall_compliance == 0.0

        # Record breach and remedy
        eng.record_breach("b-perf", "cm-perf", severity=BreachSeverity.MAJOR)
        eng.record_remedy("rem-perf", "b-perf",
                          disposition=RemedyDisposition.PENALTY_APPLIED,
                          amount="5000")

        # After remediation, SLA improves
        eng.evaluate_sla("w-recovery", "cm-perf", _T1, _T2, compliance=0.99)

        # New assessment shows improvement
        a2 = eng.assess_contract("a-after", "c-ops")
        assert a2.breached_commitments == 0
        assert a2.healthy_commitments == 1
        assert a2.overall_compliance == 1.0

        # Confirms improvement: compliance went from 0.0 to 1.0
        assert a2.overall_compliance > a1.overall_compliance


class TestGoldenScenario5RenewalWindowEscalatesBeforeExpiry:
    """Renewal window escalates before contract expiry."""

    def test_renewal_escalation(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-annual", "tenant-y", "vendor-z",
                              "Annual Support Contract",
                              expires_at=_FUTURE)
        eng.activate_contract("c-annual")

        # Schedule a renewal window with a past close date to simulate overdue
        eng.schedule_renewal("rw-annual", "c-annual", _PAST, _PAST)

        # Detect violations: should find the overdue renewal
        violations = eng.detect_contract_violations()
        assert len(violations) >= 1
        overdue = [v for v in violations if v["operation"] == "overdue_renewal"]
        assert len(overdue) == 1
        assert overdue[0]["contract_id"] == "c-annual"
        assert overdue[0]["window_id"] == "rw-annual"

        # Idempotent: second call returns no new violations
        v2 = eng.detect_contract_violations()
        assert len(v2) == 0

        # Completing renewal resolves the situation
        eng.complete_renewal("rw-annual")
        c = eng.get_contract("c-annual")
        assert c.status == ContractStatus.RENEWED

    def test_active_contract_past_expiry_violation(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c-expired-active", "tenant-y", "vendor-z",
                              "Expired Active Contract",
                              expires_at=_PAST)
        eng.activate_contract("c-expired-active")

        violations = eng.detect_contract_violations()
        expired_active = [v for v in violations if v["operation"] == "expired_active_contract"]
        assert len(expired_active) == 1
        assert expired_active[0]["contract_id"] == "c-expired-active"


class TestGoldenScenario6FullLifecycleSnapshotAndHash:
    """Full lifecycle snapshot and hash."""

    def test_full_lifecycle(self, es):
        eng = ContractRuntimeEngine(es)

        # Empty state hash
        h_empty = eng.state_hash()
        assert len(h_empty) == 64

        # Register and activate contract
        eng.register_contract("c-life", "tenant-z", "partner-a",
                              "Full Lifecycle Contract", expires_at=_FUTURE)
        eng.activate_contract("c-life")

        # Add clause and commitment
        eng.register_clause("cl-sla", "c-life", "SLA Clause")
        eng.register_commitment("cm-sla", "c-life", "cl-sla", "tenant-z",
                                "99.9%")

        # Evaluate SLA: healthy
        eng.evaluate_sla("w-h", "cm-sla", _T0, _T1, compliance=0.99)

        # Evaluate SLA: breached (auto-creates breach)
        eng.evaluate_sla("w-b", "cm-sla", _T1, _T2, compliance=0.40)
        assert eng.breach_count >= 1

        # Record remedy
        breach = eng.breaches_for_commitment("cm-sla")[0]
        eng.record_remedy("rem-1", breach.breach_id,
                          disposition=RemedyDisposition.CREDIT_ISSUED,
                          amount="2000")

        # Schedule and complete renewal
        eng.schedule_renewal("rw-life", "c-life", _T0, _FUTURE)
        eng.complete_renewal("rw-life")
        assert eng.get_contract("c-life").status == ContractStatus.RENEWED

        # Assess the contract
        a = eng.assess_contract("assess-life", "c-life")
        assert a.total_commitments == 1

        # Take snapshot
        snap = eng.contract_snapshot("snap-life")
        assert snap.total_contracts == 1
        assert snap.total_commitments == 1
        assert snap.total_sla_windows == 2
        assert snap.total_breaches >= 1
        assert snap.total_remedies == 1
        assert snap.total_renewals == 1

        # Hash changed from empty
        h_final = eng.state_hash()
        assert h_final != h_empty

        # Verify event emission throughout
        assert es.event_count > 0

    def test_snapshot_reflects_violations(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c1", "t1", "v1", "Title", expires_at=_PAST)
        eng.activate_contract("c1")
        eng.detect_contract_violations()

        snap = eng.contract_snapshot("snap-v")
        assert snap.total_violations >= 1

    def test_hash_changes_with_each_entity_type(self, es):
        eng = ContractRuntimeEngine(es)
        hashes = [eng.state_hash()]

        eng.register_contract("c1", "t1", "v1", "Title")
        hashes.append(eng.state_hash())

        eng.register_clause("cl1", "c1", "Clause")
        hashes.append(eng.state_hash())

        eng.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        hashes.append(eng.state_hash())

        eng.evaluate_sla("w1", "cm1", _T0, _T1)
        hashes.append(eng.state_hash())

        eng.record_breach("b1", "cm1")
        hashes.append(eng.state_hash())

        eng.record_remedy("r1", "b1")
        hashes.append(eng.state_hash())

        eng.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        hashes.append(eng.state_hash())

        eng.assess_contract("a1", "c1")
        hashes.append(eng.state_hash())

        # Each addition changes the hash
        for i in range(1, len(hashes)):
            assert hashes[i] != hashes[i - 1], f"Hash unchanged at step {i}"

    def test_snapshot_after_full_lifecycle_has_all_counts(self, es):
        eng = ContractRuntimeEngine(es)
        eng.register_contract("c1", "t1", "v1", "Title", expires_at=_PAST)
        eng.activate_contract("c1")
        eng.register_clause("cl1", "c1", "Clause")
        eng.register_commitment("cm1", "c1", "cl1", "t1", "99%")
        eng.evaluate_sla("w1", "cm1", _T0, _T1, compliance=0.3)
        eng.record_breach("b-manual", "cm1", severity=BreachSeverity.MODERATE)
        auto_breach = eng.breaches_for_commitment("cm1")[0]
        eng.record_remedy("r1", auto_breach.breach_id)
        eng.schedule_renewal("rw1", "c1", _T0, _FUTURE)
        eng.detect_contract_violations()
        snap = eng.contract_snapshot("snap-full")
        assert snap.total_contracts == 1
        assert snap.active_contracts == 1
        assert snap.total_commitments == 1
        assert snap.total_sla_windows == 1
        assert snap.total_breaches == 2  # auto + manual
        assert snap.total_remedies == 1
        assert snap.total_renewals == 1
        assert snap.total_violations >= 1
