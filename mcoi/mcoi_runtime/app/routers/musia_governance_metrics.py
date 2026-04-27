"""
Governance chain observability — v4.17.0.

When the v4.15.0 chain bridge gates writes and the v4.16.0 gate gates
domain runs, operators need visibility into what the chain is doing:
how many invocations passed, how many were rejected, by which guard,
on which surface, for which tenant. Without this, every chain rejection
shows up only in the rejected request's response — invisible at the
fleet level. v4.17.0 closes that.

Counters are aggregate (no PII, no payloads) and recorded on every
chain invocation. The bridge call sites (chain_to_validator,
gate_domain_run) pass the (surface, tenant, allowed, blocking_guard,
exception) tuple to ``record()``; everything else is derived.

Memory: counter dicts are bounded by tenant count × surface × guard
count, all of which are bounded in practice. The rejection ring
buffer is hard-capped at MAX_RECENT_REJECTIONS so a long-running
process cannot OOM on a denial-storm.

Thread safety: RLock around all mutations. Snapshot returns immutable
dicts (deep-copied by record() consumers) so reading is safe without
holding the lock.

The companion router exposes ``/musia/governance/stats`` at admin
scope so operators can scrape from outside the process.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from time import time
from typing import Any


# Surfaces the chain can gate.
SURFACE_WRITE = "write"
SURFACE_DOMAIN_RUN = "domain_run"
_VALID_SURFACES = frozenset({SURFACE_WRITE, SURFACE_DOMAIN_RUN})

# Verdicts the chain can return.
VERDICT_ALLOWED = "allowed"
VERDICT_DENIED = "denied"
VERDICT_EXCEPTION = "exception"
_VALID_VERDICTS = frozenset({VERDICT_ALLOWED, VERDICT_DENIED, VERDICT_EXCEPTION})

# Cap on the rejection-event ring buffer. ~50 is plenty for forensic
# spot-checks; operators wanting full history scrape the metrics into
# a TSDB at intervals.
MAX_RECENT_REJECTIONS = 50


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

    # By (surface, verdict) — surface ∈ {"write","domain_run"}, verdict
    # ∈ {"allowed","denied","exception"}.
    runs_by_surface_verdict: dict[tuple[str, str], int]

    # By (surface, tenant_id) — total runs (any verdict).
    runs_by_surface_tenant: dict[tuple[str, str], int]

    # By blocking_guard — denial-only count of how often each guard was
    # the rejector. Helps tune ordering ("rate_limit denied 80% — move
    # cheaper checks first?") and spot guards that never fire.
    denials_by_guard: dict[str, int]

    # Last MAX_RECENT_REJECTIONS rejection events, oldest first.
    recent_rejections: tuple[RejectionEvent, ...]

    def total_runs(self) -> int:
        return sum(self.runs_by_surface_verdict.values())

    def total_denials(self) -> int:
        return sum(
            v for (_, verdict), v in self.runs_by_surface_verdict.items()
            if verdict == VERDICT_DENIED
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
        }


def _escape_prometheus_label(value: str) -> str:
    """Escape a label value per Prometheus exposition format spec."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_metric_family(
    *,
    name: str,
    help_text: str,
    metric_type: str,
    samples: list[tuple[dict[str, str], float]],
) -> list[str]:
    """Format one metric family as Prometheus text-format lines.

    Each sample is a (labels, value) tuple. Empty samples list still
    emits HELP + TYPE so the metric is discoverable as "exists but
    empty" — useful before the first request lands.
    """
    lines = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} {metric_type}",
    ]
    for labels, value in samples:
        if labels:
            label_pairs = ",".join(
                f'{k}="{_escape_prometheus_label(v)}"'
                for k, v in sorted(labels.items())
            )
            lines.append(f"{name}{{{label_pairs}}} {value}")
        else:
            lines.append(f"{name} {value}")
    return lines


