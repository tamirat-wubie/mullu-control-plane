"""Phase 214B — Request Correlation.

Purpose: Trace-ID propagation across all subsystems.
    Every governed request gets a unique correlation ID that flows
    through LLM calls, tool invocations, audit entries, and events.
Governance scope: correlation ID management only.
Dependencies: none (pure ID generation + context).
Invariants:
  - Every request gets exactly one correlation ID.
  - Correlation IDs are globally unique (UUID-based).
  - Child operations inherit parent correlation ID.
  - Correlation IDs appear in all audit/log entries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from contextvars import ContextVar

# Context variable for the current correlation ID
_current_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Context for a correlated request."""

    correlation_id: str
    parent_id: str = ""
    tenant_id: str = ""
    actor_id: str = ""
    endpoint: str = ""
    created_at: str = ""


class CorrelationManager:
    """Manages request correlation IDs."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._active: dict[str, CorrelationContext] = {}
        self._completed: list[CorrelationContext] = []

    def start(
        self,
        *,
        parent_id: str = "",
        tenant_id: str = "",
        actor_id: str = "",
        endpoint: str = "",
    ) -> CorrelationContext:
        """Start a new correlated request."""
        cid = f"cor-{uuid.uuid4().hex[:12]}"
        ctx = CorrelationContext(
            correlation_id=cid,
            parent_id=parent_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            endpoint=endpoint,
            created_at=self._clock(),
        )
        self._active[cid] = ctx
        _current_correlation_id.set(cid)
        return ctx

    def complete(self, correlation_id: str) -> None:
        """Mark a correlated request as complete."""
        ctx = self._active.pop(correlation_id, None)
        if ctx is not None:
            self._completed.append(ctx)

    def get_current(self) -> str:
        """Get the current correlation ID from context."""
        return _current_correlation_id.get("")

    def get_context(self, correlation_id: str) -> CorrelationContext | None:
        """Get context for a correlation ID."""
        return self._active.get(correlation_id)

    def child(self, parent_id: str, **kwargs: Any) -> CorrelationContext:
        """Create a child correlation (for sub-operations)."""
        return self.start(parent_id=parent_id, **kwargs)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    def summary(self) -> dict[str, Any]:
        return {
            "active": self.active_count,
            "completed": self.completed_count,
        }
