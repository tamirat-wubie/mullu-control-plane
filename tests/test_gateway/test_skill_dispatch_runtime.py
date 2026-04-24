"""Gateway skill dispatcher runtime binding tests.

Tests: platform-backed provider injection for governed skill dispatch.
"""

from decimal import Decimal
from dataclasses import dataclass, field
from typing import Any
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.skill_dispatch import SkillDispatcher, SkillIntent, build_skill_dispatcher_from_platform  # noqa: E402
from skills.financial.providers.base import AccountInfo, StubFinancialProvider  # noqa: E402


@dataclass(frozen=True, slots=True)
class PaymentResult:
    success: bool
    tx_id: str
    state: str
    amount: str
    currency: str
    provider_tx_id: str = ""
    requires_approval: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovingPaymentExecutor:
    def initiate_payment(self, *, tenant_id, amount, currency, destination, actor_id, description=""):
        return PaymentResult(
            success=True,
            tx_id="tx-123",
            state="pending_approval",
            amount=str(amount),
            currency=currency,
            requires_approval=True,
        )

    def approve_and_execute(self, tx_id, *, approver_id="", api_key=""):
        return PaymentResult(
            success=True,
            tx_id=tx_id,
            state="settled",
            amount="50",
            currency="USD",
            provider_tx_id="provider-123",
            metadata={
                "ledger_hash": "ledger-proof-123",
                "recipient_hash": "recipient-proof-123",
                "recipient_ref": "dest:pending",
            },
        )

    def refund(self, tx_id, *, reason="", actor_id="", api_key=""):
        return PaymentResult(
            success=True,
            tx_id=tx_id,
            state="refunded",
            amount="50",
            currency="USD",
            provider_tx_id="refund-123",
            metadata={"ledger_hash": "refund-ledger-proof-123"},
        )


class PlatformWithFinancialProvider:
    """Platform stub exposing a direct financial provider."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self._financial_provider = provider


class CapabilityRuntime:
    """Nested runtime stub exposing a governed financial provider."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self.financial_provider = provider


class PlatformWithCapabilityRuntime:
    """Platform stub exposing providers through a capability runtime."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self.capability_runtime = CapabilityRuntime(provider)


def _seeded_provider() -> StubFinancialProvider:
    provider = StubFinancialProvider()
    provider.seed_account(
        "tenant-1",
        AccountInfo(
            account_id="acct-1",
            name="Operating",
            account_type="checking",
            currency="USD",
            balance=Decimal("125.50"),
        ),
    )
    return provider


def test_dispatcher_uses_direct_platform_financial_provider() -> None:
    dispatcher = build_skill_dispatcher_from_platform(
        PlatformWithFinancialProvider(_seeded_provider()),
    )

    result = dispatcher.dispatch(
        SkillIntent("financial", "balance_check", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["governed"] is True
    assert "Operating" in result["response"]
    assert "125.50" in result["response"]


def test_dispatcher_uses_nested_capability_runtime_provider() -> None:
    dispatcher = build_skill_dispatcher_from_platform(
        PlatformWithCapabilityRuntime(_seeded_provider()),
    )

    result = dispatcher.dispatch(
        SkillIntent("financial", "balance_check", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "balance_check"
    assert "USD" in result["response"]
    assert "Operating" in result["response"]


def test_payment_dispatcher_emits_settled_effect_receipts() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "send_payment", {"amount": "50"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "send_payment"
    assert result["receipt_status"] == "settled"
    assert result["transaction_id"] == "tx-123"
    assert result["amount"] == "50"
    assert result["currency"] == "USD"
    assert result["recipient_hash"] == "recipient-proof-123"
    assert result["ledger_hash"] == "ledger-proof-123"


def test_refund_dispatcher_emits_refund_effect_receipts() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "refund", {"transaction_id": "tx-123"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "refund"
    assert result["receipt_status"] == "refunded"
    assert result["refund_id"] == "refund-123"
    assert result["transaction_id"] == "tx-123"
    assert result["ledger_hash"] == "refund-ledger-proof-123"


def test_refund_dispatcher_requires_transaction_id() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "refund", {"transaction_id": ""}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "refund"
    assert result["receipt_status"] == "missing_transaction_id"