def _snapshot_to_prometheus(
    snap: "GovernanceMetricsSnapshot",
    *,
    prefix: str = "mullu",
) -> str:
    """Build the Prometheus text exposition for a snapshot.

    Module-private helper; callers use ``snap.to_prometheus_text()``.
    Kept separate so both the snapshot's bound method and the HTTP
    endpoint (which may want to inject a different prefix) share one
    implementation.
    """
    chain_runs = f"{prefix}_governance_chain_runs_total"
    chain_runs_tenant = f"{prefix}_governance_chain_runs_by_tenant_total"
    chain_denials_guard = f"{prefix}_governance_chain_denials_by_guard_total"
    chain_recent_rejections = f"{prefix}_governance_chain_recent_rejections"
    chain_total_runs = f"{prefix}_governance_chain_total_runs"
    chain_total_denials = f"{prefix}_governance_chain_total_denials"

    families: list[list[str]] = []

    # By (surface, verdict) — core counters
    families.append(_format_metric_family(
        name=chain_runs,
        help_text="Total chain invocations by surface and verdict.",
        metric_type="counter",
        samples=[
            ({"surface": s, "verdict": v}, n)
            for (s, v), n in sorted(snap.runs_by_surface_verdict.items())
        ],
    ))

    # By (surface, tenant) — high-cardinality; operators may drop
    families.append(_format_metric_family(
        name=chain_runs_tenant,
        help_text=(
            "Total chain invocations by surface and tenant. "
            "Cardinality grows with tenant count; consider dropping or "
            "relabeling at scrape time on large fleets."
        ),
        metric_type="counter",
        samples=[
            ({"surface": s, "tenant": t}, n)
            for (s, t), n in sorted(snap.runs_by_surface_tenant.items())
        ],
    ))

    # By guard — denial counts
    families.append(_format_metric_family(
        name=chain_denials_guard,
        help_text="Total chain denials by blocking guard name.",
        metric_type="counter",
        samples=[
            ({"guard": g}, n)
            for g, n in sorted(snap.denials_by_guard.items())
        ],
    ))

    # Aggregate gauges
    families.append(_format_metric_family(
        name=chain_total_runs,
        help_text="Aggregate count of all chain invocations across surfaces.",
        metric_type="gauge",
        samples=[({}, snap.total_runs())],
    ))
    families.append(_format_metric_family(
        name=chain_total_denials,
        help_text="Aggregate count of chain denials across surfaces.",
        metric_type="gauge",
        samples=[({}, snap.total_denials())],
    ))

    # Ring-buffer length (gauge — bounded by MAX_RECENT_REJECTIONS)
    families.append(_format_metric_family(
        name=chain_recent_rejections,
        help_text=(
            "Number of rejection events currently held in the in-memory "
            "ring buffer (capped at MAX_RECENT_REJECTIONS)."
        ),
        metric_type="gauge",
        samples=[({}, len(snap.recent_rejections))],
    ))

    # Join with blank line between families; trailing newline required
    body = "\n\n".join("\n".join(family) for family in families)
    return body + "\n"


