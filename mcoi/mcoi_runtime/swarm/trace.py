"""Swarm trace collector.

Purpose: record append-only causal events for governed swarm runs.
Governance scope: CDCV and UWMA witness records.
Dependencies: swarm contracts.
Invariants: trace identifiers are unique and every event names its cause.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import SwarmInvariantViolation, SwarmTraceEntry


@dataclass
class SwarmTrace:
    """Append-only trace store."""

    _entries: list[SwarmTraceEntry] = field(default_factory=list)
    _counter: int = 0

    def append(self, *, goal_id: str, event_type: str, actor_id: str, caused_by: str, summary: str) -> SwarmTraceEntry:
        """Append one causal trace entry."""

        self._counter += 1
        entry = SwarmTraceEntry(
            trace_id=f"trace_{self._counter:06d}",
            goal_id=goal_id,
            event_type=event_type,
            actor_id=actor_id,
            caused_by=caused_by,
            summary=summary,
        )
        if any(existing.trace_id == entry.trace_id for existing in self._entries):
            raise SwarmInvariantViolation(f"duplicate trace_id: {entry.trace_id}")
        self._entries.append(entry)
        return entry

    def for_goal(self, goal_id: str) -> tuple[SwarmTraceEntry, ...]:
        """Return trace entries for a goal."""

        return tuple(entry for entry in self._entries if entry.goal_id == goal_id)
