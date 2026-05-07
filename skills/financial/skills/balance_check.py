"""Balance Check Skill — Read account balances.

Permission: read_financial
Risk: medium (auto-approve with audit)
Provider: any ReadOnlyFinancialProvider
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skills.financial.providers.base import ReadOnlyFinancialProvider


@dataclass(frozen=True, slots=True)
class BalanceCheckResult:
    """Result of a balance check."""

    success: bool
    accounts: tuple[dict[str, Any], ...] = ()
    error: str = ""
    provider: str = ""


def check_balance(
    provider: ReadOnlyFinancialProvider,
    tenant_id: str,
    account_id: str = "",
) -> BalanceCheckResult:
    """Check account balance(s) for a tenant.

    If account_id is empty, returns all accounts.
    """
    if account_id:
        result = provider.get_balance(tenant_id, account_id)
        if not result.success:
            return BalanceCheckResult(success=False, error=result.error, provider=result.provider)
        acc = result.data
        return BalanceCheckResult(
            success=True,
            accounts=({
                "account_id": acc.account_id,
                "name": acc.name,
                "type": acc.account_type,
                "currency": acc.currency,
                "balance": str(acc.balance),
                "available": str(acc.available_balance),
            },),
            provider=result.provider,
        )

    result = provider.get_accounts(tenant_id)
    if not result.success:
        return BalanceCheckResult(success=False, error=result.error, provider=result.provider)
    accounts = tuple(
        {
            "account_id": acc.account_id,
            "name": acc.name,
            "type": acc.account_type,
            "currency": acc.currency,
            "balance": str(acc.balance),
            "available": str(acc.available_balance),
        }
        for acc in result.data
    )
    return BalanceCheckResult(success=True, accounts=accounts, provider=result.provider)
