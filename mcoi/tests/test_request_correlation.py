"""Phase 214B — Request correlation tests."""

import pytest
from mcoi_runtime.core.request_correlation import (
    CorrelationManager,
    DEFAULT_ACTIVE_TTL_SECONDS,
    DEFAULT_MAX_COMPLETED,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestCorrelationManager:
    def test_start(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        ctx = mgr.start(tenant_id="t1", endpoint="/api/test")
        assert ctx.correlation_id.startswith("cor-")
        assert ctx.tenant_id == "t1"

    def test_complete(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        ctx = mgr.start()
        assert mgr.active_count == 1
        mgr.complete(ctx.correlation_id)
        assert mgr.active_count == 0
        assert mgr.completed_count == 1

    def test_child(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        parent = mgr.start()
        child = mgr.child(parent.correlation_id, tenant_id="t1")
        assert child.parent_id == parent.correlation_id
        assert child.correlation_id != parent.correlation_id

    def test_get_context(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        ctx = mgr.start(actor_id="actor-1")
        retrieved = mgr.get_context(ctx.correlation_id)
        assert retrieved is not None
        assert retrieved.actor_id == "actor-1"

    def test_unique_ids(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        ids = {mgr.start().correlation_id for _ in range(10)}
        assert len(ids) == 10

    def test_summary(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        mgr.start()
        mgr.start()
        s = mgr.summary()
        assert s["active"] == 2


class TestCompletedCap:
    """The completed-context ring is bounded — cannot OOM in long-running prod."""

    def test_default_cap_is_set(self):
        """A fresh manager applies DEFAULT_MAX_COMPLETED."""
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        assert mgr._completed.maxlen == DEFAULT_MAX_COMPLETED

    def test_custom_cap_respected(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK, max_completed=5)
        assert mgr._completed.maxlen == 5

    def test_completed_capped_at_maxlen(self):
        """Completing more requests than the cap evicts oldest entries.
        Without this cap, _completed grew without limit in v4.x and earlier
        — a real OOM under sustained traffic. Regression guard: this test
        existing means the bound is enforced, not just intended."""
        mgr = CorrelationManager(clock=FIXED_CLOCK, max_completed=3)
        ids = []
        for _ in range(10):
            ctx = mgr.start()
            ids.append(ctx.correlation_id)
            mgr.complete(ctx.correlation_id)
        # 10 completed, but only the cap fits
        assert mgr.completed_count == 3
        # The youngest 3 IDs should be the survivors
        survivors = [c.correlation_id for c in mgr._completed]
        assert survivors == ids[-3:]

    def test_summary_reflects_capped_count(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK, max_completed=2)
        for _ in range(5):
            ctx = mgr.start()
            mgr.complete(ctx.correlation_id)
        assert mgr.summary()["completed"] == 2


class TestActiveTTLSweep:
    """Active correlations get evicted when older than TTL — guards
    against the crashed-request leak found in v4.18 audit."""

    def test_default_ttl_set(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        assert mgr._active_ttl == DEFAULT_ACTIVE_TTL_SECONDS

    def test_ttl_none_disables_sweep(self):
        """Passing ttl=None preserves legacy behavior: entries never
        age out, only complete() removes them."""
        clock = [0.0]
        mgr = CorrelationManager(
            clock=FIXED_CLOCK,
            active_ttl_seconds=None,
            monotonic_clock=lambda: clock[0],
        )
        ctx = mgr.start()
        clock[0] = 999_999.0
        mgr.start()  # triggers sweep — but disabled
        # First entry still present even though clock advanced massively
        assert ctx.correlation_id in mgr._active

    def test_stale_entries_evicted_on_next_start(self):
        clock = [1000.0]
        mgr = CorrelationManager(
            clock=FIXED_CLOCK,
            active_ttl_seconds=10.0,
            monotonic_clock=lambda: clock[0],
        )
        old = mgr.start()
        # Advance past TTL — old entry should be evicted on next start
        clock[0] = 1100.0
        new = mgr.start()
        assert old.correlation_id not in mgr._active
        assert new.correlation_id in mgr._active
        # Eviction is implicit; the timestamp map stays in lockstep
        assert old.correlation_id not in mgr._active_inserted_at

    def test_fresh_entries_survive_sweep(self):
        clock = [1000.0]
        mgr = CorrelationManager(
            clock=FIXED_CLOCK,
            active_ttl_seconds=60.0,
            monotonic_clock=lambda: clock[0],
        )
        ctx = mgr.start()
        clock[0] = 1010.0  # 10s elapsed, well under 60s TTL
        mgr.start()
        assert ctx.correlation_id in mgr._active

    def test_explicit_cleanup_stale_returns_eviction_count(self):
        clock = [0.0]
        mgr = CorrelationManager(
            clock=FIXED_CLOCK,
            active_ttl_seconds=5.0,
            monotonic_clock=lambda: clock[0],
        )
        # Start 3 in batch
        for _ in range(3):
            mgr.start()
        clock[0] = 100.0  # all should be stale now
        evicted = mgr.cleanup_stale()
        assert evicted == 3
        assert mgr.active_count == 0

    def test_cleanup_with_no_active_returns_zero(self):
        mgr = CorrelationManager(clock=FIXED_CLOCK)
        assert mgr.cleanup_stale() == 0

    def test_complete_keeps_timestamp_map_in_sync(self):
        """A complete()d entry must also drop from the timestamp map,
        otherwise a TTL sweep would try to evict already-completed IDs."""
        mgr = CorrelationManager(clock=FIXED_CLOCK, active_ttl_seconds=5.0)
        ctx = mgr.start()
        assert ctx.correlation_id in mgr._active_inserted_at
        mgr.complete(ctx.correlation_id)
        assert ctx.correlation_id not in mgr._active_inserted_at

    def test_stale_entries_not_appended_to_completed(self):
        """Crashed requests are dropped, NOT moved to _completed —
        completion is the contract for joining the audit ring."""
        clock = [0.0]
        mgr = CorrelationManager(
            clock=FIXED_CLOCK,
            active_ttl_seconds=1.0,
            monotonic_clock=lambda: clock[0],
        )
        mgr.start()
        clock[0] = 100.0
        mgr.start()  # triggers sweep, evicts the first
        # Only the second entry's complete() should populate _completed
        assert mgr.completed_count == 0
