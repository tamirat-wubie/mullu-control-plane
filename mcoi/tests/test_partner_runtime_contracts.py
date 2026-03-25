"""Purpose: contract tests for partner_runtime.py enums and frozen dataclasses.
Governance scope: Milestone 1 contract validation.
Dependencies: pytest, partner_runtime contracts, _base utilities.
Invariants: all dataclasses are frozen; metadata becomes MappingProxyType;
    to_dict() preserves enum objects; validators reject invalid state.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.partner_runtime import (
    EcosystemAgreement,
    EcosystemRole,
    PartnerAccountLink,
    PartnerClosureReport,
    PartnerCommitment,
    PartnerDecision,
    PartnerDisposition,
    PartnerHealthSnapshot,
    PartnerHealthStatus,
    PartnerKind,
    PartnerRecord,
    PartnerSnapshot,
    PartnerStatus,
    PartnerViolation,
    RevenueShareRecord,
    RevenueShareStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = datetime.now(timezone.utc).isoformat()
TS2 = "2025-06-01"


def _pr(**kw):
    defaults = dict(
        partner_id="p1", tenant_id="t1", display_name="Acme",
        kind=PartnerKind.RESELLER, status=PartnerStatus.ACTIVE,
        tier="gold", account_link_count=3, created_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerRecord(**defaults)


def _pal(**kw):
    defaults = dict(
        link_id="l1", partner_id="p1", account_id="a1", tenant_id="t1",
        role=EcosystemRole.INTERMEDIARY, created_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerAccountLink(**defaults)


def _ea(**kw):
    defaults = dict(
        agreement_id="ag1", partner_id="p1", tenant_id="t1",
        title="Revenue Deal", contract_ref="CR-100",
        revenue_share_pct=0.3, created_at=TS, metadata={},
    )
    defaults.update(kw)
    return EcosystemAgreement(**defaults)


def _rsr(**kw):
    defaults = dict(
        share_id="s1", partner_id="p1", agreement_id="ag1", tenant_id="t1",
        gross_amount=1000.0, share_amount=300.0, share_pct=0.3,
        status=RevenueShareStatus.PENDING, created_at=TS, metadata={},
    )
    defaults.update(kw)
    return RevenueShareRecord(**defaults)


def _pc(**kw):
    defaults = dict(
        commitment_id="c1", partner_id="p1", tenant_id="t1",
        description="Quarterly target", target_value=100.0,
        actual_value=80.0, met=False, assessed_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerCommitment(**defaults)


def _phs(**kw):
    defaults = dict(
        snapshot_id="hs1", partner_id="p1", tenant_id="t1",
        health_status=PartnerHealthStatus.HEALTHY, health_score=0.95,
        sla_breaches=0, open_cases=1, billing_issues=0,
        commitment_failures=0, captured_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerHealthSnapshot(**defaults)


def _pd(**kw):
    defaults = dict(
        decision_id="d1", tenant_id="t1", partner_id="p1",
        disposition=PartnerDisposition.APPROVED, reason="all good",
        decided_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerDecision(**defaults)


def _pv(**kw):
    defaults = dict(
        violation_id="v1", tenant_id="t1", partner_id="p1",
        operation="billing_check", reason="Late payment",
        detected_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerViolation(**defaults)


def _ps(**kw):
    defaults = dict(
        snapshot_id="snap1", total_partners=10, total_links=20,
        total_agreements=5, total_revenue_shares=8, total_commitments=4,
        total_health_snapshots=3, total_decisions=2, total_violations=1,
        captured_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerSnapshot(**defaults)


def _pcr(**kw):
    defaults = dict(
        report_id="r1", tenant_id="t1", total_partners=10,
        total_links=20, total_agreements=5, total_revenue_shares=8,
        total_commitments=4, total_violations=1, closed_at=TS, metadata={},
    )
    defaults.update(kw)
    return PartnerClosureReport(**defaults)


# ===================================================================
# ENUM TESTS
# ===================================================================


class TestPartnerStatus:
    def test_members(self):
        assert set(PartnerStatus) == {
            PartnerStatus.ACTIVE, PartnerStatus.INACTIVE,
            PartnerStatus.SUSPENDED, PartnerStatus.TERMINATED,
            PartnerStatus.PROSPECT,
        }

    def test_count(self):
        assert len(PartnerStatus) == 5

    def test_values(self):
        assert PartnerStatus.ACTIVE.value == "active"
        assert PartnerStatus.INACTIVE.value == "inactive"
        assert PartnerStatus.SUSPENDED.value == "suspended"
        assert PartnerStatus.TERMINATED.value == "terminated"
        assert PartnerStatus.PROSPECT.value == "prospect"

    def test_lookup_by_value(self):
        assert PartnerStatus("active") is PartnerStatus.ACTIVE

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            PartnerStatus("unknown")


class TestPartnerKind:
    def test_members(self):
        assert len(PartnerKind) == 6

    def test_values(self):
        assert PartnerKind.RESELLER.value == "reseller"
        assert PartnerKind.DISTRIBUTOR.value == "distributor"
        assert PartnerKind.SERVICE_PARTNER.value == "service_partner"
        assert PartnerKind.TECHNOLOGY_PARTNER.value == "technology_partner"
        assert PartnerKind.REFERRAL.value == "referral"
        assert PartnerKind.MANAGED_SERVICE.value == "managed_service"

    def test_lookup_by_value(self):
        assert PartnerKind("distributor") is PartnerKind.DISTRIBUTOR

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            PartnerKind("unknown")


class TestEcosystemRole:
    def test_members(self):
        assert len(EcosystemRole) == 4

    def test_values(self):
        assert EcosystemRole.PROVIDER.value == "provider"
        assert EcosystemRole.CONSUMER.value == "consumer"
        assert EcosystemRole.INTERMEDIARY.value == "intermediary"
        assert EcosystemRole.INTEGRATOR.value == "integrator"

    def test_lookup(self):
        assert EcosystemRole("integrator") is EcosystemRole.INTEGRATOR

    def test_invalid(self):
        with pytest.raises(ValueError):
            EcosystemRole("nope")


class TestRevenueShareStatus:
    def test_members(self):
        assert len(RevenueShareStatus) == 5

    def test_values(self):
        assert RevenueShareStatus.PENDING.value == "pending"
        assert RevenueShareStatus.ACTIVE.value == "active"
        assert RevenueShareStatus.SETTLED.value == "settled"
        assert RevenueShareStatus.DISPUTED.value == "disputed"
        assert RevenueShareStatus.CANCELLED.value == "cancelled"

    def test_lookup(self):
        assert RevenueShareStatus("settled") is RevenueShareStatus.SETTLED

    def test_invalid(self):
        with pytest.raises(ValueError):
            RevenueShareStatus("nope")


class TestPartnerHealthStatus:
    def test_members(self):
        assert len(PartnerHealthStatus) == 4

    def test_values(self):
        assert PartnerHealthStatus.HEALTHY.value == "healthy"
        assert PartnerHealthStatus.AT_RISK.value == "at_risk"
        assert PartnerHealthStatus.DEGRADED.value == "degraded"
        assert PartnerHealthStatus.CRITICAL.value == "critical"

    def test_lookup(self):
        assert PartnerHealthStatus("at_risk") is PartnerHealthStatus.AT_RISK

    def test_invalid(self):
        with pytest.raises(ValueError):
            PartnerHealthStatus("x")


class TestPartnerDisposition:
    def test_members(self):
        assert len(PartnerDisposition) == 4

    def test_values(self):
        assert PartnerDisposition.APPROVED.value == "approved"
        assert PartnerDisposition.DENIED.value == "denied"
        assert PartnerDisposition.ESCALATED.value == "escalated"
        assert PartnerDisposition.DEFERRED.value == "deferred"

    def test_lookup(self):
        assert PartnerDisposition("denied") is PartnerDisposition.DENIED

    def test_invalid(self):
        with pytest.raises(ValueError):
            PartnerDisposition("x")


# ===================================================================
# PARTNER RECORD TESTS
# ===================================================================


class TestPartnerRecord:
    def test_valid_construction(self):
        r = _pr()
        assert r.partner_id == "p1"
        assert r.tenant_id == "t1"
        assert r.display_name == "Acme"
        assert r.kind is PartnerKind.RESELLER
        assert r.status is PartnerStatus.ACTIVE
        assert r.tier == "gold"
        assert r.account_link_count == 3

    def test_frozen(self):
        r = _pr()
        with pytest.raises(AttributeError):
            r.partner_id = "p2"

    def test_metadata_frozen(self):
        r = _pr(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["k"] == "v"
        with pytest.raises(TypeError):
            r.metadata["k2"] = "v2"

    def test_to_dict_preserves_enums(self):
        d = _pr().to_dict()
        assert d["kind"] is PartnerKind.RESELLER
        assert d["status"] is PartnerStatus.ACTIVE

    def test_to_dict_metadata_thawed(self):
        d = _pr(metadata={"a": 1}).to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["a"] == 1

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pr(partner_id="")

    def test_whitespace_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pr(partner_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pr(tenant_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError):
            _pr(display_name="")

    def test_negative_account_link_count_rejected(self):
        with pytest.raises(ValueError):
            _pr(account_link_count=-1)

    def test_bool_account_link_count_rejected(self):
        with pytest.raises(ValueError):
            _pr(account_link_count=True)

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            _pr(kind="reseller")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _pr(status="active")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _pr(created_at="not-a-date")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            _pr(created_at="")

    def test_simple_date_accepted(self):
        r = _pr(created_at=TS2)
        assert r.created_at == TS2

    @pytest.mark.parametrize("kind", list(PartnerKind))
    def test_all_kinds_accepted(self, kind):
        r = _pr(kind=kind)
        assert r.kind is kind

    @pytest.mark.parametrize("status", list(PartnerStatus))
    def test_all_statuses_accepted(self, status):
        r = _pr(status=status)
        assert r.status is status

    def test_zero_link_count(self):
        r = _pr(account_link_count=0)
        assert r.account_link_count == 0

    def test_large_link_count(self):
        r = _pr(account_link_count=999999)
        assert r.account_link_count == 999999

    def test_tier_can_be_empty(self):
        r = _pr(tier="")
        assert r.tier == ""

    def test_tier_can_be_nonempty(self):
        r = _pr(tier="platinum")
        assert r.tier == "platinum"

    def test_nested_metadata_frozen(self):
        r = _pr(metadata={"nested": {"a": 1}})
        assert isinstance(r.metadata["nested"], MappingProxyType)


# ===================================================================
# PARTNER ACCOUNT LINK TESTS
# ===================================================================


class TestPartnerAccountLink:
    def test_valid_construction(self):
        r = _pal()
        assert r.link_id == "l1"
        assert r.partner_id == "p1"
        assert r.account_id == "a1"
        assert r.tenant_id == "t1"
        assert r.role is EcosystemRole.INTERMEDIARY

    def test_frozen(self):
        r = _pal()
        with pytest.raises(AttributeError):
            r.link_id = "l2"

    def test_metadata_frozen(self):
        r = _pal(metadata={"x": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _pal().to_dict()
        assert d["role"] is EcosystemRole.INTERMEDIARY

    def test_empty_link_id_rejected(self):
        with pytest.raises(ValueError):
            _pal(link_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pal(partner_id="")

    def test_empty_account_id_rejected(self):
        with pytest.raises(ValueError):
            _pal(account_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pal(tenant_id="")

    def test_invalid_role_rejected(self):
        with pytest.raises(ValueError):
            _pal(role="intermediary")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _pal(created_at="bad")

    @pytest.mark.parametrize("role", list(EcosystemRole))
    def test_all_roles_accepted(self, role):
        r = _pal(role=role)
        assert r.role is role

    def test_whitespace_link_id_rejected(self):
        with pytest.raises(ValueError):
            _pal(link_id="   ")

    def test_simple_date_accepted(self):
        r = _pal(created_at=TS2)
        assert r.created_at == TS2


# ===================================================================
# ECOSYSTEM AGREEMENT TESTS
# ===================================================================


class TestEcosystemAgreement:
    def test_valid_construction(self):
        r = _ea()
        assert r.agreement_id == "ag1"
        assert r.partner_id == "p1"
        assert r.tenant_id == "t1"
        assert r.title == "Revenue Deal"
        assert r.contract_ref == "CR-100"
        assert r.revenue_share_pct == 0.3

    def test_frozen(self):
        r = _ea()
        with pytest.raises(AttributeError):
            r.title = "x"

    def test_metadata_frozen(self):
        r = _ea(metadata={"k": 2})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _ea().to_dict()
        assert "agreement_id" in d
        assert "revenue_share_pct" in d

    def test_empty_agreement_id_rejected(self):
        with pytest.raises(ValueError):
            _ea(agreement_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _ea(partner_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _ea(tenant_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            _ea(title="")

    def test_revenue_share_pct_zero(self):
        r = _ea(revenue_share_pct=0.0)
        assert r.revenue_share_pct == 0.0

    def test_revenue_share_pct_one(self):
        r = _ea(revenue_share_pct=1.0)
        assert r.revenue_share_pct == 1.0

    def test_revenue_share_pct_negative_rejected(self):
        with pytest.raises(ValueError):
            _ea(revenue_share_pct=-0.01)

    def test_revenue_share_pct_over_one_rejected(self):
        with pytest.raises(ValueError):
            _ea(revenue_share_pct=1.01)

    def test_revenue_share_pct_nan_rejected(self):
        with pytest.raises(ValueError):
            _ea(revenue_share_pct=float("nan"))

    def test_revenue_share_pct_inf_rejected(self):
        with pytest.raises(ValueError):
            _ea(revenue_share_pct=float("inf"))

    def test_revenue_share_pct_bool_rejected(self):
        with pytest.raises(ValueError):
            _ea(revenue_share_pct=True)

    def test_contract_ref_can_be_empty(self):
        r = _ea(contract_ref="")
        assert r.contract_ref == ""

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _ea(created_at="nope")

    def test_simple_date(self):
        r = _ea(created_at=TS2)
        assert r.created_at == TS2

    def test_integer_pct_accepted(self):
        r = _ea(revenue_share_pct=0)
        assert r.revenue_share_pct == 0.0

    def test_integer_one_pct_accepted(self):
        r = _ea(revenue_share_pct=1)
        assert r.revenue_share_pct == 1.0


# ===================================================================
# REVENUE SHARE RECORD TESTS
# ===================================================================


class TestRevenueShareRecord:
    def test_valid_construction(self):
        r = _rsr()
        assert r.share_id == "s1"
        assert r.gross_amount == 1000.0
        assert r.share_amount == 300.0
        assert r.share_pct == 0.3
        assert r.status is RevenueShareStatus.PENDING

    def test_frozen(self):
        r = _rsr()
        with pytest.raises(AttributeError):
            r.share_id = "s2"

    def test_metadata_frozen(self):
        r = _rsr(metadata={"x": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _rsr().to_dict()
        assert d["status"] is RevenueShareStatus.PENDING

    def test_empty_share_id_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _rsr(partner_id="")

    def test_empty_agreement_id_rejected(self):
        with pytest.raises(ValueError):
            _rsr(agreement_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _rsr(tenant_id="")

    def test_negative_gross_rejected(self):
        with pytest.raises(ValueError):
            _rsr(gross_amount=-1.0)

    def test_negative_share_amount_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_amount=-0.01)

    def test_share_pct_over_one_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_pct=1.1)

    def test_share_pct_negative_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_pct=-0.1)

    def test_share_pct_nan_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_pct=float("nan"))

    def test_gross_amount_inf_rejected(self):
        with pytest.raises(ValueError):
            _rsr(gross_amount=float("inf"))

    def test_share_amount_bool_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_amount=True)

    def test_gross_amount_bool_rejected(self):
        with pytest.raises(ValueError):
            _rsr(gross_amount=False)

    def test_share_pct_bool_rejected(self):
        with pytest.raises(ValueError):
            _rsr(share_pct=True)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _rsr(status="pending")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _rsr(created_at="bad")

    @pytest.mark.parametrize("status", list(RevenueShareStatus))
    def test_all_statuses_accepted(self, status):
        r = _rsr(status=status)
        assert r.status is status

    def test_zero_gross(self):
        r = _rsr(gross_amount=0.0)
        assert r.gross_amount == 0.0

    def test_zero_share(self):
        r = _rsr(share_amount=0.0)
        assert r.share_amount == 0.0

    def test_zero_pct(self):
        r = _rsr(share_pct=0.0)
        assert r.share_pct == 0.0

    def test_one_pct(self):
        r = _rsr(share_pct=1.0)
        assert r.share_pct == 1.0

    def test_integer_gross_accepted(self):
        r = _rsr(gross_amount=5000)
        assert r.gross_amount == 5000.0

    def test_simple_date(self):
        r = _rsr(created_at=TS2)
        assert r.created_at == TS2


# ===================================================================
# PARTNER COMMITMENT TESTS
# ===================================================================


class TestPartnerCommitment:
    def test_valid_construction(self):
        r = _pc()
        assert r.commitment_id == "c1"
        assert r.description == "Quarterly target"
        assert r.target_value == 100.0
        assert r.actual_value == 80.0
        assert r.met is False

    def test_met_true(self):
        r = _pc(met=True)
        assert r.met is True

    def test_frozen(self):
        r = _pc()
        with pytest.raises(AttributeError):
            r.met = True

    def test_metadata_frozen(self):
        r = _pc(metadata={"a": "b"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _pc().to_dict()
        assert "commitment_id" in d
        assert "met" in d
        assert "target_value" in d

    def test_empty_commitment_id_rejected(self):
        with pytest.raises(ValueError):
            _pc(commitment_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pc(partner_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pc(tenant_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            _pc(description="")

    def test_negative_target_rejected(self):
        with pytest.raises(ValueError):
            _pc(target_value=-1.0)

    def test_negative_actual_rejected(self):
        with pytest.raises(ValueError):
            _pc(actual_value=-0.5)

    def test_target_inf_rejected(self):
        with pytest.raises(ValueError):
            _pc(target_value=float("inf"))

    def test_actual_nan_rejected(self):
        with pytest.raises(ValueError):
            _pc(actual_value=float("nan"))

    def test_target_bool_rejected(self):
        with pytest.raises(ValueError):
            _pc(target_value=True)

    def test_actual_bool_rejected(self):
        with pytest.raises(ValueError):
            _pc(actual_value=False)

    def test_zero_values(self):
        r = _pc(target_value=0.0, actual_value=0.0)
        assert r.target_value == 0.0
        assert r.actual_value == 0.0

    def test_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _pc(assessed_at="bad")

    def test_simple_date(self):
        r = _pc(assessed_at=TS2)
        assert r.assessed_at == TS2

    def test_integer_target(self):
        r = _pc(target_value=500)
        assert r.target_value == 500.0


# ===================================================================
# PARTNER HEALTH SNAPSHOT TESTS
# ===================================================================


class TestPartnerHealthSnapshot:
    def test_valid_construction(self):
        r = _phs()
        assert r.snapshot_id == "hs1"
        assert r.health_status is PartnerHealthStatus.HEALTHY
        assert r.health_score == 0.95
        assert r.sla_breaches == 0
        assert r.open_cases == 1
        assert r.billing_issues == 0
        assert r.commitment_failures == 0

    def test_frozen(self):
        r = _phs()
        with pytest.raises(AttributeError):
            r.health_score = 0.5

    def test_metadata_frozen(self):
        r = _phs(metadata={"z": 9})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _phs().to_dict()
        assert d["health_status"] is PartnerHealthStatus.HEALTHY

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _phs(snapshot_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _phs(partner_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _phs(tenant_id="")

    def test_invalid_health_status_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_status="healthy")

    def test_health_score_zero(self):
        r = _phs(health_score=0.0)
        assert r.health_score == 0.0

    def test_health_score_one(self):
        r = _phs(health_score=1.0)
        assert r.health_score == 1.0

    def test_health_score_negative_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_score=-0.1)

    def test_health_score_over_one_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_score=1.01)

    def test_health_score_nan_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_score=float("nan"))

    def test_health_score_inf_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_score=float("inf"))

    def test_health_score_bool_rejected(self):
        with pytest.raises(ValueError):
            _phs(health_score=True)

    def test_negative_sla_breaches_rejected(self):
        with pytest.raises(ValueError):
            _phs(sla_breaches=-1)

    def test_negative_open_cases_rejected(self):
        with pytest.raises(ValueError):
            _phs(open_cases=-1)

    def test_negative_billing_issues_rejected(self):
        with pytest.raises(ValueError):
            _phs(billing_issues=-1)

    def test_negative_commitment_failures_rejected(self):
        with pytest.raises(ValueError):
            _phs(commitment_failures=-1)

    def test_bool_sla_breaches_rejected(self):
        with pytest.raises(ValueError):
            _phs(sla_breaches=True)

    def test_bool_open_cases_rejected(self):
        with pytest.raises(ValueError):
            _phs(open_cases=True)

    def test_bool_billing_issues_rejected(self):
        with pytest.raises(ValueError):
            _phs(billing_issues=False)

    def test_bool_commitment_failures_rejected(self):
        with pytest.raises(ValueError):
            _phs(commitment_failures=True)

    @pytest.mark.parametrize("hs", list(PartnerHealthStatus))
    def test_all_health_statuses_accepted(self, hs):
        r = _phs(health_status=hs)
        assert r.health_status is hs

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _phs(captured_at="bad")

    def test_simple_date(self):
        r = _phs(captured_at=TS2)
        assert r.captured_at == TS2

    def test_large_int_values(self):
        r = _phs(sla_breaches=999, open_cases=888, billing_issues=777, commitment_failures=666)
        assert r.sla_breaches == 999
        assert r.open_cases == 888
        assert r.billing_issues == 777
        assert r.commitment_failures == 666


# ===================================================================
# PARTNER DECISION TESTS
# ===================================================================


class TestPartnerDecision:
    def test_valid_construction(self):
        r = _pd()
        assert r.decision_id == "d1"
        assert r.tenant_id == "t1"
        assert r.partner_id == "p1"
        assert r.disposition is PartnerDisposition.APPROVED
        assert r.reason == "all good"

    def test_frozen(self):
        r = _pd()
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_metadata_frozen(self):
        r = _pd(metadata={"q": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _pd().to_dict()
        assert d["disposition"] is PartnerDisposition.APPROVED

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            _pd(decision_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pd(tenant_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pd(partner_id="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _pd(disposition="approved")

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _pd(decided_at="bad")

    def test_reason_can_be_empty(self):
        r = _pd(reason="")
        assert r.reason == ""

    @pytest.mark.parametrize("disp", list(PartnerDisposition))
    def test_all_dispositions_accepted(self, disp):
        r = _pd(disposition=disp)
        assert r.disposition is disp

    def test_simple_date(self):
        r = _pd(decided_at=TS2)
        assert r.decided_at == TS2


# ===================================================================
# PARTNER VIOLATION TESTS
# ===================================================================


class TestPartnerViolation:
    def test_valid_construction(self):
        r = _pv()
        assert r.violation_id == "v1"
        assert r.tenant_id == "t1"
        assert r.partner_id == "p1"
        assert r.operation == "billing_check"
        assert r.reason == "Late payment"

    def test_frozen(self):
        r = _pv()
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_metadata_frozen(self):
        r = _pv(metadata={"m": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _pv().to_dict()
        assert "violation_id" in d
        assert "operation" in d
        assert "reason" in d

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _pv(violation_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pv(tenant_id="")

    def test_empty_partner_id_rejected(self):
        with pytest.raises(ValueError):
            _pv(partner_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            _pv(operation="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            _pv(reason="")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            _pv(operation="   ")

    def test_whitespace_reason_rejected(self):
        with pytest.raises(ValueError):
            _pv(reason="   ")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _pv(detected_at="bad")

    def test_simple_date(self):
        r = _pv(detected_at=TS2)
        assert r.detected_at == TS2


# ===================================================================
# PARTNER SNAPSHOT TESTS
# ===================================================================


class TestPartnerSnapshot:
    def test_valid_construction(self):
        r = _ps()
        assert r.snapshot_id == "snap1"
        assert r.total_partners == 10
        assert r.total_links == 20
        assert r.total_agreements == 5
        assert r.total_revenue_shares == 8
        assert r.total_commitments == 4
        assert r.total_health_snapshots == 3
        assert r.total_decisions == 2
        assert r.total_violations == 1

    def test_frozen(self):
        r = _ps()
        with pytest.raises(AttributeError):
            r.total_partners = 99

    def test_metadata_frozen(self):
        r = _ps(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _ps().to_dict()
        for key in [
            "snapshot_id", "total_partners", "total_links", "total_agreements",
            "total_revenue_shares", "total_commitments", "total_health_snapshots",
            "total_decisions", "total_violations", "captured_at", "metadata",
        ]:
            assert key in d

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _ps(snapshot_id="")

    def test_negative_total_partners_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_partners=-1)

    def test_negative_total_links_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_links=-1)

    def test_negative_total_agreements_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_agreements=-1)

    def test_negative_total_revenue_shares_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_revenue_shares=-1)

    def test_negative_total_commitments_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_commitments=-1)

    def test_negative_total_health_snapshots_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_health_snapshots=-1)

    def test_negative_total_decisions_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_decisions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_violations=-1)

    def test_bool_total_partners_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_partners=True)

    def test_bool_total_links_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_links=False)

    def test_bool_total_agreements_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_agreements=True)

    def test_bool_total_revenue_shares_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_revenue_shares=True)

    def test_bool_total_commitments_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_commitments=True)

    def test_bool_total_health_snapshots_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_health_snapshots=True)

    def test_bool_total_decisions_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_decisions=True)

    def test_bool_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _ps(total_violations=True)

    def test_all_zeros(self):
        r = _ps(
            total_partners=0, total_links=0, total_agreements=0,
            total_revenue_shares=0, total_commitments=0,
            total_health_snapshots=0, total_decisions=0, total_violations=0,
        )
        assert r.total_partners == 0

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _ps(captured_at="bad")

    def test_simple_date(self):
        r = _ps(captured_at=TS2)
        assert r.captured_at == TS2


# ===================================================================
# PARTNER CLOSURE REPORT TESTS
# ===================================================================


class TestPartnerClosureReport:
    def test_valid_construction(self):
        r = _pcr()
        assert r.report_id == "r1"
        assert r.tenant_id == "t1"
        assert r.total_partners == 10
        assert r.total_links == 20
        assert r.total_agreements == 5
        assert r.total_revenue_shares == 8
        assert r.total_commitments == 4
        assert r.total_violations == 1

    def test_frozen(self):
        r = _pcr()
        with pytest.raises(AttributeError):
            r.report_id = "r2"

    def test_metadata_frozen(self):
        r = _pcr(metadata={"b": 2})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = _pcr().to_dict()
        for key in [
            "report_id", "tenant_id", "total_partners", "total_links",
            "total_agreements", "total_revenue_shares", "total_commitments",
            "total_violations", "closed_at", "metadata",
        ]:
            assert key in d

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            _pcr(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _pcr(tenant_id="")

    def test_negative_total_partners_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_partners=-1)

    def test_negative_total_links_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_links=-1)

    def test_negative_total_agreements_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_agreements=-1)

    def test_negative_total_revenue_shares_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_revenue_shares=-1)

    def test_negative_total_commitments_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_commitments=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_violations=-1)

    def test_bool_total_partners_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_partners=True)

    def test_bool_total_links_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_links=False)

    def test_bool_total_agreements_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_agreements=True)

    def test_bool_total_revenue_shares_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_revenue_shares=True)

    def test_bool_total_commitments_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_commitments=True)

    def test_bool_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _pcr(total_violations=True)

    def test_all_zeros(self):
        r = _pcr(
            total_partners=0, total_links=0, total_agreements=0,
            total_revenue_shares=0, total_commitments=0, total_violations=0,
        )
        assert r.total_partners == 0

    def test_invalid_closed_at(self):
        with pytest.raises(ValueError):
            _pcr(closed_at="bad")

    def test_simple_date(self):
        r = _pcr(closed_at=TS2)
        assert r.closed_at == TS2

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            _pcr(report_id="   ")

    def test_large_counts(self):
        r = _pcr(total_partners=999999, total_links=888888)
        assert r.total_partners == 999999
        assert r.total_links == 888888


# ===================================================================
# CROSS-CUTTING / INTEGRATION TESTS
# ===================================================================


class TestCrossCutting:
    """Tests that apply across multiple dataclasses."""

    def test_partner_record_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pr(), ContractRecord)

    def test_partner_account_link_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pal(), ContractRecord)

    def test_ecosystem_agreement_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_ea(), ContractRecord)

    def test_revenue_share_record_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_rsr(), ContractRecord)

    def test_partner_commitment_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pc(), ContractRecord)

    def test_partner_health_snapshot_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_phs(), ContractRecord)

    def test_partner_decision_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pd(), ContractRecord)

    def test_partner_violation_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pv(), ContractRecord)

    def test_partner_snapshot_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_ps(), ContractRecord)

    def test_partner_closure_report_is_contract_record(self):
        from mcoi_runtime.contracts._base import ContractRecord
        assert isinstance(_pcr(), ContractRecord)

    def test_all_have_to_dict(self):
        for factory in [_pr, _pal, _ea, _rsr, _pc, _phs, _pd, _pv, _ps, _pcr]:
            obj = factory()
            d = obj.to_dict()
            assert isinstance(d, dict)

    def test_all_to_dict_metadata_is_dict(self):
        for factory in [_pr, _pal, _ea, _rsr, _pc, _phs, _pd, _pv, _ps, _pcr]:
            d = factory(metadata={"k": "v"}).to_dict()
            assert isinstance(d["metadata"], dict)

    def test_all_metadata_is_mapping_proxy(self):
        for factory in [_pr, _pal, _ea, _rsr, _pc, _phs, _pd, _pv, _ps, _pcr]:
            obj = factory(metadata={"k": "v"})
            assert isinstance(obj.metadata, MappingProxyType)

    def test_all_frozen(self):
        pairs = [
            (_pr(), "partner_id"),
            (_pal(), "link_id"),
            (_ea(), "agreement_id"),
            (_rsr(), "share_id"),
            (_pc(), "commitment_id"),
            (_phs(), "snapshot_id"),
            (_pd(), "decision_id"),
            (_pv(), "violation_id"),
            (_ps(), "snapshot_id"),
            (_pcr(), "report_id"),
        ]
        for obj, attr in pairs:
            with pytest.raises(AttributeError):
                setattr(obj, attr, "changed")

    def test_nested_metadata_thawed_in_to_dict(self):
        r = _pr(metadata={"nested": {"inner": 1}})
        d = r.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)

    def test_empty_metadata_ok(self):
        for factory in [_pr, _pal, _ea, _rsr, _pc, _phs, _pd, _pv, _ps, _pcr]:
            obj = factory(metadata={})
            assert obj.metadata == MappingProxyType({})

    def test_z_suffix_datetime_accepted(self):
        ts_z = "2025-06-01T12:00:00Z"
        r = _pr(created_at=ts_z)
        assert r.created_at == ts_z

    def test_offset_datetime_accepted(self):
        ts_off = "2025-06-01T12:00:00+05:30"
        r = _pr(created_at=ts_off)
        assert r.created_at == ts_off

    def test_list_in_metadata_becomes_tuple(self):
        r = _pr(metadata={"items": [1, 2, 3]})
        assert r.metadata["items"] == (1, 2, 3)

    def test_list_in_metadata_thawed_to_list(self):
        d = _pr(metadata={"items": [1, 2, 3]}).to_dict()
        assert d["metadata"]["items"] == [1, 2, 3]

    def test_set_in_metadata_becomes_frozenset(self):
        r = _pr(metadata={"tags": {"a", "b"}})
        assert isinstance(r.metadata["tags"], frozenset)

    def test_deeply_nested_metadata_frozen(self):
        r = _ea(metadata={"l1": {"l2": {"l3": "deep"}}})
        assert isinstance(r.metadata["l1"], MappingProxyType)
        assert isinstance(r.metadata["l1"]["l2"], MappingProxyType)
        assert r.metadata["l1"]["l2"]["l3"] == "deep"

    def test_to_dict_field_count_partner_record(self):
        d = _pr().to_dict()
        assert len(d) == 9

    def test_to_dict_field_count_partner_account_link(self):
        d = _pal().to_dict()
        assert len(d) == 7

    def test_to_dict_field_count_ecosystem_agreement(self):
        d = _ea().to_dict()
        assert len(d) == 8

    def test_to_dict_field_count_revenue_share_record(self):
        d = _rsr().to_dict()
        assert len(d) == 10

    def test_to_dict_field_count_partner_commitment(self):
        d = _pc().to_dict()
        assert len(d) == 9

    def test_to_dict_field_count_partner_health_snapshot(self):
        d = _phs().to_dict()
        assert len(d) == 11

    def test_to_dict_field_count_partner_decision(self):
        d = _pd().to_dict()
        assert len(d) == 7

    def test_to_dict_field_count_partner_violation(self):
        d = _pv().to_dict()
        assert len(d) == 7

    def test_to_dict_field_count_partner_snapshot(self):
        d = _ps().to_dict()
        assert len(d) == 11

    def test_to_dict_field_count_partner_closure_report(self):
        d = _pcr().to_dict()
        assert len(d) == 10

    def test_partner_record_equality(self):
        a = _pr()
        b = _pr()
        assert a == b

    def test_partner_record_inequality(self):
        a = _pr(partner_id="p1")
        b = _pr(partner_id="p2")
        assert a != b

    def test_partner_account_link_equality(self):
        a = _pal()
        b = _pal()
        assert a == b

    def test_ecosystem_agreement_equality(self):
        a = _ea()
        b = _ea()
        assert a == b

    def test_revenue_share_record_equality(self):
        a = _rsr()
        b = _rsr()
        assert a == b

    def test_partner_commitment_equality(self):
        a = _pc()
        b = _pc()
        assert a == b

    def test_partner_health_snapshot_equality(self):
        a = _phs()
        b = _phs()
        assert a == b

    def test_partner_decision_equality(self):
        a = _pd()
        b = _pd()
        assert a == b

    def test_partner_violation_equality(self):
        a = _pv()
        b = _pv()
        assert a == b

    def test_partner_snapshot_equality(self):
        a = _ps()
        b = _ps()
        assert a == b

    def test_partner_closure_report_equality(self):
        a = _pcr()
        b = _pcr()
        assert a == b

    def test_metadata_mutation_after_creation_no_effect(self):
        original = {"k": "v"}
        r = _pr(metadata=original)
        original["k2"] = "v2"
        assert "k2" not in r.metadata

    def test_non_int_partner_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _pr(partner_id=123)

    def test_non_str_tenant_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _pr(tenant_id=42)

    def test_partner_record_to_dict_roundtrip_values(self):
        r = _pr(tier="silver", account_link_count=7)
        d = r.to_dict()
        assert d["tier"] == "silver"
        assert d["account_link_count"] == 7

    def test_revenue_share_zero_amounts_to_dict(self):
        r = _rsr(gross_amount=0.0, share_amount=0.0, share_pct=0.0)
        d = r.to_dict()
        assert d["gross_amount"] == 0.0
        assert d["share_amount"] == 0.0
        assert d["share_pct"] == 0.0

    def test_commitment_met_true_in_to_dict(self):
        d = _pc(met=True).to_dict()
        assert d["met"] is True

    def test_commitment_met_false_in_to_dict(self):
        d = _pc(met=False).to_dict()
        assert d["met"] is False

    def test_partner_health_all_int_fields_in_to_dict(self):
        d = _phs(sla_breaches=5, open_cases=3, billing_issues=2, commitment_failures=1).to_dict()
        assert d["sla_breaches"] == 5
        assert d["open_cases"] == 3
        assert d["billing_issues"] == 2
        assert d["commitment_failures"] == 1

    def test_partner_decision_reason_in_to_dict(self):
        d = _pd(reason="detailed reason").to_dict()
        assert d["reason"] == "detailed reason"

    def test_partner_violation_fields_in_to_dict(self):
        d = _pv(operation="op1", reason="r1").to_dict()
        assert d["operation"] == "op1"
        assert d["reason"] == "r1"

    def test_partner_snapshot_all_zeros_to_dict(self):
        r = _ps(
            total_partners=0, total_links=0, total_agreements=0,
            total_revenue_shares=0, total_commitments=0,
            total_health_snapshots=0, total_decisions=0, total_violations=0,
        )
        d = r.to_dict()
        for key in [
            "total_partners", "total_links", "total_agreements",
            "total_revenue_shares", "total_commitments",
            "total_health_snapshots", "total_decisions", "total_violations",
        ]:
            assert d[key] == 0

    def test_closure_report_all_zeros_to_dict(self):
        r = _pcr(
            total_partners=0, total_links=0, total_agreements=0,
            total_revenue_shares=0, total_commitments=0, total_violations=0,
        )
        d = r.to_dict()
        for key in [
            "total_partners", "total_links", "total_agreements",
            "total_revenue_shares", "total_commitments", "total_violations",
        ]:
            assert d[key] == 0

    def test_partner_record_different_kind_to_dict(self):
        d = _pr(kind=PartnerKind.MANAGED_SERVICE).to_dict()
        assert d["kind"] is PartnerKind.MANAGED_SERVICE

    def test_partner_record_different_status_to_dict(self):
        d = _pr(status=PartnerStatus.TERMINATED).to_dict()
        assert d["status"] is PartnerStatus.TERMINATED
