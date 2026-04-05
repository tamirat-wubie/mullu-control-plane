"""Tests for Phase 232 — Request Context, Tenant Partitioning, Health v3."""
from __future__ import annotations
import pytest


class TestRequestContext:
    def test_create_context(self):
        from mcoi_runtime.core.request_context import RequestContextFactory
        factory = RequestContextFactory()
        ctx = factory.create("tenant-1")
        assert ctx.tenant_id == "tenant-1"
        assert ctx.correlation_id.startswith("cor_")
        assert ctx.request_id.startswith("req_")

    def test_child_inherits_correlation(self):
        from mcoi_runtime.core.request_context import RequestContextFactory
        factory = RequestContextFactory()
        parent = factory.create("t1")
        child = parent.child(step="downstream")
        assert child.correlation_id == parent.correlation_id
        assert child.parent_id == parent.request_id
        assert child.metadata["step"] == "downstream"

    def test_active_tracking(self):
        from mcoi_runtime.core.request_context import RequestContextFactory
        factory = RequestContextFactory()
        ctx = factory.create("t1")
        assert factory.active_count == 1
        factory.complete(ctx.request_id)
        assert factory.active_count == 0

    def test_to_dict(self):
        from mcoi_runtime.core.request_context import RequestContextFactory
        factory = RequestContextFactory()
        ctx = factory.create("t1")
        d = ctx.to_dict()
        assert "correlation_id" in d
        assert "elapsed_ms" in d

    def test_summary(self):
        from mcoi_runtime.core.request_context import RequestContextFactory
        factory = RequestContextFactory()
        factory.create("t1")
        s = factory.summary()
        assert s["total_created"] == 1


class TestTenantPartition:
    def test_put_and_get(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager()
        mgr.put("t1", "key1", "value1")
        assert mgr.get("t1", "key1") == "value1"

    def test_tenant_isolation(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager()
        mgr.put("t1", "secret", "t1-data")
        mgr.put("t2", "secret", "t2-data")
        assert mgr.get("t1", "secret") == "t1-data"
        assert mgr.get("t2", "secret") == "t2-data"

    def test_cross_tenant_impossible(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager()
        mgr.put("t1", "key", "val")
        assert mgr.get("t2", "key") is None  # t2 has no data

    def test_delete(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager()
        mgr.put("t1", "k", "v")
        assert mgr.delete("t1", "k")
        assert mgr.get("t1", "k") is None

    def test_max_partitions(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager(max_partitions=2)
        mgr.put("t1", "k", "v")
        mgr.put("t2", "k", "v")
        with pytest.raises(ValueError, match="max partitions"):
            mgr.put("t3", "k", "v")

    def test_max_partitions_error_is_bounded(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager(max_partitions=2)
        mgr.put("t1", "k", "v")
        mgr.put("t2", "k", "v")
        with pytest.raises(ValueError, match="max partitions") as excinfo:
            mgr.put("t3", "k", "v")
        assert str(excinfo.value) == "max partitions exceeded"
        assert "2" not in str(excinfo.value)

    def test_summary(self):
        from mcoi_runtime.core.tenant_partition import TenantPartitionManager
        mgr = TenantPartitionManager()
        mgr.put("t1", "a", 1)
        mgr.put("t1", "b", 2)
        s = mgr.summary()
        assert s["total_partitions"] == 1
        assert s["total_records"] == 2


class TestHealthV3:
    def test_all_healthy(self):
        from mcoi_runtime.core.health_v3 import HealthAggregatorV3, ComponentHealth
        h = HealthAggregatorV3()
        h.register("db", lambda: ComponentHealth.HEALTHY)
        h.register("cache", lambda: ComponentHealth.HEALTHY)
        result = h.check_all()
        assert result["overall_score"] == 1.0
        assert result["status"] == "healthy"

    def test_degraded_score(self):
        from mcoi_runtime.core.health_v3 import HealthAggregatorV3, ComponentHealth
        h = HealthAggregatorV3()
        h.register("db", lambda: ComponentHealth.HEALTHY, weight=2.0)
        h.register("cache", lambda: ComponentHealth.UNHEALTHY, weight=1.0)
        result = h.check_all()
        # (1.0*2 + 0.0*1) / 3 = 0.6667
        assert 0.6 < result["overall_score"] < 0.7
        assert result["status"] == "degraded"

    def test_recovery_tracking(self):
        from mcoi_runtime.core.health_v3 import HealthAggregatorV3, ComponentHealth
        h = HealthAggregatorV3(recovery_threshold=3)
        h.register("db", lambda: ComponentHealth.HEALTHY)
        for _ in range(3):
            result = h.check_all()
        assert result["components"][0]["recovered"] is True

    def test_exception_in_check(self):
        from mcoi_runtime.core.health_v3 import HealthAggregatorV3
        def bad_check():
            raise RuntimeError("boom")
        h = HealthAggregatorV3()
        h.register("broken", bad_check)
        result = h.check_all()
        assert result["components"][0]["status"] == "unhealthy"

    def test_weighted_aggregation(self):
        from mcoi_runtime.core.health_v3 import HealthAggregatorV3, ComponentHealth
        h = HealthAggregatorV3()
        h.register("critical", lambda: ComponentHealth.HEALTHY, weight=10.0)
        h.register("optional", lambda: ComponentHealth.UNHEALTHY, weight=1.0)
        result = h.check_all()
        # (1.0*10 + 0.0*1) / 11 ≈ 0.909
        assert result["overall_score"] > 0.9
