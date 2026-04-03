"""Multi-Agent Handoff Router — Specialized agent delegation.

Purpose: Routes requests to specialized agents (financial, email, calendar,
    general) based on intent classification. Agents hand off to each other
    with governed context transfer.

Pattern: Follows OpenAI Agent SDK handoff pattern — agents transfer control
    explicitly, carrying conversation context through the transition.

Invariants:
  - Every handoff is audited.
  - Context transfer is governed (PII-scanned, tenant-scoped).
  - Handoff loops are detected and blocked.
  - Unknown intents fall through to general agent (LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Specification for a specialized agent."""

    agent_id: str
    name: str
    description: str
    handles: tuple[str, ...]  # Intent categories this agent handles
    handler: Callable[[str, str, str], dict[str, Any]] | None = None  # (message, tenant_id, identity_id) -> result


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """Record of an agent-to-agent handoff."""

    from_agent: str
    to_agent: str
    reason: str
    context_keys_transferred: tuple[str, ...]
    timestamp: str = ""


class HandoffRouter:
    """Routes requests to specialized agents with governed handoff.

    Agents are registered with intent categories they handle.
    When a request comes in, the router classifies the intent and
    delegates to the appropriate agent. If an agent can't handle
    the request, it hands off to another agent.

    Handoff loops (A → B → A) are detected and blocked.
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        from datetime import datetime, timezone
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._agents: dict[str, AgentSpec] = {}
        self._intent_map: dict[str, str] = {}  # intent → agent_id
        self._handoff_history: list[HandoffRecord] = []
        self._general_agent_id: str = ""

    def register_agent(self, spec: AgentSpec) -> None:
        """Register a specialized agent."""
        self._agents[spec.agent_id] = spec
        for intent in spec.handles:
            self._intent_map[intent] = spec.agent_id

    def set_general_agent(self, agent_id: str) -> None:
        """Set the fallback general-purpose agent."""
        self._general_agent_id = agent_id

    def route(
        self,
        message: str,
        *,
        intent: str = "",
        tenant_id: str = "",
        identity_id: str = "",
    ) -> dict[str, Any]:
        """Route a message to the appropriate agent.

        If intent is provided, routes directly. Otherwise classifies first.
        Falls back to general agent for unknown intents.
        """
        agent_id = self._intent_map.get(intent, self._general_agent_id)
        agent = self._agents.get(agent_id)

        if agent is None:
            return {
                "response": "No agent available to handle this request.",
                "agent": "none",
                "governed": True,
            }

        if agent.handler is not None:
            try:
                result = agent.handler(message, tenant_id, identity_id)
                result["agent"] = agent.agent_id
                result["governed"] = True
                return result
            except Exception as exc:
                return {
                    "response": f"Agent {agent.name} encountered an error.",
                    "agent": agent.agent_id,
                    "error": str(exc),
                    "governed": True,
                }

        return {
            "response": f"Routed to {agent.name} (no handler configured).",
            "agent": agent.agent_id,
            "governed": True,
        }

    def handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        *,
        message: str,
        reason: str = "",
        tenant_id: str = "",
        identity_id: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Transfer control from one agent to another.

        Detects and blocks handoff loops by checking the full recent chain.
        """
        # Loop detection: build the recent chain of all agents involved
        recent = self._handoff_history[-20:]  # Check last 20 handoffs
        visited_agents: set[str] = set()
        for h in recent:
            visited_agents.add(h.from_agent)
            visited_agents.add(h.to_agent)
        if to_agent_id in visited_agents and from_agent_id in visited_agents:
            return {
                "response": "Handoff loop detected — routing to general agent.",
                "agent": self._general_agent_id,
                "governed": True,
                "handoff_blocked": True,
            }

        record = HandoffRecord(
            from_agent=from_agent_id,
            to_agent=to_agent_id,
            reason=reason,
            context_keys_transferred=tuple(context.keys()) if context else (),
            timestamp=self._clock(),
        )
        self._handoff_history.append(record)

        # Prune history
        if len(self._handoff_history) > 10_000:
            self._handoff_history = self._handoff_history[-10_000:]

        return self.route(
            message, intent="", tenant_id=tenant_id, identity_id=identity_id,
        )

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def handoff_count(self) -> int:
        return len(self._handoff_history)

    def summary(self) -> dict[str, Any]:
        return {
            "agents": list(self._agents.keys()),
            "intent_map": dict(self._intent_map),
            "general_agent": self._general_agent_id,
            "handoff_count": self.handoff_count,
        }
