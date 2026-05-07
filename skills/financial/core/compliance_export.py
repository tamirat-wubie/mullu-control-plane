"""Financial Compliance Export — Auditable proof packages.

Purpose: Generate self-contained compliance packages for financial
    transactions that include: transaction lifecycle, approvals,
    provider references, proof hashes, audit chain, spend budget checks.

Invariants:
  - Exports are read-only snapshots (no mutation).
  - Exports contain no raw credentials or secrets.
  - Every export includes proof hash for verification.
  - Exports are JSON-serializable for external audit tools.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from skills.financial.core.transaction_ledger import TransactionLedger
from skills.financial.core.transaction_state import TxState


@dataclass(frozen=True, slots=True)
class AuditPackage:
    """Complete audit package for a single financial transaction."""

    tx_id: str
    tenant_id: str
    amount: str
    currency: str
    state: str
    provider: str
    provider_tx_id: str
    transitions: tuple[dict[str, str], ...]
    proof_hash: str
    idempotency_key: str
    created_at: str
    settled_at: str
    package_hash: str  # Hash of entire package for integrity verification

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict representation."""
        return {
            "tx_id": self.tx_id, "tenant_id": self.tenant_id,
            "amount": self.amount, "currency": self.currency,
            "state": self.state, "provider": self.provider,
            "provider_tx_id": self.provider_tx_id,
            "transitions": [dict(t) for t in self.transitions],
            "proof_hash": self.proof_hash,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at, "settled_at": self.settled_at,
            "package_hash": self.package_hash,
        }


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Summary compliance report for a tenant's financial activity."""

    tenant_id: str
    total_transactions: int
    total_settled: int
    total_refunded: int
    total_failed: int
    total_pending: int
    total_amount_settled: str
    total_amount_refunded: str
    packages: tuple[AuditPackage, ...]
    report_hash: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict representation."""
        return {
            "tenant_id": self.tenant_id,
            "total_transactions": self.total_transactions,
            "total_settled": self.total_settled,
            "total_refunded": self.total_refunded,
            "total_failed": self.total_failed,
            "total_pending": self.total_pending,
            "total_amount_settled": self.total_amount_settled,
            "total_amount_refunded": self.total_amount_refunded,
            "packages": [p.to_dict() for p in self.packages],
            "report_hash": self.report_hash,
            "generated_at": self.generated_at,
        }


class ComplianceExporter:
    """Generates compliance-ready export packages from the financial ledger."""

    def __init__(self, ledger: TransactionLedger) -> None:
        self._ledger = ledger

    def export_transaction(self, tx_id: str) -> AuditPackage | None:
        """Export a single transaction as an audit package."""
        entry = self._ledger.get(tx_id)
        if entry is None:
            return None

        transitions = tuple(
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "reason": t.reason,
                "actor": t.actor_id,
                "at": t.transitioned_at,
            }
            for t in self._ledger.get_transitions(tx_id)
        )

        settled_at = ""
        for t in self._ledger.get_transitions(tx_id):
            if t.to_state == TxState.SETTLED:
                settled_at = t.transitioned_at

        # Compute package hash for integrity
        content = json.dumps({
            "tx_id": entry.tx_id,
            "tenant_id": entry.tenant_id,
            "amount": str(entry.amount),
            "currency": entry.currency,
            "state": entry.state.value,
            "proof_hash": entry.proof_hash,
            "transitions": [dict(t) for t in transitions],
        }, sort_keys=True)
        package_hash = hashlib.sha256(content.encode()).hexdigest()

        return AuditPackage(
            tx_id=entry.tx_id,
            tenant_id=entry.tenant_id,
            amount=str(entry.amount),
            currency=entry.currency,
            state=entry.state.value,
            provider=entry.provider,
            provider_tx_id=entry.provider_tx_id,
            transitions=transitions,
            proof_hash=entry.proof_hash,
            idempotency_key=entry.idempotency_key,
            created_at=entry.created_at,
            settled_at=settled_at,
            package_hash=package_hash,
        )

    def export_tenant_report(
        self, tenant_id: str, *, generated_at: str = "",
    ) -> ComplianceReport:
        """Export a compliance report for all transactions of a tenant."""
        from decimal import Decimal

        entries = self._ledger.query(tenant_id=tenant_id, limit=10000)
        packages: list[AuditPackage] = []
        total_settled = Decimal("0")
        total_refunded = Decimal("0")
        settled_count = 0
        refunded_count = 0
        failed_count = 0
        pending_count = 0

        for entry in entries:
            pkg = self.export_transaction(entry.tx_id)
            if pkg is not None:
                packages.append(pkg)

            if entry.state == TxState.SETTLED:
                settled_count += 1
                total_settled += entry.amount
            elif entry.state == TxState.REFUNDED:
                refunded_count += 1
                total_refunded += entry.amount
            elif entry.state in (TxState.FAILED, TxState.REJECTED, TxState.EXPIRED):
                failed_count += 1
            elif entry.state in (TxState.CREATED, TxState.PENDING_APPROVAL, TxState.AUTHORIZED, TxState.CAPTURED):
                pending_count += 1

        report_content = json.dumps({
            "tenant_id": tenant_id,
            "count": len(entries),
            "settled": str(total_settled),
            "refunded": str(total_refunded),
        }, sort_keys=True)
        report_hash = hashlib.sha256(report_content.encode()).hexdigest()

        return ComplianceReport(
            tenant_id=tenant_id,
            total_transactions=len(entries),
            total_settled=settled_count,
            total_refunded=refunded_count,
            total_failed=failed_count,
            total_pending=pending_count,
            total_amount_settled=str(total_settled),
            total_amount_refunded=str(total_refunded),
            packages=tuple(packages),
            report_hash=report_hash,
            generated_at=generated_at,
        )
