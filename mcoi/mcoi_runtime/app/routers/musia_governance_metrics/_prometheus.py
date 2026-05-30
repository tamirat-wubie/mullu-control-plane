"""Prometheus exposition-format helpers for governance metrics.

Module-private formatters used by ``GovernanceMetricsSnapshot
.to_prometheus_text()``. Type hints reference ``LatencyHistogram`` and
``GovernanceMetricsSnapshot`` as forward strings to avoid an import
cycle with ``_models``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcoi_runtime.app.routers.musia_governance_metrics._models import (
        GovernanceMetricsSnapshot,
        LatencyHistogram,
    )


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

    # Φ_gov overall-verdict families (USCL v3.3 / A1). Separate from the chain
    # families above — these count the overall Φ_gov decision per construct
    # write (Φ_agent + cascade + external), including the A1 escalation/route
    # signals, which the chain counters never see.
    families.append(_format_metric_family(
        name=f"{prefix}_phi_gov_decisions_total",
        help_text="Overall Phi_gov verdicts for construct writes, by verdict.",
        metric_type="counter",
        samples=[
            ({"verdict": v}, n)
            for v, n in sorted(snap.phi_gov_decisions.items())
        ],
    ))
    families.append(_format_metric_family(
        name=f"{prefix}_phi_gov_denials_total",
        help_text="Phi_gov write denials by normalised reason category.",
        metric_type="counter",
        samples=[
            ({"category": c}, n)
            for c, n in sorted(snap.phi_gov_denials_by_category.items())
        ],
    ))
    families.append(_format_metric_family(
        name=f"{prefix}_phi_gov_cascade_coverage_total",
        help_text=(
            "Phi_gov writes by whether the dependency cascade (per-type "
            "invariant validators) ran or was skipped. A high skipped ratio "
            "means validators are not covering the write path."
        ),
        metric_type="counter",
        samples=[
            ({"outcome": o}, n)
            for o, n in sorted(snap.phi_gov_cascade_coverage.items())
        ],
    ))

    # Latency histograms by surface (v4.21.0+).
    # Prometheus convention: <metric_base>_bucket{le="<upper>"} for
    # cumulative bucket counts, plus _sum and _count. The +Inf bucket
    # is required and equals _count.
    chain_duration_base = f"{prefix}_governance_chain_duration_seconds"
    if snap.latency_by_surface:
        families.append(
            _format_histogram_family(
                metric_base=chain_duration_base,
                help_text=(
                    "Chain evaluation duration in seconds, by surface. "
                    "Buckets are cumulative ('le=' semantics). The +Inf "
                    "bucket equals the total count."
                ),
                histograms_by_label=[
                    ({"surface": surface}, snap.latency_by_surface[surface])
                    for surface in sorted(snap.latency_by_surface.keys())
                ],
            )
        )
    else:
        # Empty-state: emit HELP + TYPE so scrapers register the family
        families.append([
            f"# HELP {chain_duration_base} Chain evaluation duration in "
            f"seconds, by surface. Buckets are cumulative.",
            f"# TYPE {chain_duration_base} histogram",
        ])

    # Join with blank line between families; trailing newline required
    body = "\n\n".join("\n".join(family) for family in families)
    return body + "\n"


def _format_histogram_family(
    *,
    metric_base: str,
    help_text: str,
    histograms_by_label: list[tuple[dict[str, str], "LatencyHistogram"]],
) -> list[str]:
    """Format a histogram family in Prometheus text format.

    Each histogram series emits, for one (label_set, histogram) pair:
        - one ``<base>_bucket{le="<upper>", ...}`` line per bucket
        - one ``<base>_bucket{le="+Inf", ...}`` line (= count)
        - one ``<base>_sum{...}`` line
        - one ``<base>_count{...}`` line
    """
    lines = [
        f"# HELP {metric_base} {help_text}",
        f"# TYPE {metric_base} histogram",
    ]
    for labels, hist in histograms_by_label:
        # Bucket lines (with le label)
        for ub, count in zip(hist.upper_bounds, hist.bucket_counts):
            le_labels = dict(labels)
            le_labels["le"] = _format_le(ub)
            label_str = ",".join(
                f'{k}="{_escape_prometheus_label(v)}"'
                for k, v in sorted(le_labels.items())
            )
            lines.append(f"{metric_base}_bucket{{{label_str}}} {count}")
        # +Inf bucket — required
        inf_labels = dict(labels)
        inf_labels["le"] = "+Inf"
        label_str = ",".join(
            f'{k}="{_escape_prometheus_label(v)}"'
            for k, v in sorted(inf_labels.items())
        )
        lines.append(f"{metric_base}_bucket{{{label_str}}} {hist.count}")
        # _sum and _count
        if labels:
            label_str = ",".join(
                f'{k}="{_escape_prometheus_label(v)}"'
                for k, v in sorted(labels.items())
            )
            lines.append(f"{metric_base}_sum{{{label_str}}} {hist.sum_seconds}")
            lines.append(f"{metric_base}_count{{{label_str}}} {hist.count}")
        else:
            lines.append(f"{metric_base}_sum {hist.sum_seconds}")
            lines.append(f"{metric_base}_count {hist.count}")
    return lines


def _format_le(value: float) -> str:
    """Format a bucket upper bound for Prometheus le= labels.

    Whole-number microseconds and milliseconds expressed cleanly;
    other values use repr-style float so 0.0001 doesn't become 1e-4.
    """
    s = f"{value:.9f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s
