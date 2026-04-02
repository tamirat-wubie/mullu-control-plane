"""Financial Skills Tests — Tier 1 read-only operations.

Tests: Provider protocol, balance check, transaction history,
    spending insights, stub provider behavior.
"""

import sys
from pathlib import Path
from decimal import Decimal

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_MCOI = _ROOT / "mcoi"
if str(_MCOI) not in sys.path:
    sys.path.insert(0, str(_MCOI))

import pytest
from skills.financial.providers.base import (
    AccountInfo, TransactionRecord, StubFinancialProvider, ProviderResult,
)
from skills.financial.skills.balance_check import check_balance
from skills.financial.skills.transaction_history import get_transaction_history
from skills.financial.skills.spending_insights import analyze_spending


def _provider_with_data() -> StubFinancialProvider:
    """Create a provider with realistic test data."""
    p = StubFinancialProvider()
    p.seed_account("t1", AccountInfo(
        account_id="acc-1", name="Checking", account_type="checking",
        currency="USD", balance=Decimal("5432.10"), available_balance=Decimal("5400.00"),
        institution="Test Bank", mask="1234",
    ))
    p.seed_account("t1", AccountInfo(
        account_id="acc-2", name="Savings", account_type="savings",
        currency="USD", balance=Decimal("25000.00"), available_balance=Decimal("25000.00"),
    ))
    for i in range(10):
        p.seed_transaction("t1", TransactionRecord(
            transaction_id=f"tx-{i}", account_id="acc-1",
            amount=Decimal(f"-{(i + 1) * 10}.00"), currency="USD",
            description=f"Purchase {i}", category="food" if i % 2 == 0 else "transport",
            merchant=f"Store {i % 3}", date=f"2026-03-{15 + i}",
        ))
    return p


# ═══ Stub Provider ═══


class TestStubProvider:
    def test_get_accounts(self):
        p = _provider_with_data()
        result = p.get_accounts("t1")
        assert result.success
        assert len(result.data) == 2

    def test_get_accounts_unknown_tenant(self):
        p = StubFinancialProvider()
        result = p.get_accounts("unknown")
        assert result.success
        assert len(result.data) == 0

    def test_get_balance(self):
        p = _provider_with_data()
        result = p.get_balance("t1", "acc-1")
        assert result.success
        assert result.data.balance == Decimal("5432.10")

    def test_get_balance_not_found(self):
        p = _provider_with_data()
        result = p.get_balance("t1", "nonexistent")
        assert not result.success
        assert "not found" in result.error

    def test_get_transactions(self):
        p = _provider_with_data()
        result = p.get_transactions("t1", "acc-1")
        assert result.success
        assert len(result.data) == 10

    def test_get_transactions_with_limit(self):
        p = _provider_with_data()
        result = p.get_transactions("t1", "acc-1", limit=3)
        assert len(result.data) == 3


# ═══ Balance Check Skill ═══


class TestBalanceCheck:
    def test_all_accounts(self):
        p = _provider_with_data()
        result = check_balance(p, "t1")
        assert result.success
        assert len(result.accounts) == 2
        assert result.accounts[0]["name"] == "Checking"

    def test_single_account(self):
        p = _provider_with_data()
        result = check_balance(p, "t1", account_id="acc-1")
        assert result.success
        assert len(result.accounts) == 1
        assert result.accounts[0]["balance"] == "5432.10"

    def test_account_not_found(self):
        p = _provider_with_data()
        result = check_balance(p, "t1", account_id="bad")
        assert not result.success
        assert "not found" in result.error

    def test_empty_tenant(self):
        p = StubFinancialProvider()
        result = check_balance(p, "empty")
        assert result.success
        assert len(result.accounts) == 0


# ═══ Transaction History Skill ═══


class TestTransactionHistory:
    def test_get_history(self):
        p = _provider_with_data()
        result = get_transaction_history(p, "t1", "acc-1")
        assert result.success
        assert result.total_count == 10

    def test_get_history_with_limit(self):
        p = _provider_with_data()
        result = get_transaction_history(p, "t1", "acc-1", limit=3)
        assert result.total_count == 3

    def test_transaction_fields(self):
        p = _provider_with_data()
        result = get_transaction_history(p, "t1", "acc-1", limit=1)
        tx = result.transactions[0]
        assert "id" in tx
        assert "amount" in tx
        assert "currency" in tx
        assert "description" in tx

    def test_empty_history(self):
        p = StubFinancialProvider()
        result = get_transaction_history(p, "t1", "acc-1")
        assert result.success
        assert result.total_count == 0


# ═══ Spending Insights Skill ═══


class TestSpendingInsights:
    def test_analyze(self):
        p = _provider_with_data()
        result = analyze_spending(p, "t1", "acc-1")
        assert result.success
        assert result.transaction_count == 10
        assert Decimal(result.total_spent) > 0

    def test_categories(self):
        p = _provider_with_data()
        result = analyze_spending(p, "t1", "acc-1")
        assert len(result.categories) >= 2
        # Percentages should sum to ~100
        total_pct = sum(c.percentage for c in result.categories)
        assert 99.0 <= total_pct <= 101.0

    def test_top_merchants(self):
        p = _provider_with_data()
        result = analyze_spending(p, "t1", "acc-1")
        assert len(result.top_merchants) >= 1
        assert "merchant" in result.top_merchants[0]
        assert "total" in result.top_merchants[0]

    def test_empty_transactions(self):
        p = StubFinancialProvider()
        result = analyze_spending(p, "t1", "acc-1")
        assert result.success
        assert result.total_spent == "0"
        assert result.transaction_count == 0


# ═══ RBAC Financial Roles ═══


class TestFinancialRBAC:
    def test_financial_roles_seeded(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
        from mcoi_runtime.core.rbac_defaults import seed_default_permissions

        def _clock():
            return "2026-01-01T00:00:00Z"

        spine = EventSpineEngine(clock=_clock)
        engine = AccessRuntimeEngine(spine)
        seed_default_permissions(engine)

        roles = {r.role_id: r for r in engine._roles.values()}
        assert "financial_viewer" in roles
        assert "financial_operator" in roles
        assert "financial_approver" in roles
        assert "financial_admin" in roles

    def test_financial_viewer_permissions(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
        from mcoi_runtime.core.rbac_defaults import seed_default_permissions

        spine = EventSpineEngine(clock=lambda: "2026-01-01T00:00:00Z")
        engine = AccessRuntimeEngine(spine)
        seed_default_permissions(engine)

        roles = {r.role_id: r for r in engine._roles.values()}
        viewer = roles["financial_viewer"]
        assert "financial:GET" in viewer.permissions
        assert "financial:POST" not in viewer.permissions

    def test_financial_admin_has_wildcard(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
        from mcoi_runtime.core.rbac_defaults import seed_default_permissions

        spine = EventSpineEngine(clock=lambda: "2026-01-01T00:00:00Z")
        engine = AccessRuntimeEngine(spine)
        seed_default_permissions(engine)

        roles = {r.role_id: r for r in engine._roles.values()}
        admin = roles["financial_admin"]
        assert "financial:*" in admin.permissions
