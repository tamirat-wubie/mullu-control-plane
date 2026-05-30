"""Frozen data models for governance chain observability."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.app.routers.musia_governance_metrics._constants import (
    VERDICT_DENIED,
)
from mcoi_runtime.app.routers.musia_governance_metrics._prometheus import (
    _snapshot_to_prometheus,
)


@dataclass(frozen=True)
class LatencyHistogram:
    """A simple histogram for chain-evaluation duration in seconds.

    v4.21.0+. Buckets are cumulative ("le=" semantics): bucket i counts
    every observation with duration ≤ ``upper_bounds[i]``. The +Inf
    bucket is the total count.

    Purely additive — never subtracts. Concurrent recording is safe
    when the registry holds the lock during ``observe()``; the snapshot
    is taken under the same lock and is immutable.
    """

    upper_bounds: tuple[float, ...]
    bucket_counts: tuple[int, ...]  # cumulative; same length as upper_bounds
    sum_seconds: float
    count: int

    def p_estimate(self, p: float) -> float | None:
        """Estimate a percentile from the cumulative bucket counts.

        Returns the smallest upper bound whose cumulative count exceeds
        ``p × total``, or None if no observations yet. Coarse — useful
        only at log-scale precision (p99 of 50μs in this histogram is
        reported as "≤50μs", not 47.3μs).

        Operators wanting high-precision percentiles should ingest the
        histogram into Prometheus and use ``histogram_quantile()``.
        """
        if self.count == 0:
            return None
        target = p * self.count
        for bound, cum in zip(self.upper_bounds, self.bucket_counts):
            if cum >= target:
                return bound
        return math.inf  # in the +Inf bucket


@dataclass(frozen=True)
class RejectionEvent:
    """A single chain rejection event — for forensic visibility.

    Holds only what an operator needs to triage: when, where, who, why.
    No payload, no construct ids, no auth secrets. Reason is the
    chain-formatted ``blocked_by:<guard> (<reason>)`` string.
    """

    timestamp: float
    surface: str
    tenant_id: str
    blocking_guard: str
    reason: str


@dataclass(frozen=True)
class GovernanceMetricsSnapshot:
    """Read-only point-in-time view of the governance chain counters."""

    runs_by_surface_verdict: dict[tuple[str, str], int]
    runs_by_surface_tenant: dict[tuple[str, str], int]
    denials_by_guard: dict[str, int]
    recent_rejections: tuple[RejectionEvent, ...]
    latency_by_surface: dict[str, LatencyHistogram] = field(default_factory=dict)
    runs_by_surface_tenant_verdict: dict[tuple[str, str, str], int] = field(
        default_factory=dict
    )
    # Φ_gov overall-verdict counters (USCL v3.3 / A1). Separate from the chain
    # counters above; never included in total_runs/total_denials.
    phi_gov_decisions: dict[str, int] = field(default_factory=dict)
    phi_gov_denials_by_category: dict[str, int] = field(default_factory=dict)
    # Φ_gov cascade coverage: "ran"|"skipped" -> count. Surfaces whether the
    # per-type invariant validators (Phase 3) actually cover each write.
    phi_gov_cascade_coverage: dict[str, int] = field(default_factory=dict)

    def total_runs(self) -> int:
        return sum(self.runs_by_surface_verdict.values())

    def total_denials(self) -> int:
        return sum(
            v for (_, verdict), v in self.runs_by_surface_verdict.items()
            if verdict == VERDICT_DENIED
        )

    def for_tenant(self, tenant_id: str) -> "GovernanceMetricsSnapshot":
        """v4.24.0+: return a redacted snapshot scoped to one tenant.

        The per-tenant view exposes only what the named tenant generated:
        - ``runs_by_surface_tenant`` filtered to that tenant
        - ``runs_by_surface_verdict`` reconstructed from the 3-way index
          (this tenant's verdict breakdown only)
        - ``denials_by_guard`` reconstructed from the tenant's rejection events
        - ``recent_rejections`` filtered to that tenant
        - ``runs_by_surface_tenant_verdict`` filtered to that tenant

        Cross-tenant aggregates are dropped:
        - ``latency_by_surface`` — platform-wide; dropped to avoid
          inferring other tenants' load from aggregate counts and
          summed durations

        Empty tenant_id returns an empty snapshot (no leak via the
        always-true filter on '').
        """
        if not tenant_id:
            return GovernanceMetricsSnapshot(
                runs_by_surface_verdict={},
                runs_by_surface_tenant={},
                denials_by_guard={},
                recent_rejections=(),
                latency_by_surface={},
                runs_by_surface_tenant_verdict={},
            )
        tenant_3way = {
            (s, t, v): n
            for (s, t, v), n in self.runs_by_surface_tenant_verdict.items()
            if t == tenant_id
        }
        tenant_runs_by_verdict: dict[tuple[str, str], int] = {}
        for (s, _t, v), n in tenant_3way.items():
            tenant_runs_by_verdict[(s, v)] = (
                tenant_runs_by_verdict.get((s, v), 0) + n
            )
        tenant_runs_by_st = {
            (s, t): n
            for (s, t), n in self.runs_by_surface_tenant.items()
            if t == tenant_id
        }
        tenant_rejections = tuple(
            ev for ev in self.recent_rejections if ev.tenant_id == tenant_id
        )
        tenant_denials: dict[str, int] = {}
        for ev in tenant_rejections:
            tenant_denials[ev.blocking_guard] = (
                tenant_denials.get(ev.blocking_guard, 0) + 1
            )
        return GovernanceMetricsSnapshot(
            runs_by_surface_verdict=tenant_runs_by_verdict,
            runs_by_surface_tenant=tenant_runs_by_st,
            denials_by_guard=tenant_denials,
            recent_rejections=tenant_rejections,
            latency_by_surface={},
            runs_by_surface_tenant_verdict=tenant_3way,
        )

    def to_prometheus_text(self, *, prefix: str = "mullu") -> str:
        """Emit Prometheus exposition format (v0.0.4) for this snapshot.

        v4.20.0+. Counters use the ``_total`` suffix per Prometheus
        naming convention. Cardinality bounds:

        - ``runs_by_surface_verdict`` → 2 surfaces × 3 verdicts = 6 series
        - ``denials_by_guard`` → bounded by chain config (typically 5–15 guards)
        - ``runs_by_surface_tenant`` → 2 × tenant_count; **operators with
          large fleets should drop this metric in their scrape config or
          use Prometheus relabel rules to bound cardinality**

        Returns a string ending in ``\\n``, ready to return as
        ``Content-Type: text/plain; version=0.0.4; charset=utf-8``.

        Label values are escaped per the Prometheus spec:
        ``\\`` → ``\\\\``, ``"`` → ``\\"``, newline → ``\\n``.
        """
        return _snapshot_to_prometheus(self, prefix=prefix)

    def as_dict(self) -> dict[str, Any]:
        """JSON-serializable view. Tuple keys become ``"surface:verdict"`` etc."""
        return {
            "runs_by_surface_verdict": {
                f"{s}:{v}": n
                for (s, v), n in self.runs_by_surface_verdict.items()
            },
            "runs_by_surface_tenant": {
                f"{s}:{t}": n
                for (s, t), n in self.runs_by_surface_tenant.items()
            },
            "denials_by_guard": dict(self.denials_by_guard),
            "recent_rejections": [
                {
                    "timestamp": ev.timestamp,
                    "surface": ev.surface,
                    "tenant_id": ev.tenant_id,
                    "blocking_guard": ev.blocking_guard,
                    "reason": ev.reason,
                }
                for ev in self.recent_rejections
            ],
            "total_runs": self.total_runs(),
            "total_denials": self.total_denials(),
            "phi_gov_decisions": dict(self.phi_gov_decisions),
            "phi_gov_denials_by_category": dict(self.phi_gov_denials_by_category),
            "phi_gov_cascade_coverage": dict(self.phi_gov_cascade_coverage),
            "latency_by_surface": {
                surface: {
                    "upper_bounds": list(hist.upper_bounds),
                    "bucket_counts": list(hist.bucket_counts),
                    "sum_seconds": hist.sum_seconds,
                    "count": hist.count,
                }
                for surface, hist in self.latency_by_surface.items()
            },
        }
