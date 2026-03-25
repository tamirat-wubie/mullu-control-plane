"""Tests for contract / SLA / commitment governance runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.contract_runtime import (
    BreachRecord,
    BreachSeverity,
    CommitmentKind,
    CommitmentRecord,
    ContractAssessment,
    ContractClause,
    ContractClosureReport,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"
TS3 = "2025-07-01T00:00:00+00:00"


def _governance_contract(**overrides) -> GovernanceContractRecord:
    defaults = dict(
        contract_id="con-001",
        tenant_id="t-001",
        counterparty="cp-001",
        status=ContractStatus.ACTIVE,
        title="Service Agreement",
        description="Main SLA contract",
        effective_at=TS,
        expires_at=TS2,
    )
    defaults.update(overrides)
    return GovernanceContractRecord(**defaults)


def _clause(**overrides) -> ContractClause:
    defaults = dict(
        clause_id="cl-001",
        contract_id="con-001",
        title="Uptime Clause",
        description="99.9% uptime",
        commitment_kind=CommitmentKind.SLA,
    )
    defaults.update(overrides)
    return ContractClause(**defaults)


def _commitment(**overrides) -> CommitmentRecord:
    defaults = dict(
        commitment_id="cm-001",
        contract_id="con-001",
        clause_id="cl-001",
        tenant_id="t-001",
        kind=CommitmentKind.AVAILABILITY,
        target_value="99.9%",
        scope_ref_id="svc-001",
        scope_ref_type="service",
        created_at=TS,
    )
    defaults.update(overrides)
    return CommitmentRecord(**defaults)


def _sla_window(**overrides) -> SLAWindow:
    defaults = dict(
        window_id="sw-001",
        commitment_id="cm-001",
        status=SLAStatus.HEALTHY,
        opens_at=TS,
        closes_at=TS2,
        actual_value="99.95%",
        compliance=0.95,
    )
    defaults.update(overrides)
    return SLAWindow(**defaults)


def _breach(**overrides) -> BreachRecord:
    defaults = dict(
        breach_id="br-001",
        commitment_id="cm-001",
        contract_id="con-001",
        tenant_id="t-001",
        severity=BreachSeverity.MAJOR,
        description="SLA breach detected",
        detected_at=TS,
    )
    defaults.update(overrides)
    return BreachRecord(**defaults)


def _remedy(**overrides) -> RemedyRecord:
    defaults = dict(
        remedy_id="rm-001",
        breach_id="br-001",
        tenant_id="t-001",
        disposition=RemedyDisposition.CREDIT_ISSUED,
        amount="500.00",
        description="Credit issued",
        applied_at=TS,
    )
    defaults.update(overrides)
    return RemedyRecord(**defaults)


def _renewal_window(**overrides) -> RenewalWindow:
    defaults = dict(
        window_id="rw-001",
        contract_id="con-001",
        status=RenewalStatus.SCHEDULED,
        opens_at=TS,
        closes_at=TS2,
        completed_at=TS3,
    )
    defaults.update(overrides)
    return RenewalWindow(**defaults)


def _assessment(**overrides) -> ContractAssessment:
    defaults = dict(
        assessment_id="ca-001",
        contract_id="con-001",
        tenant_id="t-001",
        total_commitments=10,
        healthy_commitments=7,
        at_risk_commitments=2,
        breached_commitments=1,
        overall_compliance=0.85,
        assessed_at=TS,
    )
    defaults.update(overrides)
    return ContractAssessment(**defaults)


def _snapshot(**overrides) -> ContractSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_contracts=5,
        active_contracts=3,
        total_commitments=20,
        total_sla_windows=15,
        total_breaches=2,
        total_remedies=1,
        total_renewals=3,
        total_violations=0,
        captured_at=TS,
    )
    defaults.update(overrides)
    return ContractSnapshot(**defaults)


def _closure_report(**overrides) -> ContractClosureReport:
    defaults = dict(
        report_id="rpt-001",
        contract_id="con-001",
        tenant_id="t-001",
        final_status=ContractStatus.TERMINATED,
        total_commitments=10,
        total_breaches=2,
        total_remedies=1,
        total_renewals=3,
        closed_at=TS,
    )
    defaults.update(overrides)
    return ContractClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestContractStatus:
    def test_members(self):
        assert len(ContractStatus) == 6

    @pytest.mark.parametrize("member", list(ContractStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert ContractStatus.DRAFT.value == "draft"
        assert ContractStatus.ACTIVE.value == "active"
        assert ContractStatus.SUSPENDED.value == "suspended"
        assert ContractStatus.EXPIRED.value == "expired"
        assert ContractStatus.TERMINATED.value == "terminated"
        assert ContractStatus.RENEWED.value == "renewed"


class TestCommitmentKind:
    def test_members(self):
        assert len(CommitmentKind) == 6

    @pytest.mark.parametrize("member", list(CommitmentKind))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert CommitmentKind.SLA.value == "sla"
        assert CommitmentKind.OLA.value == "ola"
        assert CommitmentKind.AVAILABILITY.value == "availability"
        assert CommitmentKind.RESPONSE_TIME.value == "response_time"
        assert CommitmentKind.THROUGHPUT.value == "throughput"
        assert CommitmentKind.COMPLIANCE.value == "compliance"


class TestSLAStatus:
    def test_members(self):
        assert len(SLAStatus) == 5

    @pytest.mark.parametrize("member", list(SLAStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert SLAStatus.HEALTHY.value == "healthy"
        assert SLAStatus.AT_RISK.value == "at_risk"
        assert SLAStatus.BREACHED.value == "breached"
        assert SLAStatus.WAIVED.value == "waived"
        assert SLAStatus.CLOSED.value == "closed"


class TestBreachSeverity:
    def test_members(self):
        assert len(BreachSeverity) == 4

    @pytest.mark.parametrize("member", list(BreachSeverity))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert BreachSeverity.MINOR.value == "minor"
        assert BreachSeverity.MODERATE.value == "moderate"
        assert BreachSeverity.MAJOR.value == "major"
        assert BreachSeverity.CRITICAL.value == "critical"


class TestRenewalStatus:
    def test_members(self):
        assert len(RenewalStatus) == 5

    @pytest.mark.parametrize("member", list(RenewalStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert RenewalStatus.SCHEDULED.value == "scheduled"
        assert RenewalStatus.IN_PROGRESS.value == "in_progress"
        assert RenewalStatus.COMPLETED.value == "completed"
        assert RenewalStatus.OVERDUE.value == "overdue"
        assert RenewalStatus.DECLINED.value == "declined"


class TestRemedyDisposition:
    def test_members(self):
        assert len(RemedyDisposition) == 6

    @pytest.mark.parametrize("member", list(RemedyDisposition))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert RemedyDisposition.PENDING.value == "pending"
        assert RemedyDisposition.CREDIT_ISSUED.value == "credit_issued"
        assert RemedyDisposition.PENALTY_APPLIED.value == "penalty_applied"
        assert RemedyDisposition.WAIVED.value == "waived"
        assert RemedyDisposition.ESCALATED.value == "escalated"
        assert RemedyDisposition.CLOSED.value == "closed"


# ===================================================================
# GovernanceContractRecord tests
# ===================================================================


class TestGovernanceContractRecord:
    def test_happy_path(self):
        rec = _governance_contract()
        assert rec.contract_id == "con-001"
        assert rec.tenant_id == "t-001"
        assert rec.counterparty == "cp-001"
        assert rec.status is ContractStatus.ACTIVE
        assert rec.title == "Service Agreement"
        assert rec.description == "Main SLA contract"
        assert rec.effective_at == TS
        assert rec.expires_at == TS2

    def test_frozen(self):
        rec = _governance_contract()
        with pytest.raises(AttributeError):
            rec.title = "changed"

    def test_slots(self):
        assert "__slots__" in dir(GovernanceContractRecord)

    def test_default_status_is_draft(self):
        rec = _governance_contract(status=ContractStatus.DRAFT)
        assert rec.status is ContractStatus.DRAFT

    def test_metadata_frozen(self):
        rec = _governance_contract(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _governance_contract(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _governance_contract(metadata={"items": [1, 2, 3]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["contract_id", "tenant_id", "counterparty", "title"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _governance_contract(**{field: ""})

    @pytest.mark.parametrize("field", ["contract_id", "tenant_id", "counterparty", "title"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _governance_contract(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _governance_contract(status="active")

    def test_invalid_effective_at_rejected(self):
        with pytest.raises(ValueError):
            _governance_contract(effective_at="not-a-date")

    def test_empty_effective_at_rejected(self):
        with pytest.raises(ValueError):
            _governance_contract(effective_at="")

    def test_expires_at_optional_empty(self):
        rec = _governance_contract(expires_at="")
        assert rec.expires_at == ""

    def test_to_dict_preserves_enums(self):
        rec = _governance_contract()
        d = rec.to_dict()
        assert d["status"] is ContractStatus.ACTIVE

    def test_to_dict_keys(self):
        rec = _governance_contract()
        d = rec.to_dict()
        expected_keys = {
            "contract_id", "tenant_id", "counterparty", "status",
            "title", "description", "effective_at", "expires_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(ContractStatus))
    def test_all_statuses_accepted(self, status):
        rec = _governance_contract(status=status)
        assert rec.status is status


# ===================================================================
# ContractClause tests
# ===================================================================


class TestContractClause:
    def test_happy_path(self):
        rec = _clause()
        assert rec.clause_id == "cl-001"
        assert rec.contract_id == "con-001"
        assert rec.title == "Uptime Clause"
        assert rec.description == "99.9% uptime"
        assert rec.commitment_kind is CommitmentKind.SLA

    def test_frozen(self):
        rec = _clause()
        with pytest.raises(AttributeError):
            rec.clause_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ContractClause)

    @pytest.mark.parametrize("field", ["clause_id", "contract_id", "title"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _clause(**{field: ""})

    @pytest.mark.parametrize("field", ["clause_id", "contract_id", "title"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _clause(**{field: "   "})

    def test_invalid_commitment_kind_rejected(self):
        with pytest.raises(ValueError):
            _clause(commitment_kind="sla")

    def test_metadata_frozen(self):
        rec = _clause(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _clause()
        d = rec.to_dict()
        assert d["commitment_kind"] is CommitmentKind.SLA

    @pytest.mark.parametrize("kind", list(CommitmentKind))
    def test_all_commitment_kinds_accepted(self, kind):
        rec = _clause(commitment_kind=kind)
        assert rec.commitment_kind is kind

    def test_default_commitment_kind_is_sla(self):
        rec = _clause()
        assert rec.commitment_kind is CommitmentKind.SLA


# ===================================================================
# CommitmentRecord tests
# ===================================================================


class TestCommitmentRecord:
    def test_happy_path(self):
        rec = _commitment()
        assert rec.commitment_id == "cm-001"
        assert rec.contract_id == "con-001"
        assert rec.clause_id == "cl-001"
        assert rec.tenant_id == "t-001"
        assert rec.kind is CommitmentKind.AVAILABILITY
        assert rec.target_value == "99.9%"
        assert rec.scope_ref_id == "svc-001"
        assert rec.scope_ref_type == "service"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _commitment()
        with pytest.raises(AttributeError):
            rec.kind = CommitmentKind.SLA

    def test_slots(self):
        assert "__slots__" in dir(CommitmentRecord)

    @pytest.mark.parametrize("field", [
        "commitment_id", "contract_id", "clause_id", "tenant_id", "target_value",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _commitment(**{field: ""})

    @pytest.mark.parametrize("field", [
        "commitment_id", "contract_id", "clause_id", "tenant_id", "target_value",
    ])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _commitment(**{field: "   "})

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            _commitment(kind="sla")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _commitment(created_at="not-a-date")

    def test_metadata_frozen(self):
        rec = _commitment(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _commitment()
        d = rec.to_dict()
        assert d["kind"] is CommitmentKind.AVAILABILITY


# ===================================================================
# SLAWindow tests
# ===================================================================


class TestSLAWindow:
    def test_happy_path(self):
        rec = _sla_window()
        assert rec.window_id == "sw-001"
        assert rec.commitment_id == "cm-001"
        assert rec.status is SLAStatus.HEALTHY
        assert rec.opens_at == TS
        assert rec.closes_at == TS2
        assert rec.actual_value == "99.95%"
        assert rec.compliance == 0.95

    def test_frozen(self):
        rec = _sla_window()
        with pytest.raises(AttributeError):
            rec.compliance = 0.5

    def test_slots(self):
        assert "__slots__" in dir(SLAWindow)

    def test_default_status_is_healthy(self):
        rec = _sla_window(status=SLAStatus.HEALTHY)
        assert rec.status is SLAStatus.HEALTHY

    @pytest.mark.parametrize("field", ["window_id", "commitment_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _sla_window(**{field: ""})

    @pytest.mark.parametrize("field", ["window_id", "commitment_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _sla_window(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(status="healthy")

    def test_invalid_opens_at_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(opens_at="bad")

    def test_invalid_closes_at_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(closes_at="bad")

    def test_compliance_zero(self):
        rec = _sla_window(compliance=0.0)
        assert rec.compliance == 0.0

    def test_compliance_one(self):
        rec = _sla_window(compliance=1.0)
        assert rec.compliance == 1.0

    def test_compliance_negative_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(compliance=-0.1)

    def test_compliance_above_one_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(compliance=1.01)

    def test_compliance_nan_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(compliance=float("nan"))

    def test_compliance_inf_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(compliance=float("inf"))

    def test_compliance_bool_rejected(self):
        with pytest.raises(ValueError):
            _sla_window(compliance=True)

    def test_metadata_frozen(self):
        rec = _sla_window(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _sla_window()
        d = rec.to_dict()
        assert d["status"] is SLAStatus.HEALTHY

    @pytest.mark.parametrize("status", list(SLAStatus))
    def test_all_statuses_accepted(self, status):
        rec = _sla_window(status=status)
        assert rec.status is status


# ===================================================================
# BreachRecord tests
# ===================================================================


class TestBreachRecord:
    def test_happy_path(self):
        rec = _breach()
        assert rec.breach_id == "br-001"
        assert rec.commitment_id == "cm-001"
        assert rec.contract_id == "con-001"
        assert rec.tenant_id == "t-001"
        assert rec.severity is BreachSeverity.MAJOR
        assert rec.description == "SLA breach detected"
        assert rec.detected_at == TS

    def test_frozen(self):
        rec = _breach()
        with pytest.raises(AttributeError):
            rec.severity = BreachSeverity.MINOR

    def test_slots(self):
        assert "__slots__" in dir(BreachRecord)

    def test_default_severity_is_minor(self):
        rec = _breach(severity=BreachSeverity.MINOR)
        assert rec.severity is BreachSeverity.MINOR

    @pytest.mark.parametrize("field", [
        "breach_id", "commitment_id", "contract_id", "tenant_id",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _breach(**{field: ""})

    @pytest.mark.parametrize("field", [
        "breach_id", "commitment_id", "contract_id", "tenant_id",
    ])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _breach(**{field: "   "})

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            _breach(severity="major")

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError):
            _breach(detected_at="not-a-date")

    def test_metadata_frozen(self):
        rec = _breach(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _breach()
        d = rec.to_dict()
        assert d["severity"] is BreachSeverity.MAJOR

    @pytest.mark.parametrize("severity", list(BreachSeverity))
    def test_all_severities_accepted(self, severity):
        rec = _breach(severity=severity)
        assert rec.severity is severity


# ===================================================================
# RemedyRecord tests
# ===================================================================


class TestRemedyRecord:
    def test_happy_path(self):
        rec = _remedy()
        assert rec.remedy_id == "rm-001"
        assert rec.breach_id == "br-001"
        assert rec.tenant_id == "t-001"
        assert rec.disposition is RemedyDisposition.CREDIT_ISSUED
        assert rec.amount == "500.00"
        assert rec.description == "Credit issued"
        assert rec.applied_at == TS

    def test_frozen(self):
        rec = _remedy()
        with pytest.raises(AttributeError):
            rec.amount = "0"

    def test_slots(self):
        assert "__slots__" in dir(RemedyRecord)

    def test_default_disposition_is_pending(self):
        rec = _remedy(disposition=RemedyDisposition.PENDING)
        assert rec.disposition is RemedyDisposition.PENDING

    @pytest.mark.parametrize("field", ["remedy_id", "breach_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _remedy(**{field: ""})

    @pytest.mark.parametrize("field", ["remedy_id", "breach_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _remedy(**{field: "   "})

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _remedy(disposition="pending")

    def test_invalid_applied_at_rejected(self):
        with pytest.raises(ValueError):
            _remedy(applied_at="not-a-date")

    def test_metadata_frozen(self):
        rec = _remedy(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _remedy()
        d = rec.to_dict()
        assert d["disposition"] is RemedyDisposition.CREDIT_ISSUED

    @pytest.mark.parametrize("disposition", list(RemedyDisposition))
    def test_all_dispositions_accepted(self, disposition):
        rec = _remedy(disposition=disposition)
        assert rec.disposition is disposition


# ===================================================================
# RenewalWindow tests
# ===================================================================


class TestRenewalWindow:
    def test_happy_path(self):
        rec = _renewal_window()
        assert rec.window_id == "rw-001"
        assert rec.contract_id == "con-001"
        assert rec.status is RenewalStatus.SCHEDULED
        assert rec.opens_at == TS
        assert rec.closes_at == TS2
        assert rec.completed_at == TS3

    def test_frozen(self):
        rec = _renewal_window()
        with pytest.raises(AttributeError):
            rec.status = RenewalStatus.COMPLETED

    def test_slots(self):
        assert "__slots__" in dir(RenewalWindow)

    def test_default_status_is_scheduled(self):
        rec = _renewal_window(status=RenewalStatus.SCHEDULED)
        assert rec.status is RenewalStatus.SCHEDULED

    @pytest.mark.parametrize("field", ["window_id", "contract_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _renewal_window(**{field: ""})

    @pytest.mark.parametrize("field", ["window_id", "contract_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _renewal_window(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(status="scheduled")

    def test_invalid_opens_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(opens_at="bad")

    def test_invalid_closes_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(closes_at="bad")

    def test_completed_at_optional_empty(self):
        rec = _renewal_window(completed_at="")
        assert rec.completed_at == ""

    def test_metadata_frozen(self):
        rec = _renewal_window(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _renewal_window()
        d = rec.to_dict()
        assert d["status"] is RenewalStatus.SCHEDULED

    @pytest.mark.parametrize("status", list(RenewalStatus))
    def test_all_statuses_accepted(self, status):
        rec = _renewal_window(status=status)
        assert rec.status is status


# ===================================================================
# ContractAssessment tests
# ===================================================================


class TestContractAssessment:
    def test_happy_path(self):
        rec = _assessment()
        assert rec.assessment_id == "ca-001"
        assert rec.contract_id == "con-001"
        assert rec.tenant_id == "t-001"
        assert rec.total_commitments == 10
        assert rec.healthy_commitments == 7
        assert rec.at_risk_commitments == 2
        assert rec.breached_commitments == 1
        assert rec.overall_compliance == 0.85
        assert rec.assessed_at == TS

    def test_frozen(self):
        rec = _assessment()
        with pytest.raises(AttributeError):
            rec.total_commitments = 5

    def test_slots(self):
        assert "__slots__" in dir(ContractAssessment)

    @pytest.mark.parametrize("field", ["assessment_id", "contract_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    @pytest.mark.parametrize("field", ["assessment_id", "contract_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: "   "})

    @pytest.mark.parametrize("field", [
        "total_commitments", "healthy_commitments",
        "at_risk_commitments", "breached_commitments",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_commitments", "healthy_commitments",
        "at_risk_commitments", "breached_commitments",
    ])
    def test_zero_int_accepted(self, field):
        rec = _assessment(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", [
        "total_commitments", "healthy_commitments",
        "at_risk_commitments", "breached_commitments",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: True})

    def test_overall_compliance_zero(self):
        rec = _assessment(overall_compliance=0.0)
        assert rec.overall_compliance == 0.0

    def test_overall_compliance_one(self):
        rec = _assessment(overall_compliance=1.0)
        assert rec.overall_compliance == 1.0

    def test_overall_compliance_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(overall_compliance=-0.01)

    def test_overall_compliance_above_one_rejected(self):
        with pytest.raises(ValueError):
            _assessment(overall_compliance=1.01)

    def test_overall_compliance_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(overall_compliance=float("nan"))

    def test_overall_compliance_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(overall_compliance=float("inf"))

    def test_overall_compliance_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(overall_compliance=True)

    def test_invalid_assessed_at_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_metadata_frozen(self):
        rec = _assessment(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        rec = _assessment()
        d = rec.to_dict()
        expected = {
            "assessment_id", "contract_id", "tenant_id",
            "total_commitments", "healthy_commitments",
            "at_risk_commitments", "breached_commitments",
            "overall_compliance", "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected


# ===================================================================
# ContractSnapshot tests
# ===================================================================


class TestContractSnapshot:
    def test_happy_path(self):
        rec = _snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_contracts == 5
        assert rec.active_contracts == 3
        assert rec.total_commitments == 20
        assert rec.total_sla_windows == 15
        assert rec.total_breaches == 2
        assert rec.total_remedies == 1
        assert rec.total_renewals == 3
        assert rec.total_violations == 0
        assert rec.captured_at == TS

    def test_frozen(self):
        rec = _snapshot()
        with pytest.raises(AttributeError):
            rec.total_contracts = 10

    def test_slots(self):
        assert "__slots__" in dir(ContractSnapshot)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="   ")

    @pytest.mark.parametrize("field", [
        "total_contracts", "active_contracts", "total_commitments",
        "total_sla_windows", "total_breaches", "total_remedies",
        "total_renewals", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_contracts", "active_contracts", "total_commitments",
        "total_sla_windows", "total_breaches", "total_remedies",
        "total_renewals", "total_violations",
    ])
    def test_zero_int_accepted(self, field):
        rec = _snapshot(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", [
        "total_contracts", "active_contracts", "total_commitments",
        "total_sla_windows", "total_breaches", "total_remedies",
        "total_renewals", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: False})

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_metadata_frozen(self):
        rec = _snapshot(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        rec = _snapshot()
        d = rec.to_dict()
        expected = {
            "snapshot_id", "total_contracts", "active_contracts",
            "total_commitments", "total_sla_windows", "total_breaches",
            "total_remedies", "total_renewals", "total_violations",
            "captured_at", "metadata",
        }
        assert set(d.keys()) == expected


# ===================================================================
# ContractClosureReport tests
# ===================================================================


class TestContractClosureReport:
    def test_happy_path(self):
        rec = _closure_report()
        assert rec.report_id == "rpt-001"
        assert rec.contract_id == "con-001"
        assert rec.tenant_id == "t-001"
        assert rec.final_status is ContractStatus.TERMINATED
        assert rec.total_commitments == 10
        assert rec.total_breaches == 2
        assert rec.total_remedies == 1
        assert rec.total_renewals == 3
        assert rec.closed_at == TS

    def test_frozen(self):
        rec = _closure_report()
        with pytest.raises(AttributeError):
            rec.report_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ContractClosureReport)

    def test_default_final_status_is_terminated(self):
        rec = _closure_report()
        assert rec.final_status is ContractStatus.TERMINATED

    @pytest.mark.parametrize("field", ["report_id", "contract_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "contract_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: "   "})

    def test_invalid_final_status_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(final_status="terminated")

    @pytest.mark.parametrize("field", [
        "total_commitments", "total_breaches", "total_remedies", "total_renewals",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_commitments", "total_breaches", "total_remedies", "total_renewals",
    ])
    def test_zero_int_accepted(self, field):
        rec = _closure_report(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", [
        "total_commitments", "total_breaches", "total_remedies", "total_renewals",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: True})

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="bad")

    def test_metadata_frozen(self):
        rec = _closure_report(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        rec = _closure_report()
        d = rec.to_dict()
        assert d["final_status"] is ContractStatus.TERMINATED

    @pytest.mark.parametrize("status", list(ContractStatus))
    def test_all_final_statuses_accepted(self, status):
        rec = _closure_report(final_status=status)
        assert rec.final_status is status

    def test_to_dict_keys(self):
        rec = _closure_report()
        d = rec.to_dict()
        expected = {
            "report_id", "contract_id", "tenant_id", "final_status",
            "total_commitments", "total_breaches", "total_remedies",
            "total_renewals", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected


# ===================================================================
# Cross-cutting / integration-style tests
# ===================================================================


class TestCrossCutting:
    """Tests that span multiple types or verify shared behaviors."""

    def test_all_dataclasses_are_frozen(self):
        classes = [
            GovernanceContractRecord, ContractClause, CommitmentRecord,
            SLAWindow, BreachRecord, RemedyRecord, RenewalWindow,
            ContractAssessment, ContractSnapshot, ContractClosureReport,
        ]
        for cls in classes:
            assert dataclasses.fields(cls) is not None
            params = cls.__dataclass_params__
            assert params.frozen is True, f"{cls.__name__} must be frozen"

    def test_all_dataclasses_have_slots(self):
        classes = [
            GovernanceContractRecord, ContractClause, CommitmentRecord,
            SLAWindow, BreachRecord, RemedyRecord, RenewalWindow,
            ContractAssessment, ContractSnapshot, ContractClosureReport,
        ]
        for cls in classes:
            params = cls.__dataclass_params__
            assert params.slots is True, f"{cls.__name__} must have slots"

    def test_all_dataclasses_extend_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        classes = [
            GovernanceContractRecord, ContractClause, CommitmentRecord,
            SLAWindow, BreachRecord, RemedyRecord, RenewalWindow,
            ContractAssessment, ContractSnapshot, ContractClosureReport,
        ]
        for cls in classes:
            assert issubclass(cls, ContractRecord), f"{cls.__name__} must extend ContractRecord"

    def test_empty_metadata_default(self):
        rec = _governance_contract()
        assert rec.metadata == MappingProxyType({})

    def test_governance_contract_iso_z_suffix_accepted(self):
        rec = _governance_contract(effective_at="2025-06-01T00:00:00Z")
        assert rec.effective_at == "2025-06-01T00:00:00Z"

    def test_sla_window_compliance_int_zero_accepted(self):
        rec = _sla_window(compliance=0)
        assert rec.compliance == 0.0

    def test_sla_window_compliance_int_one_accepted(self):
        rec = _sla_window(compliance=1)
        assert rec.compliance == 1.0

    def test_assessment_overall_compliance_int_accepted(self):
        rec = _assessment(overall_compliance=1)
        assert rec.overall_compliance == 1.0

    def test_deeply_nested_metadata_frozen(self):
        rec = _governance_contract(metadata={
            "level1": {"level2": {"level3": [1, 2, 3]}},
        })
        assert isinstance(rec.metadata["level1"], MappingProxyType)
        assert isinstance(rec.metadata["level1"]["level2"], MappingProxyType)
        assert isinstance(rec.metadata["level1"]["level2"]["level3"], tuple)

    def test_metadata_with_set_becomes_frozenset(self):
        rec = _clause(metadata={"tags": frozenset(["a", "b"])})
        assert isinstance(rec.metadata["tags"], frozenset)

    def test_to_dict_metadata_thawed(self):
        rec = _governance_contract(metadata={"key": [1, 2]})
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["key"], list)
