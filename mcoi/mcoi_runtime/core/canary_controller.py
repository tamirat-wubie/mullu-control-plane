"""Phase 227C — Canary Deployment Controller.

Purpose: Manage canary deployments with traffic splitting, promotion,
    and rollback based on health metrics.
Dependencies: None (stdlib only).
Invariants:
  - Traffic split percentages sum to 100.
  - Rollback is immediate.
  - Promotion requires health threshold.
  - All deployment actions are auditable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class DeploymentStatus(Enum):
    ACTIVE = "active"
    CANARY = "canary"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentVersion:
    """A deployment version with traffic weight."""
    version: str
    traffic_pct: float
    status: DeploymentStatus
    deployed_at: float
    health_score: float = 100.0


@dataclass
class CanaryDeployment:
    """Tracks a canary deployment lifecycle."""
    deployment_id: str
    stable_version: str
    canary_version: str
    canary_traffic_pct: float
    status: DeploymentStatus = DeploymentStatus.CANARY
    created_at: float = field(default_factory=time.time)
    health_checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def stable_traffic_pct(self) -> float:
        return 100.0 - self.canary_traffic_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "stable_version": self.stable_version,
            "canary_version": self.canary_version,
            "canary_traffic_pct": self.canary_traffic_pct,
            "stable_traffic_pct": self.stable_traffic_pct,
            "status": self.status.value,
            "health_checks": len(self.health_checks),
        }


class CanaryController:
    """Manages canary deployments with traffic splitting and health gating."""

    def __init__(self, health_threshold: float = 90.0,
                 clock: Callable[[], str] | None = None):
        self._health_threshold = health_threshold
        self._clock = clock
        self._deployments: dict[str, CanaryDeployment] = {}
        self._active_deployment: CanaryDeployment | None = None
        self._history: list[CanaryDeployment] = []

    def create_canary(self, deployment_id: str, stable_version: str,
                      canary_version: str, initial_traffic_pct: float = 5.0) -> CanaryDeployment:
        if initial_traffic_pct < 0 or initial_traffic_pct > 100:
            raise ValueError(f"Traffic percentage must be 0-100: {initial_traffic_pct}")
        if self._active_deployment:
            raise ValueError("Active canary deployment already exists")

        deployment = CanaryDeployment(
            deployment_id=deployment_id,
            stable_version=stable_version,
            canary_version=canary_version,
            canary_traffic_pct=initial_traffic_pct,
        )
        self._deployments[deployment_id] = deployment
        self._active_deployment = deployment
        return deployment

    def increase_traffic(self, deployment_id: str, new_pct: float) -> CanaryDeployment:
        dep = self._get_active(deployment_id)
        if new_pct < dep.canary_traffic_pct:
            raise ValueError("Cannot decrease traffic (use rollback instead)")
        if new_pct > 100:
            raise ValueError("Traffic cannot exceed 100%")
        dep.canary_traffic_pct = new_pct
        return dep

    def record_health(self, deployment_id: str, health_score: float) -> None:
        dep = self._get_active(deployment_id)
        dep.health_checks.append({
            "score": health_score,
            "timestamp": time.time(),
        })

    def can_promote(self, deployment_id: str) -> bool:
        dep = self._get_active(deployment_id)
        if not dep.health_checks:
            return False
        recent = dep.health_checks[-3:] if len(dep.health_checks) >= 3 else dep.health_checks
        avg = sum(h["score"] for h in recent) / len(recent)
        return avg >= self._health_threshold

    def promote(self, deployment_id: str) -> CanaryDeployment:
        dep = self._get_active(deployment_id)
        if not self.can_promote(deployment_id):
            raise ValueError("Health threshold not met for promotion")
        dep.status = DeploymentStatus.COMPLETED
        dep.canary_traffic_pct = 100.0
        self._active_deployment = None
        self._history.append(dep)
        return dep

    def rollback(self, deployment_id: str) -> CanaryDeployment:
        dep = self._get_active(deployment_id)
        dep.status = DeploymentStatus.ROLLED_BACK
        dep.canary_traffic_pct = 0.0
        self._active_deployment = None
        self._history.append(dep)
        return dep

    def route_request(self) -> str:
        """Return which version should handle the next request."""
        if not self._active_deployment:
            return "stable"
        import random
        if random.random() * 100 < self._active_deployment.canary_traffic_pct:
            return "canary"
        return "stable"

    def _get_active(self, deployment_id: str) -> CanaryDeployment:
        dep = self._deployments.get(deployment_id)
        if not dep:
            raise ValueError(f"Deployment not found: {deployment_id}")
        if dep.status not in (DeploymentStatus.CANARY, DeploymentStatus.PROMOTING):
            raise ValueError(f"Deployment not active: {dep.status.value}")
        return dep

    @property
    def active_deployment(self) -> CanaryDeployment | None:
        return self._active_deployment

    def summary(self) -> dict[str, Any]:
        return {
            "total_deployments": len(self._deployments),
            "active_deployment": self._active_deployment.to_dict() if self._active_deployment else None,
            "history_count": len(self._history),
            "health_threshold": self._health_threshold,
        }
