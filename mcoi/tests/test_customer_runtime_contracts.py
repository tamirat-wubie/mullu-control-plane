"""Comprehensive tests for customer_runtime contracts.

Covers all 6 enums, 10 frozen dataclasses, validation logic,
frozen immutability, to_dict() round-trip, and metadata freezing.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.customer_runtime import (
    AccountHealthSnapshot,
    AccountHealthStatus,
    AccountRecord,
    AccountStatus,
    CustomerClosureReport,
    CustomerDecision,
    CustomerDisposition,
    CustomerRecord,
    CustomerSnapshot,
    CustomerStatus,
    CustomerViolation,
    EntitlementRecord,
    EntitlementStatus,
    ProductRecord,
    ProductStatus,
    SubscriptionRecord,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestCustomerStatusEnum:
    def test_members_count(self):
        assert len(CustomerStatus) == 5

    def test_active(self):
        assert CustomerStatus.ACTIVE.value == "active"

    def test_inactive(self):
        assert CustomerStatus.INACTIVE.value == "inactive"

    def test_suspended(self):
        assert CustomerStatus.SUSPENDED.value == "suspended"

    def test_churned(self):
        assert CustomerStatus.CHURNED.value == "churned"

    def test_prospect(self):
        assert CustomerStatus.PROSPECT.value == "prospect"

    def test_all_values_unique(self):
        vals = [m.value for m in CustomerStatus]
        assert len(vals) == len(set(vals))


class TestAccountStatusEnum:
    def test_members_count(self):
        assert len(AccountStatus) == 5

    def test_active(self):
        assert AccountStatus.ACTIVE.value == "active"

    def test_suspended(self):
        assert AccountStatus.SUSPENDED.value == "suspended"

    def test_closed(self):
        assert AccountStatus.CLOSED.value == "closed"

    def test_delinquent(self):
        assert AccountStatus.DELINQUENT.value == "delinquent"

    def test_pending(self):
        assert AccountStatus.PENDING.value == "pending"

    def test_all_values_unique(self):
        vals = [m.value for m in AccountStatus]
        assert len(vals) == len(set(vals))


class TestProductStatusEnum:
    def test_members_count(self):
        assert len(ProductStatus) == 4

    def test_active(self):
        assert ProductStatus.ACTIVE.value == "active"

    def test_draft(self):
        assert ProductStatus.DRAFT.value == "draft"

    def test_deprecated(self):
        assert ProductStatus.DEPRECATED.value == "deprecated"

    def test_retired(self):
        assert ProductStatus.RETIRED.value == "retired"

    def test_all_values_unique(self):
        vals = [m.value for m in ProductStatus]
        assert len(vals) == len(set(vals))


class TestEntitlementStatusEnum:
    def test_members_count(self):
        assert len(EntitlementStatus) == 4

    def test_active(self):
        assert EntitlementStatus.ACTIVE.value == "active"

    def test_expired(self):
        assert EntitlementStatus.EXPIRED.value == "expired"

    def test_revoked(self):
        assert EntitlementStatus.REVOKED.value == "revoked"

    def test_suspended(self):
        assert EntitlementStatus.SUSPENDED.value == "suspended"

    def test_all_values_unique(self):
        vals = [m.value for m in EntitlementStatus]
        assert len(vals) == len(set(vals))


class TestAccountHealthStatusEnum:
    def test_members_count(self):
        assert len(AccountHealthStatus) == 4

    def test_healthy(self):
        assert AccountHealthStatus.HEALTHY.value == "healthy"

    def test_at_risk(self):
        assert AccountHealthStatus.AT_RISK.value == "at_risk"

    def test_degraded(self):
        assert AccountHealthStatus.DEGRADED.value == "degraded"

    def test_critical(self):
        assert AccountHealthStatus.CRITICAL.value == "critical"

    def test_all_values_unique(self):
        vals = [m.value for m in AccountHealthStatus]
        assert len(vals) == len(set(vals))


class TestCustomerDispositionEnum:
    def test_members_count(self):
        assert len(CustomerDisposition) == 4

    def test_approved(self):
        assert CustomerDisposition.APPROVED.value == "approved"

    def test_denied(self):
        assert CustomerDisposition.DENIED.value == "denied"

    def test_escalated(self):
        assert CustomerDisposition.ESCALATED.value == "escalated"

    def test_deferred(self):
        assert CustomerDisposition.DEFERRED.value == "deferred"

    def test_all_values_unique(self):
        vals = [m.value for m in CustomerDisposition]
        assert len(vals) == len(set(vals))


# ---------------------------------------------------------------------------
# CustomerRecord
# ---------------------------------------------------------------------------


class TestCustomerRecord:
    def _make(self, **kw):
        defaults = dict(
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Acme",
            status=CustomerStatus.ACTIVE,
            tier="gold",
            account_count=3,
            created_at=NOW,
            metadata={"k": "v"},
        )
        defaults.update(kw)
        return CustomerRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.customer_id == "cust-1"
        assert r.tenant_id == "t-1"
        assert r.display_name == "Acme"
        assert r.status is CustomerStatus.ACTIVE
        assert r.tier == "gold"
        assert r.account_count == 3

    def test_empty_tier_allowed(self):
        r = self._make(tier="")
        assert r.tier == ""

    def test_zero_account_count(self):
        r = self._make(account_count=0)
        assert r.account_count == 0

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.customer_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"a": "b"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        r = self._make()
        d = r.to_dict()
        assert d["customer_id"] == "cust-1"
        assert d["status"] is CustomerStatus.ACTIVE
        assert isinstance(d["metadata"], dict)

    def test_to_dict_metadata_thawed(self):
        r = self._make(metadata={"x": [1, 2]})
        d = r.to_dict()
        assert isinstance(d["metadata"]["x"], list)

    # --- rejection: customer_id ---
    def test_reject_empty_customer_id(self):
        with pytest.raises(ValueError):
            self._make(customer_id="")

    def test_reject_whitespace_customer_id(self):
        with pytest.raises(ValueError):
            self._make(customer_id="   ")

    # --- rejection: tenant_id ---
    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_whitespace_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="  ")

    # --- rejection: display_name ---
    def test_reject_empty_display_name(self):
        with pytest.raises(ValueError):
            self._make(display_name="")

    # --- rejection: status ---
    def test_reject_string_status(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_reject_wrong_enum_status(self):
        with pytest.raises(ValueError):
            self._make(status=AccountStatus.ACTIVE)

    # --- rejection: account_count ---
    def test_reject_negative_account_count(self):
        with pytest.raises(ValueError):
            self._make(account_count=-1)

    def test_reject_bool_account_count(self):
        with pytest.raises(ValueError):
            self._make(account_count=True)

    # --- rejection: created_at ---
    def test_reject_empty_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_reject_garbage_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    # --- all status variants ---
    @pytest.mark.parametrize("st", list(CustomerStatus))
    def test_all_statuses(self, st):
        r = self._make(status=st)
        assert r.status is st

    def test_nested_metadata_frozen(self):
        r = self._make(metadata={"a": {"b": "c"}})
        assert isinstance(r.metadata["a"], MappingProxyType)


# ---------------------------------------------------------------------------
# AccountRecord
# ---------------------------------------------------------------------------


class TestAccountRecord:
    def _make(self, **kw):
        defaults = dict(
            account_id="acc-1",
            customer_id="cust-1",
            tenant_id="t-1",
            display_name="Main Account",
            status=AccountStatus.ACTIVE,
            contract_ref="CR-001",
            entitlement_count=5,
            created_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return AccountRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.account_id == "acc-1"
        assert r.customer_id == "cust-1"
        assert r.status is AccountStatus.ACTIVE
        assert r.entitlement_count == 5

    def test_empty_contract_ref_allowed(self):
        r = self._make(contract_ref="")
        assert r.contract_ref == ""

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.account_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["account_id"] == "acc-1"
        assert d["status"] is AccountStatus.ACTIVE

    def test_reject_empty_account_id(self):
        with pytest.raises(ValueError):
            self._make(account_id="")

    def test_reject_empty_customer_id(self):
        with pytest.raises(ValueError):
            self._make(customer_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_empty_display_name(self):
        with pytest.raises(ValueError):
            self._make(display_name="")

    def test_reject_string_status(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_reject_wrong_enum_status(self):
        with pytest.raises(ValueError):
            self._make(status=CustomerStatus.ACTIVE)

    def test_reject_negative_entitlement_count(self):
        with pytest.raises(ValueError):
            self._make(entitlement_count=-1)

    def test_reject_bool_entitlement_count(self):
        with pytest.raises(ValueError):
            self._make(entitlement_count=False)

    def test_reject_bad_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="nope")

    def test_zero_entitlement_count(self):
        r = self._make(entitlement_count=0)
        assert r.entitlement_count == 0

    @pytest.mark.parametrize("st", list(AccountStatus))
    def test_all_statuses(self, st):
        r = self._make(status=st)
        assert r.status is st


# ---------------------------------------------------------------------------
# ProductRecord
# ---------------------------------------------------------------------------


class TestProductRecord:
    def _make(self, **kw):
        defaults = dict(
            product_id="prod-1",
            tenant_id="t-1",
            display_name="Widget",
            status=ProductStatus.ACTIVE,
            category="SaaS",
            base_price=99.99,
            created_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return ProductRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.product_id == "prod-1"
        assert r.base_price == 99.99

    def test_empty_category_allowed(self):
        r = self._make(category="")
        assert r.category == ""

    def test_zero_base_price(self):
        r = self._make(base_price=0.0)
        assert r.base_price == 0.0

    def test_int_base_price_coerced(self):
        r = self._make(base_price=10)
        assert r.base_price == 10.0

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.product_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["product_id"] == "prod-1"
        assert d["status"] is ProductStatus.ACTIVE

    def test_reject_empty_product_id(self):
        with pytest.raises(ValueError):
            self._make(product_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_empty_display_name(self):
        with pytest.raises(ValueError):
            self._make(display_name="")

    def test_reject_string_status(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_reject_wrong_enum_status(self):
        with pytest.raises(ValueError):
            self._make(status=AccountStatus.ACTIVE)

    def test_reject_negative_base_price(self):
        with pytest.raises(ValueError):
            self._make(base_price=-0.01)

    def test_reject_nan_base_price(self):
        with pytest.raises(ValueError):
            self._make(base_price=float("nan"))

    def test_reject_inf_base_price(self):
        with pytest.raises(ValueError):
            self._make(base_price=float("inf"))

    def test_reject_bool_base_price(self):
        with pytest.raises(ValueError):
            self._make(base_price=True)

    def test_reject_bad_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="garbage")

    @pytest.mark.parametrize("st", list(ProductStatus))
    def test_all_statuses(self, st):
        r = self._make(status=st)
        assert r.status is st


# ---------------------------------------------------------------------------
# SubscriptionRecord
# ---------------------------------------------------------------------------


class TestSubscriptionRecord:
    def _make(self, **kw):
        defaults = dict(
            subscription_id="sub-1",
            account_id="acc-1",
            product_id="prod-1",
            tenant_id="t-1",
            status=AccountStatus.ACTIVE,
            quantity=5,
            start_at=NOW,
            end_at=NOW,
            created_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return SubscriptionRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.subscription_id == "sub-1"
        assert r.quantity == 5

    def test_quantity_one(self):
        r = self._make(quantity=1)
        assert r.quantity == 1

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.subscription_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["subscription_id"] == "sub-1"
        assert d["status"] is AccountStatus.ACTIVE

    def test_reject_empty_subscription_id(self):
        with pytest.raises(ValueError):
            self._make(subscription_id="")

    def test_reject_empty_account_id(self):
        with pytest.raises(ValueError):
            self._make(account_id="")

    def test_reject_empty_product_id(self):
        with pytest.raises(ValueError):
            self._make(product_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_string_status(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_reject_wrong_enum_status(self):
        with pytest.raises(ValueError):
            self._make(status=CustomerStatus.ACTIVE)

    def test_reject_zero_quantity(self):
        with pytest.raises(ValueError):
            self._make(quantity=0)

    def test_reject_negative_quantity(self):
        with pytest.raises(ValueError):
            self._make(quantity=-1)

    def test_reject_bool_quantity(self):
        with pytest.raises(ValueError):
            self._make(quantity=True)

    def test_reject_bad_start_at(self):
        with pytest.raises(ValueError):
            self._make(start_at="bad")

    def test_reject_bad_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    @pytest.mark.parametrize("st", list(AccountStatus))
    def test_all_statuses(self, st):
        r = self._make(status=st)
        assert r.status is st


# ---------------------------------------------------------------------------
# EntitlementRecord
# ---------------------------------------------------------------------------


class TestEntitlementRecord:
    def _make(self, **kw):
        defaults = dict(
            entitlement_id="ent-1",
            account_id="acc-1",
            tenant_id="t-1",
            service_ref="svc-A",
            status=EntitlementStatus.ACTIVE,
            granted_at=NOW,
            expires_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return EntitlementRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.entitlement_id == "ent-1"
        assert r.service_ref == "svc-A"
        assert r.status is EntitlementStatus.ACTIVE

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.entitlement_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["entitlement_id"] == "ent-1"
        assert d["status"] is EntitlementStatus.ACTIVE

    def test_reject_empty_entitlement_id(self):
        with pytest.raises(ValueError):
            self._make(entitlement_id="")

    def test_reject_empty_account_id(self):
        with pytest.raises(ValueError):
            self._make(account_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_empty_service_ref(self):
        with pytest.raises(ValueError):
            self._make(service_ref="")

    def test_reject_string_status(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_reject_wrong_enum_status(self):
        with pytest.raises(ValueError):
            self._make(status=AccountStatus.ACTIVE)

    def test_reject_bad_granted_at(self):
        with pytest.raises(ValueError):
            self._make(granted_at="nope")

    @pytest.mark.parametrize("st", list(EntitlementStatus))
    def test_all_statuses(self, st):
        r = self._make(status=st)
        assert r.status is st


# ---------------------------------------------------------------------------
# AccountHealthSnapshot
# ---------------------------------------------------------------------------


class TestAccountHealthSnapshot:
    def _make(self, **kw):
        defaults = dict(
            snapshot_id="snap-1",
            account_id="acc-1",
            tenant_id="t-1",
            health_status=AccountHealthStatus.HEALTHY,
            health_score=0.95,
            sla_breaches=0,
            open_cases=2,
            billing_issues=0,
            entitlement_count=10,
            captured_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return AccountHealthSnapshot(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.snapshot_id == "snap-1"
        assert r.health_score == 0.95
        assert r.health_status is AccountHealthStatus.HEALTHY

    def test_health_score_zero(self):
        r = self._make(health_score=0.0)
        assert r.health_score == 0.0

    def test_health_score_one(self):
        r = self._make(health_score=1.0)
        assert r.health_score == 1.0

    def test_health_score_int_zero(self):
        r = self._make(health_score=0)
        assert r.health_score == 0.0

    def test_health_score_int_one(self):
        r = self._make(health_score=1)
        assert r.health_score == 1.0

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.snapshot_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["snapshot_id"] == "snap-1"
        assert d["health_status"] is AccountHealthStatus.HEALTHY

    def test_reject_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_reject_empty_account_id(self):
        with pytest.raises(ValueError):
            self._make(account_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_string_health_status(self):
        with pytest.raises(ValueError):
            self._make(health_status="healthy")

    def test_reject_wrong_enum_health_status(self):
        with pytest.raises(ValueError):
            self._make(health_status=CustomerStatus.ACTIVE)

    def test_reject_health_score_above_one(self):
        with pytest.raises(ValueError):
            self._make(health_score=1.01)

    def test_reject_health_score_below_zero(self):
        with pytest.raises(ValueError):
            self._make(health_score=-0.01)

    def test_reject_health_score_nan(self):
        with pytest.raises(ValueError):
            self._make(health_score=float("nan"))

    def test_reject_health_score_inf(self):
        with pytest.raises(ValueError):
            self._make(health_score=float("inf"))

    def test_reject_health_score_bool(self):
        with pytest.raises(ValueError):
            self._make(health_score=True)

    def test_reject_negative_sla_breaches(self):
        with pytest.raises(ValueError):
            self._make(sla_breaches=-1)

    def test_reject_negative_open_cases(self):
        with pytest.raises(ValueError):
            self._make(open_cases=-1)

    def test_reject_negative_billing_issues(self):
        with pytest.raises(ValueError):
            self._make(billing_issues=-1)

    def test_reject_negative_entitlement_count(self):
        with pytest.raises(ValueError):
            self._make(entitlement_count=-1)

    def test_reject_bool_sla_breaches(self):
        with pytest.raises(ValueError):
            self._make(sla_breaches=True)

    def test_reject_bool_open_cases(self):
        with pytest.raises(ValueError):
            self._make(open_cases=True)

    def test_reject_bool_billing_issues(self):
        with pytest.raises(ValueError):
            self._make(billing_issues=False)

    def test_reject_bool_entitlement_count(self):
        with pytest.raises(ValueError):
            self._make(entitlement_count=True)

    def test_reject_bad_captured_at(self):
        with pytest.raises(ValueError):
            self._make(captured_at="nope")

    @pytest.mark.parametrize("st", list(AccountHealthStatus))
    def test_all_statuses(self, st):
        r = self._make(health_status=st)
        assert r.health_status is st

    def test_all_zero_counters(self):
        r = self._make(sla_breaches=0, open_cases=0, billing_issues=0, entitlement_count=0)
        assert r.sla_breaches == 0
        assert r.open_cases == 0
        assert r.billing_issues == 0
        assert r.entitlement_count == 0


# ---------------------------------------------------------------------------
# CustomerDecision
# ---------------------------------------------------------------------------


class TestCustomerDecision:
    def _make(self, **kw):
        defaults = dict(
            decision_id="dec-1",
            tenant_id="t-1",
            customer_id="cust-1",
            account_id="acc-1",
            disposition=CustomerDisposition.APPROVED,
            reason="looks good",
            decided_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return CustomerDecision(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.decision_id == "dec-1"
        assert r.disposition is CustomerDisposition.APPROVED
        assert r.reason == "looks good"

    def test_empty_account_id_allowed(self):
        r = self._make(account_id="")
        assert r.account_id == ""

    def test_empty_reason_allowed(self):
        r = self._make(reason="")
        assert r.reason == ""

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.decision_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["decision_id"] == "dec-1"
        assert d["disposition"] is CustomerDisposition.APPROVED

    def test_reject_empty_decision_id(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_empty_customer_id(self):
        with pytest.raises(ValueError):
            self._make(customer_id="")

    def test_reject_string_disposition(self):
        with pytest.raises(ValueError):
            self._make(disposition="approved")

    def test_reject_wrong_enum_disposition(self):
        with pytest.raises(ValueError):
            self._make(disposition=CustomerStatus.ACTIVE)

    def test_reject_bad_decided_at(self):
        with pytest.raises(ValueError):
            self._make(decided_at="nope")

    @pytest.mark.parametrize("disp", list(CustomerDisposition))
    def test_all_dispositions(self, disp):
        r = self._make(disposition=disp)
        assert r.disposition is disp


# ---------------------------------------------------------------------------
# CustomerViolation
# ---------------------------------------------------------------------------


class TestCustomerViolation:
    def _make(self, **kw):
        defaults = dict(
            violation_id="viol-1",
            tenant_id="t-1",
            operation="create_account",
            reason="duplicate found",
            detected_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return CustomerViolation(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.violation_id == "viol-1"
        assert r.operation == "create_account"
        assert r.reason == "duplicate found"

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.violation_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["violation_id"] == "viol-1"
        assert isinstance(d["metadata"], dict)

    def test_to_json(self):
        r = self._make(metadata={})
        j = r.to_json()
        assert '"violation_id"' in j
        assert '"viol-1"' in j

    def test_reject_empty_violation_id(self):
        with pytest.raises(ValueError):
            self._make(violation_id="")

    def test_reject_whitespace_violation_id(self):
        with pytest.raises(ValueError):
            self._make(violation_id="   ")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_empty_operation(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_reject_empty_reason(self):
        with pytest.raises(ValueError):
            self._make(reason="")

    def test_reject_bad_detected_at(self):
        with pytest.raises(ValueError):
            self._make(detected_at="nope")

    def test_reject_empty_detected_at(self):
        with pytest.raises(ValueError):
            self._make(detected_at="")


# ---------------------------------------------------------------------------
# CustomerSnapshot
# ---------------------------------------------------------------------------


class TestCustomerSnapshot:
    def _make(self, **kw):
        defaults = dict(
            snapshot_id="snap-1",
            total_customers=10,
            total_accounts=20,
            total_products=5,
            total_subscriptions=15,
            total_entitlements=30,
            total_health_snapshots=8,
            total_decisions=3,
            total_violations=1,
            captured_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return CustomerSnapshot(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.snapshot_id == "snap-1"
        assert r.total_customers == 10
        assert r.total_accounts == 20

    def test_all_zeros(self):
        r = self._make(
            total_customers=0, total_accounts=0, total_products=0,
            total_subscriptions=0, total_entitlements=0,
            total_health_snapshots=0, total_decisions=0, total_violations=0,
        )
        assert r.total_customers == 0

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.snapshot_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["snapshot_id"] == "snap-1"
        assert d["total_customers"] == 10

    def test_to_json(self):
        r = self._make(metadata={})
        j = r.to_json()
        assert '"snap-1"' in j

    def test_reject_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_reject_negative_total_customers(self):
        with pytest.raises(ValueError):
            self._make(total_customers=-1)

    def test_reject_negative_total_accounts(self):
        with pytest.raises(ValueError):
            self._make(total_accounts=-1)

    def test_reject_negative_total_products(self):
        with pytest.raises(ValueError):
            self._make(total_products=-1)

    def test_reject_negative_total_subscriptions(self):
        with pytest.raises(ValueError):
            self._make(total_subscriptions=-1)

    def test_reject_negative_total_entitlements(self):
        with pytest.raises(ValueError):
            self._make(total_entitlements=-1)

    def test_reject_negative_total_health_snapshots(self):
        with pytest.raises(ValueError):
            self._make(total_health_snapshots=-1)

    def test_reject_negative_total_decisions(self):
        with pytest.raises(ValueError):
            self._make(total_decisions=-1)

    def test_reject_negative_total_violations(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_reject_bool_total_customers(self):
        with pytest.raises(ValueError):
            self._make(total_customers=True)

    def test_reject_bool_total_accounts(self):
        with pytest.raises(ValueError):
            self._make(total_accounts=False)

    def test_reject_bad_captured_at(self):
        with pytest.raises(ValueError):
            self._make(captured_at="nope")


# ---------------------------------------------------------------------------
# CustomerClosureReport
# ---------------------------------------------------------------------------


class TestCustomerClosureReport:
    def _make(self, **kw):
        defaults = dict(
            report_id="rpt-1",
            tenant_id="t-1",
            total_customers=10,
            total_accounts=20,
            total_products=5,
            total_subscriptions=15,
            total_entitlements=30,
            total_violations=2,
            closed_at=NOW,
            metadata={},
        )
        defaults.update(kw)
        return CustomerClosureReport(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.report_id == "rpt-1"
        assert r.tenant_id == "t-1"
        assert r.total_customers == 10

    def test_all_zeros(self):
        r = self._make(
            total_customers=0, total_accounts=0, total_products=0,
            total_subscriptions=0, total_entitlements=0, total_violations=0,
        )
        assert r.total_violations == 0

    def test_frozen(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.report_id = "x"

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["report_id"] == "rpt-1"
        assert isinstance(d["metadata"], dict)

    def test_to_json(self):
        r = self._make(metadata={})
        j = r.to_json()
        assert '"rpt-1"' in j

    def test_reject_empty_report_id(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_reject_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_reject_negative_total_customers(self):
        with pytest.raises(ValueError):
            self._make(total_customers=-1)

    def test_reject_negative_total_accounts(self):
        with pytest.raises(ValueError):
            self._make(total_accounts=-1)

    def test_reject_negative_total_products(self):
        with pytest.raises(ValueError):
            self._make(total_products=-1)

    def test_reject_negative_total_subscriptions(self):
        with pytest.raises(ValueError):
            self._make(total_subscriptions=-1)

    def test_reject_negative_total_entitlements(self):
        with pytest.raises(ValueError):
            self._make(total_entitlements=-1)

    def test_reject_negative_total_violations(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_reject_bool_total_customers(self):
        with pytest.raises(ValueError):
            self._make(total_customers=True)

    def test_reject_bool_total_violations(self):
        with pytest.raises(ValueError):
            self._make(total_violations=False)

    def test_reject_bad_closed_at(self):
        with pytest.raises(ValueError):
            self._make(closed_at="nope")

    def test_reject_empty_closed_at(self):
        with pytest.raises(ValueError):
            self._make(closed_at="")


# ---------------------------------------------------------------------------
# Cross-cutting: datetime edge cases
# ---------------------------------------------------------------------------


class TestDatetimeEdgeCases:
    """Datetime validation edge cases shared across records."""

    def test_iso_with_z_suffix(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at="2025-06-01T12:00:00Z",
        )
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_iso_with_offset(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at="2025-06-01T12:00:00+05:30",
        )
        assert r.created_at == "2025-06-01T12:00:00+05:30"

    def test_iso_with_microseconds(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at="2025-06-01T12:00:00.123456+00:00",
        )
        assert "123456" in r.created_at

    def test_iso_date_only_accepted(self):
        # Python 3.11+ accepts date-only strings
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at="2025-06-01",
        )
        assert r.created_at == "2025-06-01"


# ---------------------------------------------------------------------------
# Cross-cutting: metadata deep nesting and freeze_value
# ---------------------------------------------------------------------------


class TestMetadataFreezing:
    def test_nested_dict_frozen(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata={"a": {"b": {"c": 1}}},
        )
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert isinstance(r.metadata["a"]["b"], MappingProxyType)

    def test_list_in_metadata_becomes_tuple(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata={"items": [1, 2, 3]},
        )
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)

    def test_set_in_metadata_becomes_frozenset(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata={"tags": {1, 2}},
        )
        assert isinstance(r.metadata["tags"], frozenset)

    def test_empty_metadata(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata={},
        )
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_to_dict_thaws_nested(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata={"items": [1, 2]},
        )
        d = r.to_dict()
        assert isinstance(d["metadata"]["items"], list)

    def test_original_dict_not_mutated(self):
        original = {"k": "v"}
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            created_at=NOW, metadata=original,
        )
        original["k"] = "changed"
        assert r.metadata["k"] == "v"


# ---------------------------------------------------------------------------
# Cross-cutting: to_dict preserves enum objects
# ---------------------------------------------------------------------------


class TestToDictEnumPreservation:
    def test_customer_record_enum(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            status=CustomerStatus.CHURNED, created_at=NOW,
        )
        d = r.to_dict()
        assert d["status"] is CustomerStatus.CHURNED

    def test_account_record_enum(self):
        r = AccountRecord(
            account_id="a1", customer_id="c1", tenant_id="t1",
            display_name="A", status=AccountStatus.DELINQUENT, created_at=NOW,
        )
        d = r.to_dict()
        assert d["status"] is AccountStatus.DELINQUENT

    def test_product_record_enum(self):
        r = ProductRecord(
            product_id="p1", tenant_id="t1", display_name="W",
            status=ProductStatus.DRAFT, created_at=NOW,
        )
        d = r.to_dict()
        assert d["status"] is ProductStatus.DRAFT

    def test_subscription_record_enum(self):
        r = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", status=AccountStatus.CLOSED,
            start_at=NOW, end_at=NOW, created_at=NOW,
        )
        d = r.to_dict()
        assert d["status"] is AccountStatus.CLOSED

    def test_entitlement_record_enum(self):
        r = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc", status=EntitlementStatus.REVOKED,
            granted_at=NOW, expires_at=NOW,
        )
        d = r.to_dict()
        assert d["status"] is EntitlementStatus.REVOKED

    def test_health_snapshot_enum(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_status=AccountHealthStatus.CRITICAL,
            health_score=0.1, captured_at=NOW,
        )
        d = r.to_dict()
        assert d["health_status"] is AccountHealthStatus.CRITICAL

    def test_decision_enum(self):
        r = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            disposition=CustomerDisposition.DENIED, decided_at=NOW,
        )
        d = r.to_dict()
        assert d["disposition"] is CustomerDisposition.DENIED


# ---------------------------------------------------------------------------
# Cross-cutting: frozen setattr on every dataclass
# ---------------------------------------------------------------------------


class TestAllFrozen:
    def test_customer_record_frozen(self):
        r = CustomerRecord(customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW)
        with pytest.raises(AttributeError):
            r.tenant_id = "new"

    def test_account_record_frozen(self):
        r = AccountRecord(account_id="a1", customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW)
        with pytest.raises(AttributeError):
            r.status = AccountStatus.CLOSED

    def test_product_record_frozen(self):
        r = ProductRecord(product_id="p1", tenant_id="t1", display_name="W", created_at=NOW)
        with pytest.raises(AttributeError):
            r.base_price = 999.0

    def test_subscription_record_frozen(self):
        r = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", start_at=NOW, end_at=NOW, created_at=NOW,
        )
        with pytest.raises(AttributeError):
            r.quantity = 99

    def test_entitlement_record_frozen(self):
        r = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc", granted_at=NOW, expires_at=NOW,
        )
        with pytest.raises(AttributeError):
            r.service_ref = "new"

    def test_health_snapshot_frozen(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.5, captured_at=NOW,
        )
        with pytest.raises(AttributeError):
            r.health_score = 0.1

    def test_decision_frozen(self):
        r = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        )
        with pytest.raises(AttributeError):
            r.reason = "new"

    def test_violation_frozen(self):
        r = CustomerViolation(
            violation_id="v1", tenant_id="t1", operation="op",
            reason="r", detected_at=NOW,
        )
        with pytest.raises(AttributeError):
            r.operation = "new"

    def test_snapshot_frozen(self):
        r = CustomerSnapshot(snapshot_id="s1", captured_at=NOW)
        with pytest.raises(AttributeError):
            r.total_customers = 99

    def test_closure_report_frozen(self):
        r = CustomerClosureReport(report_id="r1", tenant_id="t1", closed_at=NOW)
        with pytest.raises(AttributeError):
            r.total_violations = 99


# ---------------------------------------------------------------------------
# Cross-cutting: to_dict returns plain dict
# ---------------------------------------------------------------------------


class TestToDictReturnType:
    def test_customer_record(self):
        d = CustomerRecord(customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW).to_dict()
        assert isinstance(d, dict)

    def test_account_record(self):
        d = AccountRecord(account_id="a1", customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW).to_dict()
        assert isinstance(d, dict)

    def test_product_record(self):
        d = ProductRecord(product_id="p1", tenant_id="t1", display_name="W", created_at=NOW).to_dict()
        assert isinstance(d, dict)

    def test_subscription_record(self):
        d = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", start_at=NOW, end_at=NOW, created_at=NOW,
        ).to_dict()
        assert isinstance(d, dict)

    def test_entitlement_record(self):
        d = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc", granted_at=NOW, expires_at=NOW,
        ).to_dict()
        assert isinstance(d, dict)

    def test_health_snapshot(self):
        d = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.5, captured_at=NOW,
        ).to_dict()
        assert isinstance(d, dict)

    def test_decision(self):
        d = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        ).to_dict()
        assert isinstance(d, dict)

    def test_violation(self):
        d = CustomerViolation(
            violation_id="v1", tenant_id="t1", operation="op",
            reason="r", detected_at=NOW,
        ).to_dict()
        assert isinstance(d, dict)

    def test_snapshot(self):
        d = CustomerSnapshot(snapshot_id="s1", captured_at=NOW).to_dict()
        assert isinstance(d, dict)

    def test_closure_report(self):
        d = CustomerClosureReport(report_id="r1", tenant_id="t1", closed_at=NOW).to_dict()
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# Cross-cutting: to_json on enum-free records
# ---------------------------------------------------------------------------


class TestToJsonEnumFreeRecords:
    def test_violation_to_json(self):
        r = CustomerViolation(
            violation_id="v1", tenant_id="t1", operation="op",
            reason="r", detected_at=NOW, metadata={},
        )
        j = r.to_json()
        import json
        parsed = json.loads(j)
        assert parsed["violation_id"] == "v1"

    def test_snapshot_to_json(self):
        r = CustomerSnapshot(snapshot_id="s1", captured_at=NOW, metadata={})
        j = r.to_json()
        import json
        parsed = json.loads(j)
        assert parsed["snapshot_id"] == "s1"

    def test_closure_report_to_json(self):
        r = CustomerClosureReport(
            report_id="r1", tenant_id="t1", closed_at=NOW, metadata={},
        )
        j = r.to_json()
        import json
        parsed = json.loads(j)
        assert parsed["report_id"] == "r1"


# ---------------------------------------------------------------------------
# Additional edge-case tests to reach ~300
# ---------------------------------------------------------------------------


class TestCustomerRecordEdgeCases:
    def test_large_account_count(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            account_count=999999, created_at=NOW,
        )
        assert r.account_count == 999999

    def test_unicode_display_name(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="Acme Corp",
            created_at=NOW,
        )
        assert r.display_name == "Acme Corp"

    def test_whitespace_only_display_name_rejected(self):
        with pytest.raises(ValueError):
            CustomerRecord(
                customer_id="c1", tenant_id="t1", display_name="  \t ",
                created_at=NOW,
            )

    def test_default_status(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW,
        )
        assert r.status is CustomerStatus.ACTIVE

    def test_default_tier(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW,
        )
        assert r.tier == ""

    def test_default_account_count(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW,
        )
        assert r.account_count == 0

    def test_default_metadata(self):
        r = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A", created_at=NOW,
        )
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0


class TestAccountRecordEdgeCases:
    def test_large_entitlement_count(self):
        r = AccountRecord(
            account_id="a1", customer_id="c1", tenant_id="t1",
            display_name="A", entitlement_count=100000, created_at=NOW,
        )
        assert r.entitlement_count == 100000

    def test_default_contract_ref(self):
        r = AccountRecord(
            account_id="a1", customer_id="c1", tenant_id="t1",
            display_name="A", created_at=NOW,
        )
        assert r.contract_ref == ""

    def test_default_entitlement_count(self):
        r = AccountRecord(
            account_id="a1", customer_id="c1", tenant_id="t1",
            display_name="A", created_at=NOW,
        )
        assert r.entitlement_count == 0

    def test_whitespace_account_id_rejected(self):
        with pytest.raises(ValueError):
            AccountRecord(
                account_id="  ", customer_id="c1", tenant_id="t1",
                display_name="A", created_at=NOW,
            )


class TestProductRecordEdgeCases:
    def test_very_large_price(self):
        r = ProductRecord(
            product_id="p1", tenant_id="t1", display_name="W",
            base_price=1_000_000.50, created_at=NOW,
        )
        assert r.base_price == 1_000_000.50

    def test_default_category(self):
        r = ProductRecord(
            product_id="p1", tenant_id="t1", display_name="W", created_at=NOW,
        )
        assert r.category == ""

    def test_default_base_price(self):
        r = ProductRecord(
            product_id="p1", tenant_id="t1", display_name="W", created_at=NOW,
        )
        assert r.base_price == 0.0

    def test_neg_inf_base_price_rejected(self):
        with pytest.raises(ValueError):
            ProductRecord(
                product_id="p1", tenant_id="t1", display_name="W",
                base_price=float("-inf"), created_at=NOW,
            )


class TestSubscriptionRecordEdgeCases:
    def test_large_quantity(self):
        r = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", quantity=50000,
            start_at=NOW, end_at=NOW, created_at=NOW,
        )
        assert r.quantity == 50000

    def test_default_quantity(self):
        r = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", start_at=NOW, end_at=NOW, created_at=NOW,
        )
        assert r.quantity == 1

    def test_default_status(self):
        r = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", start_at=NOW, end_at=NOW, created_at=NOW,
        )
        assert r.status is AccountStatus.ACTIVE

    def test_whitespace_subscription_id_rejected(self):
        with pytest.raises(ValueError):
            SubscriptionRecord(
                subscription_id="  ", account_id="a1", product_id="p1",
                tenant_id="t1", start_at=NOW, end_at=NOW, created_at=NOW,
            )


class TestEntitlementRecordEdgeCases:
    def test_default_status(self):
        r = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc", granted_at=NOW, expires_at=NOW,
        )
        assert r.status is EntitlementStatus.ACTIVE

    def test_whitespace_service_ref_rejected(self):
        with pytest.raises(ValueError):
            EntitlementRecord(
                entitlement_id="e1", account_id="a1", tenant_id="t1",
                service_ref="  ", granted_at=NOW, expires_at=NOW,
            )

    def test_different_granted_and_expires(self):
        r = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc",
            granted_at="2025-01-01T00:00:00+00:00",
            expires_at="2026-01-01T00:00:00+00:00",
        )
        assert r.granted_at != r.expires_at


class TestAccountHealthEdgeCases:
    def test_default_health_status(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.5, captured_at=NOW,
        )
        assert r.health_status is AccountHealthStatus.HEALTHY

    def test_default_health_score(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            captured_at=NOW,
        )
        assert r.health_score == 1.0

    def test_boundary_health_score_half(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.5, captured_at=NOW,
        )
        assert r.health_score == 0.5

    def test_health_score_near_zero(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.001, captured_at=NOW,
        )
        assert r.health_score == pytest.approx(0.001)

    def test_health_score_near_one(self):
        r = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.999, captured_at=NOW,
        )
        assert r.health_score == pytest.approx(0.999)

    def test_reject_neg_inf_health_score(self):
        with pytest.raises(ValueError):
            AccountHealthSnapshot(
                snapshot_id="s1", account_id="a1", tenant_id="t1",
                health_score=float("-inf"), captured_at=NOW,
            )


class TestCustomerDecisionEdgeCases:
    def test_default_disposition(self):
        r = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        )
        assert r.disposition is CustomerDisposition.APPROVED

    def test_default_account_id(self):
        r = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        )
        assert r.account_id == ""

    def test_default_reason(self):
        r = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        )
        assert r.reason == ""

    def test_whitespace_decision_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerDecision(
                decision_id="  ", tenant_id="t1", customer_id="c1",
                decided_at=NOW,
            )

    def test_whitespace_customer_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerDecision(
                decision_id="d1", tenant_id="t1", customer_id="  ",
                decided_at=NOW,
            )


class TestCustomerViolationEdgeCases:
    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            CustomerViolation(
                violation_id="v1", tenant_id="t1", operation="   ",
                reason="r", detected_at=NOW,
            )

    def test_whitespace_reason_rejected(self):
        with pytest.raises(ValueError):
            CustomerViolation(
                violation_id="v1", tenant_id="t1", operation="op",
                reason="   ", detected_at=NOW,
            )

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerViolation(
                violation_id="v1", tenant_id="  ", operation="op",
                reason="r", detected_at=NOW,
            )


class TestCustomerSnapshotEdgeCases:
    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="  ", captured_at=NOW)

    def test_reject_bool_total_products(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_products=True, captured_at=NOW)

    def test_reject_bool_total_subscriptions(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_subscriptions=True, captured_at=NOW)

    def test_reject_bool_total_entitlements(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_entitlements=False, captured_at=NOW)

    def test_reject_bool_total_health_snapshots(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_health_snapshots=True, captured_at=NOW)

    def test_reject_bool_total_decisions(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_decisions=True, captured_at=NOW)

    def test_reject_bool_total_violations(self):
        with pytest.raises(ValueError):
            CustomerSnapshot(snapshot_id="s1", total_violations=True, captured_at=NOW)


class TestClosureReportEdgeCases:
    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="  ", tenant_id="t1", closed_at=NOW)

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="r1", tenant_id="  ", closed_at=NOW)

    def test_reject_bool_total_accounts(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="r1", tenant_id="t1", total_accounts=True, closed_at=NOW)

    def test_reject_bool_total_products(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="r1", tenant_id="t1", total_products=False, closed_at=NOW)

    def test_reject_bool_total_subscriptions(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="r1", tenant_id="t1", total_subscriptions=True, closed_at=NOW)

    def test_reject_bool_total_entitlements(self):
        with pytest.raises(ValueError):
            CustomerClosureReport(report_id="r1", tenant_id="t1", total_entitlements=True, closed_at=NOW)


# ---------------------------------------------------------------------------
# to_dict field completeness
# ---------------------------------------------------------------------------


class TestToDictFieldCompleteness:
    def test_customer_record_all_fields(self):
        d = CustomerRecord(
            customer_id="c1", tenant_id="t1", display_name="A",
            status=CustomerStatus.PROSPECT, tier="silver",
            account_count=2, created_at=NOW, metadata={"x": 1},
        ).to_dict()
        expected_keys = {
            "customer_id", "tenant_id", "display_name", "status",
            "tier", "account_count", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_account_record_all_fields(self):
        d = AccountRecord(
            account_id="a1", customer_id="c1", tenant_id="t1",
            display_name="A", status=AccountStatus.PENDING,
            contract_ref="CR", entitlement_count=1, created_at=NOW,
        ).to_dict()
        expected_keys = {
            "account_id", "customer_id", "tenant_id", "display_name",
            "status", "contract_ref", "entitlement_count", "created_at",
            "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_product_record_all_fields(self):
        d = ProductRecord(
            product_id="p1", tenant_id="t1", display_name="W",
            status=ProductStatus.RETIRED, category="Cat",
            base_price=1.0, created_at=NOW,
        ).to_dict()
        expected_keys = {
            "product_id", "tenant_id", "display_name", "status",
            "category", "base_price", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_subscription_record_all_fields(self):
        d = SubscriptionRecord(
            subscription_id="s1", account_id="a1", product_id="p1",
            tenant_id="t1", quantity=2, start_at=NOW, end_at=NOW,
            created_at=NOW,
        ).to_dict()
        expected_keys = {
            "subscription_id", "account_id", "product_id", "tenant_id",
            "status", "quantity", "start_at", "end_at", "created_at",
            "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_entitlement_record_all_fields(self):
        d = EntitlementRecord(
            entitlement_id="e1", account_id="a1", tenant_id="t1",
            service_ref="svc", granted_at=NOW, expires_at=NOW,
        ).to_dict()
        expected_keys = {
            "entitlement_id", "account_id", "tenant_id", "service_ref",
            "status", "granted_at", "expires_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_health_snapshot_all_fields(self):
        d = AccountHealthSnapshot(
            snapshot_id="s1", account_id="a1", tenant_id="t1",
            health_score=0.5, captured_at=NOW,
        ).to_dict()
        expected_keys = {
            "snapshot_id", "account_id", "tenant_id", "health_status",
            "health_score", "sla_breaches", "open_cases", "billing_issues",
            "entitlement_count", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_decision_all_fields(self):
        d = CustomerDecision(
            decision_id="d1", tenant_id="t1", customer_id="c1",
            decided_at=NOW,
        ).to_dict()
        expected_keys = {
            "decision_id", "tenant_id", "customer_id", "account_id",
            "disposition", "reason", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_violation_all_fields(self):
        d = CustomerViolation(
            violation_id="v1", tenant_id="t1", operation="op",
            reason="r", detected_at=NOW,
        ).to_dict()
        expected_keys = {
            "violation_id", "tenant_id", "operation", "reason",
            "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_snapshot_all_fields(self):
        d = CustomerSnapshot(snapshot_id="s1", captured_at=NOW).to_dict()
        expected_keys = {
            "snapshot_id", "total_customers", "total_accounts",
            "total_products", "total_subscriptions", "total_entitlements",
            "total_health_snapshots", "total_decisions", "total_violations",
            "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_closure_report_all_fields(self):
        d = CustomerClosureReport(
            report_id="r1", tenant_id="t1", closed_at=NOW,
        ).to_dict()
        expected_keys = {
            "report_id", "tenant_id", "total_customers", "total_accounts",
            "total_products", "total_subscriptions", "total_entitlements",
            "total_violations", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys
