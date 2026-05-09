"""
Governance chain observability — v4.17.0.

When the v4.15.0 chain bridge gates writes and the v4.16.0 gate gates
domain runs, operators need visibility into what the chain is doing:
how many invocations passed, how many were rejected, by which guard,
on which surface, for which tenant. Without this, every chain rejection
shows up only in the rejected request's response — invisible at the
fleet level. v4.17.0 closes that.

Originally a single 784-line module. Split into:
- ``_constants``: surface/verdict/bucket constants
- ``_models``: ``LatencyHistogram``, ``RejectionEvent``, ``GovernanceMetricsSnapshot``
- ``_prometheus``: text-exposition formatting helpers
- ``_registry``: ``GovernanceMetricsRegistry`` + ``REGISTRY`` singleton
- ``_routes``: FastAPI ``router`` with /stats, /metrics, /stats/tenant, /metrics/tenant

Public import surface is preserved. Existing
``from mcoi_runtime.app.routers.musia_governance_metrics import REGISTRY, ...``
continues to work via the re-exports below.
"""
from __future__ import annotations

from mcoi_runtime.app.routers.musia_governance_metrics._constants import (
    DEFAULT_LATENCY_BUCKETS_SECONDS,
    MAX_RECENT_REJECTIONS,
    SURFACE_DOMAIN_RUN,
    SURFACE_WRITE,
    VERDICT_ALLOWED,
    VERDICT_DENIED,
    VERDICT_EXCEPTION,
)
from mcoi_runtime.app.routers.musia_governance_metrics._models import (
    GovernanceMetricsSnapshot,
    LatencyHistogram,
    RejectionEvent,
)
from mcoi_runtime.app.routers.musia_governance_metrics._registry import (
    REGISTRY,
    GovernanceMetricsRegistry,
)
from mcoi_runtime.app.routers.musia_governance_metrics._routes import router

__all__ = [
    "DEFAULT_LATENCY_BUCKETS_SECONDS",
    "GovernanceMetricsRegistry",
    "GovernanceMetricsSnapshot",
    "LatencyHistogram",
    "MAX_RECENT_REJECTIONS",
    "REGISTRY",
    "RejectionEvent",
    "SURFACE_DOMAIN_RUN",
    "SURFACE_WRITE",
    "VERDICT_ALLOWED",
    "VERDICT_DENIED",
    "VERDICT_EXCEPTION",
    "router",
]
