"""Tests for Phase 231B — Multi-Region Routing Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.region_router import (
    RegionRouter, RoutingStrategy, RegionStatus,
)


class TestRegionRouter:
    def test_add_region(self):
        router = RegionRouter()
        r = router.add_region("us-east-1", latency_ms=20.0)
        assert r.name == "us-east-1"
        assert r.status == RegionStatus.HEALTHY

    def test_latency_routing(self):
        router = RegionRouter(RoutingStrategy.LATENCY)
        router.add_region("us-east", latency_ms=50.0)
        router.add_region("eu-west", latency_ms=20.0)
        selected = router.route()
        assert selected is not None
        assert selected.name == "eu-west"

    def test_round_robin(self):
        router = RegionRouter(RoutingStrategy.ROUND_ROBIN)
        router.add_region("a")
        router.add_region("b")
        names = [router.route().name for _ in range(4)]
        assert names == ["a", "b", "a", "b"]

    def test_failover_primary(self):
        router = RegionRouter(RoutingStrategy.FAILOVER)
        router.add_region("primary", is_primary=True)
        router.add_region("secondary")
        selected = router.route()
        assert selected.name == "primary"

    def test_failover_to_secondary(self):
        router = RegionRouter(RoutingStrategy.FAILOVER)
        router.add_region("primary", is_primary=True)
        router.add_region("secondary")
        router.update_health("primary", RegionStatus.UNHEALTHY)
        selected = router.route()
        assert selected.name == "secondary"
        assert router.summary()["failovers"] == 1

    def test_no_healthy_regions(self):
        router = RegionRouter()
        router.add_region("r1")
        router.update_health("r1", RegionStatus.UNHEALTHY)
        assert router.route() is None

    def test_degraded_still_routable(self):
        router = RegionRouter(RoutingStrategy.LATENCY)
        router.add_region("r1", latency_ms=10.0)
        router.update_health("r1", RegionStatus.DEGRADED)
        assert router.route() is not None

    def test_update_nonexistent(self):
        router = RegionRouter()
        assert router.update_health("missing", RegionStatus.HEALTHY) is None

    def test_requests_tracked(self):
        router = RegionRouter(RoutingStrategy.LATENCY)
        router.add_region("r1", latency_ms=10.0)
        router.route()
        router.route()
        assert router.summary()["regions"][0]["requests_routed"] == 2

    def test_summary(self):
        router = RegionRouter()
        router.add_region("r1")
        router.add_region("r2")
        s = router.summary()
        assert s["total_regions"] == 2
        assert s["healthy_regions"] == 2
