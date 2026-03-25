"""Purpose: customer runtime integration bridge.
Governance scope: composing customer runtime with contracts, billing,
    SLA breaches, settlements, cases, service requests; memory mesh
    and graph attachment.
Dependencies: customer_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every customer action emits events.
  - Customer state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .customer_runtime import CustomerRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-custint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CustomerRuntimeIntegration:
    """Integration bridge for customer runtime with platform layers."""

    def __init__(
        self,
        customer_engine: CustomerRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(customer_engine, CustomerRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "customer_engine must be a CustomerRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._customer = customer_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Customer from platform layers
    # ------------------------------------------------------------------

    def customer_from_contract(
        self,
        customer_id: str,
        account_id: str,
        tenant_id: str,
        display_name: str,
        contract_ref: str,
        tier: str = "standard",
    ) -> dict[str, Any]:
        cust = self._customer.register_customer(
            customer_id=customer_id,
            tenant_id=tenant_id,
            display_name=display_name,
            tier=tier,
        )
        acct = self._customer.register_account(
            account_id=account_id,
            customer_id=customer_id,
            tenant_id=tenant_id,
            display_name=f"{display_name} - Primary",
            contract_ref=contract_ref,
        )
        _emit(self._events, "customer_from_contract", {
            "customer_id": customer_id, "account_id": account_id, "contract_ref": contract_ref,
        }, customer_id)
        return {
            "customer_id": cust.customer_id,
            "account_id": acct.account_id,
            "tenant_id": tenant_id,
            "contract_ref": contract_ref,
            "tier": tier,
            "source_type": "contract",
        }

    def account_from_billing(
        self,
        account_id: str,
        customer_id: str,
        tenant_id: str,
        display_name: str,
        billing_ref: str,
    ) -> dict[str, Any]:
        acct = self._customer.register_account(
            account_id=account_id,
            customer_id=customer_id,
            tenant_id=tenant_id,
            display_name=display_name,
            contract_ref=billing_ref,
        )
        _emit(self._events, "account_from_billing", {
            "account_id": account_id, "billing_ref": billing_ref,
        }, account_id)
        return {
            "account_id": acct.account_id,
            "customer_id": customer_id,
            "tenant_id": tenant_id,
            "billing_ref": billing_ref,
            "source_type": "billing",
        }

    def health_from_sla_breach(
        self,
        snapshot_id: str,
        account_id: str,
        tenant_id: str,
        breach_count: int = 1,
    ) -> dict[str, Any]:
        snap = self._customer.account_health(
            snapshot_id=snapshot_id,
            account_id=account_id,
            tenant_id=tenant_id,
            sla_breaches=breach_count,
        )
        _emit(self._events, "health_from_sla_breach", {
            "snapshot_id": snapshot_id, "account_id": account_id, "breaches": breach_count,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "account_id": account_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "sla_breaches": breach_count,
            "source_type": "sla_breach",
        }

    def health_from_settlement(
        self,
        snapshot_id: str,
        account_id: str,
        tenant_id: str,
        billing_issues: int = 1,
    ) -> dict[str, Any]:
        snap = self._customer.account_health(
            snapshot_id=snapshot_id,
            account_id=account_id,
            tenant_id=tenant_id,
            billing_issues=billing_issues,
        )
        _emit(self._events, "health_from_settlement", {
            "snapshot_id": snapshot_id, "account_id": account_id, "billing_issues": billing_issues,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "account_id": account_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "billing_issues": billing_issues,
            "source_type": "settlement",
        }

    def health_from_case(
        self,
        snapshot_id: str,
        account_id: str,
        tenant_id: str,
        open_cases: int = 1,
    ) -> dict[str, Any]:
        snap = self._customer.account_health(
            snapshot_id=snapshot_id,
            account_id=account_id,
            tenant_id=tenant_id,
            open_cases=open_cases,
        )
        _emit(self._events, "health_from_case", {
            "snapshot_id": snapshot_id, "account_id": account_id, "open_cases": open_cases,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "account_id": account_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "open_cases": open_cases,
            "source_type": "case",
        }

    def health_from_service_request(
        self,
        snapshot_id: str,
        account_id: str,
        tenant_id: str,
        open_cases: int = 0,
        sla_breaches: int = 0,
    ) -> dict[str, Any]:
        snap = self._customer.account_health(
            snapshot_id=snapshot_id,
            account_id=account_id,
            tenant_id=tenant_id,
            open_cases=open_cases,
            sla_breaches=sla_breaches,
        )
        _emit(self._events, "health_from_service_request", {
            "snapshot_id": snapshot_id, "account_id": account_id,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "account_id": account_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "open_cases": open_cases,
            "sla_breaches": sla_breaches,
            "source_type": "service_request",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_customer_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-cust", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "customers": self._customer.customer_count,
            "accounts": self._customer.account_count,
            "products": self._customer.product_count,
            "subscriptions": self._customer.subscription_count,
            "entitlements": self._customer.entitlement_count,
            "health_snapshots": self._customer.health_snapshot_count,
            "decisions": self._customer.decision_count,
            "violations": self._customer.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Customer runtime state",
            content=content,
            tags=("customer", "account", "product"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_customer_to_memory", {"memory_id": mid, "scope_ref_id": scope_ref_id}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_customer_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "customers": self._customer.customer_count,
            "accounts": self._customer.account_count,
            "products": self._customer.product_count,
            "subscriptions": self._customer.subscription_count,
            "entitlements": self._customer.entitlement_count,
            "health_snapshots": self._customer.health_snapshot_count,
            "decisions": self._customer.decision_count,
            "violations": self._customer.violation_count,
        }
