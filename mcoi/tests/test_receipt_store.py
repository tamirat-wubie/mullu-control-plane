"""Tests for `mcoi/mcoi_runtime/contracts/receipt_store.py`.

Closes the architectural-shape half of the "Receipts not persisted" gap:
exercises the `ReceiptStore` Protocol's degraded-no-op semantics and the
`InMemoryReceiptStore` default-implementation behavior, plus the
ProofBridge → ReceiptStore wiring.

Mirror tests for AuditStore would live under test_audit_trail.py; this
file's structure follows that pattern (base class no-op tests, then
in-memory implementation tests).
"""
from __future__ import annotations

import pytest

from mcoi_runtime.contracts.proof import CausalLineage
from mcoi_runtime.contracts.receipt_store import (
    InMemoryReceiptStore,
    ReceiptStore,
)
from mcoi_runtime.core.proof_bridge import ProofBridge


def _clock() -> str:
    return "2026-04-28T00:00:00Z"


def _lineage(entity_id: str = "e1", depth: int = 1) -> CausalLineage:
    return CausalLineage(
        lineage_id=f"lin-{entity_id}",
        entity_id=entity_id,
        receipt_chain=(f"rcpt-{entity_id}",),
        root_receipt_id=f"rcpt-{entity_id}",
        current_state="running",
        depth=depth,
    )


# ── Base class: degraded-no-op semantics ─────────────────────────────


class TestReceiptStoreBaseClass:
    """A bare ReceiptStore() must be safe — no exceptions, no surprises.
    Mirrors AuditStore's "degraded gracefully" rationale."""

    def test_get_lineage_returns_none(self):
        s = ReceiptStore()
        assert s.get_lineage("anyone") is None

    def test_record_lineage_is_noop(self):
        s = ReceiptStore()
        s.record_lineage("e1", _lineage("e1"))
        # Still no lineage — base class is a black hole.
        assert s.get_lineage("e1") is None

    def test_evict_oldest_is_noop(self):
        s = ReceiptStore()
        s.evict_oldest()  # must not raise

    def test_has_lineage_returns_false(self):
        assert ReceiptStore().has_lineage("anyone") is False

    def test_len_is_zero(self):
        assert len(ReceiptStore()) == 0

    def test_max_entries_has_safe_default(self):
        assert ReceiptStore().max_entries >= 1


# ── InMemoryReceiptStore: working implementation ─────────────────────


class TestInMemoryReceiptStore:
    def test_record_then_get(self):
        s = InMemoryReceiptStore()
        s.record_lineage("e1", _lineage("e1"))
        result = s.get_lineage("e1")
        assert result is not None
        assert result.entity_id == "e1"

    def test_record_overwrites(self):
        s = InMemoryReceiptStore()
        s.record_lineage("e1", _lineage("e1", depth=1))
        s.record_lineage("e1", _lineage("e1", depth=5))
        result = s.get_lineage("e1")
        assert result is not None
        assert result.depth == 5

    def test_has_lineage(self):
        s = InMemoryReceiptStore()
        assert s.has_lineage("e1") is False
        s.record_lineage("e1", _lineage("e1"))
        assert s.has_lineage("e1") is True

    def test_len_grows_with_records(self):
        s = InMemoryReceiptStore()
        assert len(s) == 0
        s.record_lineage("e1", _lineage("e1"))
        assert len(s) == 1
        s.record_lineage("e2", _lineage("e2"))
        assert len(s) == 2
        # Overwriting same key doesn't grow length.
        s.record_lineage("e1", _lineage("e1", depth=2))
        assert len(s) == 2

    def test_evict_oldest_removes_first_inserted(self):
        s = InMemoryReceiptStore()
        s.record_lineage("first", _lineage("first"))
        s.record_lineage("middle", _lineage("middle"))
        s.record_lineage("last", _lineage("last"))
        s.evict_oldest()
        assert s.has_lineage("first") is False
        assert s.has_lineage("middle") is True
        assert s.has_lineage("last") is True

    def test_evict_oldest_on_empty_is_safe(self):
        InMemoryReceiptStore().evict_oldest()  # must not raise

    def test_max_entries_floor(self):
        with pytest.raises(ValueError):
            InMemoryReceiptStore(max_entries=0)
        with pytest.raises(ValueError):
            InMemoryReceiptStore(max_entries=-5)

    def test_custom_max_entries_respected(self):
        s = InMemoryReceiptStore(max_entries=3)
        assert s.max_entries == 3


# ── ProofBridge ↔ ReceiptStore wiring ────────────────────────────────


class TestProofBridgeUsesStore:
    """ProofBridge defaults to InMemoryReceiptStore; injection wires a
    custom store; bridge state goes entirely through the store."""

    def test_default_store_is_in_memory(self):
        bridge = ProofBridge(clock=_clock)
        # Internal but worth pinning: default must be InMemoryReceiptStore
        # so behavior matches pre-Protocol code.
        assert isinstance(bridge._store, InMemoryReceiptStore)

    def test_injected_store_is_used(self):
        custom = InMemoryReceiptStore(max_entries=5)
        bridge = ProofBridge(clock=_clock, store=custom)
        assert bridge._store is custom

    def test_lineage_count_reflects_store_state(self):
        bridge = ProofBridge(clock=_clock)
        assert bridge.lineage_count == 0
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        # Bridge wraps each request as entity_id = f"request:{tenant}:{endpoint}",
        # so two distinct (tenant, endpoint) pairs produce two lineages.
        bridge.certify_governance_decision(
            tenant_id="t2", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        assert bridge.lineage_count == 2

    def test_get_lineage_delegates_to_store(self):
        bridge = ProofBridge(clock=_clock)
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        # entity_id format is request:{tenant_id}:{endpoint}
        lineage = bridge.get_lineage("request:t1:/api/test")
        assert lineage is not None
        assert lineage.depth == 1

    def test_disabled_store_makes_bridge_lineage_free(self):
        """A bare ReceiptStore() base-class instance disables all lineage
        tracking — useful for tests or surfaces where lineage is
        intentionally not retained. Receipts still emit; lineage is
        always empty."""
        bridge = ProofBridge(clock=_clock, store=ReceiptStore())
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        assert bridge.lineage_count == 0
        assert bridge.get_lineage("request:t1:/api/test") is None

    def test_eviction_at_capacity(self):
        """When store reaches max_entries and a new entity arrives, the
        oldest lineage is evicted. Same FIFO discipline as the
        pre-Protocol dict."""
        store = InMemoryReceiptStore(max_entries=2)
        bridge = ProofBridge(clock=_clock, store=store)
        # Three different (tenant, endpoint) pairs → three entity_ids.
        for n in range(3):
            bridge.certify_governance_decision(
                tenant_id=f"t{n}", endpoint="/api/test",
                guard_results=[{"guard_name": "g", "allowed": True, "reason": ""}],
                decision="allowed",
            )
        # Store capped at 2; the first entity's lineage is evicted.
        assert bridge.lineage_count == 2
        assert bridge.get_lineage("request:t0:/api/test") is None
        assert bridge.get_lineage("request:t1:/api/test") is not None
        assert bridge.get_lineage("request:t2:/api/test") is not None
