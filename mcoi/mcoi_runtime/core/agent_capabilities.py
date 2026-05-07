"""Agent Capability Registry — What each agent can do.

Purpose: Declares and tracks the capabilities of each agent so the
    platform can route tasks to the right agent, enforce capability
    gates, and provide discovery for multi-agent coordination.
Governance scope: capability declaration and query.
Dependencies: none (pure data + threading).
Invariants:
  - Capabilities are tenant-scoped (no cross-tenant leakage).
  - Each agent has a declared capability set (not inferred).
  - Capability queries are bounded and thread-safe.
  - Agents cannot claim capabilities without registration.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class AgentCapability:
    """A single declared capability of an agent."""

    name: str
    description: str = ""
    version: str = "1.0"
    requires_approval: bool = False
    max_concurrent: int = 0  # 0 = unlimited
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """An agent's registered profile with capabilities."""

    agent_id: str
    tenant_id: str
    name: str
    capabilities: frozenset[str]  # capability names
    enabled: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_capability(self, name: str) -> bool:
        return name in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "capabilities": sorted(self.capabilities),
            "enabled": self.enabled,
        }


class AgentCapabilityRegistry:
    """Registry of agent capabilities for task routing and discovery.

    Usage:
        registry = AgentCapabilityRegistry()

        # Register capabilities
        registry.register_capability(AgentCapability(
            name="financial_analysis", description="Analyze financial data",
        ))

        # Register an agent with capabilities
        registry.register_agent(AgentProfile(
            agent_id="agent-1", tenant_id="t1", name="Finance Bot",
            capabilities=frozenset({"financial_analysis", "report_generation"}),
        ))

        # Find agents for a task
        agents = registry.find_agents_with_capability("financial_analysis", "t1")
    """

    MAX_CAPABILITIES = 1000
    MAX_AGENTS_PER_TENANT = 500

    def __init__(self) -> None:
        self._capabilities: dict[str, AgentCapability] = {}
        self._agents: dict[str, AgentProfile] = {}  # agent_id → profile
        self._lock = threading.Lock()

    def register_capability(self, capability: AgentCapability) -> None:
        """Register a capability definition."""
        with self._lock:
            if len(self._capabilities) >= self.MAX_CAPABILITIES:
                raise ValueError("capability registry is full")
            self._capabilities[capability.name] = capability

    def register_agent(self, profile: AgentProfile) -> None:
        """Register an agent with its capabilities."""
        with self._lock:
            # Validate capabilities exist
            unknown = profile.capabilities - set(self._capabilities.keys())
            if unknown:
                raise ValueError(f"unknown capabilities: {unknown}")

            # Tenant capacity check
            tenant_count = sum(
                1 for a in self._agents.values()
                if a.tenant_id == profile.tenant_id
            )
            if tenant_count >= self.MAX_AGENTS_PER_TENANT:
                raise ValueError("tenant agent limit reached")

            self._agents[profile.agent_id] = profile

    def unregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        return self._agents.get(agent_id)

    def find_agents_with_capability(
        self,
        capability_name: str,
        tenant_id: str = "",
        *,
        enabled_only: bool = True,
    ) -> list[AgentProfile]:
        """Find agents that have a specific capability."""
        with self._lock:
            results = []
            for agent in self._agents.values():
                if tenant_id and agent.tenant_id != tenant_id:
                    continue
                if enabled_only and not agent.enabled:
                    continue
                if capability_name in agent.capabilities:
                    results.append(agent)
            return results

    def find_agent_for_task(
        self,
        required_capabilities: frozenset[str],
        tenant_id: str,
    ) -> AgentProfile | None:
        """Find the best agent that has ALL required capabilities."""
        with self._lock:
            for agent in self._agents.values():
                if agent.tenant_id != tenant_id:
                    continue
                if not agent.enabled:
                    continue
                if required_capabilities.issubset(agent.capabilities):
                    return agent
            return None

    def list_capabilities(self) -> list[AgentCapability]:
        with self._lock:
            return list(self._capabilities.values())

    def list_agents(self, tenant_id: str = "") -> list[AgentProfile]:
        with self._lock:
            agents = list(self._agents.values())
            if tenant_id:
                agents = [a for a in agents if a.tenant_id == tenant_id]
            return agents

    def disable_agent(self, agent_id: str) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            # Rebuild with enabled=False (frozen dataclass)
            self._agents[agent_id] = AgentProfile(
                agent_id=agent.agent_id, tenant_id=agent.tenant_id,
                name=agent.name, capabilities=agent.capabilities,
                enabled=False, description=agent.description,
                metadata=agent.metadata,
            )
            return True

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            enabled = sum(1 for a in self._agents.values() if a.enabled)
            return {
                "capabilities": len(self._capabilities),
                "agents": len(self._agents),
                "enabled_agents": enabled,
            }
