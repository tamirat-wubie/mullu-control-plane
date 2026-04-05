"""Phase 207C — Capability Engine.

Purpose: Manages agent capabilities with runtime discovery, dependency
    resolution, and capability composition for complex tasks.
Governance scope: capability management only.
Dependencies: agent_protocol.
Invariants:
  - Capabilities are typed and validated.
  - Composite capabilities require all sub-capabilities.
  - Capability queries are deterministic.
  - Disabled capabilities are excluded from discovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Describes a capability with metadata."""

    capability_id: str
    name: str
    description: str
    category: str = "general"  # "llm", "tool", "data", "system"
    requires: tuple[str, ...] = ()  # Sub-capability dependencies
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    """Result of matching a capability requirement."""

    capability_id: str
    matched: bool
    agent_ids: tuple[str, ...]
    missing_deps: tuple[str, ...] = ()


class CapabilityEngine:
    """Manages capability registry with composition and discovery."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDescriptor] = {}
        self._agent_capabilities: dict[str, set[str]] = {}  # agent_id -> capability_ids

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Register a capability."""
        if descriptor.capability_id in self._capabilities:
            raise ValueError("capability already registered")
        self._capabilities[descriptor.capability_id] = descriptor

    def assign_to_agent(self, agent_id: str, capability_id: str) -> None:
        """Assign a capability to an agent."""
        if capability_id not in self._capabilities:
            raise ValueError("unknown capability")
        if agent_id not in self._agent_capabilities:
            self._agent_capabilities[agent_id] = set()
        self._agent_capabilities[agent_id].add(capability_id)

    def agent_has(self, agent_id: str, capability_id: str) -> bool:
        """Check if an agent has a specific capability."""
        return capability_id in self._agent_capabilities.get(agent_id, set())

    def find_agents(self, capability_id: str) -> list[str]:
        """Find all agents with a given capability."""
        cap = self._capabilities.get(capability_id)
        if cap is None or not cap.enabled:
            return []
        return sorted(
            aid for aid, caps in self._agent_capabilities.items()
            if capability_id in caps
        )

    def match(self, capability_id: str) -> CapabilityMatch:
        """Match a capability requirement against available agents."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return CapabilityMatch(
                capability_id=capability_id, matched=False,
                agent_ids=(), missing_deps=(capability_id,),
            )

        # Check sub-dependencies
        missing = []
        for dep_id in cap.requires:
            if dep_id not in self._capabilities or not self._capabilities[dep_id].enabled:
                missing.append(dep_id)

        agents = self.find_agents(capability_id)
        return CapabilityMatch(
            capability_id=capability_id,
            matched=len(agents) > 0 and len(missing) == 0,
            agent_ids=tuple(agents),
            missing_deps=tuple(missing),
        )

    def list_capabilities(self, category: str | None = None) -> list[CapabilityDescriptor]:
        """List registered capabilities, optionally filtered by category."""
        caps = sorted(self._capabilities.values(), key=lambda c: c.capability_id)
        if category is not None:
            caps = [c for c in caps if c.category == category]
        return caps

    def agent_capabilities(self, agent_id: str) -> list[CapabilityDescriptor]:
        """Get all capabilities assigned to an agent."""
        cap_ids = self._agent_capabilities.get(agent_id, set())
        return sorted(
            [self._capabilities[cid] for cid in cap_ids if cid in self._capabilities],
            key=lambda c: c.capability_id,
        )

    def disable(self, capability_id: str) -> bool:
        """Disable a capability."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return False
        self._capabilities[capability_id] = CapabilityDescriptor(
            capability_id=cap.capability_id, name=cap.name,
            description=cap.description, category=cap.category,
            requires=cap.requires, enabled=False,
        )
        return True

    @property
    def count(self) -> int:
        return len(self._capabilities)

    def summary(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        for cap in self._capabilities.values():
            by_category[cap.category] = by_category.get(cap.category, 0) + 1
        return {
            "total": self.count,
            "by_category": by_category,
            "agents_with_capabilities": len(self._agent_capabilities),
        }
