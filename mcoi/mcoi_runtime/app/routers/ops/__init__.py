"""Operational / infrastructure endpoints extracted from server.py.

Covers metrics, rate-limiting, configuration management, monitoring,
deployment readiness, feature flags, dependency graphs, and all other
ops-facing routes.

Originally a single 738-line module with 40 endpoints across ~30
micro-sections. Split into a `ops/` subpackage clustering by genuine
concern, with the small read-only "*_summary" endpoints aggregated
into ``summaries.py`` rather than spawning 20 single-endpoint files:

- ``config``: get/history/update/rollback/watcher/drift (6)
- ``snapshots``: system snapshot, list, create (3)
- ``coordination``: checkpoint, restore (2)
- ``metrics``: governance metrics, Prometheus, Grafana dashboard (3)
- ``release``: api version, release info, latest release (3)
- ``rate_limit``: rate limiter status, per-client info (2)
- ``feature_flags``: list flags, check flag (2)
- ``dependencies``: subsystem graph, impact analysis (2)
- ``diagnostics``: benchmarks, import analysis, proof bridge (3)
- ``summaries``: 24 small read-only ops summaries / dashboards / lists

External callers only import ``router``; preserved via the aggregation below.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    config,
    coordination,
    dependencies,
    diagnostics,
    feature_flags,
    metrics,
    rate_limit,
    release,
    snapshots,
    summaries,
)

router = APIRouter()

for _sub in (
    config,
    snapshots,
    coordination,
    metrics,
    release,
    rate_limit,
    feature_flags,
    dependencies,
    diagnostics,
    summaries,
):
    router.include_router(_sub.router)

__all__ = ["router"]
