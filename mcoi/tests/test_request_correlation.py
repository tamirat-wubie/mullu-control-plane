"""Phase 214B — Request correlation tests."""

import pytest
from mcoi_runtime.core.request_correlation import CorrelationManager

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
