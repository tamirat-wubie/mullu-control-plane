"""v4.31.0 — atomic audit append under cross-worker concurrency (audit F4).

Pre-v4.31, every ``AuditTrail`` instance kept its own
``_sequence`` counter starting at 0 and its own ``_last_hash``
starting at genesis. Two workers writing to the same shared store
each produced ``sequence=1, 2, 3, ...`` independently, with each
worker's ``previous_hash`` chain reflecting only the entries it
itself had written. Result: a forked chain — the persisted log
contained two distinct entries at every sequence, each linked to a
different predecessor. Cross-worker verification was structurally
impossible.

v4.31 introduces ``AuditStore.try_append`` — an optional atomic
test-and-allocate primitive that owns sequence allocation and
chain-head linkage. When a store overrides it, ``AuditTrail``
delegates the sequence + previous_hash + entry_hash computation to
the store. Detection uses the same MRO override-sentinel as v4.27
``BudgetStore.try_record_spend``, v4.29
``RateLimitStore.try_consume``, and v4.30
``HashChainStore.try_append``: stores signal capability by
overriding the method, nothing more.

  - InMemoryAuditStore: ``threading.Lock``-guarded sequence + chain
    head. Single-process atomic.
  - PostgresAuditStore: not implemented in v4.31 (own PR; needs a
    SERIAL/identity ``sequence`` column or a ``FOR UPDATE`` lock on
    the latest row to compute ``previous_hash`` server-side).

These tests exercise the in-memory atomic path under thread
concurrency simulating multiple workers, plus dispatch and
backward-compat surfaces.
"""
from __future__ import annotations

import threading

import pytest

from mcoi_runtime.core.audit_trail import (
    AuditEntry,
    AuditStore,
    AuditTrail,
    _canonical_hash_v1,
    verify_chain_from_entries,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryAuditStore,
)


_FIXED_CLOCK = lambda: "2026-04-27T00:00:00Z"


def _record_kwargs(i: int) -> dict:
    return {
        "action": "test.action",
        "actor_id": f"actor-{i}",
        "tenant_id": "tenant-1",
        "target": f"target-{i}",
        "outcome": "success",
        "detail": {"i": i},
    }


# ============================================================
# AuditStore base class contract
# ============================================================


class TestAuditStoreBase:
    def test_base_try_append_returns_none(self):
        store = AuditStore()
        result = store.try_append(
            action="a", actor_id="x", tenant_id="t", target="y",
            outcome="ok", detail={}, recorded_at=_FIXED_CLOCK(),
        )
        assert result is None

    def test_trail_with_base_store_uses_in_process_path(self):
        # Base AuditStore doesn't override try_append → AuditTrail
        # falls through to the per-process counter. append() still
        # fires for write-through.
        store = AuditStore()
        trail = AuditTrail(clock=_FIXED_CLOCK, store=store)
        e1 = trail.record(**_record_kwargs(1))
        e2 = trail.record(**_record_kwargs(2))
        assert e1.sequence == 1
        assert e2.sequence == 2
        assert e2.previous_hash == e1.entry_hash


# ============================================================
# InMemoryAuditStore.try_append semantics
# ============================================================


class TestInMemoryStoreTryAppend:
    def test_first_append_starts_at_seq_1(self):
        store = InMemoryAuditStore()
        e = store.try_append(
            action="a", actor_id="x", tenant_id="t", target="y",
            outcome="ok", detail={}, recorded_at=_FIXED_CLOCK(),
        )
        assert e is not None
        assert e.sequence == 1

    def test_subsequent_append_links_to_predecessor(self):
        store = InMemoryAuditStore()
        e1 = store.try_append(
            action="a", actor_id="x", tenant_id="t", target="y",
            outcome="ok", detail={}, recorded_at=_FIXED_CLOCK(),
        )
        e2 = store.try_append(
            action="b", actor_id="x", tenant_id="t", target="z",
            outcome="ok", detail={}, recorded_at=_FIXED_CLOCK(),
        )
        assert e1 is not None and e2 is not None
        assert e2.sequence == 2
        assert e2.previous_hash == e1.entry_hash

    def test_entry_hash_matches_canonical(self):
        store = InMemoryAuditStore()
        e = store.try_append(
            action="a", actor_id="x", tenant_id="t", target="y",
            outcome="ok", detail={"k": "v"},
            recorded_at=_FIXED_CLOCK(),
        )
        assert e is not None
        recomputed = _canonical_hash_v1({
            "sequence": e.sequence,
            "action": e.action,
            "actor_id": e.actor_id,
            "tenant_id": e.tenant_id,
            "target": e.target,
            "outcome": e.outcome,
            "detail": e.detail,
            "previous_hash": e.previous_hash,
            "recorded_at": e.recorded_at,
        })
        assert e.entry_hash == recomputed

    def test_persists_in_internal_list(self):
        store = InMemoryAuditStore()
        for i in range(5):
            store.try_append(**_record_kwargs(i), recorded_at=_FIXED_CLOCK())
        assert store.count() == 5


# ============================================================
# Concurrency — the F4 fix in action
# ============================================================


