"""Gateway memory constitution tests.

Tests: governed memory cell admission, scoped lookup, expiry filtering,
    and router admission from tenant mapping metadata.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.memory_constitution import (  # noqa: E402
    GovernedMemoryCell,
    InMemoryGovernedMemoryStore,
)
from gateway.router import GatewayRouter  # noqa: E402
from gateway.tenant_identity import TenantMapping  # noqa: E402


class StubPlatform:
    """Minimal platform stub for router construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        raise AssertionError("memory constitution tests should not open sessions")


def _cell(**overrides):
    payload = {
        "memory_id": "",
        "tenant_id": "tenant-1",
        "owner_id": "identity-1",
        "scope": "response_format",
        "fact": "Prefers architecture, algorithm, code ordering.",
        "source": "user_profile",
        "confidence": 0.95,
        "sensitivity": "low",
        "expires_at": "never",
        "allowed_use": ("response_formatting",),
        "forbidden_use": ("external_sharing",),
        "last_verified_at": "2026-04-24T12:00:00+00:00",
        "mutation_history": ("created:user_profile",),
    }
    payload.update(overrides)
    return GovernedMemoryCell(**payload)


def test_governed_memory_store_admits_complete_cell():
    store = InMemoryGovernedMemoryStore(clock=lambda: "2026-04-24T12:00:00+00:00")

    admission = store.admit(_cell())
    cells = store.query(
        tenant_id="tenant-1",
        owner_id="identity-1",
        allowed_use="response_formatting",
        scope="response_format",
    )

    assert admission.accepted is True
    assert admission.memory_id.startswith("mem-")
    assert admission.cell_hash
    assert len(cells) == 1
    assert cells[0].cell_hash == admission.cell_hash


def test_governed_memory_store_rejects_unsourced_cell():
    store = InMemoryGovernedMemoryStore(clock=lambda: "2026-04-24T12:00:00+00:00")

    admission = store.admit(_cell(source=""))

    assert admission.accepted is False
    assert admission.reason == "source_required"
    assert store.count() == 0


def test_governed_memory_store_filters_forbidden_and_expired_cells():
    store = InMemoryGovernedMemoryStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    store.admit(_cell(memory_id="usable"))
    store.admit(_cell(
        memory_id="expired",
        expires_at="2026-04-23T12:00:00+00:00",
    ))

    allowed = store.query(
        tenant_id="tenant-1",
        owner_id="identity-1",
        allowed_use="response_formatting",
    )
    forbidden = store.query(
        tenant_id="tenant-1",
        owner_id="identity-1",
        allowed_use="external_sharing",
    )

    assert [cell.memory_id for cell in allowed] == ["usable"]
    assert forbidden == []
    assert store.count() == 1


def test_router_admits_mapping_memory_metadata():
    memory_store = InMemoryGovernedMemoryStore(clock=lambda: "2026-04-24T12:00:00+00:00")
    router = GatewayRouter(
        platform=StubPlatform(),
        memory_store=memory_store,
    )
    mapping = TenantMapping(
        channel="web",
        sender_id="subject-1",
        tenant_id="tenant-1",
        identity_id="identity-1",
        metadata={
            "memory_cells": [{
                "scope": "response_format",
                "fact": "Prefers architecture, algorithm, code ordering.",
                "source": "user_profile",
                "confidence": 0.95,
                "sensitivity": "low",
                "expires_at": "never",
                "allowed_use": ["response_formatting"],
                "forbidden_use": ["external_sharing"],
                "last_verified_at": "2026-04-24T12:00:00+00:00",
                "mutation_history": ["created:user_profile"],
            }],
        },
    )

    router.register_tenant_mapping(mapping)
    cells = router.governed_memory_for(
        mapping,
        allowed_use="response_formatting",
        scope="response_format",
    )
    summary = router.summary()

    assert len(cells) == 1
    assert cells[0].owner_id == "identity-1"
    assert cells[0].allowed_use == ("response_formatting",)
    assert summary["memory_store"]["active_cells"] == 1
