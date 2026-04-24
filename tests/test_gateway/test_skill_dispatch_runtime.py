"""Gateway skill dispatcher runtime binding tests.

Tests: platform-backed provider injection for governed skill dispatch.
"""

from decimal import Decimal
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.skill_dispatch import SkillIntent, build_skill_dispatcher_from_platform  # noqa: E402
from skills.financial.providers.base import AccountInfo, StubFinancialProvider  # noqa: E402


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
