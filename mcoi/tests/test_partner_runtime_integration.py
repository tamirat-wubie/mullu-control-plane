"""Tests for PartnerRuntimeIntegration bridge.

Covers constructor validation, partner_from_contract, partner_from_customer_account,
partner_from_procurement_vendor, health methods (sla_breach, settlement, case),
memory mesh attachment, graph attachment, event emission, and invariant enforcement.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.partner_runtime import PartnerRuntimeEngine
from mcoi_runtime.core.partner_runtime_integration import PartnerRuntimeIntegration
from mcoi_runtime.contracts.partner_runtime import PartnerKind, EcosystemRole
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# -----------------------------------------------------------------------
# Fixtures and helpers
# -----------------------------------------------------------------------


@pytest.fixture
def env():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    pe = PartnerRuntimeEngine(es)
    integ = PartnerRuntimeIntegration(pe, es, mm)
    return es, mm, pe, integ


def _make_partner(integ: PartnerRuntimeIntegration, suffix: str = "1") -> dict:
    """Helper: create a partner via contract with sensible defaults."""
    return integ.partner_from_contract(
        partner_id=f"p-{suffix}",
        tenant_id=f"t-{suffix}",
        display_name=f"Partner {suffix}",
        contract_ref=f"ctr-{suffix}",
    )


# -----------------------------------------------------------------------
# 1. Constructor validation (3 tests)
# -----------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor rejects invalid dependency types."""

    def test_invalid_partner_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="partner_engine"):
            PartnerRuntimeIntegration("bad", es, mm)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        pe = PartnerRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            PartnerRuntimeIntegration(pe, "bad", mm)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        pe = PartnerRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            PartnerRuntimeIntegration(pe, es, "bad")


# -----------------------------------------------------------------------
# 2. partner_from_contract (12 tests)
# -----------------------------------------------------------------------


