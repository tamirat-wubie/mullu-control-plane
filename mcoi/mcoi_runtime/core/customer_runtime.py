"""Purpose: product / customer / account runtime engine.
Governance scope: registering customers, accounts, products, subscriptions,
    granting/revoking entitlements, tracking account health, detecting
    violations, producing immutable snapshots.
Dependencies: customer_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Churned customers cannot be modified.
  - Closed accounts cannot be modified.
  - Revoked/expired entitlements block service access.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.customer_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cust", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_CUSTOMER_TERMINAL = frozenset({CustomerStatus.CHURNED})
_ACCOUNT_TERMINAL = frozenset({AccountStatus.CLOSED})
_ENTITLEMENT_INACTIVE = frozenset({EntitlementStatus.EXPIRED, EntitlementStatus.REVOKED})
_PRODUCT_TERMINAL = frozenset({ProductStatus.RETIRED})


class CustomerRuntimeEngine:
    """Product / customer / account runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._customers: dict[str, CustomerRecord] = {}
        self._accounts: dict[str, AccountRecord] = {}
        self._products: dict[str, ProductRecord] = {}
        self._subscriptions: dict[str, SubscriptionRecord] = {}
        self._entitlements: dict[str, EntitlementRecord] = {}
        self._health_snapshots: dict[str, AccountHealthSnapshot] = {}
        self._decisions: dict[str, CustomerDecision] = {}
        self._violations: dict[str, CustomerViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def customer_count(self) -> int:
        return len(self._customers)

    @property
    def account_count(self) -> int:
        return len(self._accounts)

    @property
    def product_count(self) -> int:
        return len(self._products)

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    @property
    def entitlement_count(self) -> int:
        return len(self._entitlements)

    @property
    def health_snapshot_count(self) -> int:
        return len(self._health_snapshots)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    def register_customer(
        self,
        customer_id: str,
        tenant_id: str,
        display_name: str,
        tier: str = "standard",
        status: CustomerStatus = CustomerStatus.ACTIVE,
    ) -> CustomerRecord:
        if customer_id in self._customers:
            raise RuntimeCoreInvariantError("customer already registered")
        now = self._now()
        record = CustomerRecord(
            customer_id=customer_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=status,
            tier=tier,
            account_count=0,
            created_at=now,
        )
        self._customers[customer_id] = record
        _emit(self._events, "register_customer", {"customer_id": customer_id, "tenant_id": tenant_id}, customer_id, self._now())
        return record

    def get_customer(self, customer_id: str) -> CustomerRecord:
        if customer_id not in self._customers:
            raise RuntimeCoreInvariantError("unknown customer")
        return self._customers[customer_id]

    def update_customer_status(self, customer_id: str, status: CustomerStatus) -> CustomerRecord:
        if customer_id not in self._customers:
            raise RuntimeCoreInvariantError("unknown customer")
        old = self._customers[customer_id]
        if old.status in _CUSTOMER_TERMINAL:
            raise RuntimeCoreInvariantError("customer is in terminal state")
        updated = CustomerRecord(
            customer_id=old.customer_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=status,
            tier=old.tier,
            account_count=old.account_count,
            created_at=old.created_at,
        )
        self._customers[customer_id] = updated
        _emit(self._events, "update_customer_status", {"customer_id": customer_id, "status": status.value}, customer_id, self._now())
        return updated

    def customers_for_tenant(self, tenant_id: str) -> tuple[CustomerRecord, ...]:
        return tuple(c for c in self._customers.values() if c.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def register_account(
        self,
        account_id: str,
        customer_id: str,
        tenant_id: str,
        display_name: str,
        contract_ref: str = "",
        status: AccountStatus = AccountStatus.ACTIVE,
    ) -> AccountRecord:
        if account_id in self._accounts:
            raise RuntimeCoreInvariantError("account already registered")
        if customer_id not in self._customers:
            raise RuntimeCoreInvariantError("unknown customer")
        cust = self._customers[customer_id]
        if cust.status in _CUSTOMER_TERMINAL:
            raise RuntimeCoreInvariantError("customer is in terminal state")
        now = self._now()
        record = AccountRecord(
            account_id=account_id,
            customer_id=customer_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=status,
            contract_ref=contract_ref if contract_ref else "none",
            entitlement_count=0,
            created_at=now,
        )
        self._accounts[account_id] = record
        # Increment customer account_count
        updated_cust = CustomerRecord(
            customer_id=cust.customer_id,
            tenant_id=cust.tenant_id,
            display_name=cust.display_name,
            status=cust.status,
            tier=cust.tier,
            account_count=cust.account_count + 1,
            created_at=cust.created_at,
        )
        self._customers[customer_id] = updated_cust
        _emit(self._events, "register_account", {"account_id": account_id, "customer_id": customer_id}, account_id, self._now())
        return record

    def get_account(self, account_id: str) -> AccountRecord:
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("unknown account")
        return self._accounts[account_id]

    def update_account_status(self, account_id: str, status: AccountStatus) -> AccountRecord:
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("unknown account")
        old = self._accounts[account_id]
        if old.status in _ACCOUNT_TERMINAL:
            raise RuntimeCoreInvariantError("account is in terminal state")
        updated = AccountRecord(
            account_id=old.account_id,
            customer_id=old.customer_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=status,
            contract_ref=old.contract_ref,
            entitlement_count=old.entitlement_count,
            created_at=old.created_at,
        )
        self._accounts[account_id] = updated
        _emit(self._events, "update_account_status", {"account_id": account_id, "status": status.value}, account_id, self._now())
        return updated

    def accounts_for_customer(self, customer_id: str) -> tuple[AccountRecord, ...]:
        return tuple(a for a in self._accounts.values() if a.customer_id == customer_id)

    def accounts_for_tenant(self, tenant_id: str) -> tuple[AccountRecord, ...]:
        return tuple(a for a in self._accounts.values() if a.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def register_product(
        self,
        product_id: str,
        tenant_id: str,
        display_name: str,
        category: str = "general",
        base_price: float = 0.0,
        status: ProductStatus = ProductStatus.ACTIVE,
    ) -> ProductRecord:
        if product_id in self._products:
            raise RuntimeCoreInvariantError("product already registered")
        now = self._now()
        record = ProductRecord(
            product_id=product_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=status,
            category=category,
            base_price=base_price,
            created_at=now,
        )
        self._products[product_id] = record
        _emit(self._events, "register_product", {"product_id": product_id, "tenant_id": tenant_id}, product_id, self._now())
        return record

    def get_product(self, product_id: str) -> ProductRecord:
        if product_id not in self._products:
            raise RuntimeCoreInvariantError("unknown product")
        return self._products[product_id]

    def deprecate_product(self, product_id: str) -> ProductRecord:
        if product_id not in self._products:
            raise RuntimeCoreInvariantError("unknown product")
        old = self._products[product_id]
        if old.status in _PRODUCT_TERMINAL:
            raise RuntimeCoreInvariantError("product is in terminal state")
        updated = ProductRecord(
            product_id=old.product_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=ProductStatus.DEPRECATED,
            category=old.category,
            base_price=old.base_price,
            created_at=old.created_at,
        )
        self._products[product_id] = updated
        _emit(self._events, "deprecate_product", {"product_id": product_id}, product_id, self._now())
        return updated

    def retire_product(self, product_id: str) -> ProductRecord:
        if product_id not in self._products:
            raise RuntimeCoreInvariantError("unknown product")
        old = self._products[product_id]
        if old.status in _PRODUCT_TERMINAL:
            raise RuntimeCoreInvariantError("product already retired")
        updated = ProductRecord(
            product_id=old.product_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=ProductStatus.RETIRED,
            category=old.category,
            base_price=old.base_price,
            created_at=old.created_at,
        )
        self._products[product_id] = updated
        _emit(self._events, "retire_product", {"product_id": product_id}, product_id, self._now())
        return updated

    def products_for_tenant(self, tenant_id: str) -> tuple[ProductRecord, ...]:
        return tuple(p for p in self._products.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def register_subscription(
        self,
        subscription_id: str,
        account_id: str,
        product_id: str,
        tenant_id: str,
        quantity: int = 1,
        start_at: str = "",
        end_at: str = "",
    ) -> SubscriptionRecord:
        if subscription_id in self._subscriptions:
            raise RuntimeCoreInvariantError("subscription already registered")
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("unknown account")
        if product_id not in self._products:
            raise RuntimeCoreInvariantError("unknown product")
        acct = self._accounts[account_id]
        if acct.status in _ACCOUNT_TERMINAL:
            raise RuntimeCoreInvariantError("account is in terminal state")
        prod = self._products[product_id]
        if prod.status in _PRODUCT_TERMINAL:
            raise RuntimeCoreInvariantError("product is in terminal state")
        now = self._now()
        effective_start = start_at if start_at else now
        effective_end = end_at if end_at else now
        record = SubscriptionRecord(
            subscription_id=subscription_id,
            account_id=account_id,
            product_id=product_id,
            tenant_id=tenant_id,
            status=AccountStatus.ACTIVE,
            quantity=quantity,
            start_at=effective_start,
            end_at=effective_end,
            created_at=now,
        )
        self._subscriptions[subscription_id] = record
        _emit(self._events, "register_subscription", {
            "subscription_id": subscription_id, "account_id": account_id, "product_id": product_id,
        }, subscription_id, self._now())
        return record

    def get_subscription(self, subscription_id: str) -> SubscriptionRecord:
        if subscription_id not in self._subscriptions:
            raise RuntimeCoreInvariantError("unknown subscription")
        return self._subscriptions[subscription_id]

    def subscriptions_for_account(self, account_id: str) -> tuple[SubscriptionRecord, ...]:
        return tuple(s for s in self._subscriptions.values() if s.account_id == account_id)

    def subscriptions_for_product(self, product_id: str) -> tuple[SubscriptionRecord, ...]:
        return tuple(s for s in self._subscriptions.values() if s.product_id == product_id)

    # ------------------------------------------------------------------
    # Entitlements
    # ------------------------------------------------------------------

    def grant_entitlement(
        self,
        entitlement_id: str,
        account_id: str,
        tenant_id: str,
        service_ref: str,
        expires_at: str = "",
    ) -> EntitlementRecord:
        if entitlement_id in self._entitlements:
            raise RuntimeCoreInvariantError("entitlement already exists")
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("unknown account")
        acct = self._accounts[account_id]
        if acct.status in _ACCOUNT_TERMINAL:
            raise RuntimeCoreInvariantError("account is in terminal state")
        now = self._now()
        effective_expires = expires_at if expires_at else now
        record = EntitlementRecord(
            entitlement_id=entitlement_id,
            account_id=account_id,
            tenant_id=tenant_id,
            service_ref=service_ref,
            status=EntitlementStatus.ACTIVE,
            granted_at=now,
            expires_at=effective_expires,
        )
        self._entitlements[entitlement_id] = record
        # Increment entitlement_count on account
        updated_acct = AccountRecord(
            account_id=acct.account_id,
            customer_id=acct.customer_id,
            tenant_id=acct.tenant_id,
            display_name=acct.display_name,
            status=acct.status,
            contract_ref=acct.contract_ref,
            entitlement_count=acct.entitlement_count + 1,
            created_at=acct.created_at,
        )
        self._accounts[account_id] = updated_acct
        _emit(self._events, "grant_entitlement", {
            "entitlement_id": entitlement_id, "account_id": account_id, "service_ref": service_ref,
        }, entitlement_id, self._now())
        return record

    def revoke_entitlement(self, entitlement_id: str) -> EntitlementRecord:
        if entitlement_id not in self._entitlements:
            raise RuntimeCoreInvariantError("unknown entitlement")
        old = self._entitlements[entitlement_id]
        if old.status in _ENTITLEMENT_INACTIVE:
            raise RuntimeCoreInvariantError("entitlement already inactive")
        now = self._now()
        updated = EntitlementRecord(
            entitlement_id=old.entitlement_id,
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            service_ref=old.service_ref,
            status=EntitlementStatus.REVOKED,
            granted_at=old.granted_at,
            expires_at=now,
        )
        self._entitlements[entitlement_id] = updated
        _emit(self._events, "revoke_entitlement", {"entitlement_id": entitlement_id}, entitlement_id, self._now())
        return updated

    def get_entitlement(self, entitlement_id: str) -> EntitlementRecord:
        if entitlement_id not in self._entitlements:
            raise RuntimeCoreInvariantError("unknown entitlement")
        return self._entitlements[entitlement_id]

    def check_entitlement(self, account_id: str, service_ref: str) -> bool:
        """Check if an account has an active entitlement for a service."""
        for e in self._entitlements.values():
            if e.account_id == account_id and e.service_ref == service_ref and e.status == EntitlementStatus.ACTIVE:
                return True
        return False

    def entitlements_for_account(self, account_id: str) -> tuple[EntitlementRecord, ...]:
        return tuple(e for e in self._entitlements.values() if e.account_id == account_id)

    def active_entitlements_for_account(self, account_id: str) -> tuple[EntitlementRecord, ...]:
        return tuple(
            e for e in self._entitlements.values()
            if e.account_id == account_id and e.status == EntitlementStatus.ACTIVE
        )

    # ------------------------------------------------------------------
    # Account health
    # ------------------------------------------------------------------

    def account_health(
        self,
        snapshot_id: str,
        account_id: str,
        tenant_id: str,
        sla_breaches: int = 0,
        open_cases: int = 0,
        billing_issues: int = 0,
    ) -> AccountHealthSnapshot:
        if snapshot_id in self._health_snapshots:
            raise RuntimeCoreInvariantError("health snapshot already exists")
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("unknown account")
        now = self._now()
        entitlement_count = len(self.active_entitlements_for_account(account_id))

        # Derive health score: start at 1.0, deduct per issue
        score = 1.0
        score -= sla_breaches * 0.15
        score -= open_cases * 0.1
        score -= billing_issues * 0.2
        score = max(0.0, min(1.0, round(score, 4)))

        health_status = self._derive_health_status(score)

        snapshot = AccountHealthSnapshot(
            snapshot_id=snapshot_id,
            account_id=account_id,
            tenant_id=tenant_id,
            health_status=health_status,
            health_score=score,
            sla_breaches=sla_breaches,
            open_cases=open_cases,
            billing_issues=billing_issues,
            entitlement_count=entitlement_count,
            captured_at=now,
        )
        self._health_snapshots[snapshot_id] = snapshot
        _emit(self._events, "account_health", {
            "snapshot_id": snapshot_id, "account_id": account_id, "health_score": score,
        }, snapshot_id, self._now())

        # Auto-decision: if CRITICAL, record an escalation decision
        if health_status == AccountHealthStatus.CRITICAL:
            acct = self._accounts[account_id]
            dec_id = stable_identifier("dec-cust", {"account_id": account_id, "snapshot_id": snapshot_id})
            if dec_id not in self._decisions:
                decision = CustomerDecision(
                    decision_id=dec_id,
                    tenant_id=tenant_id,
                    customer_id=acct.customer_id,
                    account_id=account_id,
                    disposition=CustomerDisposition.ESCALATED,
                    reason="account health critical",
                    decided_at=now,
                )
                self._decisions[dec_id] = decision

        return snapshot

    def get_health_snapshot(self, snapshot_id: str) -> AccountHealthSnapshot:
        if snapshot_id not in self._health_snapshots:
            raise RuntimeCoreInvariantError("unknown health snapshot")
        return self._health_snapshots[snapshot_id]

    def health_snapshots_for_account(self, account_id: str) -> tuple[AccountHealthSnapshot, ...]:
        return tuple(h for h in self._health_snapshots.values() if h.account_id == account_id)

    # ------------------------------------------------------------------
    # Customer snapshot
    # ------------------------------------------------------------------

    def customer_snapshot(self, snapshot_id: str) -> CustomerSnapshot:
        now = self._now()
        return CustomerSnapshot(
            snapshot_id=snapshot_id,
            total_customers=len(self._customers),
            total_accounts=len(self._accounts),
            total_products=len(self._products),
            total_subscriptions=len(self._subscriptions),
            total_entitlements=len(self._entitlements),
            total_health_snapshots=len(self._health_snapshots),
            total_decisions=len(self._decisions),
            total_violations=len(self._violations),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_customer_violations(self, tenant_id: str) -> tuple[CustomerViolation, ...]:
        """Detect customer/account violations. Idempotent per violation_id."""
        now = self._now()
        new_violations: list[CustomerViolation] = []

        # 1. Accounts with no entitlements (active accounts only)
        for a in self._accounts.values():
            if a.tenant_id == tenant_id and a.status == AccountStatus.ACTIVE:
                active_ents = self.active_entitlements_for_account(a.account_id)
                if not active_ents:
                    vid = stable_identifier("viol-cust", {"type": "no_entitlements", "account_id": a.account_id})
                    if vid not in self._violations:
                        v = CustomerViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="no_entitlements",
                            reason="active account has no active entitlements",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. Delinquent accounts
        for a in self._accounts.values():
            if a.tenant_id == tenant_id and a.status == AccountStatus.DELINQUENT:
                vid = stable_identifier("viol-cust", {"type": "delinquent_account", "account_id": a.account_id})
                if vid not in self._violations:
                    v = CustomerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="delinquent_account",
                        reason="account is delinquent",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Subscriptions on retired products
        for s in self._subscriptions.values():
            if s.tenant_id == tenant_id and s.status == AccountStatus.ACTIVE:
                prod = self._products.get(s.product_id)
                if prod and prod.status == ProductStatus.RETIRED:
                    vid = stable_identifier("viol-cust", {"type": "retired_product_subscription", "subscription_id": s.subscription_id})
                    if vid not in self._violations:
                        v = CustomerViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="retired_product_subscription",
                            reason="subscription on retired product",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        _emit(self._events, "detect_customer_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id, self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[CustomerViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> CustomerClosureReport:
        now = self._now()
        return CustomerClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_customers=len([c for c in self._customers.values() if c.tenant_id == tenant_id]),
            total_accounts=len([a for a in self._accounts.values() if a.tenant_id == tenant_id]),
            total_products=len([p for p in self._products.values() if p.tenant_id == tenant_id]),
            total_subscriptions=len([s for s in self._subscriptions.values() if s.tenant_id == tenant_id]),
            total_entitlements=len([e for e in self._entitlements.values() if e.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            closed_at=now,
        )

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "customers": self._customers,
            "accounts": self._accounts,
            "products": self._products,
            "subscriptions": self._subscriptions,
            "entitlements": self._entitlements,
            "health_snapshots": self._health_snapshots,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._customers):
            parts.append(f"c:{k}")
        for k in sorted(self._accounts):
            parts.append(f"a:{k}")
        for k in sorted(self._products):
            parts.append(f"p:{k}")
        for k in sorted(self._subscriptions):
            parts.append(f"s:{k}")
        for k in sorted(self._entitlements):
            parts.append(f"e:{k}")
        for k in sorted(self._health_snapshots):
            parts.append(f"h:{k}")
        for k in sorted(self._decisions):
            parts.append(f"d:{k}")
        for k in sorted(self._violations):
            parts.append(f"v:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_health_status(score: float) -> AccountHealthStatus:
        if score >= 0.8:
            return AccountHealthStatus.HEALTHY
        if score >= 0.5:
            return AccountHealthStatus.AT_RISK
        if score >= 0.3:
            return AccountHealthStatus.DEGRADED
        return AccountHealthStatus.CRITICAL
