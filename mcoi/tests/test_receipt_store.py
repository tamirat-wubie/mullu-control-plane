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

import json

import pytest

from mcoi_runtime.contracts import receipt_store as receipt_store_module
from mcoi_runtime.contracts.proof import CausalLineage
from mcoi_runtime.contracts.receipt_store import (
    InMemoryReceiptStore,
    JsonlReceiptStore,
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


def _proof(endpoint: str = "/api/test"):
    bridge = ProofBridge(clock=_clock)
    return bridge.certify_governance_decision(
        tenant_id="t1",
        endpoint=endpoint,
        guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
        decision="allowed",
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

    def test_record_receipt_is_noop(self):
        receipt = _proof().capsule.receipt
        s = ReceiptStore()
        s.record_receipt(receipt)
        assert s.get_receipt(receipt.receipt_id) is None
        assert s.receipt_count == 0
        assert s.latest_receipt_hash == "genesis"

    def test_evict_oldest_is_noop(self):
        s = ReceiptStore()
        s.evict_oldest()  # must not raise

    def test_has_lineage_returns_false(self):
        assert ReceiptStore().has_lineage("anyone") is False

    def test_len_is_zero(self):
        assert len(ReceiptStore()) == 0

    def test_max_entries_has_safe_default(self):
        assert ReceiptStore().max_entries >= 1

    def test_base_class_validates_inputs_before_noop(self):
        s = ReceiptStore()
        with pytest.raises(ValueError, match="entity_id"):
            s.get_lineage("")
        with pytest.raises(ValueError, match="lineage"):
            s.record_lineage("e1", "bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="entity_id"):
            s.has_lineage("")
        with pytest.raises(ValueError, match="receipt"):
            s.record_receipt("bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="receipt_id"):
            s.get_receipt("")


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
        with pytest.raises(ValueError):
            InMemoryReceiptStore(max_entries=True)  # type: ignore[arg-type]

    def test_custom_max_entries_respected(self):
        s = InMemoryReceiptStore(max_entries=3)
        assert s.max_entries == 3

    def test_record_lineage_requires_matching_entity(self):
        s = InMemoryReceiptStore()
        with pytest.raises(ValueError, match="entity_id"):
            s.record_lineage("", _lineage("e1"))
        with pytest.raises(ValueError, match="lineage"):
            s.record_lineage("e1", "bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="match"):
            s.record_lineage("e1", _lineage("other"))

    def test_record_then_get_receipt(self):
        receipt = _proof().capsule.receipt
        s = InMemoryReceiptStore()
        s.record_receipt(receipt)
        result = s.get_receipt(receipt.receipt_id)
        assert result is receipt
        assert result.receipt_id == receipt.receipt_id
        assert result.receipt_hash == receipt.receipt_hash

    def test_record_receipt_overwrites_same_id(self):
        receipt = _proof().capsule.receipt
        s = InMemoryReceiptStore()
        s.record_receipt(receipt)
        s.record_receipt(receipt)
        result = s.get_receipt(receipt.receipt_id)
        assert result is receipt
        assert result.receipt_id == receipt.receipt_id
        assert s.get_receipt("missing") is None

    def test_receipt_count_and_latest_hash_track_insertions(self):
        s = InMemoryReceiptStore()
        first = _proof("/api/first").capsule.receipt
        second = _proof("/api/second").capsule.receipt
        assert s.receipt_count == 0
        assert s.latest_receipt_hash == "genesis"

        s.record_receipt(first)
        assert s.receipt_count == 1
        assert s.latest_receipt_hash == first.receipt_hash

        s.record_receipt(second)
        assert s.receipt_count == 2
        assert s.latest_receipt_hash == second.receipt_hash


# ── JsonlReceiptStore: durable append-only implementation ────────────


class TestJsonlReceiptStore:
    def test_sync_on_write_defaults_off(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        store = JsonlReceiptStore(path)

        assert store.sync_on_write is False
        assert store.path == path
        assert store.receipt_count == 0

    def test_sync_on_write_calls_fsync_for_appends(self, tmp_path, monkeypatch):
        path = tmp_path / "receipts.jsonl"
        fsync_calls: list[int] = []

        def fake_fsync(file_descriptor: int) -> None:
            fsync_calls.append(file_descriptor)

        monkeypatch.setattr(receipt_store_module.os, "fsync", fake_fsync)
        store = JsonlReceiptStore(path, sync_on_write=True)
        receipt = _proof().capsule.receipt

        store.record_receipt(receipt)

        assert store.sync_on_write is True
        assert len(fsync_calls) == 1
        assert path.read_text(encoding="utf-8").count("receipt_record") == 1

    def test_sync_on_write_must_be_boolean(self, tmp_path):
        path = tmp_path / "receipts.jsonl"

        with pytest.raises(ValueError, match="sync_on_write"):
            JsonlReceiptStore(path, sync_on_write="true")  # type: ignore[arg-type]

        assert not path.exists()
        assert path.parent.exists()

    def test_persists_receipt_and_lineage_across_reopen(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        store = JsonlReceiptStore(path)
        bridge = ProofBridge(clock=_clock, store=store)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
            decision="allowed",
        )

        reopened = JsonlReceiptStore(path)
        receipt = reopened.get_receipt(proof.capsule.receipt.receipt_id)
        lineage = reopened.get_lineage("request:t1:/api/test")
        assert receipt is not None
        assert receipt.receipt_hash == proof.receipt_hash
        assert lineage is not None
        assert lineage.depth == 1

    def test_append_only_file_records_typed_events(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        store = JsonlReceiptStore(path)
        receipt = _proof().capsule.receipt
        store.record_receipt(receipt)
        store.record_lineage(receipt.entity_id, _lineage(receipt.entity_id))

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert '"type":"receipt_record"' in lines[0]
        assert '"type":"lineage_upsert"' in lines[1]

    def test_replays_eviction_events(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        store = JsonlReceiptStore(path, max_entries=2)
        bridge = ProofBridge(clock=_clock, store=store)
        for n in range(3):
            bridge.certify_governance_decision(
                tenant_id=f"t{n}", endpoint="/api/test",
                guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
                decision="allowed",
            )

        reopened = JsonlReceiptStore(path, max_entries=2)
        assert len(reopened) == 2
        assert reopened.get_lineage("request:t0:/api/test") is None
        assert reopened.get_lineage("request:t1:/api/test") is not None
        assert reopened.get_lineage("request:t2:/api/test") is not None

    def test_reopened_store_resumes_proof_bridge_causal_parent(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        first_store = JsonlReceiptStore(path)
        first_bridge = ProofBridge(clock=_clock, store=first_store)
        first_proof = first_bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/first",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
            decision="allowed",
        )

        reopened_store = JsonlReceiptStore(path)
        resumed_bridge = ProofBridge(clock=_clock, store=reopened_store)
        resumed_summary = resumed_bridge.summary()
        second_proof = resumed_bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/second",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
            decision="allowed",
        )
        fresh_bridge = ProofBridge(clock=_clock, store=JsonlReceiptStore(tmp_path / "fresh.jsonl"))
        fresh_second_proof = fresh_bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/second",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": "ok"}],
            decision="allowed",
        )

        assert reopened_store.receipt_count == 2
        assert resumed_summary["receipt_count"] == 1
        assert resumed_summary["last_receipt_hash"] == first_proof.receipt_hash[:16]
        assert resumed_bridge.receipt_count == 2
        assert second_proof.capsule.receipt.causal_parent != fresh_second_proof.capsule.receipt.causal_parent
        assert second_proof.receipt_hash != fresh_second_proof.receipt_hash

    def test_rejects_malformed_jsonl(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        path.write_text("{not-json}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="malformed"):
            JsonlReceiptStore(path)

    def test_rejects_unsupported_event_type(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        path.write_text('{"type":"unknown"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported event type"):
            JsonlReceiptStore(path)

    def test_rejects_malformed_receipt_guard(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        receipt = _proof().capsule.receipt.to_json_dict()
        receipt["guard_verdicts"] = ["bad"]
        path.write_text(
            '{"receipt":' + json.dumps(receipt) + ',"type":"receipt_record"}\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="guard_verdicts"):
            JsonlReceiptStore(path)


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

    def test_certify_records_receipt_in_store(self):
        store = InMemoryReceiptStore()
        bridge = ProofBridge(clock=_clock, store=store)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        stored = store.get_receipt(proof.capsule.receipt.receipt_id)
        assert stored is proof.capsule.receipt
        assert stored.receipt_hash == proof.receipt_hash
        assert bridge.receipt_count == 1

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
