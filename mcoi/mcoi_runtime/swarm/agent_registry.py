"""Agent registry for governed swarm work.

Purpose: select specialist agents by tenant, role, and bounded capabilities.
Governance scope: no anonymous worker, no tenant crossing, no forbidden
capability delegation.
Dependencies: swarm contracts.
Invariants: selected agents must satisfy every required task capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import AgentIdentity, SwarmInvariantViolation, SwarmTask


@dataclass
class AgentRegistry:
    """In-memory specialist identity registry."""

    _agents: dict[str, AgentIdentity] = field(default_factory=dict)

    def register(self, identity: AgentIdentity) -> None:
        """Register one unique governed agent identity."""

        if identity.agent_id in self._agents:
            raise SwarmInvariantViolation(f"duplicate agent_id: {identity.agent_id}")
        self._agents[identity.agent_id] = identity

    def get(self, agent_id: str) -> AgentIdentity:
        """Return an agent identity or raise an explicit invariant error."""

        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise SwarmInvariantViolation(f"unknown agent_id: {agent_id}") from exc

    def select(self, task: SwarmTask) -> AgentIdentity:
        """Select the first deterministic agent that can satisfy the task."""

        for identity in sorted(self._agents.values(), key=lambda item: item.agent_id):
            if identity.tenant_id != task.tenant_id:
                continue
            if identity.role != task.required_role:
                continue
            if identity.can_perform(task.required_capabilities):
                return identity
        raise SwarmInvariantViolation(f"no governed agent can satisfy task: {task.task_id}")

    @property
    def count(self) -> int:
        """Return registered identity count."""

        return len(self._agents)
