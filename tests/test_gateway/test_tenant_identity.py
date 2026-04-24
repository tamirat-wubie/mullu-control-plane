"""Gateway tenant identity tests.

Tests: durable identity store contract, revocation behavior, and router wiring.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayRouter  # noqa: E402
from gateway.tenant_identity import (  # noqa: E402
    InMemoryTenantIdentityStore,
    TenantMapping,
    build_tenant_identity_store_from_env,
)


class StubPlatform:
    """Minimal platform stub for router construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        raise AssertionError("tenant identity tests should not open sessions")


def test_in_memory_tenant_identity_store_resolves_active_mapping():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    store.save(TenantMapping(
        channel="slack",
        sender_id="U123",
        tenant_id="tenant-1",
        identity_id="identity-1",
        roles=("operator",),
        approval_authority=True,
    ))

    mapping = store.resolve("slack", "U123")

    assert mapping is not None
    assert mapping.tenant_id == "tenant-1"
    assert mapping.identity_id == "identity-1"
    assert mapping.roles == ("operator",)
    assert mapping.approval_authority is True
    assert mapping.created_at == "2026-04-24T12:00:00+00:00"


def test_in_memory_tenant_identity_store_does_not_resolve_revoked_mapping():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    store.save(TenantMapping(
        channel="telegram",
        sender_id="42",
        tenant_id="tenant-1",
        identity_id="identity-1",
        revoked_at="2026-04-24T13:00:00+00:00",
    ))

    mapping = store.resolve("telegram", "42")

    assert mapping is None
    assert store.count() == 0
    assert store.status()["active_mappings"] == 0


def test_build_tenant_identity_store_from_env_uses_memory_backend(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_TENANT_IDENTITY_BACKEND", "memory")

    store = build_tenant_identity_store_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")

    assert store.status()["backend"] == "memory"
    assert store.count() == 0


def test_router_uses_injected_tenant_identity_store():
    store = InMemoryTenantIdentityStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    router = GatewayRouter(
        platform=StubPlatform(),
        tenant_identity_store=store,
    )
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="subject-1",
        tenant_id="tenant-1",
        identity_id="identity-1",
    ))

    mapping = router.resolve_tenant("web", "subject-1")
    summary = router.summary()

    assert mapping is not None
    assert mapping.tenant_id == "tenant-1"
    assert summary["tenant_mappings"] == 1
    assert summary["tenant_identity_store"]["backend"] == "memory"
