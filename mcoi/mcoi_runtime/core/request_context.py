"""Phase 232A — Request Context Propagation.

Purpose: Propagate correlation IDs, tenant context, and trace metadata
    through the entire request lifecycle without threading globals.
Dependencies: None (stdlib only).
Invariants:
  - Every request gets a unique correlation ID.
  - Context is immutable once created.
  - Child contexts inherit parent correlation.
  - Context is never shared between requests.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RequestContext:
    """Immutable request context propagated through the call chain."""
    correlation_id: str
    tenant_id: str
    request_id: str
    parent_id: str = ""
    trace_id: str = ""
    started_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def child(self, **extra_metadata: Any) -> RequestContext:
        """Create a child context inheriting correlation."""
        merged = {**self.metadata, **extra_metadata}
        return RequestContext(
            correlation_id=self.correlation_id,
            tenant_id=self.tenant_id,
            request_id=f"req_{secrets.token_hex(6)}",
            parent_id=self.request_id,
            trace_id=self.trace_id or self.correlation_id,
            metadata=merged,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "elapsed_ms": round((time.time() - self.started_at) * 1000, 2),
        }


class RequestContextFactory:
    """Creates and tracks request contexts."""

    def __init__(self):
        self._total_created = 0
        self._active: dict[str, RequestContext] = {}

    def create(self, tenant_id: str, **metadata: Any) -> RequestContext:
        ctx = RequestContext(
            correlation_id=f"cor_{secrets.token_hex(8)}",
            tenant_id=tenant_id,
            request_id=f"req_{secrets.token_hex(6)}",
            trace_id=f"trace_{secrets.token_hex(8)}",
            metadata=metadata,
        )
        self._active[ctx.request_id] = ctx
        self._total_created += 1
        return ctx

    def complete(self, request_id: str) -> RequestContext | None:
        return self._active.pop(request_id, None)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def summary(self) -> dict[str, Any]:
        return {
            "total_created": self._total_created,
            "active": self.active_count,
        }
