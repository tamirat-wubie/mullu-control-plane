"""Purpose: revenue / billing / credit runtime engine.
Governance scope: registering billing accounts; generating charges, credits,
    and penalties; tracking invoices and disputes; computing revenue recognition;
    detecting billing violations; producing immutable snapshots.
Dependencies: billing_runtime contracts, event_spine, core invariants.
Invariants:
  - Incomplete invoices cannot be issued.
  - Disputes pause revenue recognition.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.billing_runtime import (
    BillingAccount,
    BillingClosureReport,
    BillingDecision,
    BillingStatus,
    BillingViolation,
    ChargeKind,
    ChargeRecord,
    CreditDisposition,
    CreditRecord,
    DisputeRecord,
    DisputeStatus,
    InvoiceRecord,
    InvoiceStatus,
    PenaltyRecord,
    RevenueRecognitionStatus,
    RevenueSnapshot,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-bill", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_INVOICE_TERMINAL = frozenset({InvoiceStatus.PAID, InvoiceStatus.VOIDED})
_DISPUTE_TERMINAL = frozenset({
    DisputeStatus.RESOLVED_ACCEPTED,
    DisputeStatus.RESOLVED_REJECTED,
    DisputeStatus.WITHDRAWN,
})


class BillingRuntimeEngine:
    """Revenue, billing, and credit engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._accounts: dict[str, BillingAccount] = {}
        self._invoices: dict[str, InvoiceRecord] = {}
        self._charges: dict[str, ChargeRecord] = {}
        self._credits: dict[str, CreditRecord] = {}
        self._penalties: dict[str, PenaltyRecord] = {}
        self._disputes: dict[str, DisputeRecord] = {}
        self._decisions: dict[str, BillingDecision] = {}
        self._violations: dict[str, BillingViolation] = {}
        self._snapshot_ids: set[str] = set()

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
    def account_count(self) -> int:
        return len(self._accounts)

    @property
    def invoice_count(self) -> int:
        return len(self._invoices)

    @property
    def charge_count(self) -> int:
        return len(self._charges)

    @property
    def credit_count(self) -> int:
        return len(self._credits)

    @property
    def penalty_count(self) -> int:
        return len(self._penalties)

    @property
    def dispute_count(self) -> int:
        return len(self._disputes)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def register_account(
        self,
        account_id: str,
        tenant_id: str,
        counterparty: str,
        *,
        currency: str = "USD",
    ) -> BillingAccount:
        """Register a billing account."""
        if account_id in self._accounts:
            raise RuntimeCoreInvariantError("Duplicate account_id")
        now = self._now()
        acct = BillingAccount(
            account_id=account_id,
            tenant_id=tenant_id,
            counterparty=counterparty,
            status=BillingStatus.ACTIVE,
            currency=currency,
            created_at=now,
        )
        self._accounts[account_id] = acct
        _emit(self._events, "account_registered", {
            "account_id": account_id, "counterparty": counterparty,
        }, account_id, self._now())
        return acct

    def get_account(self, account_id: str) -> BillingAccount:
        """Get a billing account by ID."""
        a = self._accounts.get(account_id)
        if a is None:
            raise RuntimeCoreInvariantError("Unknown account_id")
        return a

    def suspend_account(self, account_id: str) -> BillingAccount:
        """Suspend a billing account."""
        old = self.get_account(account_id)
        if old.status != BillingStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only suspend ACTIVE accounts")
        updated = BillingAccount(
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=BillingStatus.SUSPENDED,
            currency=old.currency,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._accounts[account_id] = updated
        _emit(self._events, "account_suspended", {
            "account_id": account_id,
        }, account_id, self._now())
        return updated

    def close_account(self, account_id: str) -> BillingAccount:
        """Close a billing account."""
        old = self.get_account(account_id)
        if old.status == BillingStatus.CLOSED:
            raise RuntimeCoreInvariantError("Account already closed")
        updated = BillingAccount(
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=BillingStatus.CLOSED,
            currency=old.currency,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._accounts[account_id] = updated
        _emit(self._events, "account_closed", {
            "account_id": account_id,
        }, account_id, self._now())
        return updated

    def accounts_for_tenant(self, tenant_id: str) -> tuple[BillingAccount, ...]:
        """Return all accounts for a tenant."""
        return tuple(a for a in self._accounts.values() if a.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def create_invoice(
        self,
        invoice_id: str,
        account_id: str,
        *,
        due_at: str = "",
        currency: str = "",
    ) -> InvoiceRecord:
        """Create an invoice for a billing account."""
        if invoice_id in self._invoices:
            raise RuntimeCoreInvariantError("Duplicate invoice_id")
        acct = self.get_account(account_id)
        now = self._now()
        if not due_at:
            due_at = now
        if not currency:
            currency = acct.currency
        inv = InvoiceRecord(
            invoice_id=invoice_id,
            account_id=account_id,
            tenant_id=acct.tenant_id,
            status=InvoiceStatus.DRAFT,
            total_amount=0.0,
            currency=currency,
            issued_at=now,
            due_at=due_at,
        )
        self._invoices[invoice_id] = inv
        _emit(self._events, "invoice_created", {
            "invoice_id": invoice_id, "account_id": account_id,
        }, invoice_id, self._now())
        return inv

    def get_invoice(self, invoice_id: str) -> InvoiceRecord:
        """Get an invoice by ID."""
        i = self._invoices.get(invoice_id)
        if i is None:
            raise RuntimeCoreInvariantError("Unknown invoice_id")
        return i

    def issue_invoice(self, invoice_id: str) -> InvoiceRecord:
        """Issue a draft invoice."""
        old = self.get_invoice(invoice_id)
        if old.status != InvoiceStatus.DRAFT:
            raise RuntimeCoreInvariantError("Can only issue DRAFT invoices")
        # Compute total from charges
        charges = self.charges_for_invoice(invoice_id)
        total = sum(c.amount for c in charges)
        updated = InvoiceRecord(
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            status=InvoiceStatus.ISSUED,
            total_amount=total,
            currency=old.currency,
            issued_at=self._now(),
            due_at=old.due_at,
            metadata=old.metadata,
        )
        self._invoices[invoice_id] = updated
        _emit(self._events, "invoice_issued", {
            "invoice_id": invoice_id, "total_amount": total,
        }, invoice_id, self._now())
        return updated

    def pay_invoice(self, invoice_id: str) -> InvoiceRecord:
        """Mark an invoice as paid."""
        old = self.get_invoice(invoice_id)
        if old.status in _INVOICE_TERMINAL:
            raise RuntimeCoreInvariantError("cannot pay finalized invoice")
        updated = InvoiceRecord(
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            status=InvoiceStatus.PAID,
            total_amount=old.total_amount,
            currency=old.currency,
            issued_at=old.issued_at,
            due_at=old.due_at,
            metadata=old.metadata,
        )
        self._invoices[invoice_id] = updated
        _emit(self._events, "invoice_paid", {
            "invoice_id": invoice_id,
        }, invoice_id, self._now())
        return updated

    def void_invoice(self, invoice_id: str) -> InvoiceRecord:
        """Void an invoice."""
        old = self.get_invoice(invoice_id)
        if old.status in _INVOICE_TERMINAL:
            raise RuntimeCoreInvariantError("cannot void finalized invoice")
        updated = InvoiceRecord(
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            tenant_id=old.tenant_id,
            status=InvoiceStatus.VOIDED,
            total_amount=old.total_amount,
            currency=old.currency,
            issued_at=old.issued_at,
            due_at=old.due_at,
            metadata=old.metadata,
        )
        self._invoices[invoice_id] = updated
        _emit(self._events, "invoice_voided", {
            "invoice_id": invoice_id,
        }, invoice_id, self._now())
        return updated

    def invoices_for_account(self, account_id: str) -> tuple[InvoiceRecord, ...]:
        """Return all invoices for an account."""
        return tuple(i for i in self._invoices.values() if i.account_id == account_id)

    # ------------------------------------------------------------------
    # Charges
    # ------------------------------------------------------------------

    def add_charge(
        self,
        charge_id: str,
        invoice_id: str,
        amount: float,
        *,
        kind: ChargeKind = ChargeKind.SERVICE,
        description: str = "",
        scope_ref_id: str = "",
        scope_ref_type: str = "",
    ) -> ChargeRecord:
        """Add a charge to an invoice."""
        if charge_id in self._charges:
            raise RuntimeCoreInvariantError("Duplicate charge_id")
        inv = self.get_invoice(invoice_id)
        if inv.status in _INVOICE_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot add charge to terminal invoice")
        now = self._now()
        charge = ChargeRecord(
            charge_id=charge_id,
            invoice_id=invoice_id,
            kind=kind,
            description=description,
            amount=amount,
            scope_ref_id=scope_ref_id,
            scope_ref_type=scope_ref_type,
            created_at=now,
        )
        self._charges[charge_id] = charge
        _emit(self._events, "charge_added", {
            "charge_id": charge_id, "invoice_id": invoice_id,
            "amount": amount, "kind": kind.value,
        }, invoice_id, self._now())
        return charge

    def charges_for_invoice(self, invoice_id: str) -> tuple[ChargeRecord, ...]:
        """Return all charges for an invoice."""
        return tuple(c for c in self._charges.values() if c.invoice_id == invoice_id)

    # ------------------------------------------------------------------
    # Credits
    # ------------------------------------------------------------------

    def add_credit(
        self,
        credit_id: str,
        account_id: str,
        breach_id: str,
        amount: float,
        *,
        reason: str = "",
    ) -> CreditRecord:
        """Add a credit to an account from a breach."""
        if credit_id in self._credits:
            raise RuntimeCoreInvariantError("Duplicate credit_id")
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("Unknown account_id")
        now = self._now()
        credit = CreditRecord(
            credit_id=credit_id,
            account_id=account_id,
            breach_id=breach_id,
            disposition=CreditDisposition.APPLIED,
            amount=amount,
            reason=reason,
            applied_at=now,
        )
        self._credits[credit_id] = credit
        _emit(self._events, "credit_added", {
            "credit_id": credit_id, "account_id": account_id,
            "amount": amount,
        }, account_id, self._now())
        return credit

    def credits_for_account(self, account_id: str) -> tuple[CreditRecord, ...]:
        """Return all credits for an account."""
        return tuple(c for c in self._credits.values() if c.account_id == account_id)

    # ------------------------------------------------------------------
    # Penalties
    # ------------------------------------------------------------------

    def add_penalty(
        self,
        penalty_id: str,
        account_id: str,
        breach_id: str,
        amount: float,
        *,
        reason: str = "",
    ) -> PenaltyRecord:
        """Add a penalty to an account from a breach."""
        if penalty_id in self._penalties:
            raise RuntimeCoreInvariantError("Duplicate penalty_id")
        if account_id not in self._accounts:
            raise RuntimeCoreInvariantError("Unknown account_id")
        now = self._now()
        penalty = PenaltyRecord(
            penalty_id=penalty_id,
            account_id=account_id,
            breach_id=breach_id,
            amount=amount,
            reason=reason,
            assessed_at=now,
        )
        self._penalties[penalty_id] = penalty
        _emit(self._events, "penalty_added", {
            "penalty_id": penalty_id, "account_id": account_id,
            "amount": amount,
        }, account_id, self._now())
        return penalty

    def penalties_for_account(self, account_id: str) -> tuple[PenaltyRecord, ...]:
        """Return all penalties for an account."""
        return tuple(p for p in self._penalties.values() if p.account_id == account_id)

    # ------------------------------------------------------------------
    # Disputes
    # ------------------------------------------------------------------

    def open_dispute(
        self,
        dispute_id: str,
        invoice_id: str,
        *,
        reason: str = "",
        amount: float = 0.0,
    ) -> DisputeRecord:
        """Open a dispute against an invoice."""
        if dispute_id in self._disputes:
            raise RuntimeCoreInvariantError("Duplicate dispute_id")
        inv = self.get_invoice(invoice_id)
        now = self._now()
        dispute = DisputeRecord(
            dispute_id=dispute_id,
            invoice_id=invoice_id,
            account_id=inv.account_id,
            status=DisputeStatus.OPEN,
            reason=reason,
            amount=amount,
            opened_at=now,
        )
        self._disputes[dispute_id] = dispute

        # Move invoice to DISPUTED status
        if inv.status not in _INVOICE_TERMINAL:
            updated_inv = InvoiceRecord(
                invoice_id=inv.invoice_id,
                account_id=inv.account_id,
                tenant_id=inv.tenant_id,
                status=InvoiceStatus.DISPUTED,
                total_amount=inv.total_amount,
                currency=inv.currency,
                issued_at=inv.issued_at,
                due_at=inv.due_at,
                metadata=inv.metadata,
            )
            self._invoices[invoice_id] = updated_inv

        _emit(self._events, "dispute_opened", {
            "dispute_id": dispute_id, "invoice_id": invoice_id,
            "amount": amount,
        }, invoice_id, self._now())
        return dispute

    def resolve_dispute(
        self,
        dispute_id: str,
        *,
        accepted: bool = False,
    ) -> DisputeRecord:
        """Resolve a dispute."""
        old = self._disputes.get(dispute_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown dispute_id")
        if old.status in _DISPUTE_TERMINAL:
            raise RuntimeCoreInvariantError("dispute already resolved")
        now = self._now()
        status = DisputeStatus.RESOLVED_ACCEPTED if accepted else DisputeStatus.RESOLVED_REJECTED
        updated = DisputeRecord(
            dispute_id=old.dispute_id,
            invoice_id=old.invoice_id,
            account_id=old.account_id,
            status=status,
            reason=old.reason,
            amount=old.amount,
            opened_at=old.opened_at,
            resolved_at=now,
            metadata=old.metadata,
        )
        self._disputes[dispute_id] = updated

        # If accepted, issue credit for disputed amount
        if accepted and old.amount > 0:
            credit_id = stable_identifier("cred-disp", {
                "dispute": dispute_id,
            })
            if credit_id not in self._credits:
                self.add_credit(
                    credit_id, old.account_id, f"dispute-{dispute_id}",
                    old.amount, reason="accepted dispute credit",
                )

        _emit(self._events, "dispute_resolved", {
            "dispute_id": dispute_id, "accepted": accepted,
        }, old.invoice_id, self._now())
        return updated

    def disputes_for_invoice(self, invoice_id: str) -> tuple[DisputeRecord, ...]:
        """Return all disputes for an invoice."""
        return tuple(d for d in self._disputes.values() if d.invoice_id == invoice_id)

    # ------------------------------------------------------------------
    # Revenue computation
    # ------------------------------------------------------------------

    def compute_recognized_revenue(self) -> float:
        """Compute total recognized revenue (paid invoices)."""
        return sum(
            inv.total_amount for inv in self._invoices.values()
            if inv.status == InvoiceStatus.PAID
        )

    def compute_pending_revenue(self) -> float:
        """Compute total pending revenue (issued but not paid/voided)."""
        return sum(
            inv.total_amount for inv in self._invoices.values()
            if inv.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE, InvoiceStatus.DISPUTED)
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_billing_violations(self) -> tuple[BillingViolation, ...]:
        """Detect billing violations."""
        now = self._now()
        new_violations: list[BillingViolation] = []

        # Overdue invoices
        for inv in self._invoices.values():
            if inv.status == InvoiceStatus.ISSUED:
                try:
                    due_dt = datetime.fromisoformat(inv.due_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > due_dt:
                        vid = stable_identifier("viol-bill", {
                            "inv": inv.invoice_id, "op": "overdue",
                        })
                        if vid not in self._violations:
                            # Mark invoice as overdue
                            overdue_inv = InvoiceRecord(
                                invoice_id=inv.invoice_id,
                                account_id=inv.account_id,
                                tenant_id=inv.tenant_id,
                                status=InvoiceStatus.OVERDUE,
                                total_amount=inv.total_amount,
                                currency=inv.currency,
                                issued_at=inv.issued_at,
                                due_at=inv.due_at,
                                metadata=inv.metadata,
                            )
                            self._invoices[inv.invoice_id] = overdue_inv

                            v = BillingViolation(
                                violation_id=vid,
                                account_id=inv.account_id,
                                tenant_id=inv.tenant_id,
                                operation="overdue_invoice",
                                reason="invoice overdue",
                                detected_at=now,
                            )
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        # Delinquent accounts (multiple overdue invoices)
        for acct in self._accounts.values():
            if acct.status == BillingStatus.ACTIVE:
                overdue_count = sum(
                    1 for inv in self._invoices.values()
                    if inv.account_id == acct.account_id and inv.status == InvoiceStatus.OVERDUE
                )
                if overdue_count >= 2:
                    vid = stable_identifier("viol-bill", {
                        "acct": acct.account_id, "op": "delinquent",
                    })
                    if vid not in self._violations:
                        # Mark account as delinquent
                        delinquent = BillingAccount(
                            account_id=acct.account_id,
                            tenant_id=acct.tenant_id,
                            counterparty=acct.counterparty,
                            status=BillingStatus.DELINQUENT,
                            currency=acct.currency,
                            created_at=acct.created_at,
                            metadata=acct.metadata,
                        )
                        self._accounts[acct.account_id] = delinquent

                        v = BillingViolation(
                            violation_id=vid,
                            account_id=acct.account_id,
                            tenant_id=acct.tenant_id,
                            operation="delinquent_account",
                            reason="account delinquent",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "billing_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan", self._now())
        return tuple(new_violations)

    def violations_for_account(self, account_id: str) -> tuple[BillingViolation, ...]:
        """Return all violations for an account."""
        return tuple(v for v in self._violations.values() if v.account_id == account_id)

    # ------------------------------------------------------------------
    # Revenue snapshot
    # ------------------------------------------------------------------

    def revenue_snapshot(self, snapshot_id: str) -> RevenueSnapshot:
        """Capture a point-in-time revenue and billing snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._now()
        snap = RevenueSnapshot(
            snapshot_id=snapshot_id,
            total_accounts=self.account_count,
            total_invoices=self.invoice_count,
            total_charges=self.charge_count,
            total_credits=self.credit_count,
            total_penalties=self.penalty_count,
            total_disputes=self.dispute_count,
            total_recognized_revenue=self.compute_recognized_revenue(),
            total_pending_revenue=self.compute_pending_revenue(),
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "revenue_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, self._now())
        return snap

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "accounts": self._accounts,
            "invoices": self._invoices,
            "charges": self._charges,
            "credits": self._credits,
            "penalties": self._penalties,
            "disputes": self._disputes,
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
        result["snapshot_ids"] = sorted(self._snapshot_ids)
        result["_state_hash"] = self.state_hash()
        return result

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"accounts={self.account_count}",
            f"invoices={self.invoice_count}",
            f"charges={self.charge_count}",
            f"credits={self.credit_count}",
            f"penalties={self.penalty_count}",
            f"disputes={self.dispute_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
