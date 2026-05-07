"""Purpose: settlement / payments / collections runtime engine.
Governance scope: recording payments, applying cash to invoices, tracking
    open balances and aging, managing collection cases and dunning notices,
    handling refunds and writeoffs, computing collected vs outstanding vs
    disputed cash state, producing immutable snapshots.
Dependencies: settlement_runtime contracts, event_spine, core invariants.
Invariants:
  - Disputes pause collection progression.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.settlement_runtime import (
    AgingSnapshot,
    CashApplication,
    CollectionCase,
    CollectionStatus,
    DunningNotice,
    DunningSeverity,
    PaymentMethodKind,
    PaymentRecord,
    PaymentStatus,
    RefundRecord,
    SettlementClosureReport,
    SettlementDecision,
    SettlementRecord,
    SettlementStatus,
    WriteoffDisposition,
    WriteoffRecord,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-sett", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_COLLECTION_TERMINAL = frozenset({
    CollectionStatus.RESOLVED,
    CollectionStatus.CLOSED,
})

_SETTLEMENT_TERMINAL = frozenset({
    SettlementStatus.SETTLED,
    SettlementStatus.WRITTEN_OFF,
})


class SettlementRuntimeEngine:
    """Settlement, payments, and collections engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._payments: dict[str, PaymentRecord] = {}
        self._settlements: dict[str, SettlementRecord] = {}
        self._collections: dict[str, CollectionCase] = {}
        self._dunning: dict[str, DunningNotice] = {}
        self._applications: dict[str, CashApplication] = {}
        self._refunds: dict[str, RefundRecord] = {}
        self._writeoffs: dict[str, WriteoffRecord] = {}
        self._decisions: dict[str, SettlementDecision] = {}
        self._snapshot_ids: set[str] = set()
        # Index: invoice_id -> settlement_id
        self._invoice_settlement: dict[str, str] = {}

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
    def payment_count(self) -> int:
        return len(self._payments)

    @property
    def settlement_count(self) -> int:
        return len(self._settlements)

    @property
    def collection_count(self) -> int:
        return len(self._collections)

    @property
    def dunning_count(self) -> int:
        return len(self._dunning)

    @property
    def application_count(self) -> int:
        return len(self._applications)

    @property
    def refund_count(self) -> int:
        return len(self._refunds)

    @property
    def writeoff_count(self) -> int:
        return len(self._writeoffs)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    # ------------------------------------------------------------------
    # Settlements (balance tracking per invoice)
    # ------------------------------------------------------------------

    def create_settlement(
        self,
        settlement_id: str,
        invoice_id: str,
        account_id: str,
        total_amount: float,
        *,
        currency: str = "USD",
    ) -> SettlementRecord:
        """Create a settlement record for an invoice."""
        if settlement_id in self._settlements:
            raise RuntimeCoreInvariantError("Duplicate settlement_id")
        if invoice_id in self._invoice_settlement:
            raise RuntimeCoreInvariantError("Invoice already has a settlement")
        now = self._now()
        s = SettlementRecord(
            settlement_id=settlement_id,
            invoice_id=invoice_id,
            account_id=account_id,
            total_amount=total_amount,
            paid_amount=0.0,
            credit_applied=0.0,
            outstanding=total_amount,
            status=SettlementStatus.OPEN,
            currency=currency,
            created_at=now,
        )
        self._settlements[settlement_id] = s
        self._invoice_settlement[invoice_id] = settlement_id
        _emit(self._events, "settlement_created", {
            "settlement_id": settlement_id, "invoice_id": invoice_id,
            "total_amount": total_amount,
        }, settlement_id, self._now())
        return s

    def get_settlement(self, settlement_id: str) -> SettlementRecord:
        """Get a settlement by ID."""
        s = self._settlements.get(settlement_id)
        if s is None:
            raise RuntimeCoreInvariantError("Unknown settlement_id")
        return s

    def settlement_for_invoice(self, invoice_id: str) -> SettlementRecord:
        """Get the settlement for an invoice."""
        sid = self._invoice_settlement.get(invoice_id)
        if sid is None:
            raise RuntimeCoreInvariantError("No settlement for invoice")
        return self._settlements[sid]

    def settlements_for_account(self, account_id: str) -> tuple[SettlementRecord, ...]:
        """Return all settlements for an account."""
        return tuple(
            s for s in self._settlements.values() if s.account_id == account_id
        )

    def _update_settlement_status(self, settlement_id: str) -> SettlementRecord:
        """Recompute settlement status based on current amounts."""
        old = self._settlements[settlement_id]
        if old.outstanding <= 0.0:
            status = SettlementStatus.SETTLED
        elif old.paid_amount > 0.0 or old.credit_applied > 0.0:
            status = SettlementStatus.PARTIAL
        else:
            status = old.status
        if status != old.status:
            updated = SettlementRecord(
                settlement_id=old.settlement_id,
                invoice_id=old.invoice_id,
                account_id=old.account_id,
                total_amount=old.total_amount,
                paid_amount=old.paid_amount,
                credit_applied=old.credit_applied,
                outstanding=old.outstanding,
                status=status,
                currency=old.currency,
                created_at=old.created_at,
                metadata=old.metadata,
            )
            self._settlements[settlement_id] = updated
            return updated
        return old

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def record_payment(
        self,
        payment_id: str,
        invoice_id: str,
        account_id: str,
        amount: float,
        *,
        currency: str = "USD",
        method: PaymentMethodKind = PaymentMethodKind.BANK_TRANSFER,
        reference: str = "",
    ) -> PaymentRecord:
        """Record a payment received."""
        if payment_id in self._payments:
            raise RuntimeCoreInvariantError("Duplicate payment_id")
        now = self._now()
        p = PaymentRecord(
            payment_id=payment_id,
            invoice_id=invoice_id,
            account_id=account_id,
            amount=amount,
            currency=currency,
            method=method,
            status=PaymentStatus.CLEARED,
            reference=reference,
            received_at=now,
        )
        self._payments[payment_id] = p
        _emit(self._events, "payment_recorded", {
            "payment_id": payment_id, "invoice_id": invoice_id,
            "amount": amount,
        }, payment_id, self._now())
        return p

    def get_payment(self, payment_id: str) -> PaymentRecord:
        """Get a payment by ID."""
        p = self._payments.get(payment_id)
        if p is None:
            raise RuntimeCoreInvariantError("Unknown payment_id")
        return p

    def payments_for_invoice(self, invoice_id: str) -> tuple[PaymentRecord, ...]:
        """Return all payments for an invoice."""
        return tuple(
            p for p in self._payments.values() if p.invoice_id == invoice_id
        )

    # ------------------------------------------------------------------
    # Cash application
    # ------------------------------------------------------------------

    def apply_cash(
        self,
        application_id: str,
        settlement_id: str,
        payment_id: str,
        amount: float,
    ) -> CashApplication:
        """Apply a payment to a settlement."""
        if application_id in self._applications:
            raise RuntimeCoreInvariantError("Duplicate application_id")
        s = self.get_settlement(settlement_id)
        if s.status in _SETTLEMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot apply cash to settlement in current status")
        if payment_id not in self._payments:
            raise RuntimeCoreInvariantError("Unknown payment_id")

        # Cap application at outstanding amount
        effective = min(amount, s.outstanding)
        now = self._now()
        app = CashApplication(
            application_id=application_id,
            settlement_id=settlement_id,
            payment_id=payment_id,
            amount=effective,
            applied_at=now,
        )
        self._applications[application_id] = app

        # Update settlement amounts
        new_paid = s.paid_amount + effective
        new_outstanding = max(0.0, s.outstanding - effective)
        updated = SettlementRecord(
            settlement_id=s.settlement_id,
            invoice_id=s.invoice_id,
            account_id=s.account_id,
            total_amount=s.total_amount,
            paid_amount=new_paid,
            credit_applied=s.credit_applied,
            outstanding=new_outstanding,
            status=s.status,
            currency=s.currency,
            created_at=s.created_at,
            metadata=s.metadata,
        )
        self._settlements[settlement_id] = updated
        self._update_settlement_status(settlement_id)

        _emit(self._events, "cash_applied", {
            "application_id": application_id, "settlement_id": settlement_id,
            "amount": effective,
        }, settlement_id, self._now())
        return app

    def apply_credit(
        self,
        application_id: str,
        settlement_id: str,
        credit_ref: str,
        amount: float,
    ) -> CashApplication:
        """Apply a credit against a settlement balance."""
        if application_id in self._applications:
            raise RuntimeCoreInvariantError("Duplicate application_id")
        s = self.get_settlement(settlement_id)
        if s.status in _SETTLEMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot apply credit to settlement in current status")

        effective = min(amount, s.outstanding)
        now = self._now()
        app = CashApplication(
            application_id=application_id,
            settlement_id=settlement_id,
            payment_id=credit_ref,
            amount=effective,
            applied_at=now,
        )
        self._applications[application_id] = app

        new_credit = s.credit_applied + effective
        new_outstanding = max(0.0, s.outstanding - effective)
        updated = SettlementRecord(
            settlement_id=s.settlement_id,
            invoice_id=s.invoice_id,
            account_id=s.account_id,
            total_amount=s.total_amount,
            paid_amount=s.paid_amount,
            credit_applied=new_credit,
            outstanding=new_outstanding,
            status=s.status,
            currency=s.currency,
            created_at=s.created_at,
            metadata=s.metadata,
        )
        self._settlements[settlement_id] = updated
        self._update_settlement_status(settlement_id)

        _emit(self._events, "credit_applied_to_settlement", {
            "application_id": application_id, "settlement_id": settlement_id,
            "amount": effective,
        }, settlement_id, self._now())
        return app

    def applications_for_settlement(
        self, settlement_id: str,
    ) -> tuple[CashApplication, ...]:
        """Return all applications for a settlement."""
        return tuple(
            a for a in self._applications.values()
            if a.settlement_id == settlement_id
        )

    # ------------------------------------------------------------------
    # Collection cases
    # ------------------------------------------------------------------

    def open_collection_case(
        self,
        case_id: str,
        invoice_id: str,
        account_id: str,
        outstanding_amount: float,
    ) -> CollectionCase:
        """Open a collection case for an unpaid invoice."""
        if case_id in self._collections:
            raise RuntimeCoreInvariantError("Duplicate case_id")
        now = self._now()
        c = CollectionCase(
            case_id=case_id,
            invoice_id=invoice_id,
            account_id=account_id,
            status=CollectionStatus.OPEN,
            outstanding_amount=outstanding_amount,
            dunning_count=0,
            opened_at=now,
        )
        self._collections[case_id] = c
        _emit(self._events, "collection_case_opened", {
            "case_id": case_id, "invoice_id": invoice_id,
            "outstanding_amount": outstanding_amount,
        }, case_id, self._now())
        return c

    def get_collection_case(self, case_id: str) -> CollectionCase:
        """Get a collection case by ID."""
        c = self._collections.get(case_id)
        if c is None:
            raise RuntimeCoreInvariantError("Unknown case_id")
        return c

    def escalate_collection(self, case_id: str) -> CollectionCase:
        """Escalate a collection case."""
        old = self.get_collection_case(case_id)
        if old.status in _COLLECTION_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot escalate collection in current status")
        updated = CollectionCase(
            case_id=old.case_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=CollectionStatus.ESCALATED,
            outstanding_amount=old.outstanding_amount,
            dunning_count=old.dunning_count,
            opened_at=old.opened_at,
            closed_at=old.closed_at,
            metadata=old.metadata,
        )
        self._collections[case_id] = updated
        _emit(self._events, "collection_escalated", {
            "case_id": case_id,
        }, case_id, self._now())
        return updated

    def pause_collection(self, case_id: str) -> CollectionCase:
        """Pause a collection case (e.g., due to dispute)."""
        old = self.get_collection_case(case_id)
        if old.status in _COLLECTION_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot pause collection in current status")
        updated = CollectionCase(
            case_id=old.case_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=CollectionStatus.PAUSED,
            outstanding_amount=old.outstanding_amount,
            dunning_count=old.dunning_count,
            opened_at=old.opened_at,
            closed_at=old.closed_at,
            metadata=old.metadata,
        )
        self._collections[case_id] = updated
        _emit(self._events, "collection_paused", {
            "case_id": case_id,
        }, case_id, self._now())
        return updated

    def resume_collection(self, case_id: str) -> CollectionCase:
        """Resume a paused collection case."""
        old = self.get_collection_case(case_id)
        if old.status != CollectionStatus.PAUSED:
            raise RuntimeCoreInvariantError("Can only resume paused collections")
        updated = CollectionCase(
            case_id=old.case_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=CollectionStatus.IN_PROGRESS,
            outstanding_amount=old.outstanding_amount,
            dunning_count=old.dunning_count,
            opened_at=old.opened_at,
            closed_at=old.closed_at,
            metadata=old.metadata,
        )
        self._collections[case_id] = updated
        _emit(self._events, "collection_resumed", {
            "case_id": case_id,
        }, case_id, self._now())
        return updated

    def resolve_collection(self, case_id: str) -> CollectionCase:
        """Resolve a collection case (payment received)."""
        old = self.get_collection_case(case_id)
        if old.status in _COLLECTION_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot resolve collection in current status")
        now = self._now()
        updated = CollectionCase(
            case_id=old.case_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=CollectionStatus.RESOLVED,
            outstanding_amount=0.0,
            dunning_count=old.dunning_count,
            opened_at=old.opened_at,
            closed_at=now,
            metadata=old.metadata,
        )
        self._collections[case_id] = updated
        _emit(self._events, "collection_resolved", {
            "case_id": case_id,
        }, case_id, self._now())
        return updated

    def close_collection(self, case_id: str) -> CollectionCase:
        """Close a collection case."""
        old = self.get_collection_case(case_id)
        if old.status == CollectionStatus.CLOSED:
            raise RuntimeCoreInvariantError("Collection already closed")
        now = self._now()
        updated = CollectionCase(
            case_id=old.case_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=CollectionStatus.CLOSED,
            outstanding_amount=old.outstanding_amount,
            dunning_count=old.dunning_count,
            opened_at=old.opened_at,
            closed_at=now,
            metadata=old.metadata,
        )
        self._collections[case_id] = updated
        _emit(self._events, "collection_closed", {
            "case_id": case_id,
        }, case_id, self._now())
        return updated

    def collections_for_account(
        self, account_id: str,
    ) -> tuple[CollectionCase, ...]:
        """Return all collection cases for an account."""
        return tuple(
            c for c in self._collections.values() if c.account_id == account_id
        )

    # ------------------------------------------------------------------
    # Dunning notices
    # ------------------------------------------------------------------

    def issue_dunning_notice(
        self,
        notice_id: str,
        case_id: str,
        account_id: str,
        *,
        severity: DunningSeverity = DunningSeverity.REMINDER,
        message: str = "",
    ) -> DunningNotice:
        """Issue a dunning notice for a collection case."""
        if notice_id in self._dunning:
            raise RuntimeCoreInvariantError("Duplicate notice_id")
        cc = self.get_collection_case(case_id)
        if cc.status in _COLLECTION_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot issue dunning for collection in current status")
        now = self._now()
        notice = DunningNotice(
            notice_id=notice_id,
            case_id=case_id,
            account_id=account_id,
            severity=severity,
            message=message,
            sent_at=now,
        )
        self._dunning[notice_id] = notice

        # Increment dunning count on collection case
        updated_cc = CollectionCase(
            case_id=cc.case_id,
            invoice_id=cc.invoice_id,
            account_id=cc.account_id,
            status=CollectionStatus.IN_PROGRESS if cc.status == CollectionStatus.OPEN else cc.status,
            outstanding_amount=cc.outstanding_amount,
            dunning_count=cc.dunning_count + 1,
            opened_at=cc.opened_at,
            closed_at=cc.closed_at,
            metadata=cc.metadata,
        )
        self._collections[case_id] = updated_cc

        _emit(self._events, "dunning_notice_issued", {
            "notice_id": notice_id, "case_id": case_id,
            "severity": severity.value,
        }, case_id, self._now())
        return notice

    def notices_for_case(self, case_id: str) -> tuple[DunningNotice, ...]:
        """Return all dunning notices for a case."""
        return tuple(
            n for n in self._dunning.values() if n.case_id == case_id
        )

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    def record_refund(
        self,
        refund_id: str,
        payment_id: str,
        account_id: str,
        amount: float,
        *,
        reason: str = "",
    ) -> RefundRecord:
        """Record a refund against a payment."""
        if refund_id in self._refunds:
            raise RuntimeCoreInvariantError("Duplicate refund_id")
        if payment_id not in self._payments:
            raise RuntimeCoreInvariantError("Unknown payment_id")
        now = self._now()
        refund = RefundRecord(
            refund_id=refund_id,
            payment_id=payment_id,
            account_id=account_id,
            amount=amount,
            reason=reason,
            refunded_at=now,
        )
        self._refunds[refund_id] = refund

        # Mark payment as reversed if refund equals full amount
        pay = self._payments[payment_id]
        total_refunded = sum(
            r.amount for r in self._refunds.values() if r.payment_id == payment_id
        )
        if total_refunded >= pay.amount:
            reversed_pay = PaymentRecord(
                payment_id=pay.payment_id,
                invoice_id=pay.invoice_id,
                account_id=pay.account_id,
                amount=pay.amount,
                currency=pay.currency,
                method=pay.method,
                status=PaymentStatus.REVERSED,
                reference=pay.reference,
                received_at=pay.received_at,
                metadata=pay.metadata,
            )
            self._payments[payment_id] = reversed_pay

        _emit(self._events, "refund_recorded", {
            "refund_id": refund_id, "payment_id": payment_id,
            "amount": amount,
        }, payment_id, self._now())
        return refund

    def refunds_for_payment(self, payment_id: str) -> tuple[RefundRecord, ...]:
        """Return all refunds for a payment."""
        return tuple(
            r for r in self._refunds.values() if r.payment_id == payment_id
        )

    # ------------------------------------------------------------------
    # Writeoffs
    # ------------------------------------------------------------------

    def record_writeoff(
        self,
        writeoff_id: str,
        settlement_id: str,
        account_id: str,
        amount: float,
        *,
        reason: str = "",
    ) -> WriteoffRecord:
        """Record a writeoff of uncollectable balance."""
        if writeoff_id in self._writeoffs:
            raise RuntimeCoreInvariantError("Duplicate writeoff_id")
        s = self.get_settlement(settlement_id)
        if s.status in _SETTLEMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot write off settlement in current status")
        now = self._now()
        effective = min(amount, s.outstanding)
        wo = WriteoffRecord(
            writeoff_id=writeoff_id,
            settlement_id=settlement_id,
            account_id=account_id,
            amount=effective,
            disposition=WriteoffDisposition.APPROVED,
            reason=reason,
            written_off_at=now,
        )
        self._writeoffs[writeoff_id] = wo

        # Update settlement outstanding and status
        new_outstanding = max(0.0, s.outstanding - effective)
        status = SettlementStatus.WRITTEN_OFF if new_outstanding <= 0.0 else s.status
        updated = SettlementRecord(
            settlement_id=s.settlement_id,
            invoice_id=s.invoice_id,
            account_id=s.account_id,
            total_amount=s.total_amount,
            paid_amount=s.paid_amount,
            credit_applied=s.credit_applied,
            outstanding=new_outstanding,
            status=status,
            currency=s.currency,
            created_at=s.created_at,
            metadata=s.metadata,
        )
        self._settlements[settlement_id] = updated

        _emit(self._events, "writeoff_recorded", {
            "writeoff_id": writeoff_id, "settlement_id": settlement_id,
            "amount": effective,
        }, settlement_id, self._now())
        return wo

    def writeoffs_for_settlement(
        self, settlement_id: str,
    ) -> tuple[WriteoffRecord, ...]:
        """Return all writeoffs for a settlement."""
        return tuple(
            w for w in self._writeoffs.values() if w.settlement_id == settlement_id
        )

    # ------------------------------------------------------------------
    # Dispute interaction
    # ------------------------------------------------------------------

    def mark_settlement_disputed(self, settlement_id: str) -> SettlementRecord:
        """Mark a settlement as disputed (pauses collection)."""
        old = self.get_settlement(settlement_id)
        if old.status in _SETTLEMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot dispute settlement in current status")
        updated = SettlementRecord(
            settlement_id=old.settlement_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            total_amount=old.total_amount,
            paid_amount=old.paid_amount,
            credit_applied=old.credit_applied,
            outstanding=old.outstanding,
            status=SettlementStatus.DISPUTED,
            currency=old.currency,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._settlements[settlement_id] = updated
        _emit(self._events, "settlement_disputed", {
            "settlement_id": settlement_id,
        }, settlement_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Revenue computations
    # ------------------------------------------------------------------

    def compute_total_collected(self) -> float:
        """Total cash collected (cleared payments minus refunds)."""
        total_payments = sum(
            p.amount for p in self._payments.values()
            if p.status == PaymentStatus.CLEARED
        )
        total_refunds = sum(r.amount for r in self._refunds.values())
        return max(0.0, total_payments - total_refunds)

    def compute_total_outstanding(self) -> float:
        """Total outstanding across all non-terminal settlements."""
        return sum(
            s.outstanding for s in self._settlements.values()
            if s.status not in _SETTLEMENT_TERMINAL
        )

    def compute_total_disputed(self) -> float:
        """Total outstanding in disputed settlements."""
        return sum(
            s.outstanding for s in self._settlements.values()
            if s.status == SettlementStatus.DISPUTED
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_settlement_violations(self) -> tuple[SettlementDecision, ...]:
        """Detect settlement violations and produce decisions."""
        now = self._now()
        new_decisions: list[SettlementDecision] = []

        # Collection cases with 3+ dunning notices without resolution -> escalation decision
        for cc in list(self._collections.values()):
            if cc.status not in _COLLECTION_TERMINAL and cc.dunning_count >= 3:
                did = stable_identifier("dec-sett", {
                    "case": cc.case_id, "op": "escalation_needed",
                })
                if did not in self._decisions:
                    d = SettlementDecision(
                        decision_id=did,
                        settlement_id=cc.case_id,
                        description="Collection case requires dunning escalation",
                        decided_by="settlement_engine",
                        decided_at=now,
                    )
                    self._decisions[did] = d
                    new_decisions.append(d)

                    # Auto-escalate if not already
                    if cc.status not in (CollectionStatus.ESCALATED, CollectionStatus.PAUSED):
                        self.escalate_collection(cc.case_id)

        # Settlements open with zero payments for extended periods (flag)
        for s in self._settlements.values():
            if s.status == SettlementStatus.OPEN and s.paid_amount == 0.0 and s.credit_applied == 0.0:
                did = stable_identifier("dec-sett", {
                    "sett": s.settlement_id, "op": "no_payment",
                })
                if did not in self._decisions:
                    d = SettlementDecision(
                        decision_id=did,
                        settlement_id=s.settlement_id,
                        description="Settlement has no payments applied",
                        decided_by="settlement_engine",
                        decided_at=now,
                    )
                    self._decisions[did] = d
                    new_decisions.append(d)

        if new_decisions:
            _emit(self._events, "settlement_violations_detected", {
                "count": len(new_decisions),
            }, "violation-scan", self._now())
        return tuple(new_decisions)

    def decisions_for_settlement(
        self, settlement_id: str,
    ) -> tuple[SettlementDecision, ...]:
        """Return all decisions for a settlement."""
        return tuple(
            d for d in self._decisions.values() if d.settlement_id == settlement_id
        )

    # ------------------------------------------------------------------
    # Aging snapshot
    # ------------------------------------------------------------------

    def aging_snapshot(self, snapshot_id: str) -> AgingSnapshot:
        """Capture a point-in-time aging snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._now()
        snap = AgingSnapshot(
            snapshot_id=snapshot_id,
            total_settlements=self.settlement_count,
            total_open=sum(
                1 for s in self._settlements.values()
                if s.status == SettlementStatus.OPEN
            ),
            total_partial=sum(
                1 for s in self._settlements.values()
                if s.status == SettlementStatus.PARTIAL
            ),
            total_settled=sum(
                1 for s in self._settlements.values()
                if s.status == SettlementStatus.SETTLED
            ),
            total_disputed=sum(
                1 for s in self._settlements.values()
                if s.status == SettlementStatus.DISPUTED
            ),
            total_written_off=sum(
                1 for s in self._settlements.values()
                if s.status == SettlementStatus.WRITTEN_OFF
            ),
            total_outstanding=self.compute_total_outstanding(),
            total_collected=self.compute_total_collected(),
            total_refunded=sum(r.amount for r in self._refunds.values()),
            total_collection_cases=self.collection_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "aging_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, self._now())
        return snap

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def _collections_map(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "payments": self._payments,
            "settlements": self._settlements,
            "collections": self._collections,
            "dunning": self._dunning,
            "applications": self._applications,
            "refunds": self._refunds,
            "writeoffs": self._writeoffs,
            "decisions": self._decisions,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections_map().items():
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
        result["snapshot_ids"] = sorted(self._snapshot_ids)
        result["invoice_settlement"] = dict(self._invoice_settlement)
        result["_state_hash"] = self.state_hash()
        return result

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"payments={self.payment_count}",
            f"settlements={self.settlement_count}",
            f"collections={self.collection_count}",
            f"dunning={self.dunning_count}",
            f"applications={self.application_count}",
            f"refunds={self.refund_count}",
            f"writeoffs={self.writeoff_count}",
            f"decisions={self.decision_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
