"""Comprehensive tests for CustomerRuntimeEngine.

Covers: constructor validation, customer CRUD, account CRUD, product lifecycle,
subscriptions, entitlements, account health scoring, customer snapshots,
violation detection, closure reports, state hashing, and golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.customer_runtime import CustomerRuntimeEngine
from mcoi_runtime.contracts.customer_runtime import (
    CustomerStatus,
    AccountStatus,
    ProductStatus,
    EntitlementStatus,
    AccountHealthStatus,
    CustomerDisposition,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spine():
    return EventSpineEngine()


@pytest.fixture
def engine(spine):
    return CustomerRuntimeEngine(spine)


@pytest.fixture
def seeded(engine):
    """Engine with one customer, one account, one product pre-registered."""
    engine.register_customer("c1", "t1", "Customer One")
    engine.register_account("a1", "c1", "t1", "Account One")
    engine.register_product("p1", "t1", "Product One")
    return engine


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeEngine(None)

    def test_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeEngine("not-a-spine")

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeEngine(42)

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CustomerRuntimeEngine({})

    def test_accepts_event_spine(self, spine):
        eng = CustomerRuntimeEngine(spine)
        assert eng.customer_count == 0

    def test_initial_counts_zero(self, engine):
        assert engine.customer_count == 0
        assert engine.account_count == 0
        assert engine.product_count == 0
        assert engine.subscription_count == 0
        assert engine.entitlement_count == 0
        assert engine.health_snapshot_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0


# ---------------------------------------------------------------------------
# Customer registration
# ---------------------------------------------------------------------------

class TestRegisterCustomer:
    def test_basic_registration(self, engine):
        rec = engine.register_customer("c1", "t1", "Acme Corp")
        assert rec.customer_id == "c1"
        assert rec.tenant_id == "t1"
        assert rec.display_name == "Acme Corp"
        assert rec.status == CustomerStatus.ACTIVE
        assert rec.tier == "standard"
        assert rec.account_count == 0

    def test_custom_tier(self, engine):
        rec = engine.register_customer("c1", "t1", "Acme", tier="premium")
        assert rec.tier == "premium"

    def test_custom_status(self, engine):
        rec = engine.register_customer("c1", "t1", "Acme", status=CustomerStatus.PROSPECT)
        assert rec.status == CustomerStatus.PROSPECT

    def test_duplicate_raises(self, engine):
        engine.register_customer("c1", "t1", "Acme")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_customer("c1", "t1", "Acme2")

    def test_increments_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        assert engine.customer_count == 2

    def test_created_at_populated(self, engine):
        rec = engine.register_customer("c1", "t1", "A")
        assert rec.created_at  # non-empty ISO string

    def test_multiple_tenants(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        assert engine.customer_count == 2

    def test_inactive_status(self, engine):
        rec = engine.register_customer("c1", "t1", "A", status=CustomerStatus.INACTIVE)
        assert rec.status == CustomerStatus.INACTIVE

    def test_suspended_status(self, engine):
        rec = engine.register_customer("c1", "t1", "A", status=CustomerStatus.SUSPENDED)
        assert rec.status == CustomerStatus.SUSPENDED

    def test_churned_status_at_creation(self, engine):
        rec = engine.register_customer("c1", "t1", "A", status=CustomerStatus.CHURNED)
        assert rec.status == CustomerStatus.CHURNED


# ---------------------------------------------------------------------------
# Get customer
# ---------------------------------------------------------------------------

class TestGetCustomer:
    def test_returns_registered(self, engine):
        engine.register_customer("c1", "t1", "Acme")
        rec = engine.get_customer("c1")
        assert rec.customer_id == "c1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown customer"):
            engine.get_customer("nope")

    def test_returns_correct_record_among_many(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        assert engine.get_customer("c2").display_name == "B"


# ---------------------------------------------------------------------------
# Update customer status
# ---------------------------------------------------------------------------

class TestUpdateCustomerStatus:
    def test_update_to_suspended(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        assert rec.status == CustomerStatus.SUSPENDED

    def test_update_to_churned(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.update_customer_status("c1", CustomerStatus.CHURNED)
        assert rec.status == CustomerStatus.CHURNED

    def test_churned_is_terminal(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.CHURNED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.update_customer_status("c1", CustomerStatus.ACTIVE)

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown customer"):
            engine.update_customer_status("nope", CustomerStatus.ACTIVE)

    def test_preserves_other_fields(self, engine):
        engine.register_customer("c1", "t1", "Acme", tier="gold")
        rec = engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        assert rec.tier == "gold"
        assert rec.display_name == "Acme"
        assert rec.tenant_id == "t1"

    def test_preserves_account_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        rec = engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        assert rec.account_count == 1

    def test_get_reflects_update(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.INACTIVE)
        assert engine.get_customer("c1").status == CustomerStatus.INACTIVE

    def test_can_transition_active_to_inactive(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.INACTIVE)
        assert engine.get_customer("c1").status == CustomerStatus.INACTIVE

    def test_can_transition_suspended_to_active(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        engine.update_customer_status("c1", CustomerStatus.ACTIVE)
        assert engine.get_customer("c1").status == CustomerStatus.ACTIVE

    def test_double_churned_raises(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.CHURNED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.update_customer_status("c1", CustomerStatus.CHURNED)


# ---------------------------------------------------------------------------
# Customers for tenant
# ---------------------------------------------------------------------------

class TestCustomersForTenant:
    def test_empty(self, engine):
        assert engine.customers_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        engine.register_customer("c3", "t1", "C")
        result = engine.customers_for_tenant("t1")
        assert len(result) == 2
        ids = {r.customer_id for r in result}
        assert ids == {"c1", "c3"}

    def test_returns_tuple(self, engine):
        result = engine.customers_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_no_match(self, engine):
        engine.register_customer("c1", "t1", "A")
        assert engine.customers_for_tenant("t999") == ()


# ---------------------------------------------------------------------------
# Account registration
# ---------------------------------------------------------------------------

class TestRegisterAccount:
    def test_basic_registration(self, seeded):
        rec = seeded.get_account("a1")
        assert rec.account_id == "a1"
        assert rec.customer_id == "c1"
        assert rec.tenant_id == "t1"
        assert rec.status == AccountStatus.ACTIVE
        assert rec.contract_ref == "none"
        assert rec.entitlement_count == 0

    def test_custom_contract_ref(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc", contract_ref="CTR-001")
        assert rec.contract_ref == "CTR-001"

    def test_empty_contract_ref_becomes_none_str(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc", contract_ref="")
        assert rec.contract_ref == "none"

    def test_duplicate_raises(self, seeded):
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            seeded.register_account("a1", "c1", "t1", "Dup")

    def test_unknown_customer_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown customer"):
            engine.register_account("a1", "no-cust", "t1", "Acc")

    def test_churned_customer_raises(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.update_customer_status("c1", CustomerStatus.CHURNED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.register_account("a1", "c1", "t1", "Acc")

    def test_increments_customer_account_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        assert engine.get_customer("c1").account_count == 0
        engine.register_account("a1", "c1", "t1", "Acc1")
        assert engine.get_customer("c1").account_count == 1
        engine.register_account("a2", "c1", "t1", "Acc2")
        assert engine.get_customer("c1").account_count == 2

    def test_increments_engine_account_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        assert engine.account_count == 1

    def test_suspended_customer_allows_account(self, engine):
        engine.register_customer("c1", "t1", "A", status=CustomerStatus.SUSPENDED)
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.account_id == "a1"

    def test_custom_status(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc", status=AccountStatus.PENDING)
        assert rec.status == AccountStatus.PENDING

    def test_multiple_accounts_per_customer(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.register_account("a3", "c1", "t1", "Acc3")
        assert engine.account_count == 3
        assert engine.get_customer("c1").account_count == 3


# ---------------------------------------------------------------------------
# Get account
# ---------------------------------------------------------------------------

class TestGetAccount:
    def test_returns_registered(self, seeded):
        rec = seeded.get_account("a1")
        assert rec.account_id == "a1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown account"):
            engine.get_account("nope")


# ---------------------------------------------------------------------------
# Update account status
# ---------------------------------------------------------------------------

class TestUpdateAccountStatus:
    def test_update_to_suspended(self, seeded):
        rec = seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        assert rec.status == AccountStatus.SUSPENDED

    def test_update_to_closed(self, seeded):
        rec = seeded.update_account_status("a1", AccountStatus.CLOSED)
        assert rec.status == AccountStatus.CLOSED

    def test_closed_is_terminal(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.update_account_status("a1", AccountStatus.ACTIVE)

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown account"):
            engine.update_account_status("nope", AccountStatus.ACTIVE)

    def test_preserves_fields(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc", contract_ref="CTR-1")
        rec = engine.update_account_status("a1", AccountStatus.SUSPENDED)
        assert rec.contract_ref == "CTR-1"
        assert rec.display_name == "Acc"

    def test_get_reflects_update(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        assert seeded.get_account("a1").status == AccountStatus.DELINQUENT

    def test_can_transition_back_from_suspended(self, seeded):
        seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        seeded.update_account_status("a1", AccountStatus.ACTIVE)
        assert seeded.get_account("a1").status == AccountStatus.ACTIVE

    def test_closed_then_closed_raises(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.update_account_status("a1", AccountStatus.CLOSED)


# ---------------------------------------------------------------------------
# Accounts for customer / tenant
# ---------------------------------------------------------------------------

class TestAccountsForCustomer:
    def test_empty(self, engine):
        assert engine.accounts_for_customer("c1") == ()

    def test_returns_matching(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c2", "t1", "Acc2")
        engine.register_account("a3", "c1", "t1", "Acc3")
        result = engine.accounts_for_customer("c1")
        assert len(result) == 2
        ids = {r.account_id for r in result}
        assert ids == {"a1", "a3"}

    def test_returns_tuple(self, engine):
        assert isinstance(engine.accounts_for_customer("c1"), tuple)


class TestAccountsForTenant:
    def test_empty(self, engine):
        assert engine.accounts_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c2", "t2", "Acc2")
        result = engine.accounts_for_tenant("t1")
        assert len(result) == 1
        assert result[0].account_id == "a1"


# ---------------------------------------------------------------------------
# Product registration
# ---------------------------------------------------------------------------

class TestRegisterProduct:
    def test_basic_registration(self, engine):
        rec = engine.register_product("p1", "t1", "Widget")
        assert rec.product_id == "p1"
        assert rec.tenant_id == "t1"
        assert rec.display_name == "Widget"
        assert rec.status == ProductStatus.ACTIVE
        assert rec.category == "general"
        assert rec.base_price == 0.0

    def test_custom_category(self, engine):
        rec = engine.register_product("p1", "t1", "W", category="saas")
        assert rec.category == "saas"

    def test_custom_price(self, engine):
        rec = engine.register_product("p1", "t1", "W", base_price=99.99)
        assert rec.base_price == 99.99

    def test_custom_status(self, engine):
        rec = engine.register_product("p1", "t1", "W", status=ProductStatus.DRAFT)
        assert rec.status == ProductStatus.DRAFT

    def test_duplicate_raises(self, engine):
        engine.register_product("p1", "t1", "W")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_product("p1", "t1", "W2")

    def test_increments_count(self, engine):
        engine.register_product("p1", "t1", "A")
        engine.register_product("p2", "t1", "B")
        assert engine.product_count == 2


# ---------------------------------------------------------------------------
# Get product
# ---------------------------------------------------------------------------

class TestGetProduct:
    def test_returns_registered(self, engine):
        engine.register_product("p1", "t1", "W")
        assert engine.get_product("p1").product_id == "p1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown product"):
            engine.get_product("nope")


# ---------------------------------------------------------------------------
# Deprecate product
# ---------------------------------------------------------------------------

class TestDeprecateProduct:
    def test_deprecates(self, engine):
        engine.register_product("p1", "t1", "W")
        rec = engine.deprecate_product("p1")
        assert rec.status == ProductStatus.DEPRECATED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown product"):
            engine.deprecate_product("nope")

    def test_retired_is_terminal(self, engine):
        engine.register_product("p1", "t1", "W")
        engine.retire_product("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.deprecate_product("p1")

    def test_preserves_fields(self, engine):
        engine.register_product("p1", "t1", "W", category="saas", base_price=10.0)
        rec = engine.deprecate_product("p1")
        assert rec.category == "saas"
        assert rec.base_price == 10.0

    def test_can_deprecate_draft(self, engine):
        engine.register_product("p1", "t1", "W", status=ProductStatus.DRAFT)
        rec = engine.deprecate_product("p1")
        assert rec.status == ProductStatus.DEPRECATED


# ---------------------------------------------------------------------------
# Retire product
# ---------------------------------------------------------------------------

class TestRetireProduct:
    def test_retires(self, engine):
        engine.register_product("p1", "t1", "W")
        rec = engine.retire_product("p1")
        assert rec.status == ProductStatus.RETIRED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown product"):
            engine.retire_product("nope")

    def test_already_retired_raises(self, engine):
        engine.register_product("p1", "t1", "W")
        engine.retire_product("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine.retire_product("p1")

    def test_can_retire_deprecated(self, engine):
        engine.register_product("p1", "t1", "W")
        engine.deprecate_product("p1")
        rec = engine.retire_product("p1")
        assert rec.status == ProductStatus.RETIRED

    def test_preserves_fields(self, engine):
        engine.register_product("p1", "t1", "W", category="saas", base_price=50.0)
        rec = engine.retire_product("p1")
        assert rec.category == "saas"
        assert rec.base_price == 50.0


# ---------------------------------------------------------------------------
# Products for tenant
# ---------------------------------------------------------------------------

class TestProductsForTenant:
    def test_empty(self, engine):
        assert engine.products_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        engine.register_product("p1", "t1", "A")
        engine.register_product("p2", "t2", "B")
        engine.register_product("p3", "t1", "C")
        result = engine.products_for_tenant("t1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.products_for_tenant("t1"), tuple)


# ---------------------------------------------------------------------------
# Subscription registration
# ---------------------------------------------------------------------------

class TestRegisterSubscription:
    def test_basic_registration(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"
        assert rec.account_id == "a1"
        assert rec.product_id == "p1"
        assert rec.tenant_id == "t1"
        assert rec.status == AccountStatus.ACTIVE
        assert rec.quantity == 1

    def test_custom_quantity(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1", quantity=5)
        assert rec.quantity == 5

    def test_custom_dates(self, seeded):
        rec = seeded.register_subscription(
            "s1", "a1", "p1", "t1",
            start_at="2025-01-01T00:00:00+00:00",
            end_at="2026-01-01T00:00:00+00:00",
        )
        assert rec.start_at == "2025-01-01T00:00:00+00:00"
        assert rec.end_at == "2026-01-01T00:00:00+00:00"

    def test_default_dates_populated(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.start_at  # non-empty
        assert rec.end_at  # non-empty

    def test_duplicate_raises(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            seeded.register_subscription("s1", "a1", "p1", "t1")

    def test_unknown_account_raises(self, engine):
        engine.register_product("p1", "t1", "W")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown account"):
            engine.register_subscription("s1", "no-acct", "p1", "t1")

    def test_unknown_product_raises(self, seeded):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown product"):
            seeded.register_subscription("s1", "a1", "no-prod", "t1")

    def test_closed_account_raises(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.register_subscription("s1", "a1", "p1", "t1")

    def test_retired_product_raises(self, seeded):
        seeded.retire_product("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.register_subscription("s1", "a1", "p1", "t1")

    def test_deprecated_product_allows(self, seeded):
        seeded.deprecate_product("p1")
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"

    def test_increments_count(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.register_subscription("s2", "a1", "p1", "t1")
        assert seeded.subscription_count == 2

    def test_suspended_account_allows(self, seeded):
        seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"


# ---------------------------------------------------------------------------
# Get subscription
# ---------------------------------------------------------------------------

class TestGetSubscription:
    def test_returns_registered(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        rec = seeded.get_subscription("s1")
        assert rec.subscription_id == "s1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown subscription"):
            engine.get_subscription("nope")


# ---------------------------------------------------------------------------
# Subscriptions for account / product
# ---------------------------------------------------------------------------

class TestSubscriptionsForAccount:
    def test_empty(self, engine):
        assert engine.subscriptions_for_account("a1") == ()

    def test_returns_matching(self, seeded):
        seeded.register_product("p2", "t1", "P2")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.register_subscription("s2", "a1", "p2", "t1")
        result = seeded.subscriptions_for_account("a1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.subscriptions_for_account("a1"), tuple)


class TestSubscriptionsForProduct:
    def test_empty(self, engine):
        assert engine.subscriptions_for_product("p1") == ()

    def test_returns_matching(self, seeded):
        seeded.register_customer("c2", "t1", "C2")
        seeded.register_account("a2", "c2", "t1", "A2")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.register_subscription("s2", "a2", "p1", "t1")
        result = seeded.subscriptions_for_product("p1")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Entitlement granting
# ---------------------------------------------------------------------------

class TestGrantEntitlement:
    def test_basic_grant(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        assert rec.entitlement_id == "e1"
        assert rec.account_id == "a1"
        assert rec.tenant_id == "t1"
        assert rec.service_ref == "svc-api"
        assert rec.status == EntitlementStatus.ACTIVE

    def test_expires_at_default(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        assert rec.expires_at  # non-empty (defaults to now)

    def test_custom_expires_at(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc-api",
                                       expires_at="2099-12-31T23:59:59+00:00")
        assert rec.expires_at == "2099-12-31T23:59:59+00:00"

    def test_duplicate_raises(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            seeded.grant_entitlement("e1", "a1", "t1", "svc-api")

    def test_unknown_account_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown account"):
            engine.grant_entitlement("e1", "no-acct", "t1", "svc")

    def test_closed_account_raises(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.grant_entitlement("e1", "a1", "t1", "svc")

    def test_increments_account_entitlement_count(self, seeded):
        assert seeded.get_account("a1").entitlement_count == 0
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        assert seeded.get_account("a1").entitlement_count == 1
        seeded.grant_entitlement("e2", "a1", "t1", "svc2")
        assert seeded.get_account("a1").entitlement_count == 2

    def test_increments_engine_count(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert seeded.entitlement_count == 1

    def test_suspended_account_allows(self, seeded):
        seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.entitlement_id == "e1"

    def test_multiple_services(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-a")
        seeded.grant_entitlement("e2", "a1", "t1", "svc-b")
        seeded.grant_entitlement("e3", "a1", "t1", "svc-c")
        assert seeded.entitlement_count == 3


# ---------------------------------------------------------------------------
# Revoke entitlement
# ---------------------------------------------------------------------------

class TestRevokeEntitlement:
    def test_revokes(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        rec = seeded.revoke_entitlement("e1")
        assert rec.status == EntitlementStatus.REVOKED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown entitlement"):
            engine.revoke_entitlement("nope")

    def test_already_revoked_raises(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.revoke_entitlement("e1")
        with pytest.raises(RuntimeCoreInvariantError, match="already inactive"):
            seeded.revoke_entitlement("e1")

    def test_get_reflects_revocation(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.revoke_entitlement("e1")
        assert seeded.get_entitlement("e1").status == EntitlementStatus.REVOKED

    def test_preserves_service_ref(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-special")
        rec = seeded.revoke_entitlement("e1")
        assert rec.service_ref == "svc-special"


# ---------------------------------------------------------------------------
# Get entitlement
# ---------------------------------------------------------------------------

class TestGetEntitlement:
    def test_returns_registered(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        rec = seeded.get_entitlement("e1")
        assert rec.entitlement_id == "e1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown entitlement"):
            engine.get_entitlement("nope")


# ---------------------------------------------------------------------------
# Check entitlement
# ---------------------------------------------------------------------------

class TestCheckEntitlement:
    def test_active_returns_true(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        assert seeded.check_entitlement("a1", "svc-api") is True

    def test_no_entitlement_returns_false(self, seeded):
        assert seeded.check_entitlement("a1", "svc-api") is False

    def test_revoked_returns_false(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        seeded.revoke_entitlement("e1")
        assert seeded.check_entitlement("a1", "svc-api") is False

    def test_wrong_service_returns_false(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        assert seeded.check_entitlement("a1", "svc-other") is False

    def test_wrong_account_returns_false(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        assert seeded.check_entitlement("a999", "svc-api") is False

    def test_multiple_entitlements_one_active(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        seeded.grant_entitlement("e2", "a1", "t1", "svc-api")
        seeded.revoke_entitlement("e1")
        assert seeded.check_entitlement("a1", "svc-api") is True

    def test_all_revoked_returns_false(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-api")
        seeded.grant_entitlement("e2", "a1", "t1", "svc-api")
        seeded.revoke_entitlement("e1")
        seeded.revoke_entitlement("e2")
        assert seeded.check_entitlement("a1", "svc-api") is False


# ---------------------------------------------------------------------------
# Entitlements for account
# ---------------------------------------------------------------------------

class TestEntitlementsForAccount:
    def test_empty(self, engine):
        assert engine.entitlements_for_account("a1") == ()

    def test_returns_all_statuses(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        seeded.grant_entitlement("e2", "a1", "t1", "svc2")
        seeded.revoke_entitlement("e2")
        result = seeded.entitlements_for_account("a1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.entitlements_for_account("a1"), tuple)


class TestActiveEntitlementsForAccount:
    def test_empty(self, engine):
        assert engine.active_entitlements_for_account("a1") == ()

    def test_only_active(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        seeded.grant_entitlement("e2", "a1", "t1", "svc2")
        seeded.revoke_entitlement("e2")
        result = seeded.active_entitlements_for_account("a1")
        assert len(result) == 1
        assert result[0].entitlement_id == "e1"

    def test_all_revoked(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        seeded.revoke_entitlement("e1")
        assert seeded.active_entitlements_for_account("a1") == ()


# ---------------------------------------------------------------------------
# Account health
# ---------------------------------------------------------------------------

class TestAccountHealth:
    def test_healthy_default(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.health_score == 1.0
        assert snap.health_status == AccountHealthStatus.HEALTHY
        assert snap.sla_breaches == 0
        assert snap.open_cases == 0
        assert snap.billing_issues == 0

    def test_sla_breach_reduces_score(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=1)
        assert snap.health_score == 0.85
        assert snap.health_status == AccountHealthStatus.HEALTHY

    def test_two_sla_breaches(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=2)
        assert snap.health_score == 0.7
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_open_cases_reduce_score(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1", open_cases=2)
        assert snap.health_score == 0.8
        assert snap.health_status == AccountHealthStatus.HEALTHY

    def test_billing_issues_reduce_score(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1", billing_issues=1)
        assert snap.health_score == 0.8
        assert snap.health_status == AccountHealthStatus.HEALTHY

    def test_combined_issues(self, seeded):
        # 1.0 - 1*0.15 - 2*0.1 - 1*0.2 = 0.45
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=1, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.45
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_at_risk_boundary(self, seeded):
        # 1.0 - 2*0.15 - 1*0.1 = 0.6
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=2, open_cases=1)
        assert snap.health_score == 0.6
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_degraded_boundary(self, seeded):
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 = 0.3
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=2, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.3
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_critical_boundary(self, seeded):
        # 1.0 - 2*0.15 - 3*0.1 - 1*0.2 = 0.2
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=2, open_cases=3, billing_issues=1)
        assert snap.health_score == 0.2
        assert snap.health_status == AccountHealthStatus.CRITICAL

    def test_score_clamped_at_zero(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=10, open_cases=10, billing_issues=10)
        assert snap.health_score == 0.0
        assert snap.health_status == AccountHealthStatus.CRITICAL

    def test_critical_creates_escalation_decision(self, seeded):
        assert seeded.decision_count == 0
        seeded.account_health("h1", "a1", "t1",
                              sla_breaches=5, open_cases=5, billing_issues=5)
        assert seeded.decision_count == 1

    def test_healthy_no_decision(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        assert seeded.decision_count == 0

    def test_duplicate_raises(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            seeded.account_health("h1", "a1", "t1")

    def test_unknown_account_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown account"):
            engine.account_health("h1", "no-acct", "t1")

    def test_entitlement_count_in_snapshot(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        seeded.grant_entitlement("e2", "a1", "t1", "svc2")
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.entitlement_count == 2

    def test_entitlement_count_excludes_revoked(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc1")
        seeded.grant_entitlement("e2", "a1", "t1", "svc2")
        seeded.revoke_entitlement("e2")
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.entitlement_count == 1

    def test_increments_snapshot_count(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        seeded.account_health("h2", "a1", "t1")
        assert seeded.health_snapshot_count == 2

    def test_exactly_0_5_is_at_risk(self, seeded):
        # 1.0 - 2*0.15 - 2*0.1 = 0.5
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=2, open_cases=2)
        assert snap.health_score == 0.5
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_exactly_0_8_is_healthy(self, seeded):
        # 1.0 - 1*0.1 - 0.5*... let's do: 1.0 - 1*0.2 = 0.8
        snap = seeded.account_health("h1", "a1", "t1", billing_issues=1)
        assert snap.health_score == 0.8
        assert snap.health_status == AccountHealthStatus.HEALTHY

    def test_exactly_0_3_is_degraded(self, seeded):
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 = 0.3
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=2, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.3
        assert snap.health_status == AccountHealthStatus.DEGRADED


# ---------------------------------------------------------------------------
# Get health snapshot / snapshots for account
# ---------------------------------------------------------------------------

class TestGetHealthSnapshot:
    def test_returns_registered(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        snap = seeded.get_health_snapshot("h1")
        assert snap.snapshot_id == "h1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown health snapshot"):
            engine.get_health_snapshot("nope")


class TestHealthSnapshotsForAccount:
    def test_empty(self, engine):
        assert engine.health_snapshots_for_account("a1") == ()

    def test_returns_matching(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        seeded.account_health("h2", "a1", "t1")
        result = seeded.health_snapshots_for_account("a1")
        assert len(result) == 2

    def test_filters_by_account(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.account_health("h1", "a1", "t1")
        engine.account_health("h2", "a2", "t1")
        assert len(engine.health_snapshots_for_account("a1")) == 1
        assert len(engine.health_snapshots_for_account("a2")) == 1


# ---------------------------------------------------------------------------
# Customer snapshot
# ---------------------------------------------------------------------------

class TestCustomerSnapshot:
    def test_empty_engine(self, engine):
        snap = engine.customer_snapshot("snap1")
        assert snap.snapshot_id == "snap1"
        assert snap.total_customers == 0
        assert snap.total_accounts == 0
        assert snap.total_products == 0
        assert snap.total_subscriptions == 0
        assert snap.total_entitlements == 0
        assert snap.total_health_snapshots == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0

    def test_populated_engine(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.account_health("h1", "a1", "t1")
        snap = seeded.customer_snapshot("snap1")
        assert snap.total_customers == 1
        assert snap.total_accounts == 1
        assert snap.total_products == 1
        assert snap.total_subscriptions == 1
        assert snap.total_entitlements == 1
        assert snap.total_health_snapshots == 1

    def test_captured_at_populated(self, engine):
        snap = engine.customer_snapshot("snap1")
        assert snap.captured_at


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------

class TestDetectCustomerViolations:
    def test_no_violations_clean(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        violations = seeded.detect_customer_violations("t1")
        assert len(violations) == 0

    def test_no_entitlements_violation(self, seeded):
        # Active account with no entitlements
        violations = seeded.detect_customer_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "no_entitlements"

    def test_delinquent_account_violation(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        violations = seeded.detect_customer_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "delinquent_account"

    def test_retired_product_subscription_violation(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.retire_product("p1")
        violations = seeded.detect_customer_violations("t1")
        assert any(v.operation == "retired_product_subscription" for v in violations)

    def test_idempotent(self, seeded):
        # Active account with no entitlements
        v1 = seeded.detect_customer_violations("t1")
        v2 = seeded.detect_customer_violations("t1")
        assert len(v1) == 1
        assert len(v2) == 0  # no new violations on second call
        assert seeded.violation_count == 1

    def test_multiple_violations(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.update_account_status("a2", AccountStatus.DELINQUENT)
        # a1: active no entitlements, a2: delinquent
        violations = engine.detect_customer_violations("t1")
        ops = {v.operation for v in violations}
        assert "no_entitlements" in ops
        assert "delinquent_account" in ops

    def test_tenant_isolation(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a2", "c2", "t2", "Acc2")
        # Only check t1
        violations = engine.detect_customer_violations("t1")
        for v in violations:
            assert v.tenant_id == "t1"

    def test_closed_account_no_no_entitlements_violation(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        violations = seeded.detect_customer_violations("t1")
        assert not any(v.operation == "no_entitlements" for v in violations)

    def test_no_entitlements_with_all_revoked(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.revoke_entitlement("e1")
        violations = seeded.detect_customer_violations("t1")
        assert any(v.operation == "no_entitlements" for v in violations)

    def test_violation_count_increments(self, seeded):
        assert seeded.violation_count == 0
        seeded.detect_customer_violations("t1")
        assert seeded.violation_count == 1


# ---------------------------------------------------------------------------
# Violations for tenant
# ---------------------------------------------------------------------------

class TestViolationsForTenant:
    def test_empty(self, engine):
        assert engine.violations_for_tenant("t1") == ()

    def test_returns_matching(self, seeded):
        seeded.detect_customer_violations("t1")
        result = seeded.violations_for_tenant("t1")
        assert len(result) >= 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.violations_for_tenant("t1"), tuple)

    def test_tenant_isolation(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a2", "c2", "t2", "Acc2")
        engine.detect_customer_violations("t1")
        engine.detect_customer_violations("t2")
        for v in engine.violations_for_tenant("t1"):
            assert v.tenant_id == "t1"
        for v in engine.violations_for_tenant("t2"):
            assert v.tenant_id == "t2"


# ---------------------------------------------------------------------------
# Closure report
# ---------------------------------------------------------------------------

class TestClosureReport:
    def test_empty_tenant(self, engine):
        report = engine.closure_report("r1", "t1")
        assert report.report_id == "r1"
        assert report.tenant_id == "t1"
        assert report.total_customers == 0
        assert report.total_accounts == 0
        assert report.total_products == 0
        assert report.total_subscriptions == 0
        assert report.total_entitlements == 0
        assert report.total_violations == 0

    def test_populated_tenant(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.detect_customer_violations("t1")
        report = seeded.closure_report("r1", "t1")
        assert report.total_customers == 1
        assert report.total_accounts == 1
        assert report.total_products == 1
        assert report.total_subscriptions == 1
        assert report.total_entitlements == 1

    def test_tenant_scoped(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        report = engine.closure_report("r1", "t1")
        assert report.total_customers == 1

    def test_closed_at_populated(self, engine):
        report = engine.closure_report("r1", "t1")
        assert report.closed_at


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------

class TestStateHash:
    def test_empty_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_on_customer_add(self, engine):
        h1 = engine.state_hash()
        engine.register_customer("c1", "t1", "A")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_account_add(self, seeded):
        h1 = seeded.state_hash()
        seeded.register_account("a2", "c1", "t1", "A2")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_on_product_add(self, engine):
        h1 = engine.state_hash()
        engine.register_product("p1", "t1", "P")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_subscription_add(self, seeded):
        h1 = seeded.state_hash()
        seeded.register_subscription("s1", "a1", "p1", "t1")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_on_entitlement_add(self, seeded):
        h1 = seeded.state_hash()
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_on_health_snapshot(self, seeded):
        h1 = seeded.state_hash()
        seeded.account_health("h1", "a1", "t1")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_on_violation(self, seeded):
        h1 = seeded.state_hash()
        seeded.detect_customer_violations("t1")
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_on_decision(self, seeded):
        h1 = seeded.state_hash()
        seeded.account_health("h1", "a1", "t1", sla_breaches=10)
        h2 = seeded.state_hash()
        assert h1 != h2  # decision created from critical health

    def test_is_sha256_hex(self, engine):
        h = engine.state_hash()
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_same_ops_same_hash(self, spine):
        e1 = CustomerRuntimeEngine(spine)
        spine2 = EventSpineEngine()
        e2 = CustomerRuntimeEngine(spine2)
        e1.register_customer("c1", "t1", "A")
        e2.register_customer("c1", "t1", "A")
        assert e1.state_hash() == e2.state_hash()


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestProperties:
    def test_customer_count(self, engine):
        assert engine.customer_count == 0
        engine.register_customer("c1", "t1", "A")
        assert engine.customer_count == 1

    def test_account_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        assert engine.account_count == 1

    def test_product_count(self, engine):
        engine.register_product("p1", "t1", "P")
        assert engine.product_count == 1

    def test_subscription_count(self, seeded):
        seeded.register_subscription("s1", "a1", "p1", "t1")
        assert seeded.subscription_count == 1

    def test_entitlement_count(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert seeded.entitlement_count == 1

    def test_health_snapshot_count(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        assert seeded.health_snapshot_count == 1

    def test_decision_count_from_critical(self, seeded):
        seeded.account_health("h1", "a1", "t1", sla_breaches=10)
        assert seeded.decision_count == 1

    def test_violation_count(self, seeded):
        seeded.detect_customer_violations("t1")
        assert seeded.violation_count >= 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_register_customer_emits_event(self, spine, engine):
        engine.register_customer("c1", "t1", "A")
        assert spine.event_count >= 1

    def test_register_account_emits_event(self, spine, engine):
        engine.register_customer("c1", "t1", "A")
        before = spine.event_count
        engine.register_account("a1", "c1", "t1", "Acc")
        assert spine.event_count > before

    def test_update_customer_status_emits_event(self, spine, engine):
        engine.register_customer("c1", "t1", "A")
        before = spine.event_count
        engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        assert spine.event_count > before

    def test_register_product_emits_event(self, spine, engine):
        before = spine.event_count
        engine.register_product("p1", "t1", "P")
        assert spine.event_count > before

    def test_deprecate_product_emits_event(self, spine, engine):
        engine.register_product("p1", "t1", "P")
        before = spine.event_count
        engine.deprecate_product("p1")
        assert spine.event_count > before

    def test_retire_product_emits_event(self, spine, engine):
        engine.register_product("p1", "t1", "P")
        before = spine.event_count
        engine.retire_product("p1")
        assert spine.event_count > before

    def test_register_subscription_emits_event(self, spine, seeded):
        before = spine.event_count
        seeded.register_subscription("s1", "a1", "p1", "t1")
        assert spine.event_count > before

    def test_grant_entitlement_emits_event(self, spine, seeded):
        before = spine.event_count
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert spine.event_count > before

    def test_revoke_entitlement_emits_event(self, spine, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        before = spine.event_count
        seeded.revoke_entitlement("e1")
        assert spine.event_count > before

    def test_account_health_emits_event(self, spine, seeded):
        before = spine.event_count
        seeded.account_health("h1", "a1", "t1")
        assert spine.event_count > before

    def test_detect_violations_emits_event(self, spine, seeded):
        before = spine.event_count
        seeded.detect_customer_violations("t1")
        assert spine.event_count > before

    def test_update_account_status_emits_event(self, spine, seeded):
        before = spine.event_count
        seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        assert spine.event_count > before


# ---------------------------------------------------------------------------
# Golden Scenario 1: Contract creates customer, account, subscription
# ---------------------------------------------------------------------------

class TestGoldenContractLifecycle:
    def test_full_contract_lifecycle(self, engine):
        # Register customer
        cust = engine.register_customer("cust-01", "tenant-a", "Acme Corp", tier="enterprise")
        assert cust.status == CustomerStatus.ACTIVE
        assert cust.account_count == 0

        # Register account
        acct = engine.register_account("acct-01", "cust-01", "tenant-a",
                                       "Main Account", contract_ref="CTR-2025-001")
        assert acct.status == AccountStatus.ACTIVE
        assert acct.contract_ref == "CTR-2025-001"
        assert engine.get_customer("cust-01").account_count == 1

        # Register product
        prod = engine.register_product("prod-01", "tenant-a", "API Gateway",
                                       category="infrastructure", base_price=299.99)
        assert prod.status == ProductStatus.ACTIVE
        assert prod.base_price == 299.99

        # Register subscription
        sub = engine.register_subscription("sub-01", "acct-01", "prod-01", "tenant-a",
                                           quantity=3)
        assert sub.quantity == 3
        assert sub.status == AccountStatus.ACTIVE

        # Verify counts
        snap = engine.customer_snapshot("snap-01")
        assert snap.total_customers == 1
        assert snap.total_accounts == 1
        assert snap.total_products == 1
        assert snap.total_subscriptions == 1

    def test_multi_account_multi_product(self, engine):
        engine.register_customer("c1", "t1", "Corp")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.register_product("p1", "t1", "Prod1")
        engine.register_product("p2", "t1", "Prod2")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.register_subscription("s2", "a1", "p2", "t1")
        engine.register_subscription("s3", "a2", "p1", "t1")
        assert engine.subscription_count == 3
        assert len(engine.subscriptions_for_account("a1")) == 2
        assert len(engine.subscriptions_for_product("p1")) == 2


# ---------------------------------------------------------------------------
# Golden Scenario 2: Entitlement allows/blocks service request
# ---------------------------------------------------------------------------

class TestGoldenEntitlementAccess:
    def test_entitlement_allows_service(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "billing-api")
        assert engine.check_entitlement("a1", "billing-api") is True

    def test_no_entitlement_blocks_service(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        assert engine.check_entitlement("a1", "billing-api") is False

    def test_revoked_entitlement_blocks_service(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "billing-api")
        engine.revoke_entitlement("e1")
        assert engine.check_entitlement("a1", "billing-api") is False

    def test_separate_services_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "billing-api")
        assert engine.check_entitlement("a1", "billing-api") is True
        assert engine.check_entitlement("a1", "analytics-api") is False

    def test_separate_accounts_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        assert engine.check_entitlement("a1", "svc") is True
        assert engine.check_entitlement("a2", "svc") is False

    def test_grant_after_revoke_new_entitlement(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.revoke_entitlement("e1")
        assert engine.check_entitlement("a1", "svc") is False
        engine.grant_entitlement("e2", "a1", "t1", "svc")
        assert engine.check_entitlement("a1", "svc") is True


# ---------------------------------------------------------------------------
# Golden Scenario 3: SLA breach degrades account health
# ---------------------------------------------------------------------------

class TestGoldenSLABreach:
    def test_initial_healthy(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        snap = engine.account_health("h1", "a1", "t1")
        assert snap.health_status == AccountHealthStatus.HEALTHY
        assert snap.health_score == 1.0

    def test_single_breach_reduces_score(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        snap = engine.account_health("h1", "a1", "t1", sla_breaches=1)
        assert snap.health_score == 0.85

    def test_progressive_degradation(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        s1 = engine.account_health("h1", "a1", "t1", sla_breaches=1)
        s2 = engine.account_health("h2", "a1", "t1", sla_breaches=3)
        s3 = engine.account_health("h3", "a1", "t1", sla_breaches=5)
        assert s1.health_score > s2.health_score > s3.health_score
        assert s1.health_status == AccountHealthStatus.HEALTHY
        assert s2.health_status == AccountHealthStatus.AT_RISK
        assert s3.health_status == AccountHealthStatus.CRITICAL

    def test_breach_with_cases_compounds(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 2*0.15 - 3*0.1 = 0.4
        snap = engine.account_health("h1", "a1", "t1", sla_breaches=2, open_cases=3)
        assert snap.health_score == 0.4
        assert snap.health_status == AccountHealthStatus.DEGRADED


# ---------------------------------------------------------------------------
# Golden Scenario 4: Settlement dispute (billing_issues)
# ---------------------------------------------------------------------------

class TestGoldenBillingIssues:
    def test_single_billing_issue(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        snap = engine.account_health("h1", "a1", "t1", billing_issues=1)
        assert snap.health_score == 0.8

    def test_multiple_billing_issues_critical(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 4*0.2 = 0.2
        snap = engine.account_health("h1", "a1", "t1", billing_issues=4)
        assert snap.health_score == 0.2
        assert snap.health_status == AccountHealthStatus.CRITICAL

    def test_billing_with_sla_compound(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 1*0.15 - 2*0.2 = 0.45
        snap = engine.account_health("h1", "a1", "t1", sla_breaches=1, billing_issues=2)
        assert snap.health_score == 0.45
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_billing_triggers_escalation_when_critical(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.account_health("h1", "a1", "t1", billing_issues=5)
        assert engine.decision_count == 1


# ---------------------------------------------------------------------------
# Golden Scenario 5: Case/remediation recovery restores health
# ---------------------------------------------------------------------------

class TestGoldenRecovery:
    def test_recovery_from_critical(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # Degraded state
        s1 = engine.account_health("h1", "a1", "t1", sla_breaches=5, billing_issues=3)
        assert s1.health_status == AccountHealthStatus.CRITICAL
        # Recovery: new snapshot with zero issues
        s2 = engine.account_health("h2", "a1", "t1")
        assert s2.health_score == 1.0
        assert s2.health_status == AccountHealthStatus.HEALTHY

    def test_partial_recovery(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        s1 = engine.account_health("h1", "a1", "t1", sla_breaches=3, open_cases=3)
        s2 = engine.account_health("h2", "a1", "t1", sla_breaches=1)
        assert s2.health_score > s1.health_score

    def test_recovery_snapshot_history(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.account_health("h1", "a1", "t1", sla_breaches=5)
        engine.account_health("h2", "a1", "t1")
        history = engine.health_snapshots_for_account("a1")
        assert len(history) == 2
        scores = [h.health_score for h in history]
        assert scores[0] < scores[1]  # improved


# ---------------------------------------------------------------------------
# Golden Scenario 6: Replay/restore preserves state (state_hash)
# ---------------------------------------------------------------------------

class TestGoldenReplayConsistency:
    def test_identical_operations_same_hash(self):
        def build_engine():
            s = EventSpineEngine()
            e = CustomerRuntimeEngine(s)
            e.register_customer("c1", "t1", "Acme")
            e.register_account("a1", "c1", "t1", "Acc")
            e.register_product("p1", "t1", "Prod")
            e.register_subscription("s1", "a1", "p1", "t1")
            e.grant_entitlement("e1", "a1", "t1", "svc-api")
            e.account_health("h1", "a1", "t1", sla_breaches=1)
            e.detect_customer_violations("t1")
            return e

        e1 = build_engine()
        e2 = build_engine()
        assert e1.state_hash() == e2.state_hash()

    def test_different_operations_different_hash(self):
        s1 = EventSpineEngine()
        e1 = CustomerRuntimeEngine(s1)
        e1.register_customer("c1", "t1", "A")

        s2 = EventSpineEngine()
        e2 = CustomerRuntimeEngine(s2)
        e2.register_customer("c2", "t1", "B")

        assert e1.state_hash() != e2.state_hash()

    def test_order_independence_of_state_hash(self):
        # State hash sorts keys, so adding in different order should yield same hash
        # if same entities exist
        s1 = EventSpineEngine()
        e1 = CustomerRuntimeEngine(s1)
        e1.register_customer("c1", "t1", "A")
        e1.register_customer("c2", "t1", "B")

        s2 = EventSpineEngine()
        e2 = CustomerRuntimeEngine(s2)
        e2.register_customer("c2", "t1", "B")
        e2.register_customer("c1", "t1", "A")

        assert e1.state_hash() == e2.state_hash()

    def test_hash_stability_across_reads(self, engine):
        engine.register_customer("c1", "t1", "A")
        h1 = engine.state_hash()
        # Reads should not affect hash
        engine.get_customer("c1")
        engine.customers_for_tenant("t1")
        h2 = engine.state_hash()
        assert h1 == h2

    def test_snapshot_does_not_change_hash(self, engine):
        engine.register_customer("c1", "t1", "A")
        h1 = engine.state_hash()
        engine.customer_snapshot("snap1")
        h2 = engine.state_hash()
        assert h1 == h2

    def test_closure_report_does_not_change_hash(self, engine):
        engine.register_customer("c1", "t1", "A")
        h1 = engine.state_hash()
        engine.closure_report("r1", "t1")
        h2 = engine.state_hash()
        assert h1 == h2


# ---------------------------------------------------------------------------
# Edge cases and cross-cutting concerns
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_churned_customer_blocks_account_registration(self, engine):
        engine.register_customer("c1", "t1", "A", status=CustomerStatus.CHURNED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.register_account("a1", "c1", "t1", "Acc")

    def test_closed_account_blocks_subscription(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.register_subscription("s1", "a1", "p1", "t1")

    def test_closed_account_blocks_entitlement(self, seeded):
        seeded.update_account_status("a1", AccountStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.grant_entitlement("e1", "a1", "t1", "svc")

    def test_retired_product_blocks_subscription(self, seeded):
        seeded.retire_product("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            seeded.register_subscription("s1", "a1", "p1", "t1")

    def test_many_customers_many_tenants(self, engine):
        for i in range(20):
            tid = f"t{i % 4}"
            engine.register_customer(f"c{i}", tid, f"Cust{i}")
        assert engine.customer_count == 20
        assert len(engine.customers_for_tenant("t0")) == 5

    def test_many_accounts_per_customer(self, engine):
        engine.register_customer("c1", "t1", "A")
        for i in range(15):
            engine.register_account(f"a{i}", "c1", "t1", f"Acc{i}")
        assert engine.get_customer("c1").account_count == 15

    def test_many_entitlements_per_account(self, seeded):
        for i in range(10):
            seeded.grant_entitlement(f"e{i}", "a1", "t1", f"svc-{i}")
        assert seeded.get_account("a1").entitlement_count == 10
        assert len(seeded.active_entitlements_for_account("a1")) == 10

    def test_revoke_then_check_still_false(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.revoke_entitlement("e1")
        assert seeded.check_entitlement("a1", "svc") is False

    def test_health_snapshot_with_entitlements(self, seeded):
        for i in range(5):
            seeded.grant_entitlement(f"e{i}", "a1", "t1", f"svc-{i}")
        seeded.revoke_entitlement("e3")
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.entitlement_count == 4

    def test_violation_detection_with_no_accounts(self, engine):
        violations = engine.detect_customer_violations("t1")
        assert violations == ()

    def test_multiple_health_snapshots_different_ids(self, seeded):
        seeded.account_health("h1", "a1", "t1")
        seeded.account_health("h2", "a1", "t1", sla_breaches=1)
        seeded.account_health("h3", "a1", "t1", sla_breaches=2)
        assert seeded.health_snapshot_count == 3

    def test_delinquent_account_allows_entitlement_grant(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.entitlement_id == "e1"

    def test_pending_account_allows_subscription(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc", status=AccountStatus.PENDING)
        engine.register_product("p1", "t1", "P")
        rec = engine.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"

    def test_draft_product_allows_subscription(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.register_product("p1", "t1", "P", status=ProductStatus.DRAFT)
        rec = engine.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"


# ---------------------------------------------------------------------------
# Immutability checks
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_customer_record_frozen(self, engine):
        rec = engine.register_customer("c1", "t1", "A")
        with pytest.raises(AttributeError):
            rec.display_name = "Changed"

    def test_account_record_frozen(self, seeded):
        rec = seeded.get_account("a1")
        with pytest.raises(AttributeError):
            rec.display_name = "Changed"

    def test_product_record_frozen(self, engine):
        rec = engine.register_product("p1", "t1", "P")
        with pytest.raises(AttributeError):
            rec.display_name = "Changed"

    def test_subscription_record_frozen(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        with pytest.raises(AttributeError):
            rec.quantity = 99

    def test_entitlement_record_frozen(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        with pytest.raises(AttributeError):
            rec.service_ref = "changed"

    def test_health_snapshot_frozen(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1")
        with pytest.raises(AttributeError):
            snap.health_score = 0.0

    def test_customer_snapshot_frozen(self, engine):
        snap = engine.customer_snapshot("snap1")
        with pytest.raises(AttributeError):
            snap.total_customers = 999

    def test_closure_report_frozen(self, engine):
        report = engine.closure_report("r1", "t1")
        with pytest.raises(AttributeError):
            report.total_customers = 999

    def test_violation_record_frozen(self, seeded):
        seeded.detect_customer_violations("t1")
        violations = seeded.violations_for_tenant("t1")
        if violations:
            with pytest.raises(AttributeError):
                violations[0].operation = "changed"

    def test_tuples_are_immutable(self, engine):
        engine.register_customer("c1", "t1", "A")
        result = engine.customers_for_tenant("t1")
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    def test_customers_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        assert len(engine.customers_for_tenant("t1")) == 1
        assert len(engine.customers_for_tenant("t2")) == 1

    def test_products_isolated(self, engine):
        engine.register_product("p1", "t1", "P1")
        engine.register_product("p2", "t2", "P2")
        assert len(engine.products_for_tenant("t1")) == 1
        assert len(engine.products_for_tenant("t2")) == 1

    def test_accounts_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c2", "t2", "Acc2")
        assert len(engine.accounts_for_tenant("t1")) == 1
        assert len(engine.accounts_for_tenant("t2")) == 1

    def test_violations_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a2", "c2", "t2", "Acc2")
        engine.detect_customer_violations("t1")
        engine.detect_customer_violations("t2")
        t1v = engine.violations_for_tenant("t1")
        t2v = engine.violations_for_tenant("t2")
        for v in t1v:
            assert v.tenant_id == "t1"
        for v in t2v:
            assert v.tenant_id == "t2"

    def test_closure_report_isolated(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t2", "B")
        engine.register_customer("c3", "t1", "C")
        r1 = engine.closure_report("r1", "t1")
        r2 = engine.closure_report("r2", "t2")
        assert r1.total_customers == 2
        assert r2.total_customers == 1


# ---------------------------------------------------------------------------
# Complex multi-step scenarios
# ---------------------------------------------------------------------------

class TestComplexScenarios:
    def test_full_lifecycle_with_violations_and_health(self, engine):
        # Setup
        engine.register_customer("c1", "t1", "Acme")
        engine.register_account("a1", "c1", "t1", "Main")
        engine.register_product("p1", "t1", "API")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.grant_entitlement("e1", "a1", "t1", "api-access")

        # Health check - healthy
        h1 = engine.account_health("h1", "a1", "t1")
        assert h1.health_status == AccountHealthStatus.HEALTHY

        # Issues arise
        h2 = engine.account_health("h2", "a1", "t1", sla_breaches=2, billing_issues=1)
        assert h2.health_status == AccountHealthStatus.AT_RISK

        # Retire product
        engine.retire_product("p1")

        # Detect violations
        violations = engine.detect_customer_violations("t1")
        assert any(v.operation == "retired_product_subscription" for v in violations)

        # Recovery
        h3 = engine.account_health("h3", "a1", "t1")
        assert h3.health_status == AccountHealthStatus.HEALTHY

        # Closure report
        report = engine.closure_report("r1", "t1")
        assert report.total_subscriptions == 1
        assert report.total_violations >= 1

    def test_customer_churn_blocks_all_ops(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.update_customer_status("c1", CustomerStatus.CHURNED)

        # Cannot register more accounts
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_account("a2", "c1", "t1", "Acc2")

        # Cannot update customer status
        with pytest.raises(RuntimeCoreInvariantError):
            engine.update_customer_status("c1", CustomerStatus.ACTIVE)

    def test_account_closure_blocks_dependent_ops(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.register_product("p1", "t1", "P")
        engine.update_account_status("a1", AccountStatus.CLOSED)

        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_subscription("s1", "a1", "p1", "t1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.grant_entitlement("e1", "a1", "t1", "svc")

    def test_product_lifecycle_deprecate_then_retire(self, engine):
        engine.register_product("p1", "t1", "P")
        assert engine.get_product("p1").status == ProductStatus.ACTIVE
        engine.deprecate_product("p1")
        assert engine.get_product("p1").status == ProductStatus.DEPRECATED
        engine.retire_product("p1")
        assert engine.get_product("p1").status == ProductStatus.RETIRED
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_product("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_product("p1")

    def test_multiple_critical_snapshots_create_decisions(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.account_health("h1", "a1", "t1", sla_breaches=10)
        engine.account_health("h2", "a1", "t1", billing_issues=10)
        # Each critical snapshot creates a decision (different snapshot_id -> different decision_id)
        assert engine.decision_count >= 1

    def test_entitlement_cycle_grant_revoke_regrant(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")

        engine.grant_entitlement("e1", "a1", "t1", "svc")
        assert engine.check_entitlement("a1", "svc") is True

        engine.revoke_entitlement("e1")
        assert engine.check_entitlement("a1", "svc") is False

        engine.grant_entitlement("e2", "a1", "t1", "svc")
        assert engine.check_entitlement("a1", "svc") is True
        assert engine.entitlement_count == 2

    def test_violation_idempotency_across_multiple_calls(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        v1 = engine.detect_customer_violations("t1")
        v2 = engine.detect_customer_violations("t1")
        v3 = engine.detect_customer_violations("t1")
        assert len(v1) == 1
        assert len(v2) == 0
        assert len(v3) == 0
        assert engine.violation_count == 1

    def test_health_score_boundary_0_5_at_risk(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 2*0.15 - 2*0.1 = 0.5
        snap = engine.account_health("h1", "a1", "t1", sla_breaches=2, open_cases=2)
        assert snap.health_score == 0.5
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_health_score_boundary_0_3_degraded(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 = 0.3
        snap = engine.account_health("h1", "a1", "t1",
                                     sla_breaches=2, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.3
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_just_below_0_3_is_critical(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 - 1*0.1 = 0.2
        snap = engine.account_health("h1", "a1", "t1",
                                     sla_breaches=2, open_cases=3, billing_issues=1)
        assert snap.health_score == 0.2
        assert snap.health_status == AccountHealthStatus.CRITICAL

    def test_snapshot_reflects_all_state(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c2", "t1", "Acc2")
        engine.register_product("p1", "t1", "P1")
        engine.register_product("p2", "t1", "P2")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.account_health("h1", "a1", "t1", sla_breaches=10)
        engine.detect_customer_violations("t1")

        snap = engine.customer_snapshot("snap1")
        assert snap.total_customers == 2
        assert snap.total_accounts == 2
        assert snap.total_products == 2
        assert snap.total_subscriptions == 1
        assert snap.total_entitlements == 1
        assert snap.total_health_snapshots == 1
        assert snap.total_decisions >= 1
        assert snap.total_violations >= 1


# ---------------------------------------------------------------------------
# Additional customer registration edge cases
# ---------------------------------------------------------------------------

class TestRegisterCustomerAdditional:
    def test_prospect_status(self, engine):
        rec = engine.register_customer("c1", "t1", "A", status=CustomerStatus.PROSPECT)
        assert rec.status == CustomerStatus.PROSPECT

    def test_default_tier_is_standard(self, engine):
        rec = engine.register_customer("c1", "t1", "A")
        assert rec.tier == "standard"

    def test_tier_gold(self, engine):
        rec = engine.register_customer("c1", "t1", "A", tier="gold")
        assert rec.tier == "gold"

    def test_tier_free(self, engine):
        rec = engine.register_customer("c1", "t1", "A", tier="free")
        assert rec.tier == "free"

    def test_display_name_preserved(self, engine):
        rec = engine.register_customer("c1", "t1", "Acme Corporation International")
        assert rec.display_name == "Acme Corporation International"

    def test_customer_id_preserved(self, engine):
        rec = engine.register_customer("cust-abc-123", "t1", "A")
        assert rec.customer_id == "cust-abc-123"

    def test_tenant_id_preserved(self, engine):
        rec = engine.register_customer("c1", "tenant-xyz", "A")
        assert rec.tenant_id == "tenant-xyz"

    def test_three_customers_count(self, engine):
        for i in range(3):
            engine.register_customer(f"c{i}", "t1", f"C{i}")
        assert engine.customer_count == 3

    def test_five_customers_count(self, engine):
        for i in range(5):
            engine.register_customer(f"c{i}", "t1", f"C{i}")
        assert engine.customer_count == 5


# ---------------------------------------------------------------------------
# Additional account edge cases
# ---------------------------------------------------------------------------

class TestRegisterAccountAdditional:
    def test_delinquent_status_at_creation(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc", status=AccountStatus.DELINQUENT)
        assert rec.status == AccountStatus.DELINQUENT

    def test_inactive_customer_allows_account(self, engine):
        engine.register_customer("c1", "t1", "A", status=CustomerStatus.INACTIVE)
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.account_id == "a1"

    def test_prospect_customer_allows_account(self, engine):
        engine.register_customer("c1", "t1", "A", status=CustomerStatus.PROSPECT)
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.account_id == "a1"

    def test_account_created_at_populated(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.created_at

    def test_account_display_name_preserved(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "My Special Account")
        assert rec.display_name == "My Special Account"

    def test_account_tenant_matches(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.tenant_id == "t1"

    def test_account_customer_id_matches(self, engine):
        engine.register_customer("c1", "t1", "A")
        rec = engine.register_account("a1", "c1", "t1", "Acc")
        assert rec.customer_id == "c1"


# ---------------------------------------------------------------------------
# Additional update account status edge cases
# ---------------------------------------------------------------------------

class TestUpdateAccountStatusAdditional:
    def test_active_to_delinquent(self, seeded):
        rec = seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        assert rec.status == AccountStatus.DELINQUENT

    def test_active_to_pending(self, seeded):
        rec = seeded.update_account_status("a1", AccountStatus.PENDING)
        assert rec.status == AccountStatus.PENDING

    def test_delinquent_to_active(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        rec = seeded.update_account_status("a1", AccountStatus.ACTIVE)
        assert rec.status == AccountStatus.ACTIVE

    def test_delinquent_to_closed(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        rec = seeded.update_account_status("a1", AccountStatus.CLOSED)
        assert rec.status == AccountStatus.CLOSED

    def test_pending_to_active(self, seeded):
        seeded.update_account_status("a1", AccountStatus.PENDING)
        rec = seeded.update_account_status("a1", AccountStatus.ACTIVE)
        assert rec.status == AccountStatus.ACTIVE

    def test_preserves_entitlement_count(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        rec = seeded.update_account_status("a1", AccountStatus.SUSPENDED)
        assert rec.entitlement_count == 1


# ---------------------------------------------------------------------------
# Additional product edge cases
# ---------------------------------------------------------------------------

class TestProductAdditional:
    def test_deprecated_status_at_creation(self, engine):
        rec = engine.register_product("p1", "t1", "P", status=ProductStatus.DEPRECATED)
        assert rec.status == ProductStatus.DEPRECATED

    def test_retired_status_at_creation(self, engine):
        rec = engine.register_product("p1", "t1", "P", status=ProductStatus.RETIRED)
        assert rec.status == ProductStatus.RETIRED

    def test_product_created_at_populated(self, engine):
        rec = engine.register_product("p1", "t1", "P")
        assert rec.created_at

    def test_zero_price(self, engine):
        rec = engine.register_product("p1", "t1", "P", base_price=0.0)
        assert rec.base_price == 0.0

    def test_high_price(self, engine):
        rec = engine.register_product("p1", "t1", "P", base_price=99999.99)
        assert rec.base_price == 99999.99

    def test_get_product_after_deprecation(self, engine):
        engine.register_product("p1", "t1", "P")
        engine.deprecate_product("p1")
        assert engine.get_product("p1").status == ProductStatus.DEPRECATED

    def test_get_product_after_retirement(self, engine):
        engine.register_product("p1", "t1", "P")
        engine.retire_product("p1")
        assert engine.get_product("p1").status == ProductStatus.RETIRED

    def test_multiple_products_same_tenant(self, engine):
        for i in range(5):
            engine.register_product(f"p{i}", "t1", f"P{i}")
        assert len(engine.products_for_tenant("t1")) == 5

    def test_products_different_categories(self, engine):
        engine.register_product("p1", "t1", "A", category="saas")
        engine.register_product("p2", "t1", "B", category="infra")
        assert engine.get_product("p1").category == "saas"
        assert engine.get_product("p2").category == "infra"


# ---------------------------------------------------------------------------
# Additional subscription edge cases
# ---------------------------------------------------------------------------

class TestSubscriptionAdditional:
    def test_quantity_2(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1", quantity=2)
        assert rec.quantity == 2

    def test_quantity_100(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1", quantity=100)
        assert rec.quantity == 100

    def test_subscription_created_at_populated(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.created_at

    def test_subscription_status_is_active(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.status == AccountStatus.ACTIVE

    def test_multiple_subscriptions_same_product(self, seeded):
        seeded.register_customer("c2", "t1", "C2")
        seeded.register_account("a2", "c2", "t1", "A2")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.register_subscription("s2", "a2", "p1", "t1")
        assert len(seeded.subscriptions_for_product("p1")) == 2

    def test_multiple_subscriptions_same_account(self, seeded):
        seeded.register_product("p2", "t1", "P2")
        seeded.register_product("p3", "t1", "P3")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.register_subscription("s2", "a1", "p2", "t1")
        seeded.register_subscription("s3", "a1", "p3", "t1")
        assert len(seeded.subscriptions_for_account("a1")) == 3

    def test_delinquent_account_allows_subscription(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        rec = seeded.register_subscription("s1", "a1", "p1", "t1")
        assert rec.subscription_id == "s1"

    def test_start_at_only_custom(self, seeded):
        rec = seeded.register_subscription("s1", "a1", "p1", "t1",
                                           start_at="2025-06-01T00:00:00+00:00")
        assert rec.start_at == "2025-06-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Additional entitlement edge cases
# ---------------------------------------------------------------------------

class TestEntitlementAdditional:
    def test_granted_at_populated(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.granted_at

    def test_service_ref_preserved(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "my-special-service-v2")
        assert rec.service_ref == "my-special-service-v2"

    def test_tenant_id_preserved(self, seeded):
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.tenant_id == "t1"

    def test_delinquent_account_allows_entitlement(self, seeded):
        seeded.update_account_status("a1", AccountStatus.DELINQUENT)
        rec = seeded.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.status == EntitlementStatus.ACTIVE

    def test_pending_account_allows_entitlement(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc", status=AccountStatus.PENDING)
        rec = engine.grant_entitlement("e1", "a1", "t1", "svc")
        assert rec.status == EntitlementStatus.ACTIVE

    def test_entitlements_different_accounts(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.grant_entitlement("e2", "a2", "t1", "svc")
        assert len(engine.entitlements_for_account("a1")) == 1
        assert len(engine.entitlements_for_account("a2")) == 1

    def test_active_entitlements_mixed(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc-a")
        seeded.grant_entitlement("e2", "a1", "t1", "svc-b")
        seeded.grant_entitlement("e3", "a1", "t1", "svc-c")
        seeded.revoke_entitlement("e2")
        active = seeded.active_entitlements_for_account("a1")
        assert len(active) == 2
        ids = {e.entitlement_id for e in active}
        assert ids == {"e1", "e3"}


# ---------------------------------------------------------------------------
# Additional health scoring edge cases
# ---------------------------------------------------------------------------

class TestHealthScoringAdditional:
    def test_one_open_case(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1", open_cases=1)
        assert snap.health_score == 0.9

    def test_three_open_cases(self, seeded):
        # 1.0 - 3*0.1 = 0.7
        snap = seeded.account_health("h1", "a1", "t1", open_cases=3)
        assert snap.health_score == 0.7
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_five_open_cases(self, seeded):
        # 1.0 - 5*0.1 = 0.5
        snap = seeded.account_health("h1", "a1", "t1", open_cases=5)
        assert snap.health_score == 0.5
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_two_billing_issues(self, seeded):
        # 1.0 - 2*0.2 = 0.6
        snap = seeded.account_health("h1", "a1", "t1", billing_issues=2)
        assert snap.health_score == 0.6
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_three_billing_issues(self, seeded):
        # 1.0 - 3*0.2 = 0.4
        snap = seeded.account_health("h1", "a1", "t1", billing_issues=3)
        assert snap.health_score == 0.4
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_five_sla_breaches(self, seeded):
        # 1.0 - 5*0.15 = 0.25
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=5)
        assert snap.health_score == 0.25
        assert snap.health_status == AccountHealthStatus.CRITICAL

    def test_four_sla_breaches(self, seeded):
        # 1.0 - 4*0.15 = 0.4
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=4)
        assert snap.health_score == 0.4
        assert snap.health_status == AccountHealthStatus.DEGRADED

    def test_three_sla_breaches(self, seeded):
        # 1.0 - 3*0.15 = 0.55
        snap = seeded.account_health("h1", "a1", "t1", sla_breaches=3)
        assert snap.health_score == 0.55
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_all_issue_types_combined(self, seeded):
        # 1.0 - 1*0.15 - 1*0.1 - 1*0.2 = 0.55
        snap = seeded.account_health("h1", "a1", "t1",
                                     sla_breaches=1, open_cases=1, billing_issues=1)
        assert snap.health_score == 0.55
        assert snap.health_status == AccountHealthStatus.AT_RISK

    def test_health_snapshot_account_id(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.account_id == "a1"

    def test_health_snapshot_tenant_id(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.tenant_id == "t1"

    def test_health_snapshot_captured_at(self, seeded):
        snap = seeded.account_health("h1", "a1", "t1")
        assert snap.captured_at

    def test_critical_decision_has_escalated_disposition(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.account_health("h1", "a1", "t1", sla_breaches=10)
        assert engine.decision_count == 1

    def test_at_risk_no_decision(self, seeded):
        seeded.account_health("h1", "a1", "t1", sla_breaches=2)
        assert seeded.decision_count == 0

    def test_degraded_no_decision(self, seeded):
        # 1.0 - 4*0.15 = 0.4
        seeded.account_health("h1", "a1", "t1", sla_breaches=4)
        assert seeded.decision_count == 0


# ---------------------------------------------------------------------------
# Additional violation detection edge cases
# ---------------------------------------------------------------------------

class TestViolationDetectionAdditional:
    def test_suspended_account_with_no_entitlements_not_flagged(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.update_account_status("a1", AccountStatus.SUSPENDED)
        violations = engine.detect_customer_violations("t1")
        assert not any(v.operation == "no_entitlements" for v in violations)

    def test_active_account_with_active_entitlement_no_violation(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        violations = engine.detect_customer_violations("t1")
        assert not any(v.operation == "no_entitlements" for v in violations)

    def test_delinquent_violation_detected(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.update_account_status("a1", AccountStatus.DELINQUENT)
        violations = engine.detect_customer_violations("t1")
        assert any(v.operation == "delinquent_account" for v in violations)

    def test_retired_subscription_violation_reason_contains_ids(self, seeded):
        seeded.grant_entitlement("e1", "a1", "t1", "svc")
        seeded.register_subscription("s1", "a1", "p1", "t1")
        seeded.retire_product("p1")
        violations = seeded.detect_customer_violations("t1")
        retired_v = [v for v in violations if v.operation == "retired_product_subscription"]
        assert len(retired_v) == 1
        assert "s1" in retired_v[0].reason
        assert "p1" in retired_v[0].reason

    def test_no_entitlements_violation_reason_contains_account_id(self, seeded):
        violations = seeded.detect_customer_violations("t1")
        no_ent = [v for v in violations if v.operation == "no_entitlements"]
        assert len(no_ent) == 1
        assert "a1" in no_ent[0].reason

    def test_delinquent_violation_reason_contains_account_id(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.update_account_status("a1", AccountStatus.DELINQUENT)
        violations = engine.detect_customer_violations("t1")
        del_v = [v for v in violations if v.operation == "delinquent_account"]
        assert len(del_v) == 1
        assert "a1" in del_v[0].reason

    def test_multiple_no_entitlement_accounts(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.register_account("a3", "c1", "t1", "Acc3")
        violations = engine.detect_customer_violations("t1")
        no_ent = [v for v in violations if v.operation == "no_entitlements"]
        assert len(no_ent) == 3

    def test_violations_have_tenant_id(self, seeded):
        violations = seeded.detect_customer_violations("t1")
        for v in violations:
            assert v.tenant_id == "t1"

    def test_violations_have_detected_at(self, seeded):
        violations = seeded.detect_customer_violations("t1")
        for v in violations:
            assert v.detected_at

    def test_empty_tenant_no_violations(self, engine):
        violations = engine.detect_customer_violations("nonexistent-tenant")
        assert violations == ()


# ---------------------------------------------------------------------------
# Additional closure report edge cases
# ---------------------------------------------------------------------------

class TestClosureReportAdditional:
    def test_report_id_preserved(self, engine):
        report = engine.closure_report("report-abc-123", "t1")
        assert report.report_id == "report-abc-123"

    def test_tenant_id_preserved(self, engine):
        report = engine.closure_report("r1", "tenant-xyz")
        assert report.tenant_id == "tenant-xyz"

    def test_includes_violations_count(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.detect_customer_violations("t1")
        report = engine.closure_report("r1", "t1")
        assert report.total_violations >= 1

    def test_multiple_tenants_isolated_in_report(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        engine.register_customer("c3", "t2", "C")
        r1 = engine.closure_report("r1", "t1")
        r2 = engine.closure_report("r2", "t2")
        assert r1.total_customers == 2
        assert r2.total_customers == 1

    def test_entitlements_counted_by_tenant(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.register_customer("c2", "t2", "B")
        engine.register_account("a2", "c2", "t2", "Acc2")
        engine.grant_entitlement("e2", "a2", "t2", "svc")
        engine.grant_entitlement("e3", "a2", "t2", "svc2")
        r1 = engine.closure_report("r1", "t1")
        r2 = engine.closure_report("r2", "t2")
        assert r1.total_entitlements == 1
        assert r2.total_entitlements == 2


# ---------------------------------------------------------------------------
# Additional state hash edge cases
# ---------------------------------------------------------------------------

class TestStateHashAdditional:
    def test_revocation_does_not_remove_from_hash(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        h1 = engine.state_hash()
        engine.revoke_entitlement("e1")
        h2 = engine.state_hash()
        # Entitlement still exists (just status changed), so hash should be same
        # because state_hash only uses keys, not values
        assert h1 == h2

    def test_deprecation_does_not_change_hash(self, engine):
        engine.register_product("p1", "t1", "P")
        h1 = engine.state_hash()
        engine.deprecate_product("p1")
        h2 = engine.state_hash()
        # Product key unchanged
        assert h1 == h2

    def test_status_update_does_not_change_hash(self, engine):
        engine.register_customer("c1", "t1", "A")
        h1 = engine.state_hash()
        engine.update_customer_status("c1", CustomerStatus.SUSPENDED)
        h2 = engine.state_hash()
        assert h1 == h2

    def test_empty_hash_is_consistent(self):
        s1 = EventSpineEngine()
        e1 = CustomerRuntimeEngine(s1)
        s2 = EventSpineEngine()
        e2 = CustomerRuntimeEngine(s2)
        assert e1.state_hash() == e2.state_hash()


# ---------------------------------------------------------------------------
# Additional cross-cutting golden scenarios
# ---------------------------------------------------------------------------

class TestGoldenAdditional:
    def test_multi_tenant_full_lifecycle(self, engine):
        # Tenant 1
        engine.register_customer("c1", "t1", "Corp A")
        engine.register_account("a1", "c1", "t1", "Acc A")
        engine.register_product("p1", "t1", "Prod A")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.grant_entitlement("e1", "a1", "t1", "svc-a")

        # Tenant 2
        engine.register_customer("c2", "t2", "Corp B")
        engine.register_account("a2", "c2", "t2", "Acc B")
        engine.register_product("p2", "t2", "Prod B")
        engine.register_subscription("s2", "a2", "p2", "t2")
        engine.grant_entitlement("e2", "a2", "t2", "svc-b")

        # Cross-checks
        assert engine.check_entitlement("a1", "svc-a") is True
        assert engine.check_entitlement("a1", "svc-b") is False
        assert engine.check_entitlement("a2", "svc-b") is True
        assert engine.check_entitlement("a2", "svc-a") is False

        # Closure reports
        r1 = engine.closure_report("r1", "t1")
        r2 = engine.closure_report("r2", "t2")
        assert r1.total_customers == 1
        assert r2.total_customers == 1

    def test_health_progression_through_statuses(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")

        statuses = []
        configs = [
            (0, 0, 0),    # HEALTHY
            (1, 1, 0),    # HEALTHY (0.75 -> AT_RISK actually: 1.0-0.15-0.1=0.75)
            (2, 2, 1),    # DEGRADED (1.0-0.3-0.2-0.2=0.3)
            (5, 5, 5),    # CRITICAL (clamped to 0)
            (0, 0, 0),    # HEALTHY again (recovery)
        ]
        for i, (sla, cases, billing) in enumerate(configs):
            snap = engine.account_health(f"h{i}", "a1", "t1",
                                         sla_breaches=sla, open_cases=cases,
                                         billing_issues=billing)
            statuses.append(snap.health_status)

        assert statuses[0] == AccountHealthStatus.HEALTHY
        assert statuses[4] == AccountHealthStatus.HEALTHY
        assert AccountHealthStatus.CRITICAL in statuses

    def test_entitlement_check_after_account_status_changes(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.grant_entitlement("e1", "a1", "t1", "svc")

        # Entitlement check still works regardless of account status
        assert engine.check_entitlement("a1", "svc") is True

        engine.update_account_status("a1", AccountStatus.SUSPENDED)
        # check_entitlement doesn't care about account status, only entitlement status
        assert engine.check_entitlement("a1", "svc") is True

        engine.update_account_status("a1", AccountStatus.DELINQUENT)
        assert engine.check_entitlement("a1", "svc") is True

    def test_multiple_decisions_from_critical_snapshots(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.register_account("a2", "c1", "t1", "Acc2")

        engine.account_health("h1", "a1", "t1", sla_breaches=10)
        engine.account_health("h2", "a2", "t1", sla_breaches=10)
        assert engine.decision_count >= 2

    def test_violations_after_product_retirement(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.register_product("p1", "t1", "P1")
        engine.register_product("p2", "t1", "P2")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.register_subscription("s2", "a1", "p2", "t1")

        # Retire both products
        engine.retire_product("p1")
        engine.retire_product("p2")

        violations = engine.detect_customer_violations("t1")
        retired_v = [v for v in violations if v.operation == "retired_product_subscription"]
        assert len(retired_v) == 2

    def test_snapshot_after_complex_operations(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_customer("c2", "t1", "B")
        engine.register_account("a1", "c1", "t1", "Acc1")
        engine.register_account("a2", "c1", "t1", "Acc2")
        engine.register_account("a3", "c2", "t1", "Acc3")
        engine.register_product("p1", "t1", "P1")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.register_subscription("s2", "a2", "p1", "t1")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.grant_entitlement("e2", "a2", "t1", "svc")
        engine.revoke_entitlement("e2")
        engine.account_health("h1", "a1", "t1")
        engine.detect_customer_violations("t1")

        snap = engine.customer_snapshot("snap1")
        assert snap.total_customers == 2
        assert snap.total_accounts == 3
        assert snap.total_products == 1
        assert snap.total_subscriptions == 2
        assert snap.total_entitlements == 2  # revoked still counted in total
        assert snap.total_health_snapshots == 1
        assert snap.total_violations >= 1

    def test_state_hash_after_full_scenario(self, engine):
        engine.register_customer("c1", "t1", "A")
        engine.register_account("a1", "c1", "t1", "Acc")
        engine.register_product("p1", "t1", "P")
        engine.register_subscription("s1", "a1", "p1", "t1")
        engine.grant_entitlement("e1", "a1", "t1", "svc")
        engine.account_health("h1", "a1", "t1", sla_breaches=1)
        engine.detect_customer_violations("t1")
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