class TestConcurrentAppend:
    def test_50_threads_no_chain_fork(self):
        """50 concurrent try_append calls on one store →
        exactly 50 entries with sequences {1..50}, valid linkage."""
        store = InMemoryAuditStore()

        def worker(i: int):
            store.try_append(**_record_kwargs(i), recorded_at=_FIXED_CLOCK())

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = sorted(store.query(limit=100), key=lambda e: e.sequence)
        seqs = [e.sequence for e in entries]
        assert seqs == list(range(1, 51))

        # Each entry's previous_hash matches its predecessor's entry_hash.
        for prev, cur in zip(entries, entries[1:]):
            assert cur.previous_hash == prev.entry_hash

    def test_two_audittrails_one_store_no_fork(self):
        """Two AuditTrail instances sharing one store simulate two
        worker processes. Pre-v4.31 each would produce its own
        sequence=1, 2, 3 — chain forks. Post-v4.31 the store owns
        sequence allocation, so the merged log is linear."""
        store = InMemoryAuditStore()
        trail_a = AuditTrail(clock=_FIXED_CLOCK, store=store)
        trail_b = AuditTrail(clock=_FIXED_CLOCK, store=store)

        def worker(trail: AuditTrail, prefix: str, count: int):
            for i in range(count):
                trail.record(
                    action="a", actor_id=f"{prefix}-{i}",
                    tenant_id="t", target=f"x-{i}", outcome="ok",
                )

        t_a = threading.Thread(target=worker, args=(trail_a, "a", 25))
        t_b = threading.Thread(target=worker, args=(trail_b, "b", 25))
        t_a.start()
        t_b.start()
        t_a.join()
        t_b.join()

        entries = sorted(store.query(limit=100), key=lambda e: e.sequence)
        seqs = [e.sequence for e in entries]
        assert seqs == list(range(1, 51))

        # External verification: the merged chain is valid.
        raw = [
            {
                "schema_version": 1,
                "entry_id": e.entry_id,
                "sequence": e.sequence,
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "detail": e.detail,
                "entry_hash": e.entry_hash,
                "previous_hash": e.previous_hash,
                "recorded_at": e.recorded_at,
            }
            for e in entries
        ]
        result = verify_chain_from_entries(raw)
        assert result.valid is True
        assert result.entries_checked == 50

    def test_concurrent_record_through_trail(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=_FIXED_CLOCK, store=store)

        def worker(i: int):
            trail.record(**_record_kwargs(i))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = sorted(store.query(limit=200), key=lambda e: e.sequence)
        seqs = [e.sequence for e in entries]
        assert seqs == list(range(1, 101))


# ============================================================
# AuditTrail dispatch — atomic path vs in-process fallback
# ============================================================


class TestAuditTrailDispatch:
    def test_uses_store_when_overridden(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=_FIXED_CLOCK, store=store)
        e1 = trail.record(**_record_kwargs(1))
        # Sequence comes from the store, not the trail's local counter.
        # Trail's local _sequence is synced from the store's response.
        assert e1.sequence == 1
        assert trail._sequence == 1  # type: ignore[attr-defined]
        assert trail._last_hash == e1.entry_hash  # type: ignore[attr-defined]

    def test_falls_through_when_store_does_not_override(self):
        # Custom store without try_append override.
        class CounterOnlyStore(AuditStore):
            def __init__(self):
                self.appended: list[AuditEntry] = []

            def append(self, entry):
                self.appended.append(entry)

        store = CounterOnlyStore()
        trail = AuditTrail(clock=_FIXED_CLOCK, store=store)
        e1 = trail.record(**_record_kwargs(1))
        e2 = trail.record(**_record_kwargs(2))
        # In-process counter advances; store gets append() write-through.
        assert e1.sequence == 1 and e2.sequence == 2
        assert len(store.appended) == 2

    def test_no_store_uses_in_process_path(self):
        trail = AuditTrail(clock=_FIXED_CLOCK)
        e1 = trail.record(**_record_kwargs(1))
        e2 = trail.record(**_record_kwargs(2))
        assert e1.sequence == 1
        assert e2.previous_hash == e1.entry_hash

    def test_duck_typed_store_falls_through(self):
        # Duck-typed store without inheriting AuditStore at all.
        class DuckStore:
            def __init__(self):
                self.appended: list[AuditEntry] = []

            def append(self, entry):
                self.appended.append(entry)

            def store_checkpoint(self, checkpoint):
                pass

            def latest_checkpoint(self):
                return None

        store = DuckStore()
        trail = AuditTrail(clock=_FIXED_CLOCK, store=store)  # type: ignore[arg-type]
        e1 = trail.record(**_record_kwargs(1))
        # getattr default detects "no override" for duck-typed stores.
        assert e1.sequence == 1
        assert len(store.appended) == 1


# ============================================================
# Backward compatibility
# ============================================================


class TestBackwardCompat:
    def test_existing_inmemory_legacy_append_still_works(self):
        # Direct .append() (the legacy path used by AuditTrail
        # write-through when the legacy fallback fires) still works.
        store = InMemoryAuditStore()
        # Build a legacy-style entry by hand (sequence chosen
        # externally — this is exactly what the legacy path does).
        recorded_at = _FIXED_CLOCK()
        source = {
            "sequence": 7,
            "action": "x",
            "actor_id": "a",
            "tenant_id": "t",
            "target": "y",
            "outcome": "ok",
            "detail": {},
            "previous_hash": "0" * 64,
            "recorded_at": recorded_at,
        }
        entry = AuditEntry(
            entry_id="audit-7",
            sequence=7,
            action="x",
            actor_id="a",
            tenant_id="t",
            target="y",
            outcome="ok",
            detail={},
            entry_hash=_canonical_hash_v1(source),
            previous_hash="0" * 64,
            recorded_at=recorded_at,
        )
        store.append(entry)
        assert store.count() == 1
        assert store.query(limit=10)[-1].sequence == 7

    def test_record_signature_unchanged(self):
        trail = AuditTrail(clock=_FIXED_CLOCK)
        e = trail.record(
            action="a", actor_id="x", tenant_id="t",
            target="y", outcome="ok",
        )
        assert isinstance(e, AuditEntry)
        assert e.sequence == 1
