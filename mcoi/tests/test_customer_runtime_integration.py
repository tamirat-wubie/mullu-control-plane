"""Tests for CustomerRuntimeIntegration bridge.

Covers constructor validation, all 6 bridge methods, health scoring,
memory mesh attachment, graph attachment, event emission, sequential
operations, and multi-tenant isolation.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.customer_runtime import CustomerRuntimeEngine
from mcoi_runtime.core.customer_runtime_integration import CustomerRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture
def customer_engine(event_spine: EventSpineEngine) -> CustomerRuntimeEngine:
    return CustomerRuntimeEngine(event_spine)


@pytest.fixture
def bridge(
    customer_engine: CustomerRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> CustomerRuntimeIntegration:
    return CustomerRuntimeIntegration(customer_engine, event_spine, memory_engine)


def _setup_customer(bridge: CustomerRuntimeIntegration) -> dict:
    """Helper: create a customer+account via contract bridge."""
    return bridge.customer_from_contract(
        customer_id="cust-1",
        account_id="acct-1",
        tenant_id="t-1",
        display_name="Acme",
        contract_ref="con-100",
    )


# ── constructor validation ───────────────────────────────────────────


class TestConstructorValidation:
    def test_wrong_customer_engine_type(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration("bad", event_spine, memory_engine)

    def test_wrong_event_spine_type(self, customer_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration(customer_engine, "bad", memory_engine)

    def test_wrong_memory_engine_type(self, customer_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration(customer_engine, event_spine, "bad")

    def test_none_customer_engine(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration(None, event_spine, memory_engine)

    def test_none_event_spine(self, customer_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration(customer_engine, None, memory_engine)

    def test_none_memory_engine(self, customer_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeIntegration(customer_engine, event_spine, None)

    def test_valid_construction(self, customer_engine, event_spine, memory_engine):
        integ = CustomerRuntimeIntegration(customer_engine, event_spine, memory_engine)
        assert integ is not None


# ── customer_from_contract ───────────────────────────────────────────


class TestCustomerFromContract:
    def test_returns_dict(self, bridge):
        result = _setup_customer(bridge)
        assert isinstance(result, dict)

    def test_has_customer_id(self, bridge):
        result = _setup_customer(bridge)
        assert result["customer_id"] == "cust-1"

    def test_has_account_id(self, bridge):
        result = _setup_customer(bridge)
        assert result["account_id"] == "acct-1"

    def test_has_tenant_id(self, bridge):
        result = _setup_customer(bridge)
        assert result["tenant_id"] == "t-1"

    def test_has_contract_ref(self, bridge):
        result = _setup_customer(bridge)
        assert result["contract_ref"] == "con-100"

    def test_has_tier_default(self, bridge):
        result = _setup_customer(bridge)
        assert result["tier"] == "standard"

    def test_has_source_type_contract(self, bridge):
        result = _setup_customer(bridge)
        assert result["source_type"] == "contract"

    def test_custom_tier(self, bridge):
        result = bridge.customer_from_contract(
            customer_id="cust-2",
            account_id="acct-2",
            tenant_id="t-1",
            display_name="Beta",
            contract_ref="con-200",
            tier="premium",
        )
        assert result["tier"] == "premium"

    def test_all_expected_keys(self, bridge):
        result = _setup_customer(bridge)
        expected = {"customer_id", "account_id", "tenant_id", "contract_ref", "tier", "source_type"}
        assert set(result.keys()) == expected


# ── account_from_billing ─────────────────────────────────────────────


class TestAccountFromBilling:
    def test_returns_dict(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert isinstance(result, dict)

    def test_has_account_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert result["account_id"] == "acct-bill-1"

    def test_has_customer_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert result["customer_id"] == "cust-1"

    def test_has_tenant_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert result["tenant_id"] == "t-1"

    def test_has_billing_ref(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert result["billing_ref"] == "bill-500"

    def test_has_source_type_billing(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        assert result["source_type"] == "billing"

    def test_all_expected_keys(self, bridge):
        _setup_customer(bridge)
        result = bridge.account_from_billing(
            account_id="acct-bill-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-500",
        )
        expected = {"account_id", "customer_id", "tenant_id", "billing_ref", "source_type"}
        assert set(result.keys()) == expected

    def test_requires_existing_customer(self, bridge):
        with pytest.raises(RuntimeCoreInvariantError):
            bridge.account_from_billing(
                account_id="acct-bill-1",
                customer_id="nonexistent",
                tenant_id="t-1",
                display_name="Billing Acct",
                billing_ref="bill-500",
            )


# ── health_from_sla_breach ───────────────────────────────────────────


class TestHealthFromSlaBreach:
    def test_returns_dict(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert isinstance(result, dict)

    def test_has_snapshot_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert result["snapshot_id"] == "snap-1"

    def test_has_account_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert result["account_id"] == "acct-1"

    def test_has_tenant_id(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert result["tenant_id"] == "t-1"

    def test_has_source_type_sla_breach(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert result["source_type"] == "sla_breach"

    def test_has_sla_breaches_field(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1", breach_count=3)
        assert result["sla_breaches"] == 3

    def test_default_breach_count_is_1(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        assert result["sla_breaches"] == 1

    def test_score_one_breach_is_healthy(self, bridge):
        """1 breach -> score = 1.0 - 0.15 = 0.85 -> healthy."""
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1", breach_count=1)
        assert result["health_score"] == 0.85
        assert result["health_status"] == "healthy"

    def test_score_two_breaches_is_at_risk(self, bridge):
        """2 breaches -> score = 1.0 - 0.30 = 0.70 -> at_risk."""
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1", breach_count=2)
        assert result["health_score"] == 0.7
        assert result["health_status"] == "at_risk"

    def test_all_expected_keys(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_sla_breach("snap-1", "acct-1", "t-1")
        expected = {
            "snapshot_id", "account_id", "tenant_id",
            "health_score", "health_status", "sla_breaches", "source_type",
        }
        assert set(result.keys()) == expected


# ── health_from_settlement ───────────────────────────────────────────


class TestHealthFromSettlement:
    def test_returns_dict(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1")
        assert isinstance(result, dict)

    def test_has_source_type_settlement(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1")
        assert result["source_type"] == "settlement"

    def test_has_billing_issues_field(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1", billing_issues=2)
        assert result["billing_issues"] == 2

    def test_default_billing_issues_is_1(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1")
        assert result["billing_issues"] == 1

    def test_score_one_billing_issue(self, bridge):
        """1 billing issue -> score = 1.0 - 0.20 = 0.80 -> healthy."""
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1", billing_issues=1)
        assert result["health_score"] == 0.8
        assert result["health_status"] == "healthy"

    def test_all_expected_keys(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_settlement("snap-s1", "acct-1", "t-1")
        expected = {
            "snapshot_id", "account_id", "tenant_id",
            "health_score", "health_status", "billing_issues", "source_type",
        }
        assert set(result.keys()) == expected


# ── health_from_case ─────────────────────────────────────────────────


class TestHealthFromCase:
    def test_returns_dict(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1")
        assert isinstance(result, dict)

    def test_has_source_type_case(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1")
        assert result["source_type"] == "case"

    def test_has_open_cases_field(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1", open_cases=5)
        assert result["open_cases"] == 5

    def test_default_open_cases_is_1(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1")
        assert result["open_cases"] == 1

    def test_score_one_open_case(self, bridge):
        """1 open case -> score = 1.0 - 0.10 = 0.90 -> healthy."""
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1", open_cases=1)
        assert result["health_score"] == 0.9
        assert result["health_status"] == "healthy"

    def test_all_expected_keys(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_case("snap-c1", "acct-1", "t-1")
        expected = {
            "snapshot_id", "account_id", "tenant_id",
            "health_score", "health_status", "open_cases", "source_type",
        }
        assert set(result.keys()) == expected


# ── health_from_service_request ──────────────────────────────────────


class TestHealthFromServiceRequest:
    def test_returns_dict(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1")
        assert isinstance(result, dict)

    def test_has_source_type_service_request(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1")
        assert result["source_type"] == "service_request"

    def test_has_open_cases_field(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1", open_cases=2)
        assert result["open_cases"] == 2

    def test_has_sla_breaches_field(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1", sla_breaches=3)
        assert result["sla_breaches"] == 3

    def test_defaults_zero(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1")
        assert result["open_cases"] == 0
        assert result["sla_breaches"] == 0

    def test_score_defaults_perfect(self, bridge):
        """No issues -> score = 1.0 -> healthy."""
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1")
        assert result["health_score"] == 1.0
        assert result["health_status"] == "healthy"

    def test_combined_deductions(self, bridge):
        """2 open_cases + 1 sla_breach -> 1.0 - 0.20 - 0.15 = 0.65 -> at_risk."""
        _setup_customer(bridge)
        result = bridge.health_from_service_request(
            "snap-sr1", "acct-1", "t-1", open_cases=2, sla_breaches=1,
        )
        assert result["health_score"] == 0.65
        assert result["health_status"] == "at_risk"

    def test_all_expected_keys(self, bridge):
        _setup_customer(bridge)
        result = bridge.health_from_service_request("snap-sr1", "acct-1", "t-1")
        expected = {
            "snapshot_id", "account_id", "tenant_id",
            "health_score", "health_status", "open_cases", "sla_breaches", "source_type",
        }
        assert set(result.keys()) == expected


# ── attach_customer_state_to_memory_mesh ─────────────────────────────


class TestMemoryMeshAttachment:
    def test_returns_memory_record(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)

    def test_title(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        assert record.title == "Customer runtime state"

    def test_tags(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        assert record.tags == ("customer", "account", "product")

    def test_content_keys_zero_state(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        expected_keys = {
            "customers", "accounts", "products", "subscriptions",
            "entitlements", "health_snapshots", "decisions", "violations",
        }
        assert set(record.content.keys()) == expected_keys

    def test_content_values_zero_state(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        for key in record.content:
            assert record.content[key] == 0

    def test_content_after_customer_creation(self, bridge):
        _setup_customer(bridge)
        record = bridge.attach_customer_state_to_memory_mesh("scope-2")
        assert record.content["customers"] == 1
        assert record.content["accounts"] == 1

    def test_memory_id_is_non_empty(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-1")
        assert isinstance(record.memory_id, str)
        assert len(record.memory_id) > 0

    def test_scope_ref_id_preserved(self, bridge):
        record = bridge.attach_customer_state_to_memory_mesh("scope-xyz")
        assert record.scope_ref_id == "scope-xyz"


# ── attach_customer_state_to_graph ───────────────────────────────────


class TestGraphAttachment:
    def test_returns_dict(self, bridge):
        result = bridge.attach_customer_state_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_scope_ref_id(self, bridge):
        result = bridge.attach_customer_state_to_graph("scope-g1")
        assert result["scope_ref_id"] == "scope-g1"

    def test_zero_state_keys(self, bridge):
        result = bridge.attach_customer_state_to_graph("scope-g1")
        expected_keys = {
            "scope_ref_id", "customers", "accounts", "products",
            "subscriptions", "entitlements", "health_snapshots",
            "decisions", "violations",
        }
        assert set(result.keys()) == expected_keys

    def test_zero_state_values(self, bridge):
        result = bridge.attach_customer_state_to_graph("scope-g1")
        for key in ("customers", "accounts", "products", "subscriptions",
                     "entitlements", "health_snapshots", "decisions", "violations"):
            assert result[key] == 0

    def test_post_creation_state(self, bridge):
        _setup_customer(bridge)
        result = bridge.attach_customer_state_to_graph("scope-g2")
        assert result["customers"] == 1
        assert result["accounts"] == 1

    def test_post_health_snapshot_state(self, bridge):
        _setup_customer(bridge)
        bridge.health_from_sla_breach("snap-g1", "acct-1", "t-1")
        result = bridge.attach_customer_state_to_graph("scope-g3")
        assert result["health_snapshots"] == 1


# ── event emission ───────────────────────────────────────────────────


class TestEventEmission:
    def test_customer_from_contract_emits_events(self, bridge, event_spine):
        before = event_spine.event_count
        _setup_customer(bridge)
        assert event_spine.event_count > before

    def test_account_from_billing_emits_events(self, bridge, event_spine):
        _setup_customer(bridge)
        before = event_spine.event_count
        bridge.account_from_billing(
            account_id="acct-bill-ev",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Billing Acct",
            billing_ref="bill-ev",
        )
        assert event_spine.event_count > before

    def test_health_from_sla_breach_emits_events(self, bridge, event_spine):
        _setup_customer(bridge)
        before = event_spine.event_count
        bridge.health_from_sla_breach("snap-ev1", "acct-1", "t-1")
        assert event_spine.event_count > before

    def test_health_from_settlement_emits_events(self, bridge, event_spine):
        _setup_customer(bridge)
        before = event_spine.event_count
        bridge.health_from_settlement("snap-ev2", "acct-1", "t-1")
        assert event_spine.event_count > before

    def test_health_from_case_emits_events(self, bridge, event_spine):
        _setup_customer(bridge)
        before = event_spine.event_count
        bridge.health_from_case("snap-ev3", "acct-1", "t-1")
        assert event_spine.event_count > before

    def test_health_from_service_request_emits_events(self, bridge, event_spine):
        _setup_customer(bridge)
        before = event_spine.event_count
        bridge.health_from_service_request("snap-ev4", "acct-1", "t-1")
        assert event_spine.event_count > before

    def test_memory_mesh_attachment_emits_events(self, bridge, event_spine):
        before = event_spine.event_count
        bridge.attach_customer_state_to_memory_mesh("scope-ev")
        assert event_spine.event_count > before


# ── sequential operations ────────────────────────────────────────────


class TestSequentialOperations:
    def test_multiple_customers(self, bridge):
        r1 = bridge.customer_from_contract("c1", "a1", "t-1", "Alpha", "con-1")
        r2 = bridge.customer_from_contract("c2", "a2", "t-1", "Beta", "con-2")
        assert r1["customer_id"] == "c1"
        assert r2["customer_id"] == "c2"

    def test_multiple_billing_accounts(self, bridge):
        _setup_customer(bridge)
        r1 = bridge.account_from_billing("ab1", "cust-1", "t-1", "B1", "br1")
        r2 = bridge.account_from_billing("ab2", "cust-1", "t-1", "B2", "br2")
        assert r1["account_id"] == "ab1"
        assert r2["account_id"] == "ab2"

    def test_multiple_health_snapshots(self, bridge):
        _setup_customer(bridge)
        r1 = bridge.health_from_sla_breach("s1", "acct-1", "t-1", breach_count=1)
        r2 = bridge.health_from_case("s2", "acct-1", "t-1", open_cases=2)
        assert r1["source_type"] == "sla_breach"
        assert r2["source_type"] == "case"

    def test_graph_reflects_cumulative_state(self, bridge):
        bridge.customer_from_contract("c1", "a1", "t-1", "Alpha", "con-1")
        bridge.customer_from_contract("c2", "a2", "t-1", "Beta", "con-2")
        g = bridge.attach_customer_state_to_graph("scope-seq")
        assert g["customers"] == 2
        assert g["accounts"] == 2

    def test_memory_mesh_reflects_cumulative_state(self, bridge):
        bridge.customer_from_contract("c1", "a1", "t-1", "Alpha", "con-1")
        bridge.health_from_sla_breach("s1", "a1", "t-1")
        rec = bridge.attach_customer_state_to_memory_mesh("scope-seq2")
        assert rec.content["customers"] == 1
        assert rec.content["health_snapshots"] == 1


# ── multi-tenant isolation ───────────────────────────────────────────


class TestMultiTenantIsolation:
    def test_separate_tenant_customers(self, bridge):
        r1 = bridge.customer_from_contract("c-t1", "a-t1", "tenant-A", "A Corp", "con-A")
        r2 = bridge.customer_from_contract("c-t2", "a-t2", "tenant-B", "B Corp", "con-B")
        assert r1["tenant_id"] == "tenant-A"
        assert r2["tenant_id"] == "tenant-B"

    def test_graph_shows_total_across_tenants(self, bridge):
        bridge.customer_from_contract("c-t1", "a-t1", "tenant-A", "A Corp", "con-A")
        bridge.customer_from_contract("c-t2", "a-t2", "tenant-B", "B Corp", "con-B")
        g = bridge.attach_customer_state_to_graph("scope-mt")
        assert g["customers"] == 2

    def test_health_per_tenant(self, bridge):
        bridge.customer_from_contract("c-t1", "a-t1", "tenant-A", "A Corp", "con-A")
        bridge.customer_from_contract("c-t2", "a-t2", "tenant-B", "B Corp", "con-B")
        h1 = bridge.health_from_sla_breach("snap-tA", "a-t1", "tenant-A", breach_count=1)
        h2 = bridge.health_from_sla_breach("snap-tB", "a-t2", "tenant-B", breach_count=3)
        assert h1["tenant_id"] == "tenant-A"
        assert h2["tenant_id"] == "tenant-B"
        assert h1["health_score"] != h2["health_score"]

    def test_billing_account_cross_tenant(self, bridge):
        bridge.customer_from_contract("c-t1", "a-t1", "tenant-A", "A Corp", "con-A")
        result = bridge.account_from_billing("ab-t1", "c-t1", "tenant-A", "Billing", "br-A")
        assert result["tenant_id"] == "tenant-A"
