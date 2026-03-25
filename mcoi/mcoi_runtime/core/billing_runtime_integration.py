"""Purpose: billing runtime integration bridge.
Governance scope: composing billing runtime with contract, SLA, remedy,
    campaign, and reporting scopes; memory mesh and operational graph attachment.
Dependencies: billing_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every billing creation emits events.
  - Billing state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.billing_runtime import ChargeKind
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
from .billing_runtime import BillingRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-bint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class BillingRuntimeIntegration:
    """Integration bridge for billing runtime with platform layers."""

    def __init__(
        self,
        billing_engine: BillingRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(billing_engine, BillingRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "billing_engine must be a BillingRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._billing = billing_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Billing account creation helpers
    # ------------------------------------------------------------------

    def billing_from_contract(
        self,
        account_id: str,
        tenant_id: str,
        contract_id: str,
        *,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a billing account from a contract."""
        acct = self._billing.register_account(
            account_id, tenant_id, contract_id, currency=currency,
        )
        _emit(self._events, "billing_from_contract", {
            "account_id": account_id, "contract_id": contract_id,
        }, account_id)
        return {
            "account_id": acct.account_id,
            "tenant_id": acct.tenant_id,
            "counterparty": contract_id,
            "status": acct.status.value,
            "currency": acct.currency,
            "source_type": "contract",
        }

    def billing_from_sla_breach(
        self,
        penalty_id: str,
        account_id: str,
        breach_id: str,
        amount: float,
        *,
        reason: str = "SLA breach penalty",
    ) -> dict[str, Any]:
        """Create a penalty from an SLA breach."""
        pen = self._billing.add_penalty(
            penalty_id, account_id, breach_id, amount, reason=reason,
        )
        _emit(self._events, "billing_from_sla_breach", {
            "penalty_id": penalty_id, "breach_id": breach_id, "amount": amount,
        }, account_id)
        return {
            "penalty_id": pen.penalty_id,
            "account_id": pen.account_id,
            "breach_id": pen.breach_id,
            "amount": pen.amount,
            "source_type": "sla_breach",
        }

    def billing_from_remedy(
        self,
        credit_id: str,
        account_id: str,
        breach_id: str,
        amount: float,
        *,
        reason: str = "Remedy credit",
    ) -> dict[str, Any]:
        """Create a credit from a remedy action."""
        cred = self._billing.add_credit(
            credit_id, account_id, breach_id, amount, reason=reason,
        )
        _emit(self._events, "billing_from_remedy", {
            "credit_id": credit_id, "breach_id": breach_id, "amount": amount,
        }, account_id)
        return {
            "credit_id": cred.credit_id,
            "account_id": cred.account_id,
            "breach_id": cred.breach_id,
            "amount": cred.amount,
            "disposition": cred.disposition.value,
            "source_type": "remedy",
        }

    def billing_from_campaign_completion(
        self,
        invoice_id: str,
        account_id: str,
        campaign_id: str,
        amount: float,
        *,
        due_at: str = "",
    ) -> dict[str, Any]:
        """Create an invoice from a campaign completion."""
        inv = self._billing.create_invoice(
            invoice_id, account_id, due_at=due_at,
        )
        charge_id = stable_identifier("chg-camp", {
            "invoice": invoice_id, "campaign": campaign_id,
        })
        self._billing.add_charge(
            charge_id, invoice_id, amount,
            kind=ChargeKind.SERVICE,
            description=f"Campaign {campaign_id} completion",
            scope_ref_id=campaign_id,
            scope_ref_type="campaign",
        )
        _emit(self._events, "billing_from_campaign_completion", {
            "invoice_id": invoice_id, "campaign_id": campaign_id,
            "amount": amount,
        }, invoice_id)
        return {
            "invoice_id": inv.invoice_id,
            "account_id": inv.account_id,
            "charge_id": charge_id,
            "campaign_id": campaign_id,
            "amount": amount,
            "status": inv.status.value,
            "source_type": "campaign_completion",
        }

    def billing_from_reporting_requirement(
        self,
        invoice_id: str,
        account_id: str,
        requirement_id: str,
        amount: float,
        *,
        due_at: str = "",
    ) -> dict[str, Any]:
        """Create an invoice from a reporting requirement."""
        inv = self._billing.create_invoice(
            invoice_id, account_id, due_at=due_at,
        )
        charge_id = stable_identifier("chg-rpt", {
            "invoice": invoice_id, "requirement": requirement_id,
        })
        self._billing.add_charge(
            charge_id, invoice_id, amount,
            kind=ChargeKind.PROFESSIONAL_SERVICES,
            description=f"Reporting requirement {requirement_id}",
            scope_ref_id=requirement_id,
            scope_ref_type="reporting_requirement",
        )
        _emit(self._events, "billing_from_reporting_requirement", {
            "invoice_id": invoice_id, "requirement_id": requirement_id,
            "amount": amount,
        }, invoice_id)
        return {
            "invoice_id": inv.invoice_id,
            "account_id": inv.account_id,
            "charge_id": charge_id,
            "requirement_id": requirement_id,
            "amount": amount,
            "status": inv.status.value,
            "source_type": "reporting_requirement",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_billing_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist billing state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_accounts": self._billing.account_count,
            "total_invoices": self._billing.invoice_count,
            "total_charges": self._billing.charge_count,
            "total_credits": self._billing.credit_count,
            "total_penalties": self._billing.penalty_count,
            "total_disputes": self._billing.dispute_count,
            "total_violations": self._billing.violation_count,
            "recognized_revenue": self._billing.compute_recognized_revenue(),
            "pending_revenue": self._billing.compute_pending_revenue(),
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-bill", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Billing state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("billing", "revenue", "credit"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "billing_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_billing_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return billing state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_accounts": self._billing.account_count,
            "total_invoices": self._billing.invoice_count,
            "total_charges": self._billing.charge_count,
            "total_credits": self._billing.credit_count,
            "total_penalties": self._billing.penalty_count,
            "total_disputes": self._billing.dispute_count,
            "total_violations": self._billing.violation_count,
            "recognized_revenue": self._billing.compute_recognized_revenue(),
            "pending_revenue": self._billing.compute_pending_revenue(),
        }
