"""Tests for Phase 228B — Request Deduplication Pipeline."""
from __future__ import annotations
import time
import pytest
from mcoi_runtime.core.request_dedup import RequestDeduplicator


class TestRequestDeduplicator:
    def test_first_request_not_duplicate(self):
        dedup = RequestDeduplicator()
        result = dedup.check({"action": "create", "name": "test"})
        assert not result.is_duplicate
        assert result.request_hash

    def test_duplicate_detected(self):
        dedup = RequestDeduplicator()
        data = {"action": "create", "name": "test"}
        r1 = dedup.check(data)
        r2 = dedup.check(data)
        assert not r1.is_duplicate
        assert r2.is_duplicate
        assert r2.original_timestamp is not None

    def test_different_requests_not_duplicate(self):
        dedup = RequestDeduplicator()
        r1 = dedup.check({"action": "create"})
        r2 = dedup.check({"action": "delete"})
        assert not r1.is_duplicate
        assert not r2.is_duplicate

    def test_tenant_isolation(self):
        dedup = RequestDeduplicator()
        data = {"action": "create"}
        r1 = dedup.check(data, tenant_id="t1")
        r2 = dedup.check(data, tenant_id="t2")
        assert not r1.is_duplicate
        assert not r2.is_duplicate  # different tenant

    def test_same_tenant_duplicate(self):
        dedup = RequestDeduplicator()
        data = {"action": "create"}
        dedup.check(data, tenant_id="t1")
        r2 = dedup.check(data, tenant_id="t1")
        assert r2.is_duplicate

    def test_window_expiry(self):
        dedup = RequestDeduplicator(window_seconds=0.01)
        data = {"action": "create"}
        dedup.check(data)
        time.sleep(0.02)
        r2 = dedup.check(data)
        assert not r2.is_duplicate  # expired

    def test_eviction_when_full(self):
        dedup = RequestDeduplicator(max_entries=2)
        dedup.check({"a": 1})
        dedup.check({"b": 2})
        dedup.check({"c": 3})
        assert dedup.tracked_count == 2

    def test_duplicate_rate(self):
        dedup = RequestDeduplicator()
        dedup.check({"a": 1})
        dedup.check({"a": 1})
        assert dedup.duplicate_rate == 0.5

    def test_tenant_stats(self):
        dedup = RequestDeduplicator()
        dedup.check({"a": 1}, tenant_id="t1")
        dedup.check({"b": 2}, tenant_id="t1")
        stats = dedup.tenant_stats("t1")
        assert stats["tracked_requests"] == 2

    def test_summary(self):
        dedup = RequestDeduplicator(window_seconds=60.0)
        dedup.check({"a": 1})
        s = dedup.summary()
        assert s["total_checked"] == 1
        assert s["window_seconds"] == 60.0
