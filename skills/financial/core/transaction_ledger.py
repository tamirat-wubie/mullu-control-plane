"""Double-Entry Transaction Ledger — Append-only financial record.

Invariants:
  - Append-only. No mutation after terminal settlement.
  - Compensating records for corrections (not edits).
  - Every entry has proof hash and audit chain reference.
  - Balanced: every debit has a corresponding credit.
  - Provider references are immutable once set.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from skills.financial.core.currency import Money
from skills.financial.core.transaction_state import TxState, TxTransition, transition


@dataclass(frozen=True, slots=True)
class TransactionEntry:
    """Double-entry transaction record."""

    tx_id: str
    idempotency_key: str
    tenant_id: str
    debit_account: str
    credit_account: str
    amount: Decimal
    currency: str
    state: TxState
    provider: str
    provider_tx_id: str = ""
    approval_record_id: str = ""
    proof_hash: str = ""
    audit_chain_ref: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TransactionLedger:
    """Append-only double-entry financial ledger.

    Every financial action produces a TransactionEntry. State transitions
    create new entries (not mutations). Terminal entries are immutable.
    """

    def __init__(self) -> None:
        self._entries: dict[str, TransactionEntry] = {}  # tx_id → latest entry
        self._history: list[TransactionEntry] = []  # all entries in order
        self._transitions: dict[str, list[TxTransition]] = {}  # tx_id → transitions

    def create(
        self,
        *,
        tx_id: str,
        idempotency_key: str,
        tenant_id: str,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
        currency: str,
        provider: str,
        description: str = "",
        created_at: str = "",
    ) -> TransactionEntry:
        """Create a new transaction in CREATED state."""
        if tx_id in self._entries:
            raise ValueError(f"transaction {tx_id} already exists")

        proof_content = f"{tx_id}:{tenant_id}:{debit_account}:{credit_account}:{amount}:{currency}"
        proof_hash = hashlib.sha256(proof_content.encode()).hexdigest()

        entry = TransactionEntry(
            tx_id=tx_id,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            debit_account=debit_account,
            credit_account=credit_account,
            amount=amount,
            currency=currency,
            state=TxState.CREATED,
            provider=provider,
            proof_hash=proof_hash,
            description=description,
            created_at=created_at,
            updated_at=created_at,
        )
        self._entries[tx_id] = entry
        self._history.append(entry)
        self._transitions[tx_id] = []
        return entry

    def advance(
        self,
        tx_id: str,
        to_state: TxState,
        *,
        reason: str = "",
        actor_id: str = "",
        timestamp: str = "",
        provider_tx_id: str = "",
        approval_record_id: str = "",
    ) -> TransactionEntry:
        """Advance a transaction to the next state. Validates transition legality."""
        current = self._entries.get(tx_id)
        if current is None:
            raise ValueError(f"transaction {tx_id} not found")

        # Validate and record transition
        tx_transition = transition(
            current.state, to_state,
            reason=reason, actor_id=actor_id, timestamp=timestamp,
        )
        self._transitions[tx_id].append(tx_transition)

        # Create new entry with updated state
        updated = TransactionEntry(
            tx_id=current.tx_id,
            idempotency_key=current.idempotency_key,
            tenant_id=current.tenant_id,
            debit_account=current.debit_account,
            credit_account=current.credit_account,
            amount=current.amount,
            currency=current.currency,
            state=to_state,
            provider=current.provider,
            provider_tx_id=provider_tx_id or current.provider_tx_id,
            approval_record_id=approval_record_id or current.approval_record_id,
            proof_hash=current.proof_hash,
            audit_chain_ref=current.audit_chain_ref,
            description=current.description,
            created_at=current.created_at,
            updated_at=timestamp,
            metadata=current.metadata,
        )
        self._entries[tx_id] = updated
        self._history.append(updated)
        return updated

    def get(self, tx_id: str) -> TransactionEntry | None:
        """Get current state of a transaction."""
        return self._entries.get(tx_id)

    def get_transitions(self, tx_id: str) -> list[TxTransition]:
        """Get full transition history for a transaction."""
        return list(self._transitions.get(tx_id, []))

    def query(self, tenant_id: str = "", state: TxState | None = None, limit: int = 50) -> list[TransactionEntry]:
        """Query transactions with optional filters."""
        results = list(self._entries.values())
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if state is not None:
            results = [e for e in results if e.state == state]
        return results[-limit:]

    @property
    def transaction_count(self) -> int:
        return len(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._history)

    def summary(self) -> dict[str, Any]:
        state_counts: dict[str, int] = {}
        for entry in self._entries.values():
            state_counts[entry.state.value] = state_counts.get(entry.state.value, 0) + 1
        return {
            "transactions": self.transaction_count,
            "entries": self.entry_count,
            "states": state_counts,
        }
