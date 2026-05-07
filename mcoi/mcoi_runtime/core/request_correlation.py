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

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable
from contextvars import ContextVar


# Default cap on the completed-context ring. Sized for hours of fleet
# traffic in a typical deployment; operators tracking longer windows
# scrape via `summary()` and persist externally. Bounded so process
# memory cannot grow without limit on a long-running server.
DEFAULT_MAX_COMPLETED = 10_000

# Default TTL for active correlations. A request that takes longer
# than this without calling complete() is treated as crashed and
# evicted on the next start(). Set to None to disable (legacy
# behavior). Default of 1 hour is generous — well past any sane
# request, but short enough that crashed-request leaks bound to a
# few thousand entries on a high-traffic server.
DEFAULT_ACTIVE_TTL_SECONDS = 3600.0

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

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_completed: int = DEFAULT_MAX_COMPLETED,
        active_ttl_seconds: float | None = DEFAULT_ACTIVE_TTL_SECONDS,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._monotonic = monotonic_clock
        self._active_ttl = active_ttl_seconds
        self._active: dict[str, CorrelationContext] = {}
        # Parallel monotonic-time map — used only for TTL-based eviction
        # of crashed requests. Distinct from CorrelationContext.created_at
        # (string, audit-shaped, from user-supplied clock) because TTL math
        # needs a numeric monotonic source. Stays in lockstep with _active.
        self._active_inserted_at: dict[str, float] = {}
        # Bounded ring — see DEFAULT_MAX_COMPLETED. Old entries evict
        # in O(1) when the cap is hit. Read paths only use len() and
        # iteration, both of which work identically on deque.
        self._completed: deque[CorrelationContext] = deque(maxlen=max_completed)

    def cleanup_stale(self) -> int:
        """Evict active entries older than the configured TTL.

        Called automatically before each start(); operators can also
        invoke explicitly (e.g., from a periodic ops job). When TTL is
        None, this is a no-op.

        Returns the number of stale entries evicted. Stale entries are
        treated as crashed-request leaks and dropped without ever
        making it onto _completed — they ARE incomplete by definition.
        """
        if self._active_ttl is None or not self._active:
            return 0
        cutoff = self._monotonic() - self._active_ttl
        # Snapshot keys so we can mutate the dict during iteration.
        stale = [
            cid for cid, t in self._active_inserted_at.items() if t < cutoff
        ]
        for cid in stale:
            self._active.pop(cid, None)
            self._active_inserted_at.pop(cid, None)
        return len(stale)

    def start(
        self,
        *,
        parent_id: str = "",
        tenant_id: str = "",
        actor_id: str = "",
        endpoint: str = "",
    ) -> CorrelationContext:
        """Start a new correlated request.

        Before allocating, sweeps any active entries whose age exceeds
        the configured TTL. This bounds _active even when callers crash
        before complete() — without this sweep, a high-traffic server
        with even occasional crashes would accumulate stale entries
        without limit.
        """
        # Lazy sweep — amortized over starts. Cheap when no entries
        # are stale (most calls).
        self.cleanup_stale()

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
        self._active_inserted_at[cid] = self._monotonic()
        _current_correlation_id.set(cid)
        # Mirror into substrate metrics so per-request Mfidel path tracking
        # can attribute lookups to this request. v3.13.1 soak telemetry only.
        from mcoi_runtime.substrate.metrics import bind_correlation
        bind_correlation(cid)
        return ctx

    def complete(self, correlation_id: str) -> None:
        """Mark a correlated request as complete."""
        ctx = self._active.pop(correlation_id, None)
        self._active_inserted_at.pop(correlation_id, None)
        if ctx is not None:
            self._completed.append(ctx)
        # Finalize substrate per-request bucket. Returns the path verdict
        # ("legacy_only" | "canonical_only" | "mixed" | "none") which callers
        # can read via REGISTRY.snapshot() at any time.
        from mcoi_runtime.substrate.metrics import REGISTRY, bind_correlation
        REGISTRY.close_request(correlation_id)
        bind_correlation("")

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
