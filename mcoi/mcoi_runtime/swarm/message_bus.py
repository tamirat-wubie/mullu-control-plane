"""Structured swarm message bus.

Purpose: append and query auditable WHQR-style agent messages.
Governance scope: inspectable inter-agent statements and causal traceability.
Dependencies: swarm contracts.
Invariants: duplicate message identifiers are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import SwarmInvariantViolation, SwarmMessage


@dataclass
class AgentMessageBus:
    """Append-only in-memory message bus."""

    _messages: list[SwarmMessage] = field(default_factory=list)

    def publish(self, message: SwarmMessage) -> None:
        """Publish one unique structured message."""

        if any(existing.message_id == message.message_id for existing in self._messages):
            raise SwarmInvariantViolation(f"duplicate message_id: {message.message_id}")
        self._messages.append(message)

    def for_goal(self, goal_id: str) -> tuple[SwarmMessage, ...]:
        """Return all messages for a goal in insertion order."""

        return tuple(message for message in self._messages if message.goal_id == goal_id)

    @property
    def count(self) -> int:
        """Return message count."""

        return len(self._messages)
