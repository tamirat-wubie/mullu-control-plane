"""Registry-level tests for the god-mode subsystem.

Verifies the registration agreement flow: capabilities are dormant until an
explicit operator agreement promotes them to ARMED, can be withdrawn back
to WITHDRAWN, and respect the per-capability minimum justification length.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
    GodCapabilityState,
)
from mcoi_runtime.core.god_mode_integration import (
    default_capability_proposals,
    install_default_capabilities,
)
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    GodModeRegistryError,
)


_LONG_JUST = "x" * 60
_VERY_LONG_JUST = "x" * 130


@pytest.fixture
def registry() -> GodModeRegistry:
    return GodModeRegistry()


@pytest.fixture
def capability() -> GodCapability:
    return GodCapability(
        module="data",
        name="purge_tenant_now",
        description="Delete all data for a tenant immediately.",
        blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
        bypasses=("retention_window",),
        default_ttl_seconds=60,
        min_justification_chars=120,
    )


def test_register_capability_creates_dormant(registry, capability):
    registry.register_capability(capability)
    assert registry.has_capability("data", "purge_tenant_now")
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.DORMANT
    assert not registry.is_armed("data", "purge_tenant_now")


def test_register_idempotent_with_identical(registry, capability):
    registry.register_capability(capability)
    registry.register_capability(capability)  # second call ok
    assert len(registry.list_capabilities()) == 1


def test_register_conflict_with_different_descriptor_raises(registry, capability):
    registry.register_capability(capability)
    conflict = GodCapability(
        module="data",
        name="purge_tenant_now",
        description="A different description.",
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("retention_window",),
        default_ttl_seconds=60,
        min_justification_chars=120,
    )
    with pytest.raises(GodModeRegistryError):
        registry.register_capability(conflict)


def test_get_capability_unknown_raises(registry):
    with pytest.raises(GodModeRegistryError):
        registry.get_capability("nope", "missing")


def test_agree_arms_capability(registry, capability):
    registry.register_capability(capability)
    agreement = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    assert agreement.is_active
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.ARMED
    assert registry.is_armed("data", "purge_tenant_now")


def test_agree_rejects_short_justification(registry, capability):
    registry.register_capability(capability)
    with pytest.raises(GodModeRegistryError):
        registry.agree_to_register(
            module="data",
            name="purge_tenant_now",
            actor_id="alice",
            justification=_LONG_JUST,  # 60 < the cap's 120 char minimum
        )


def test_agree_unknown_capability_raises(registry):
    with pytest.raises(GodModeRegistryError):
        registry.agree_to_register(
            module="ghost",
            name="missing",
            actor_id="alice",
            justification=_VERY_LONG_JUST,
        )


def test_withdraw_agreement_reverts_state(registry, capability):
    registry.register_capability(capability)
    agreement = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    withdrawn = registry.withdraw_registration(
        agreement_id=agreement.agreement_id,
        actor_id="alice",
        reason="rotated",
    )
    assert not withdrawn.is_active
    assert (
        registry.state_of("data", "purge_tenant_now") == GodCapabilityState.WITHDRAWN
    )


def test_withdraw_twice_raises(registry, capability):
    registry.register_capability(capability)
    agreement = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.withdraw_registration(
        agreement_id=agreement.agreement_id,
        actor_id="alice",
        reason="rotated",
    )
    with pytest.raises(GodModeRegistryError):
        registry.withdraw_registration(
            agreement_id=agreement.agreement_id,
            actor_id="alice",
            reason="again",
        )


def test_withdraw_unknown_agreement_raises(registry):
    with pytest.raises(GodModeRegistryError):
        registry.withdraw_registration(
            agreement_id="god-reg-doesnotexist",
            actor_id="alice",
            reason="bad",
        )


def test_re_arm_after_withdrawal(registry, capability):
    registry.register_capability(capability)
    first = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.withdraw_registration(
        agreement_id=first.agreement_id, actor_id="alice", reason="rotated"
    )
    second = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="bob",
        justification=_VERY_LONG_JUST,
    )
    assert second.is_active
    assert registry.is_armed("data", "purge_tenant_now")


def test_suspend_blocks_armed_state(registry, capability):
    registry.register_capability(capability)
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.suspend("data", "purge_tenant_now")
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.SUSPENDED
    registry.resume("data", "purge_tenant_now")
    assert registry.is_armed("data", "purge_tenant_now")


def test_list_modules_returns_unique_sorted(registry):
    cap_a = GodCapability(
        module="rbac",
        name="impersonate_user",
        description="x",
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("identity_binding",),
        default_ttl_seconds=60,
    )
    cap_b = GodCapability(
        module="data",
        name="purge_tenant_now",
        description="y",
        blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
        bypasses=("retention_window",),
        default_ttl_seconds=60,
    )
    registry.register_capability(cap_a)
    registry.register_capability(cap_b)
    assert registry.list_modules() == ("data", "rbac")


def test_install_default_capabilities_seeds_proposals():
    fresh = GodModeRegistry()
    count = install_default_capabilities(fresh)
    assert count >= 10  # at least 10 per-module proposals
    assert count == len(default_capability_proposals())
    # All start dormant — none of them are armed without explicit consent.
    for cap in fresh.list_capabilities():
        assert fresh.state_of(cap.module, cap.name) == GodCapabilityState.DORMANT


def test_install_default_capabilities_idempotent():
    fresh = GodModeRegistry()
    first = install_default_capabilities(fresh)
    second = install_default_capabilities(fresh)
    assert first > 0
    assert second == 0


def test_default_proposals_cover_required_modules():
    proposals = default_capability_proposals()
    modules = {p.module for p in proposals}
    expected = {
        "data",
        "rbac",
        "governance",
        "temporal_scheduler",
        "constructs",
        "policy",
        "replay",
        "secrets",
        "mfidel",
        "mil_audit",
    }
    assert expected <= modules


def test_default_proposals_blast_radius_proportionate():
    """Capabilities flagged with catastrophic blast must have stricter floors."""
    for cap in default_capability_proposals():
        if cap.blast_radius == GodCapabilityBlastRadius.CATASTROPHIC:
            assert cap.min_justification_chars >= 120
            assert cap.default_ttl_seconds <= 120
            assert cap.one_shot is True