class GovernanceMetricsRegistry:
    """Thread-safe registry. Singleton-style — one per process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._runs_by_surface_verdict: dict[tuple[str, str], int] = {}
        self._runs_by_surface_tenant: dict[tuple[str, str], int] = {}
        self._denials_by_guard: dict[str, int] = {}
        self._recent_rejections: deque[RejectionEvent] = deque(
            maxlen=MAX_RECENT_REJECTIONS,
        )

    def record(
        self,
        *,
        surface: str,
        tenant_id: str,
        allowed: bool,
        blocking_guard: str | None = None,
        reason: str = "",
        exception: bool = False,
        now: float | None = None,
    ) -> None:
        """Record one chain invocation.

        Required: surface (write|domain_run) and tenant_id.
        - allowed: True → verdict=allowed; False + exception=False → denied;
          False + exception=True → verdict=exception.
        - blocking_guard / reason: only consulted on denial. ``"unknown"``
          when the bridge couldn't extract the guard name.
        - now: injectable clock for tests.

        Bad inputs raise ValueError to surface miswiring early; production
        callers should never trip these.
        """
        if surface not in _VALID_SURFACES:
            raise ValueError(f"unknown surface: {surface!r}")
        if exception:
            verdict = VERDICT_EXCEPTION
        elif allowed:
            verdict = VERDICT_ALLOWED
        else:
            verdict = VERDICT_DENIED
        ts = time() if now is None else now

        with self._lock:
            sv_key = (surface, verdict)
            self._runs_by_surface_verdict[sv_key] = (
                self._runs_by_surface_verdict.get(sv_key, 0) + 1
            )
            st_key = (surface, tenant_id)
            self._runs_by_surface_tenant[st_key] = (
                self._runs_by_surface_tenant.get(st_key, 0) + 1
            )
            if verdict == VERDICT_DENIED:
                guard = blocking_guard or "unknown"
                self._denials_by_guard[guard] = (
                    self._denials_by_guard.get(guard, 0) + 1
                )
                self._recent_rejections.append(
                    RejectionEvent(
                        timestamp=ts,
                        surface=surface,
                        tenant_id=tenant_id,
                        blocking_guard=guard,
                        reason=reason,
                    )
                )
            elif verdict == VERDICT_EXCEPTION:
                # Exceptions are treated as a fail-closed denial in the
                # bridge, so they also surface in the rejection ring for
                # forensic visibility — operators want to find chains
                # whose guards crash, not just deny.
                self._recent_rejections.append(
                    RejectionEvent(
                        timestamp=ts,
                        surface=surface,
                        tenant_id=tenant_id,
                        blocking_guard=blocking_guard or "exception",
                        reason=reason,
                    )
                )

    def snapshot(self) -> GovernanceMetricsSnapshot:
        with self._lock:
            return GovernanceMetricsSnapshot(
                runs_by_surface_verdict=dict(self._runs_by_surface_verdict),
                runs_by_surface_tenant=dict(self._runs_by_surface_tenant),
                denials_by_guard=dict(self._denials_by_guard),
                recent_rejections=tuple(self._recent_rejections),
            )

    def reset(self) -> None:
        """Test-only. Restores a fresh state."""
        with self._lock:
            self._runs_by_surface_verdict.clear()
            self._runs_by_surface_tenant.clear()
            self._denials_by_guard.clear()
            self._recent_rejections.clear()


REGISTRY = GovernanceMetricsRegistry()


# ---- HTTP surface ----


from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from mcoi_runtime.app.routers.musia_auth import require_admin


router = APIRouter(prefix="/musia/governance", tags=["musia-governance"])


# Prometheus exposition format content type (v0.0.4)
_PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/stats")
def get_stats(_: str = Depends(require_admin)) -> dict[str, Any]:
    """Snapshot of chain counters and recent rejections.

    Admin scope. The response is JSON-shape-stable: tuple-keyed dicts
    are flattened to ``"<key1>:<key2>"`` strings so clients can read by
    string-key without tuple-aware deserialization.
    """
    return REGISTRY.snapshot().as_dict()


@router.post("/stats/reset", status_code=204)
def reset_stats(_: str = Depends(require_admin)) -> None:
    """Reset counters. For ops use only — surfaces a fresh window
    (e.g., before/after a deployment). Admin scope."""
    REGISTRY.reset()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {_PROMETHEUS_CONTENT_TYPE: {}},
            "description": "Prometheus exposition format (v0.0.4).",
        }
    },
)
def get_prometheus_metrics(
    _: str = Depends(require_admin),
) -> PlainTextResponse:
    """v4.20.0+: Prometheus exposition of governance chain counters.

    Returns the same data as ``/stats`` but in Prometheus text format
    (v0.0.4) so any compatible scraper (Prometheus, Grafana Agent,
    Datadog Agent, OpenTelemetry Collector) can ingest natively.

    Admin scope — same as ``/stats``. The endpoint is deliberately at
    ``/musia/governance/metrics`` (not the customary ``/metrics`` at
    the app root) so deployments running multiple metric surfaces in
    one process can keep them separate. Operators wanting a unified
    ``/metrics`` endpoint can mount a thin aggregator that calls into
    each surface.
    """
    body = REGISTRY.snapshot().to_prometheus_text()
    return PlainTextResponse(content=body, media_type=_PROMETHEUS_CONTENT_TYPE)
