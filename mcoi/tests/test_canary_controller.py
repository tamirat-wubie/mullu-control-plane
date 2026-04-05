"""Tests for Phase 227C — Canary Deployment Controller."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.canary_controller import (
    CanaryController, CanaryDeployment, DeploymentStatus,
)


@pytest.fixture
def controller():
    return CanaryController(health_threshold=90.0)


class TestCanaryController:
    def test_create_canary(self, controller):
        dep = controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=5.0)
        assert dep.canary_traffic_pct == 5.0
        assert dep.stable_traffic_pct == 95.0
        assert dep.status == DeploymentStatus.CANARY

    def test_invalid_traffic_pct(self, controller):
        with pytest.raises(ValueError, match="0-100") as exc_info:
            controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=150.0)
        assert "150.0" not in str(exc_info.value)

    def test_duplicate_active(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        with pytest.raises(ValueError, match="Active canary"):
            controller.create_canary("d2", "v1.0", "v1.2")

    def test_unknown_deployment_reason_is_bounded(self, controller):
        with pytest.raises(ValueError, match="not found") as exc_info:
            controller.promote("ghost")
        assert "ghost" not in str(exc_info.value)

    def test_inactive_deployment_reason_is_bounded(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        for _ in range(3):
            controller.record_health("d1", 95.0)
        controller.promote("d1")
        with pytest.raises(ValueError, match="not active") as exc_info:
            controller.rollback("d1")
        assert "d1" not in str(exc_info.value)
        assert "completed" not in str(exc_info.value).lower()

    def test_increase_traffic(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=5.0)
        dep = controller.increase_traffic("d1", 25.0)
        assert dep.canary_traffic_pct == 25.0

    def test_cannot_decrease_traffic(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=25.0)
        with pytest.raises(ValueError, match="decrease"):
            controller.increase_traffic("d1", 10.0)

    def test_record_health(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        controller.record_health("d1", 95.0)
        controller.record_health("d1", 92.0)
        dep = controller.active_deployment
        assert len(dep.health_checks) == 2

    def test_can_promote(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        # Not enough health checks
        assert not controller.can_promote("d1")
        # Add healthy checks
        for _ in range(3):
            controller.record_health("d1", 95.0)
        assert controller.can_promote("d1")

    def test_cannot_promote_unhealthy(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        for _ in range(3):
            controller.record_health("d1", 50.0)
        assert not controller.can_promote("d1")

    def test_promote(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        for _ in range(3):
            controller.record_health("d1", 95.0)
        dep = controller.promote("d1")
        assert dep.status == DeploymentStatus.COMPLETED
        assert dep.canary_traffic_pct == 100.0
        assert controller.active_deployment is None

    def test_rollback(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=20.0)
        dep = controller.rollback("d1")
        assert dep.status == DeploymentStatus.ROLLED_BACK
        assert dep.canary_traffic_pct == 0.0
        assert controller.active_deployment is None

    def test_route_request_no_canary(self, controller):
        assert controller.route_request() == "stable"

    def test_route_request_with_canary(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=50.0)
        results = {controller.route_request() for _ in range(100)}
        assert "stable" in results or "canary" in results

    def test_to_dict(self, controller):
        dep = controller.create_canary("d1", "v1.0", "v1.1", initial_traffic_pct=10.0)
        d = dep.to_dict()
        assert d["canary_traffic_pct"] == 10.0
        assert d["stable_traffic_pct"] == 90.0

    def test_summary(self, controller):
        controller.create_canary("d1", "v1.0", "v1.1")
        s = controller.summary()
        assert s["total_deployments"] == 1
        assert s["active_deployment"] is not None
