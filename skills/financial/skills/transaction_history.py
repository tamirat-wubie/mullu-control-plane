"""Transaction History Skill — Read recent transactions.

Permission: read_financial
Risk: medium (auto-approve with audit)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skills.financial.providers.base import ReadOnlyFinancialProvider


@dataclass(frozen=True, slots=True)
class TransactionHistoryResult:
    """Result of a transaction history query."""

    success: bool
    transactions: tuple[dict[str, Any], ...] = ()
    total_count: int = 0
    error: str = ""


def get_transaction_history(
    provider: ReadOnlyFinancialProvider,
    tenant_id: str,
    account_id: str,
    *,
    days: int = 30,
    limit: int = 50,
) -> TransactionHistoryResult:
    """Get recent transactions for an account."""
    result = provider.get_transactions(tenant_id, account_id, days=days, limit=limit)
    if not result.success:
        return TransactionHistoryResult(success=False, error=result.error)
    txs = tuple(
        {
            "id": tx.transaction_id,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "description": tx.description,
            "category": tx.category,
            "merchant": tx.merchant,
            "date": tx.date,
            "pending": tx.pending,
        }
        for tx in result.data
    )
    return TransactionHistoryResult(success=True, transactions=txs, total_count=len(txs))
