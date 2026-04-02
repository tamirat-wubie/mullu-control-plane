"""Financial Provider Protocol — Interface for all financial data providers.

Providers are read-only adapters that fetch financial data from external
services (Plaid, TrueLayer, banking APIs). They never initiate payments.
Payment providers are a separate protocol (Tier 2).

Invariants:
  - Providers are tenant-scoped (credential per tenant).
  - Providers never store raw credentials in memory.
  - All provider calls are audited.
  - Provider failures return structured errors, never raw exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Bank/financial account summary."""

    account_id: str
    name: str
    account_type: str  # "checking", "savings", "credit", "investment"
    currency: str
    balance: Decimal
    available_balance: Decimal = Decimal("0")
    institution: str = ""
    mask: str = ""  # Last 4 digits


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """Single financial transaction from a provider."""

    transaction_id: str
    account_id: str
    amount: Decimal
    currency: str
    description: str
    category: str = ""
    merchant: str = ""
    date: str = ""
    pending: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Result from a financial provider call."""

    success: bool
    data: Any = None
    error: str = ""
    provider: str = ""


class ReadOnlyFinancialProvider(Protocol):
    """Protocol for read-only financial data providers."""

    @property
    def provider_name(self) -> str: ...

    def get_accounts(self, tenant_id: str) -> ProviderResult: ...

    def get_balance(self, tenant_id: str, account_id: str) -> ProviderResult: ...

    def get_transactions(
        self, tenant_id: str, account_id: str,
        *, days: int = 30, limit: int = 100,
    ) -> ProviderResult: ...


class StubFinancialProvider:
    """Deterministic stub provider for testing. No real API calls."""

    provider_name = "stub"

    def __init__(self) -> None:
        self._accounts: dict[str, list[AccountInfo]] = {}
        self._transactions: dict[str, list[TransactionRecord]] = {}

    def seed_account(self, tenant_id: str, account: AccountInfo) -> None:
        self._accounts.setdefault(tenant_id, []).append(account)

    def seed_transaction(self, tenant_id: str, tx: TransactionRecord) -> None:
        self._transactions.setdefault(tenant_id, []).append(tx)

    def get_accounts(self, tenant_id: str) -> ProviderResult:
        accounts = self._accounts.get(tenant_id, [])
        return ProviderResult(success=True, data=accounts, provider=self.provider_name)

    def get_balance(self, tenant_id: str, account_id: str) -> ProviderResult:
        accounts = self._accounts.get(tenant_id, [])
        for acc in accounts:
            if acc.account_id == account_id:
                return ProviderResult(success=True, data=acc, provider=self.provider_name)
        return ProviderResult(success=False, error=f"account {account_id} not found", provider=self.provider_name)

    def get_transactions(
        self, tenant_id: str, account_id: str,
        *, days: int = 30, limit: int = 100,
    ) -> ProviderResult:
        txs = [t for t in self._transactions.get(tenant_id, []) if t.account_id == account_id]
        return ProviderResult(success=True, data=txs[:limit], provider=self.provider_name)
