# Mullu Platform v4.21.0 — Latency Histograms for Governance Chain

**Release date:** TBD
**Codename:** Latency
**Migration required:** No (additive — `duration_seconds` is optional, snapshot field defaults to empty dict)

---

## What this release is

Closes the "histograms missing" gap from v4.20 release notes. v4.17
shipped chain counters; v4.20 exposed them as Prometheus text format;
v4.21 adds latency histograms for both the snapshot and Prometheus
output, populated by timing `chain.evaluate()` at the bridge call sites.

Bucket boundaries are picked from measured v4.17 benchmark numbers
(5–16μs typical, p99 ≤ 41μs) plus headroom up to 5ms for
pathological cases. Not cargo-cult — informed by data.

---

## What is new in v4.21.0

### `LatencyHistogram` dataclass

[`musia_governance_metrics.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_metrics.py).

```python
@dataclass(frozen=True)
class LatencyHistogram:
    upper_bounds: tuple[float, ...]          # bucket boundaries (seconds)
    bucket_counts: tuple[int, ...]           # cumulative (le= semantics)
    sum_seconds: float                        # total observation time
    count: int                                # total observation count

    def p_estimate(self, p: float) -> float | None:
        """Coarse percentile estimate (returns smallest matching bucket bound)."""
```

Cumulative bucket counts mean bucket *i* counts every observation with
duration ≤ `upper_bounds[i]`. The +Inf bucket is implicit (= total
count). Operators wanting precise percentiles ingest into Prometheus
and use `histogram_quantile()`.

### Default bucket boundaries

```python
DEFAULT_LATENCY_BUCKETS_SECONDS = (
    1e-6,      # 1μs   — well below any real chain
    5e-6,      # 5μs   — typical empty-bridge cost
    1e-5,      # 10μs  — typical 1-guard chain
    2.5e-5,    # 25μs  — typical 5-guard chain
    5e-5,      # 50μs  — measured p99 ceiling
    1e-4,      # 100μs — first sign of slow guard
    2.5e-4,    # 250μs
    5e-4,      # 500μs
    1e-3,      # 1ms   — clearly degraded
    2.5e-3,    # 2.5ms
    5e-3,      # 5ms   — pathological (blocking I/O in guard?)
)
```

The set deliberately undershoots the typical case (1μs and 5μs buckets
will catch nothing in normal traffic) so a sudden shift in latency
distribution shows up in the buckets that should be empty.

Operators with chains that include external HTTP calls or heavy
computation should pass custom boundaries:

```python
reg = GovernanceMetricsRegistry(
    latency_buckets_seconds=(0.01, 0.1, 1.0, 10.0),
)
```

### `record(... duration_seconds=...)` parameter

```python
METRICS.record(
    surface=SURFACE_WRITE,
    tenant_id="acme",
    allowed=True,
    duration_seconds=0.000_010,   # 10μs — populates the histogram
)
```

`duration_seconds` is optional — pre-v4.21 callers that omit it still
work (counters increment, histogram stays empty for that surface).
This keeps the v4.17–v4.20 contract intact for any downstream code
that records its own metrics through this registry.

Negative durations (clock skew defense) are clamped to 0 before
observation.

### Bridge call sites time `chain.evaluate()`

Both `chain_to_validator` and `gate_domain_run` now wrap
`chain.evaluate()` with `time.monotonic_ns()` deltas and pass
`duration_seconds` to every `_METRICS.record(...)` call —
**including the exception path**. A guard that crashes still produces
a histogram observation, because operators want to spot guards that
are slow even when they fail.

Overhead: two `monotonic_ns()` calls per chain invocation (~50–100ns
on modern hardware), well under 1% of the 5–16μs typical chain cost.

### Prometheus histogram exposition

```text
# HELP mullu_governance_chain_duration_seconds Chain evaluation duration in seconds, by surface.
# TYPE mullu_governance_chain_duration_seconds histogram
mullu_governance_chain_duration_seconds_bucket{le="0.000001",surface="write"} 0
mullu_governance_chain_duration_seconds_bucket{le="0.000005",surface="write"} 12
mullu_governance_chain_duration_seconds_bucket{le="0.00001",surface="write"} 87
mullu_governance_chain_duration_seconds_bucket{le="0.000025",surface="write"} 142
...
mullu_governance_chain_duration_seconds_bucket{le="+Inf",surface="write"} 145
mullu_governance_chain_duration_seconds_sum{surface="write"} 0.00187
mullu_governance_chain_duration_seconds_count{surface="write"} 145
```

Standard Prometheus histogram format: `_bucket{le=...}` lines with
cumulative counts, `_sum`, `_count`, +Inf bucket. Each surface gets
its own histogram series.

Empty-state still emits HELP + TYPE annotations so Prometheus
registers the family at startup.

### `as_dict()` exposes the histogram

```json
{
  "latency_by_surface": {
    "write": {
      "upper_bounds": [1e-6, 5e-6, ..., 5e-3],
      "bucket_counts": [0, 12, 87, ...],
      "sum_seconds": 0.00187,
      "count": 145
    }
  }
}
```

Same data, both formats — admin consoles parsing JSON see exactly
what scrapers see.

---

## Useful queries (PromQL)

The whole point of histograms is `histogram_quantile`:

```promql
# p50/p95/p99 chain latency by surface
histogram_quantile(0.50,
  sum by (surface, le) (
    rate(mullu_governance_chain_duration_seconds_bucket[5m])
  )
)
histogram_quantile(0.95, ...)
histogram_quantile(0.99, ...)

# Average chain latency
sum(rate(mullu_governance_chain_duration_seconds_sum[5m]))
  / sum(rate(mullu_governance_chain_duration_seconds_count[5m]))

# How much of fleet traffic exceeds 100μs?
1 - (
  sum(rate(mullu_governance_chain_duration_seconds_bucket{le="0.0001"}[5m]))
    / sum(rate(mullu_governance_chain_duration_seconds_count[5m]))
)
```

Useful alerts:

```yaml
# p99 chain latency degraded above 1ms — 100x the measured baseline
- alert: GovernanceChainSlow
  expr: |
    histogram_quantile(0.99,
      sum by (surface, le) (
        rate(mullu_governance_chain_duration_seconds_bucket[5m])
      )
    ) > 0.001
  for: 10m
  annotations:
    summary: "Chain p99 latency above 1ms — investigate slow guard"
```

---

## Test counts

| Suite                                    | v4.20.0 | v4.21.0 |
| ---------------------------------------- | ------- | ------- |
| v4.15-v4.20 governance regression        | 127     | 127     |
| v4.21 latency histograms (new)           | n/a     | 23      |

The 23 new tests in [`test_v4_21_latency_histograms.py`](mullu-control-plane/mcoi/tests/test_v4_21_latency_histograms.py) cover:

**LatencyHistogram dataclass (3)**
- Default bucket boundaries cover v4.17 measurements (5–16μs typical, p99 ≤ 41μs)
- `p_estimate()` returns None on empty histogram
- `p_estimate()` returns smallest bound meeting target percentile

**Registry recording (8)**
- `record()` without `duration_seconds` is backward-compatible (counters still work)
- `record()` with `duration_seconds` populates histogram
- Negative duration clamped to 0 (clock-skew defense)
- Cumulative bucket math verified across multiple bucket regions
- Histograms separated by surface (no cross-contamination)
- Histograms populated for allowed/denied/exception verdicts
- Reset clears histograms
- Custom bucket boundaries respected

**Bridge wiring (5)**
- `chain_to_validator` records duration on allow path
- `chain_to_validator` records duration on deny path
- `chain_to_validator` records duration on exception path
- `gate_domain_run` records duration
- Detached chain doesn't record (no-op)

**Prometheus exposition (5)**
- Histogram family emitted with correct TYPE annotation
- +Inf bucket present (Prometheus convention)
- Bucket counts cumulative and monotonic
- Empty state still emits HELP + TYPE
- Histograms separated by surface in Prometheus output

**Misc (1)**
- `as_dict()` includes `latency_by_surface` field with full structure

**End-to-end (1)**
- 10 HTTP write requests through chain produce histogram with count=10 and +Inf bucket=10

All 127 prior governance tests (v4.15–v4.20) still pass.

---

## Compatibility

- **All v4.20.x callers work unchanged.** `duration_seconds` is optional; omitting it preserves previous behavior
- **`GovernanceMetricsSnapshot` adds `latency_by_surface` field with empty default.** Frozen dataclass — code that constructs snapshots positionally would need an update, but the only construction site is `GovernanceMetricsRegistry.snapshot()` itself
- **`as_dict()` adds a `latency_by_surface` key.** JSON consumers with strict schema validation may need to allow it
- **Prometheus output adds the `mullu_governance_chain_duration_seconds_*` family.** Scrape configs that drop unknown metrics need an allow-list update

---

## Production deployment guidance

### Wiring into existing dashboards

If you already scrape `/musia/governance/metrics`, the histogram
appears automatically — no scrape config change needed. Add panels for
the PromQL queries above; the most useful at-a-glance is the
`histogram_quantile(0.99, ...)` line graph by surface.

### Bucket-boundary tuning

The defaults are tuned for the measured Mfidel chain, not for real
production guards (which may include rate-limit Redis lookups, JWT
verification, content-safety scans). If your chains regularly land
in the +Inf bucket (`_count > _bucket{le="0.005"}`), pick custom
boundaries:

```python
from mcoi_runtime.app.routers.musia_governance_metrics import (
    GovernanceMetricsRegistry,
)

# For chains with external HTTP calls, expect ms not μs
custom_buckets = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0
)
# Replace the module-level REGISTRY with a custom-bucketed instance
# at startup, BEFORE any chain activity
```

Replacing the module-level `REGISTRY` is a one-time-at-bootstrap operation
because all bridge call sites import it by reference. If you can't
restart, the existing histogram retains its boundaries — operators
should plan bucket changes alongside deploys.

### Cardinality

Histograms add `bucket_count + 2` series per surface (11 buckets +
sum + count + +Inf = 14 per surface). With 2 surfaces that's 28
new series — modest, well below typical Prometheus limits. The high-
cardinality risk in this system remains the v4.20-introduced
`_by_tenant_total` counter, not histograms.

---

## What v4.21.0 still does NOT include

- **Per-guard histograms.** Currently just per-surface; isolating
  which guard is slow requires the v4.17 benchmark harness or
  application logs. Adding per-guard histograms adds cardinality
  (guard_count × bucket_count) — possible if operators ask, but
  default-off.
- **Tenant-scoped histograms.** Same cardinality concern as
  `_by_tenant_total`. Not included by default.
- **Native sparse / exponential histograms** (Prometheus 2.40+).
  Classic histograms are universally supported; sparse histograms
  would land cleaner in OpenMetrics format. Future workstream.

---

## Cumulative production-readiness progress

```
v4.0.0 – v4.18.0  MUSIA framework + audit hardening
v4.19.0           RSA + JWKS for JWT authentication
v4.20.0           Prometheus exposition for governance metrics
v4.21.0           Latency histograms for governance chain
```

Production-readiness gap status (from v4.18 audit):
- ✅ #3 JWKS/RSA — v4.19.0
- ✅ "in-process counters only" — v4.20.0
- ✅ "no latency histograms in observability" — v4.21.0
- ⏳ #1 Live deployment evidence — needs real production environment
- ⏳ #2 Single-process state — needs Redis + Postgres
- ⏳ #4 DB schema migrations — could be done locally; bigger design surface

Three significant gaps closed in three minor releases.

---

## Honest assessment

v4.21 is a small (~110 lines source + ~360 lines tests) closing of
one specific gap: latency was measurable via the v4.17 benchmark
harness but invisible at production scrape time. This release just
plumbs the timing through the existing observability path.

The design decision worth flagging is **per-surface** rather than
per-guard. Per-guard histograms would tell operators exactly which
guard is slow — but at the cost of `guard_count × 14 series` per
surface, which on a 10-guard chain becomes 140+ series. The
per-surface choice keeps the in-process histogram bounded; operators
diagnosing a specific guard fall back to the benchmark harness or
add ad-hoc instrumentation in the guard itself.

What it is not, yet: **production-measured tuning of the bucket
boundaries**. The defaults are calibrated to the v4.17 microbenchmark
which uses trivial guards. Real production chains with rate-limit
Redis lookups will land in different buckets. After the first month
of production data, operators should review the bucket distribution
and re-tune.

**We recommend:**
- Upgrade in place. v4.21 is additive.
- Add a `histogram_quantile` panel to your Grafana dashboards using the PromQL queries above.
- After 1–4 weeks of production traffic, review where observations cluster and re-tune boundaries if needed.
- Watch for `_count > _bucket{le="0.005"}` — that's the +Inf bucket, indicating chain runs longer than the largest defined bucket.

---

## Contributors

Same single architect, same Mullusi project. v4.21 closes the
"histograms missing" gap from the v4.20 release notes — observability
data we already had, finally exposed at the right surface.
