"""Governed Payment Executor — Full pipeline for money movement.

Every payment flows through:
  spend budget → approval → idempotency → state machine → provider → settlement → ledger → proof

Permission: spend_money
Risk: high (mandatory human approval)

Invariants:
  - Over-budget requests denied BEFORE provider call.
  - Duplicate requests return cached result (idempotency).
  - State machine enforces lifecycle (no skipped states).
  - Every operation audited with proof hash.
  - Provider failures leave transaction in FAILED state (no silent loss).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from skills.financial.core.idempotency import IdempotencyStore, IdempotencyStatus, compute_key
from skills.financial.core.spend_budget import SpendBudgetManager
from skills.financial.core.transaction_ledger import TransactionLedger
from skills.financial.core.transaction_state import TxState
from skills.financial.providers.stripe_provider import StripeProvider


@dataclass(frozen=True, slots=True)
class GovernedPaymentResult:
    """Result of a governed payment execution."""

    success: bool
    tx_id: str = ""
    state: str = ""
    provider_tx_id: str = ""
    amount: str = ""
    currency: str = ""
    error: str = ""
    requires_approval: bool = False
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class GovernedPaymentExecutor:
    """Executes payments through the full governance pipeline.

    Pipeline:
    1. Spend budget check (deny if over budget)
    2. Idempotency check (return cached if duplicate)
    3. Create transaction in ledger (CREATED state)
    4. Move to PENDING_APPROVAL
    5. [Caller must approve before proceeding]
    6. Execute via provider
    7. Move to AUTHORIZED → CAPTURED → SETTLED
    8. Update spend budget
    9. Return governed result

    Approval is external — this executor creates the transaction and
    waits. The approve() method advances the state machine.
    """

    def __init__(
        self,
        *,
        provider: StripeProvider,
        spend_mgr: SpendBudgetManager,
        ledger: TransactionLedger,
        idempotency: IdempotencyStore,
        clock: Callable[[], str],
        on_approval_needed: Callable[[str, str, str, str], None] | None = None,
    ) -> None:
        self._provider = provider
        self._spend_mgr = spend_mgr
        self._ledger = ledger
        self._idempotency = idempotency
        self._clock = clock
        self._on_approval_needed = on_approval_needed  # callback(tx_id, tenant_id, amount, currency)
        self._tx_counter = 0

    def initiate_payment(
        self,
        *,
        tenant_id: str,
        amount: Decimal,
        currency: str,
        destination: str,
        description: str = "",
        actor_id: str = "",
    ) -> GovernedPaymentResult:
        """Initiate a governed payment. Returns PENDING_APPROVAL status.

        The payment is NOT executed until approve() is called.
        """
        now = self._clock()

        # 1. Spend budget check
        budget_check = self._spend_mgr.check(tenant_id, amount, currency)
        if not budget_check.allowed:
            return GovernedPaymentResult(
                success=False, error=f"spend budget denied: {budget_check.reason}",
            )

        # 2. Idempotency check
        idem_key = compute_key(tenant_id, "send_payment", destination, str(amount), currency)
        existing = self._idempotency.check(idem_key)
        if existing is not None:
            if existing.status == IdempotencyStatus.COMPLETED:
                return GovernedPaymentResult(
                    success=True, tx_id=existing.result.get("tx_id", ""),
                    state="completed_duplicate",
                    metadata={"idempotency": "returned_cached"},
                )
            if existing.status == IdempotencyStatus.IN_FLIGHT:
                return GovernedPaymentResult(
                    success=False, error="payment already in progress",
                    metadata={"idempotency": "in_flight"},
                )

        # 3. Mark in-flight (protected against race condition)
        try:
            self._idempotency.mark_in_flight(idem_key, created_at=now)
        except ValueError:
            return GovernedPaymentResult(
                success=False, error="payment already in progress (race condition)",
            )

        # 4. Create transaction in ledger
        self._tx_counter += 1
        tx_id = f"tx-{hashlib.sha256(f'{tenant_id}:{idem_key}:{self._tx_counter}'.encode()).hexdigest()[:12]}"

        try:
            self._ledger.create(
                tx_id=tx_id, idempotency_key=idem_key, tenant_id=tenant_id,
                debit_account=f"tenant:{tenant_id}",
                credit_account=f"dest:{destination}",
                amount=amount, currency=currency,
                provider=self._provider.provider_name,
                description=description, created_at=now,
            )
        except ValueError:
            self._idempotency.mark_failed(idem_key)
            return GovernedPaymentResult(success=False, error="failed to create transaction")

        # 5. Move to PENDING_APPROVAL
        self._ledger.advance(tx_id, TxState.PENDING_APPROVAL, reason="requires human approval", actor_id=actor_id, timestamp=now)

        # Notify external approval system (e.g., gateway ApprovalRouter)
        if self._on_approval_needed is not None:
            try:
                self._on_approval_needed(tx_id, tenant_id, str(amount), currency)
            except Exception:
                pass  # Approval notification must not block

        return GovernedPaymentResult(
            success=True, tx_id=tx_id, state=TxState.PENDING_APPROVAL.value,
            amount=str(amount), currency=currency,
            requires_approval=True,
        )

    def approve_and_execute(
        self,
        tx_id: str,
        *,
        approver_id: str = "",
        api_key: str = "",
    ) -> GovernedPaymentResult:
        """Approve a pending payment and execute through the provider.

        Full pipeline: AUTHORIZED → CAPTURED → SETTLED → budget update.
        """
        now = self._clock()
        entry = self._ledger.get(tx_id)
        if entry is None:
            return GovernedPaymentResult(success=False, error=f"transaction {tx_id} not found")

        if entry.state != TxState.PENDING_APPROVAL:
            return GovernedPaymentResult(
                success=False, error=f"transaction not in PENDING_APPROVAL state (is {entry.state.value})",
            )

        # Authorize
        self._ledger.advance(tx_id, TxState.AUTHORIZED, reason="approved", actor_id=approver_id, timestamp=now)

        # Execute via provider
        provider_result = self._provider.create_payment_link(
            amount=entry.amount, currency=entry.currency,
            description=entry.description,
            idempotency_key=entry.idempotency_key,
            api_key=api_key,
        )

        if not provider_result.success:
            self._ledger.advance(tx_id, TxState.FAILED, reason=f"provider error: {provider_result.error}", timestamp=now)
            self._idempotency.mark_failed(entry.idempotency_key)
            return GovernedPaymentResult(
                success=False, tx_id=tx_id, state=TxState.FAILED.value,
                error=provider_result.error,
            )

        # Capture + Settle
        self._ledger.advance(
            tx_id, TxState.CAPTURED,
            provider_tx_id=provider_result.provider_tx_id, timestamp=now,
        )
        self._ledger.advance(tx_id, TxState.SETTLED, reason="provider confirmed", timestamp=now)

        # Update spend budget
        self._spend_mgr.record_spend(entry.tenant_id, entry.amount)

        # Mark idempotency completed
        self._idempotency.mark_completed(
            entry.idempotency_key,
            {"tx_id": tx_id, "provider_tx_id": provider_result.provider_tx_id},
            completed_at=now,
        )

        return GovernedPaymentResult(
            success=True, tx_id=tx_id, state=TxState.SETTLED.value,
            provider_tx_id=provider_result.provider_tx_id,
            amount=str(entry.amount), currency=entry.currency,
            metadata={
                "ledger_hash": entry.proof_hash,
                "recipient_ref": entry.credit_account,
                "recipient_hash": hashlib.sha256(entry.credit_account.encode()).hexdigest(),
                "debit_account": entry.debit_account,
                "credit_account": entry.credit_account,
                "approval_actor_id": approver_id,
            },
        )

    def deny(self, tx_id: str, *, reason: str = "", actor_id: str = "") -> GovernedPaymentResult:
        """Deny a pending payment."""
        now = self._clock()
        entry = self._ledger.get(tx_id)
        if entry is None:
            return GovernedPaymentResult(success=False, error=f"transaction {tx_id} not found")

        self._ledger.advance(tx_id, TxState.REJECTED, reason=reason or "denied by approver", actor_id=actor_id, timestamp=now)
        self._idempotency.mark_failed(entry.idempotency_key)

        return GovernedPaymentResult(
            success=True, tx_id=tx_id, state=TxState.REJECTED.value,
        )

    def refund(self, tx_id: str, *, reason: str = "", actor_id: str = "", api_key: str = "") -> GovernedPaymentResult:
        """Refund a settled payment."""
        now = self._clock()
        entry = self._ledger.get(tx_id)
        if entry is None:
            return GovernedPaymentResult(success=False, error=f"transaction {tx_id} not found")
        if entry.state != TxState.SETTLED:
            return GovernedPaymentResult(success=False, error=f"can only refund SETTLED transactions (is {entry.state.value})")

        self._ledger.advance(tx_id, TxState.REFUND_PENDING, reason=reason, actor_id=actor_id, timestamp=now)

        refund_result = self._provider.process_refund(
            provider_tx_id=entry.provider_tx_id,
            amount=entry.amount, reason=reason,
            api_key=api_key,
        )

        if not refund_result.success:
            self._ledger.advance(tx_id, TxState.FAILED, reason=f"refund failed: {refund_result.error}", timestamp=now)
            return GovernedPaymentResult(success=False, tx_id=tx_id, state=TxState.FAILED.value, error=refund_result.error)

        self._ledger.advance(tx_id, TxState.REFUNDED, reason="refund processed", timestamp=now)
        refunded_entry = self._ledger.get(tx_id)
        ledger_hash = refunded_entry.proof_hash if refunded_entry is not None else entry.proof_hash

        return GovernedPaymentResult(
            success=True, tx_id=tx_id, state=TxState.REFUNDED.value,
            provider_tx_id=refund_result.provider_tx_id,
            amount=str(entry.amount), currency=entry.currency,
            metadata={
                "ledger_hash": ledger_hash,
                "refund_provider_tx_id": refund_result.provider_tx_id,
                "original_provider_tx_id": entry.provider_tx_id,
                "recipient_ref": entry.credit_account,
                "recipient_hash": hashlib.sha256(entry.credit_account.encode()).hexdigest(),
                "refund_actor_id": actor_id,
            },
        )
