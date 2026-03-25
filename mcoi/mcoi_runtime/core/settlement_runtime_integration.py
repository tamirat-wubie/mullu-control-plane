"""Purpose: settlement runtime integration bridge.
Governance scope: composing settlement runtime with billing invoices,
    disputes, credits, and penalties; memory mesh and operational graph
    attachment.
Dependencies: settlement_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every settlement creation emits events.
  - Settlement state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.settlement_runtime import PaymentMethodKind
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
from .settlement_runtime import SettlementRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-sint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class SettlementRuntimeIntegration:
    """Integration bridge for settlement runtime with platform layers."""

    def __init__(
        self,
        settlement_engine: SettlementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(settlement_engine, SettlementRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "settlement_engine must be a SettlementRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._settlement = settlement_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Settlement creation helpers
    # ------------------------------------------------------------------

    def settlement_from_invoice(
        self,
        settlement_id: str,
        invoice_id: str,
        account_id: str,
        total_amount: float,
        *,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a settlement from an issued invoice."""
        s = self._settlement.create_settlement(
            settlement_id, invoice_id, account_id, total_amount,
            currency=currency,
        )
        _emit(self._events, "settlement_from_invoice", {
            "settlement_id": settlement_id, "invoice_id": invoice_id,
            "total_amount": total_amount,
        }, settlement_id)
        return {
            "settlement_id": s.settlement_id,
            "invoice_id": s.invoice_id,
            "account_id": s.account_id,
            "total_amount": s.total_amount,
            "outstanding": s.outstanding,
            "status": s.status.value,
            "source_type": "invoice",
        }

    def settlement_from_dispute(
        self,
        settlement_id: str,
    ) -> dict[str, Any]:
        """Mark an existing settlement as disputed."""
        s = self._settlement.mark_settlement_disputed(settlement_id)
        _emit(self._events, "settlement_from_dispute", {
            "settlement_id": settlement_id,
        }, settlement_id)
        return {
            "settlement_id": s.settlement_id,
            "invoice_id": s.invoice_id,
            "status": s.status.value,
            "outstanding": s.outstanding,
            "source_type": "dispute",
        }

    def settlement_from_credit(
        self,
        application_id: str,
        settlement_id: str,
        credit_ref: str,
        amount: float,
    ) -> dict[str, Any]:
        """Apply a credit to a settlement."""
        app = self._settlement.apply_credit(
            application_id, settlement_id, credit_ref, amount,
        )
        s = self._settlement.get_settlement(settlement_id)
        _emit(self._events, "settlement_from_credit", {
            "application_id": application_id, "settlement_id": settlement_id,
            "amount": app.amount,
        }, settlement_id)
        return {
            "application_id": app.application_id,
            "settlement_id": settlement_id,
            "credit_ref": credit_ref,
            "amount": app.amount,
            "outstanding": s.outstanding,
            "status": s.status.value,
            "source_type": "credit",
        }

    def settlement_from_penalty(
        self,
        payment_id: str,
        invoice_id: str,
        account_id: str,
        amount: float,
        *,
        method: PaymentMethodKind = PaymentMethodKind.BANK_TRANSFER,
    ) -> dict[str, Any]:
        """Record a penalty payment (payment against a penalty invoice)."""
        p = self._settlement.record_payment(
            payment_id, invoice_id, account_id, amount, method=method,
        )
        _emit(self._events, "settlement_from_penalty", {
            "payment_id": payment_id, "invoice_id": invoice_id,
            "amount": amount,
        }, payment_id)
        return {
            "payment_id": p.payment_id,
            "invoice_id": p.invoice_id,
            "account_id": p.account_id,
            "amount": p.amount,
            "status": p.status.value,
            "source_type": "penalty",
        }

    def open_collection_from_overdue(
        self,
        case_id: str,
        invoice_id: str,
        account_id: str,
        outstanding_amount: float,
    ) -> dict[str, Any]:
        """Open a collection case from an overdue invoice."""
        cc = self._settlement.open_collection_case(
            case_id, invoice_id, account_id, outstanding_amount,
        )
        _emit(self._events, "collection_from_overdue", {
            "case_id": case_id, "invoice_id": invoice_id,
            "outstanding_amount": outstanding_amount,
        }, case_id)
        return {
            "case_id": cc.case_id,
            "invoice_id": cc.invoice_id,
            "account_id": cc.account_id,
            "outstanding_amount": cc.outstanding_amount,
            "status": cc.status.value,
            "source_type": "overdue",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_settlement_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist settlement state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_settlements": self._settlement.settlement_count,
            "total_payments": self._settlement.payment_count,
            "total_collections": self._settlement.collection_count,
            "total_refunds": self._settlement.refund_count,
            "total_writeoffs": self._settlement.writeoff_count,
            "total_collected": self._settlement.compute_total_collected(),
            "total_outstanding": self._settlement.compute_total_outstanding(),
            "total_disputed": self._settlement.compute_total_disputed(),
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-sett", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Settlement state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("settlement", "payments", "collections"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "settlement_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_settlement_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return settlement state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_settlements": self._settlement.settlement_count,
            "total_payments": self._settlement.payment_count,
            "total_collections": self._settlement.collection_count,
            "total_refunds": self._settlement.refund_count,
            "total_writeoffs": self._settlement.writeoff_count,
            "total_collected": self._settlement.compute_total_collected(),
            "total_outstanding": self._settlement.compute_total_outstanding(),
            "total_disputed": self._settlement.compute_total_disputed(),
        }
