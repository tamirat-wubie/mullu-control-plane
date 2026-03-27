"""Phase 231B — Multi-Region Routing Engine.

Purpose: Route requests to optimal region based on latency, availability,
    and failover policies. Supports active-active and active-passive.
Dependencies: None (stdlib only).
Invariants:
  - Healthy regions are preferred.
  - Failover is automatic on health check failure.
  - Routing decisions are auditable.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class RegionStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@unique
class RoutingStrategy(Enum):
    LATENCY = "latency"
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"  # primary then fallback


@dataclass
class Region:
    """A deployment region."""
    name: str
    status: RegionStatus = RegionStatus.HEALTHY
    latency_ms: float = 50.0
    capacity_percent: float = 100.0
    is_primary: bool = False
    requests_routed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "capacity_percent": self.capacity_percent,
            "is_primary": self.is_primary,
            "requests_routed": self.requests_routed,
        }


class RegionRouter:
    """Routes requests to optimal region."""

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.LATENCY):
        self._strategy = strategy
        self._regions: dict[str, Region] = {}
        self._rr_index = 0
        self._total_routes = 0
        self._failovers = 0

    def add_region(self, name: str, latency_ms: float = 50.0,
                   is_primary: bool = False) -> Region:
        region = Region(name=name, latency_ms=latency_ms, is_primary=is_primary)
        self._regions[name] = region
        return region

    def update_health(self, name: str, status: RegionStatus) -> Region | None:
        region = self._regions.get(name)
        if region:
            region.status = status
        return region

    def _healthy_regions(self) -> list[Region]:
        return [r for r in self._regions.values()
                if r.status in (RegionStatus.HEALTHY, RegionStatus.DEGRADED)]

    def route(self) -> Region | None:
        """Select optimal region based on strategy."""
        self._total_routes += 1
        healthy = self._healthy_regions()
        if not healthy:
            return None

        if self._strategy == RoutingStrategy.LATENCY:
            selected = min(healthy, key=lambda r: r.latency_ms)
        elif self._strategy == RoutingStrategy.ROUND_ROBIN:
            self._rr_index = self._rr_index % len(healthy)
            selected = healthy[self._rr_index]
            self._rr_index += 1
        elif self._strategy == RoutingStrategy.FAILOVER:
            primaries = [r for r in healthy if r.is_primary]
            if primaries:
                selected = primaries[0]
            else:
                selected = healthy[0]
                self._failovers += 1
        else:
            selected = healthy[0]

        selected.requests_routed += 1
        return selected

    def summary(self) -> dict[str, Any]:
        return {
            "strategy": self._strategy.value,
            "total_regions": len(self._regions),
            "healthy_regions": len(self._healthy_regions()),
            "total_routes": self._total_routes,
            "failovers": self._failovers,
            "regions": [r.to_dict() for r in self._regions.values()],
        }
