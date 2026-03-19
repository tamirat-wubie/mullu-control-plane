"""Purpose: verify provider registry — registration, health tracking, scope enforcement.
Governance scope: provider management tests only.
Dependencies: provider contracts, provider registry.
Invariants: disabled/unavailable providers not invocable; health from results; scope enforced.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
    ProviderHealthStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.provider_registry import ProviderRegistry


_CLOCK = "2026-03-19T00:00:00+00:00"


def _descriptor(pid: str = "prov-1", enabled: bool = True) -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=pid, name="Test Provider",
        provider_class=ProviderClass.INTEGRATION,
        credential_scope_id=f"scope-{pid}",
        enabled=enabled, base_url="https://api.test.com",
    )


def _scope(pid: str = "prov-1") -> CredentialScope:
    return CredentialScope(
        scope_id=f"scope-{pid}", provider_id=pid,
        allowed_base_urls=("https://api.test.com",),
        allowed_operations=("read",),
        rate_limit_per_minute=60,
    )


def test_register_and_get() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    assert reg.get_provider("prov-1") is not None
    assert reg.get_scope("prov-1") is not None
    assert reg.get_health("prov-1").status is ProviderHealthStatus.UNKNOWN


def test_duplicate_rejected() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
        reg.register(_descriptor(), _scope())


def test_check_invocable_enabled() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    ok, reason = reg.check_invocable("prov-1")
    assert ok is True


def test_check_invocable_disabled() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(enabled=False), _scope())
    ok, reason = reg.check_invocable("prov-1")
    assert ok is False
    assert reason == "provider_disabled"


def test_check_invocable_unavailable() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    # Simulate 3 consecutive failures -> unavailable
    reg.record_failure("prov-1", "timeout")
    reg.record_failure("prov-1", "timeout")
    reg.record_failure("prov-1", "timeout")
    ok, reason = reg.check_invocable("prov-1")
    assert ok is False
    assert reason == "provider_unavailable"


def test_health_recovers_on_success() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    reg.record_failure("prov-1", "error")
    reg.record_failure("prov-1", "error")
    assert reg.get_health("prov-1").status is ProviderHealthStatus.DEGRADED

    reg.record_success("prov-1")
    assert reg.get_health("prov-1").status is ProviderHealthStatus.HEALTHY
    assert reg.get_health("prov-1").consecutive_failures == 0


def test_url_scope_check() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(_descriptor(), _scope())
    assert reg.check_url_in_scope("prov-1", "https://api.test.com/v1/data") is True
    assert reg.check_url_in_scope("prov-1", "https://evil.com/steal") is False


def test_list_providers_by_class() -> None:
    reg = ProviderRegistry(clock=lambda: _CLOCK)
    reg.register(
        ProviderDescriptor(
            provider_id="p-int", name="Int", provider_class=ProviderClass.INTEGRATION,
            credential_scope_id="s-int", enabled=True,
        ),
        CredentialScope(scope_id="s-int", provider_id="p-int"),
    )
    reg.register(
        ProviderDescriptor(
            provider_id="p-model", name="Model", provider_class=ProviderClass.MODEL,
            credential_scope_id="s-model", enabled=True,
        ),
        CredentialScope(scope_id="s-model", provider_id="p-model"),
    )
    assert len(reg.list_providers()) == 2
    assert len(reg.list_providers(provider_class=ProviderClass.MODEL)) == 1