class TestPartnerFromContract:
    """Tests for creating a partner from a contract."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert result["partner_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["contract_ref"] == "ctr-001"
        assert result["source_type"] == "contract"

    def test_default_kind_reseller(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert result["kind"] == "reseller"

    def test_custom_kind(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001", kind=PartnerKind.DISTRIBUTOR,
        )
        assert result["kind"] == "distributor"

    def test_default_revenue_share(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert result["revenue_share_pct"] == 0.0

    def test_custom_revenue_share(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001", revenue_share_pct=0.15,
        )
        assert result["revenue_share_pct"] == 0.15

    def test_agreement_id_present(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert "agreement_id" in result
        assert isinstance(result["agreement_id"], str)
        assert len(result["agreement_id"]) > 0

    def test_agreement_id_deterministic(self, env):
        """Same inputs produce the same agreement_id."""
        _, _, _, integ = env
        r1 = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        # Build a second bridge with fresh engines to re-derive
        es2 = EventSpineEngine()
        pe2 = PartnerRuntimeEngine(es2)
        mm2 = MemoryMeshEngine()
        integ2 = PartnerRuntimeIntegration(pe2, es2, mm2)
        r2 = integ2.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        assert r1["agreement_id"] == r2["agreement_id"]

    def test_emits_event(self, env):
        es, _, _, integ = env
        before = es.event_count
        integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        # At least the integration event, plus engine events
        assert es.event_count > before

    def test_duplicate_partner_raises(self, env):
        _, _, _, integ = env
        integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            integ.partner_from_contract(
                partner_id="p1", tenant_id="t1", display_name="Acme2",
                contract_ref="ctr-002",
            )

    def test_all_partner_kinds(self, env):
        _, _, _, integ = env
        for i, kind in enumerate(PartnerKind):
            result = integ.partner_from_contract(
                partner_id=f"pk-{i}", tenant_id="t1", display_name=f"P{i}",
                contract_ref=f"ctr-{i}", kind=kind,
            )
            assert result["kind"] == kind.value

    def test_custom_tier(self, env):
        _, _, _, integ = env
        result = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001", tier="premium",
        )
        # tier is not in the return dict, but the partner is registered
        assert result["partner_id"] == "p1"


# -----------------------------------------------------------------------
# 3. partner_from_customer_account (10 tests)
# -----------------------------------------------------------------------


class TestPartnerFromCustomerAccount:
    """Tests for linking a partner via a customer account."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        assert result["link_id"] == "lnk-1"
        assert result["partner_id"] == "p-1"
        assert result["account_id"] == "acc-1"
        assert result["tenant_id"] == "t-1"
        assert result["source_type"] == "customer_account"

    def test_default_role_intermediary(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        assert result["role"] == "intermediary"

    def test_custom_role_provider(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1", role=EcosystemRole.PROVIDER,
        )
        assert result["role"] == "provider"

    def test_custom_role_consumer(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1", role=EcosystemRole.CONSUMER,
        )
        assert result["role"] == "consumer"

    def test_custom_role_integrator(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1", role=EcosystemRole.INTEGRATOR,
        )
        assert result["role"] == "integrator"

    def test_requires_existing_partner(self, env):
        _, _, _, integ = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            integ.partner_from_customer_account(
                link_id="lnk-1", partner_id="no-such", account_id="acc-1",
                tenant_id="t-1",
            )

    def test_duplicate_link_raises(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="link already exists"):
            integ.partner_from_customer_account(
                link_id="lnk-1", partner_id="p-1", account_id="acc-2",
                tenant_id="t-1",
            )

    def test_emits_event(self, env):
        es, _, _, integ = env
        _make_partner(integ, "1")
        before = es.event_count
        integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        assert es.event_count > before

    def test_multiple_links_same_partner(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        r1 = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        r2 = integ.partner_from_customer_account(
            link_id="lnk-2", partner_id="p-1", account_id="acc-2",
            tenant_id="t-1",
        )
        assert r1["link_id"] != r2["link_id"]
        assert r1["partner_id"] == r2["partner_id"]


# -----------------------------------------------------------------------
# 4. partner_from_procurement_vendor (9 tests)
# -----------------------------------------------------------------------


class TestPartnerFromProcurementVendor:
    """Tests for creating a partner from a procurement vendor."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        assert result["partner_id"] == "pv-1"
        assert result["tenant_id"] == "t1"
        assert result["vendor_ref"] == "vref-001"
        assert result["source_type"] == "procurement_vendor"

    def test_default_kind_distributor(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        assert result["kind"] == "distributor"

    def test_custom_kind(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001", kind=PartnerKind.SERVICE_PARTNER,
        )
        assert result["kind"] == "service_partner"

    def test_emits_event(self, env):
        es, _, _, integ = env
        before = es.event_count
        integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        assert es.event_count > before

    def test_duplicate_raises(self, env):
        _, _, _, integ = env
        integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            integ.partner_from_procurement_vendor(
                partner_id="pv-1", tenant_id="t1", display_name="Vendor2",
                vendor_ref="vref-002",
            )

    def test_custom_tier(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001", tier="gold",
        )
        assert result["partner_id"] == "pv-1"

    def test_no_agreement_id_key(self, env):
        _, _, _, integ = env
        result = integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="Vendor1",
            vendor_ref="vref-001",
        )
        assert "agreement_id" not in result

    def test_all_kinds(self, env):
        _, _, _, integ = env
        for i, kind in enumerate(PartnerKind):
            result = integ.partner_from_procurement_vendor(
                partner_id=f"pv-{i}", tenant_id="t1", display_name=f"V{i}",
                vendor_ref=f"vref-{i}", kind=kind,
            )
            assert result["kind"] == kind.value


# -----------------------------------------------------------------------
# 5. partner_health_from_sla_breach (8 tests)
# -----------------------------------------------------------------------


class TestPartnerHealthFromSlaBreach:
    """Tests for health snapshots from SLA breaches."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["snapshot_id"] == "snap-1"
        assert result["partner_id"] == "p-1"
        assert result["tenant_id"] == "t-1"
        assert result["source_type"] == "sla_breach"
        assert "health_score" in result
        assert "health_status" in result
        assert "sla_breaches" in result

    def test_default_breach_count_one(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["sla_breaches"] == 1

    def test_custom_breach_count(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
            breach_count=3,
        )
        assert result["sla_breaches"] == 3

    def test_health_score_decreases_with_breaches(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        r1 = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
            breach_count=1,
        )
        _make_partner(integ, "2")
        r2 = integ.partner_health_from_sla_breach(
            snapshot_id="snap-2", partner_id="p-2", tenant_id="t-2",
            breach_count=5,
        )
        assert r2["health_score"] < r1["health_score"]

    def test_requires_existing_partner(self, env):
        _, _, _, integ = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            integ.partner_health_from_sla_breach(
                snapshot_id="snap-1", partner_id="no-such", tenant_id="t-1",
            )

    def test_duplicate_snapshot_raises(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            integ.partner_health_from_sla_breach(
                snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
            )

    def test_emits_event(self, env):
        es, _, _, integ = env
        _make_partner(integ, "1")
        before = es.event_count
        integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p-1", tenant_id="t-1",
        )
        assert es.event_count > before


# -----------------------------------------------------------------------
# 6. partner_health_from_settlement (8 tests)
# -----------------------------------------------------------------------


class TestPartnerHealthFromSettlement:
    """Tests for health snapshots from billing settlements."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["snapshot_id"] == "snap-s1"
        assert result["partner_id"] == "p-1"
        assert result["tenant_id"] == "t-1"
        assert result["source_type"] == "settlement"
        assert "health_score" in result
        assert "health_status" in result
        assert "billing_issues" in result

    def test_default_billing_issues_one(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["billing_issues"] == 1

    def test_custom_billing_issues(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
            billing_issues=4,
        )
        assert result["billing_issues"] == 4

    def test_health_score_decreases(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        r1 = integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
            billing_issues=1,
        )
        _make_partner(integ, "2")
        r2 = integ.partner_health_from_settlement(
            snapshot_id="snap-s2", partner_id="p-2", tenant_id="t-2",
            billing_issues=4,
        )
        assert r2["health_score"] < r1["health_score"]

    def test_requires_existing_partner(self, env):
        _, _, _, integ = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            integ.partner_health_from_settlement(
                snapshot_id="snap-s1", partner_id="no-such", tenant_id="t-1",
            )

    def test_duplicate_snapshot_raises(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            integ.partner_health_from_settlement(
                snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
            )

    def test_emits_event(self, env):
        es, _, _, integ = env
        _make_partner(integ, "1")
        before = es.event_count
        integ.partner_health_from_settlement(
            snapshot_id="snap-s1", partner_id="p-1", tenant_id="t-1",
        )
        assert es.event_count > before


# -----------------------------------------------------------------------
# 7. partner_health_from_case (8 tests)
# -----------------------------------------------------------------------


class TestPartnerHealthFromCase:
    """Tests for health snapshots from open cases."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
        )
        assert isinstance(result, dict)

    def test_required_keys(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["snapshot_id"] == "snap-c1"
        assert result["partner_id"] == "p-1"
        assert result["tenant_id"] == "t-1"
        assert result["source_type"] == "case"
        assert "health_score" in result
        assert "health_status" in result
        assert "open_cases" in result

    def test_default_open_cases_one(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
        )
        assert result["open_cases"] == 1

    def test_custom_open_cases(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        result = integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
            open_cases=7,
        )
        assert result["open_cases"] == 7

    def test_health_score_decreases(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        r1 = integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
            open_cases=1,
        )
        _make_partner(integ, "2")
        r2 = integ.partner_health_from_case(
            snapshot_id="snap-c2", partner_id="p-2", tenant_id="t-2",
            open_cases=8,
        )
        assert r2["health_score"] < r1["health_score"]

    def test_requires_existing_partner(self, env):
        _, _, _, integ = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            integ.partner_health_from_case(
                snapshot_id="snap-c1", partner_id="no-such", tenant_id="t-1",
            )

    def test_duplicate_snapshot_raises(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            integ.partner_health_from_case(
                snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
            )

    def test_emits_event(self, env):
        es, _, _, integ = env
        _make_partner(integ, "1")
        before = es.event_count
        integ.partner_health_from_case(
            snapshot_id="snap-c1", partner_id="p-1", tenant_id="t-1",
        )
        assert es.event_count > before


# -----------------------------------------------------------------------
# 8. Health status derivation (5 tests)
# -----------------------------------------------------------------------


class TestHealthStatusDerivation:
    """Verify health_status tracks the score thresholds."""

    def test_healthy_on_zero_breaches(self, env):
        _, _, pe, integ = env
        _make_partner(integ, "1")
        # 0 breaches => score 1.0 => healthy
        result = pe.partner_health(
            snapshot_id="h-1", partner_id="p-1", tenant_id="t-1",
            sla_breaches=0,
        )
        assert result.health_status.value == "healthy"

    def test_at_risk_threshold(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        # 1 sla breach => score 0.85 => healthy (>= 0.8)
        r = integ.partner_health_from_sla_breach(
            snapshot_id="h-1", partner_id="p-1", tenant_id="t-1",
            breach_count=1,
        )
        assert r["health_status"] == "healthy"

    def test_at_risk_with_two_breaches(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        # 2 sla breaches => score 0.70 => at_risk
        r = integ.partner_health_from_sla_breach(
            snapshot_id="h-1", partner_id="p-1", tenant_id="t-1",
            breach_count=2,
        )
        assert r["health_status"] == "at_risk"

    def test_degraded_threshold(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        # 4 billing issues => score 1.0 - 4*0.2 = 0.2 => critical
        # 2 billing issues => score 1.0 - 2*0.2 = 0.6 => at_risk
        # 3 sla breaches => score 1.0 - 3*0.15 = 0.55 => at_risk
        # 4 sla breaches => score 1.0 - 4*0.15 = 0.40 => degraded
        r = integ.partner_health_from_sla_breach(
            snapshot_id="h-1", partner_id="p-1", tenant_id="t-1",
            breach_count=4,
        )
        assert r["health_status"] == "degraded"

    def test_critical_threshold(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        # 5 billing issues => score 0.0 => critical
        r = integ.partner_health_from_settlement(
            snapshot_id="h-1", partner_id="p-1", tenant_id="t-1",
            billing_issues=5,
        )
        assert r["health_status"] == "critical"


# -----------------------------------------------------------------------
# 9. attach_partner_state_to_memory_mesh (7 tests)
# -----------------------------------------------------------------------


class TestAttachPartnerStateToMemoryMesh:
    """Tests for memory mesh attachment."""

    def test_returns_memory_record(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_title(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_memory_mesh("scope-1")
        assert result.title == "Partner runtime state"

    def test_tags(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_memory_mesh("scope-1")
        assert "partner" in result.tags
        assert "ecosystem" in result.tags
        assert "marketplace" in result.tags

    def test_content_keys_empty_state(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_memory_mesh("scope-1")
        content = result.content
        for key in ("partners", "links", "agreements", "revenue_shares",
                     "commitments", "health_snapshots", "decisions", "violations"):
            assert key in content
            assert content[key] == 0

    def test_content_reflects_partner_count(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        _make_partner(integ, "2")
        result = integ.attach_partner_state_to_memory_mesh("scope-1")
        assert result.content["partners"] == 2
        assert result.content["agreements"] == 2

    def test_emits_event(self, env):
        es, _, _, integ = env
        before = es.event_count
        integ.attach_partner_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_memory_stored_in_engine(self, env):
        _, mm, _, integ = env
        record = integ.attach_partner_state_to_memory_mesh("scope-1")
        fetched = mm.get_memory(record.memory_id)
        assert fetched.memory_id == record.memory_id


# -----------------------------------------------------------------------
# 10. attach_partner_state_to_graph (5 tests)
# -----------------------------------------------------------------------


class TestAttachPartnerStateToGraph:
    """Tests for graph attachment."""

    def test_returns_dict(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_scope_ref_id(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_content_keys(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_graph("scope-1")
        for key in ("partners", "links", "agreements", "revenue_shares",
                     "commitments", "health_snapshots", "decisions", "violations"):
            assert key in result

    def test_empty_counts(self, env):
        _, _, _, integ = env
        result = integ.attach_partner_state_to_graph("scope-1")
        for key in ("partners", "links", "agreements", "revenue_shares",
                     "commitments", "health_snapshots", "decisions", "violations"):
            assert result[key] == 0

    def test_reflects_state(self, env):
        _, _, _, integ = env
        _make_partner(integ, "1")
        integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        result = integ.attach_partner_state_to_graph("scope-1")
        assert result["partners"] == 1
        assert result["links"] == 1
        assert result["agreements"] == 1


# -----------------------------------------------------------------------
# 11. Cross-method integration / golden path (5 tests)
# -----------------------------------------------------------------------


class TestGoldenPath:
    """End-to-end integration tests across multiple methods."""

    def test_full_lifecycle(self, env):
        """Contract -> link -> health -> memory -> graph."""
        _, _, _, integ = env
        contract = integ.partner_from_contract(
            partner_id="p1", tenant_id="t1", display_name="Acme",
            contract_ref="ctr-001", revenue_share_pct=0.1,
        )
        assert contract["source_type"] == "contract"

        link = integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p1", account_id="acc-1",
            tenant_id="t1",
        )
        assert link["source_type"] == "customer_account"

        health = integ.partner_health_from_sla_breach(
            snapshot_id="snap-1", partner_id="p1", tenant_id="t1",
            breach_count=1,
        )
        assert health["source_type"] == "sla_breach"

        mem = integ.attach_partner_state_to_memory_mesh("scope-full")
        assert mem.content["partners"] == 1
        assert mem.content["links"] == 1
        assert mem.content["agreements"] == 1
        assert mem.content["health_snapshots"] == 1

        graph = integ.attach_partner_state_to_graph("scope-full")
        assert graph["partners"] == 1
        assert graph["links"] == 1

    def test_multiple_partners_tracked(self, env):
        _, _, _, integ = env
        for i in range(5):
            _make_partner(integ, str(i))
        graph = integ.attach_partner_state_to_graph("scope-multi")
        assert graph["partners"] == 5
        assert graph["agreements"] == 5

    def test_health_all_sources(self, env):
        """All three health source types can be used for the same partner."""
        _, _, _, integ = env
        _make_partner(integ, "1")
        r1 = integ.partner_health_from_sla_breach(
            snapshot_id="hs-1", partner_id="p-1", tenant_id="t-1",
        )
        r2 = integ.partner_health_from_settlement(
            snapshot_id="hs-2", partner_id="p-1", tenant_id="t-1",
        )
        r3 = integ.partner_health_from_case(
            snapshot_id="hs-3", partner_id="p-1", tenant_id="t-1",
        )
        assert r1["source_type"] == "sla_breach"
        assert r2["source_type"] == "settlement"
        assert r3["source_type"] == "case"

        graph = integ.attach_partner_state_to_graph("scope-health")
        assert graph["health_snapshots"] == 3

    def test_procurement_vendor_then_graph(self, env):
        _, _, _, integ = env
        integ.partner_from_procurement_vendor(
            partner_id="pv-1", tenant_id="t1", display_name="VendorX",
            vendor_ref="vref-1",
        )
        graph = integ.attach_partner_state_to_graph("scope-pv")
        assert graph["partners"] == 1

    def test_event_count_accumulates(self, env):
        """Every operation emits at least one event."""
        es, _, _, integ = env
        initial = es.event_count
        _make_partner(integ, "1")
        after_contract = es.event_count
        assert after_contract > initial

        integ.partner_from_customer_account(
            link_id="lnk-1", partner_id="p-1", account_id="acc-1",
            tenant_id="t-1",
        )
        after_link = es.event_count
        assert after_link > after_contract

        integ.partner_health_from_sla_breach(
            snapshot_id="hs-1", partner_id="p-1", tenant_id="t-1",
        )
        after_health = es.event_count
        assert after_health > after_link

        integ.attach_partner_state_to_memory_mesh("scope-evt")
        after_mem = es.event_count
        assert after_mem > after_health
