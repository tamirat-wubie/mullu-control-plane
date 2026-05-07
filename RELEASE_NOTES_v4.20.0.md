# Mullu Platform v4.20.0 — Prometheus Exposition for Governance Metrics

**Release date:** TBD
**Codename:** Scrape
**Migration required:** No (additive — new endpoint, existing JSON `/stats` unchanged)

---

## What this release is

v4.17 ships governance chain counters with a JSON
`/musia/governance/stats` endpoint. Operators wanting to scrape these
into Prometheus, Grafana Agent, Datadog, or any OTel Collector had to
write a sidecar JSON-to-text-format translator. v4.20 ships the
translator natively as `/musia/governance/metrics`.

Same data, two formats: JSON for ad-hoc tooling and the admin console;
Prometheus exposition format (v0.0.4) for fleet observability.

---

## What is new in v4.20.0

### `GET /musia/governance/metrics`

[`musia_governance_metrics.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_metrics.py).

Returns the standard text-based exposition format with content type
`text/plain; version=0.0.4; charset=utf-8`.

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://mullu.example/musia/governance/metrics
```

```text
# HELP mullu_governance_chain_runs_total Total chain invocations by surface and verdict.
# TYPE mullu_governance_chain_runs_total counter
mullu_governance_chain_runs_total{surface="write",verdict="allowed"} 142
mullu_governance_chain_runs_total{surface="write",verdict="denied"} 8
mullu_governance_chain_runs_total{surface="domain_run",verdict="allowed"} 31

# HELP mullu_governance_chain_denials_by_guard_total Total chain denials by blocking guard name.
# TYPE mullu_governance_chain_denials_by_guard_total counter
mullu_governance_chain_denials_by_guard_total{guard="rate_limit"} 5
mullu_governance_chain_denials_by_guard_total{guard="boundary_lockdown"} 3

# HELP mullu_governance_chain_total_runs Aggregate count of all chain invocations across surfaces.
# TYPE mullu_governance_chain_total_runs gauge
mullu_governance_chain_total_runs 181
...
```

### Six metric families

| Metric | Type | Labels | Cardinality |
|---|---|---|---|
| `mullu_governance_chain_runs_total` | counter | `surface`, `verdict` | ≤6 (2 surfaces × 3 verdicts) |
| `mullu_governance_chain_runs_by_tenant_total` | counter | `surface`, `tenant` | 2 × tenant_count ⚠️ |
| `mullu_governance_chain_denials_by_guard_total` | counter | `guard` | guard_count (typically 5–15) |
| `mullu_governance_chain_total_runs` | gauge | none | 1 |
| `mullu_governance_chain_total_denials` | gauge | none | 1 |
| `mullu_governance_chain_recent_rejections` | gauge | none | 1 |

⚠️ The `_by_tenant_total` series has cardinality proportional to tenant
count. Operators with large fleets should drop or relabel this metric
in their scrape config:

```yaml
# Prometheus scrape_config snippet
metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'mullu_governance_chain_runs_by_tenant_total'
    action: drop
```

### Empty-state discoverability

Before any chain activity, the endpoint still emits HELP + TYPE
annotations for all six metric families. This lets Prometheus register
the series at startup so dashboards and alerts don't fire "metric
not found" errors during the cold-start window.

```text
# HELP mullu_governance_chain_runs_total Total chain invocations by surface and verdict.
# TYPE mullu_governance_chain_runs_total counter
# (no samples — but the family is registered)
```

### Spec-compliant label escaping

Per Prometheus exposition format v0.0.4:
- `\` → `\\`
- `"` → `\"`
- newline → `\n` (literal two-char sequence)

Tested against tenant IDs containing each of these characters, so
adversarial tenant_id values can't corrupt the output. Test:
[test_v4_20_prometheus_exposition.py](mullu-control-plane/mcoi/tests/test_v4_20_prometheus_exposition.py).

### Custom prefix

The default metric prefix is `mullu_`. Operators running the runtime
under a different brand can override:

```python
text = METRICS.snapshot().to_prometheus_text(prefix="acme_corp")
# Emits acme_corp_governance_chain_runs_total{...}
```

The HTTP endpoint always uses `mullu_` to keep deployment-time
configuration simple; operators wanting a different prefix can mount
a thin proxy.

### Admin scope

Same auth as `/musia/governance/stats` — `musia.admin` scope. The
endpoint includes per-tenant counters; multi-org deployments should
gate access at the ingress before exposing to scrapers.

---

## Why a separate path, not `/metrics`

Mullu deployments often run multiple metric surfaces (substrate path
metrics, gateway metrics, governance metrics) in one process. A single
`/metrics` endpoint at the app root would have to multiplex all of
them, adding coupling between unrelated subsystems. Each surface gets
its own scrapeable endpoint instead:

- `/musia/governance/metrics` — chain counters (this release)
- `/musia/substrate/metrics` — Mfidel path counters (future)
- `/gateway/metrics` — channel adapter counters (future)

Operators wanting a unified view can mount a thin aggregator that
scrapes each surface internally.

---

## Test counts

| Suite                                    | v4.19.0 | v4.20.0 |
| ---------------------------------------- | ------- | ------- |
| v4.17 governance metrics (regression)    | 24      | 24      |
| v4.20 Prometheus exposition (new)        | n/a     | 18      |

The 18 new tests in [`test_v4_20_prometheus_exposition.py`](mullu-control-plane/mcoi/tests/test_v4_20_prometheus_exposition.py) cover:

**Format conformance (7)**
- Empty snapshot emits HELP + TYPE for all 6 families
- Counter metrics use `_total` suffix convention
- Output ends with newline (spec requirement)
- Families separated by blank line
- Records appear in output after chain activity
- Label values alphabetically sorted (deterministic output)
- Custom prefix propagates to all metric names

**Label escaping (3)**
- `"` → `\"` in tenant IDs
- `\` → `\\` in tenant IDs
- `\n` → `\n` (literal) in tenant IDs

**Cardinality bounds (2)**
- `runs_total` series count ≤ 6 regardless of tenant traffic
- `denials_by_guard_total` series count = unique guards, NOT × tenants

**HTTP endpoint (6)**
- Returns `text/plain; version=0.0.4` content type
- Body is valid Prometheus text format
- Reflects chain activity (denials surface in body)
- Aligns with `/stats` (same data, two formats)
- Handles concurrent chain writes during scrape (snapshot consistency)
- Empty-state body is valid format (all families discoverable, gauges = 0)

---

## Compatibility

- **All v4.19.x JSON `/stats` consumers work unchanged.** The new
  endpoint is additive
- **`to_prometheus_text()` is a new method on `GovernanceMetricsSnapshot`** —
  callers using `as_dict()` see no change
- **No new dependencies.** Format is built from existing
  `MetricFamily` / `MetricSample` primitives in
  [`core/prometheus_exporter.py`](mullu-control-plane/mcoi/mcoi_runtime/core/prometheus_exporter.py)
- **Admin scope unchanged** — same as `/stats`

---

## Production deployment guidance

### Wiring Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: mullu_governance
    metrics_path: /musia/governance/metrics
    scheme: https
    static_configs:
      - targets: ['mullu.example:443']
    bearer_token_file: /etc/prometheus/mullu-admin-token
    # Drop high-cardinality per-tenant metrics on large fleets
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'mullu_governance_chain_runs_by_tenant_total'
        action: drop
```

### Wiring Grafana Agent / OpenTelemetry Collector

The exposition format is universally compatible with the Prometheus
ecosystem. Any agent that scrapes Prometheus targets (Grafana Agent,
OTel Collector with the `prometheus` receiver, Datadog Agent in
OpenMetrics mode) ingests this endpoint without translation.

### Useful queries (PromQL)

```promql
# Rejection rate by surface
sum by (surface) (rate(mullu_governance_chain_runs_total{verdict="denied"}[5m]))
  / sum by (surface) (rate(mullu_governance_chain_runs_total[5m]))

# Top blocking guards over last hour
topk(5, sum by (guard) (
  increase(mullu_governance_chain_denials_by_guard_total[1h])
))

# Are any chains crashing instead of deciding?
sum(mullu_governance_chain_runs_total{verdict="exception"}) > 0
```

### Useful alerts

```yaml
# Chain crashing in production — non-zero exception count
- alert: GovernanceChainException
  expr: sum(rate(mullu_governance_chain_runs_total{verdict="exception"}[5m])) > 0
  for: 5m
  annotations:
    summary: "A guard in the governance chain is raising"

# Rejection rate spiked
- alert: GovernanceDenialRateHigh
  expr: |
    sum(rate(mullu_governance_chain_runs_total{verdict="denied"}[5m]))
      / sum(rate(mullu_governance_chain_runs_total[5m])) > 0.1
  for: 10m
  annotations:
    summary: "Governance chain denying >10% of traffic"
```

---

## What v4.20.0 still does NOT include

- **Histograms.** Counters only — chain latency is still measured by
  the v4.17 benchmark harness, not exported as p50/p95/p99 histograms.
  Adding latency exposition is straightforward but cardinality-aware
  bucket selection deserves its own design pass. v4.21 candidate.
- **OpenMetrics format.** The newer OM format is a superset of
  Prometheus exposition; we emit the older v0.0.4 spec which any OM
  scraper still ingests. Switching to OM `# UNIT` annotations + native
  histograms would close this.
- **Push-gateway support.** Pull-based scraping only. Operators who
  need push semantics (short-lived jobs, NAT'd workers) would wire a
  pushgateway sidecar.
- **Per-tenant scrape redaction.** Admin scope sees all tenants. If
  multi-org deployments need per-org metric visibility, that's a
  separate workstream — likely a tenant-scoped variant of the endpoint
  with claim-based filtering.

---

## Cumulative MUSIA + production-readiness progress

```
v4.0.0   substrate (Mfidel + Tier 1)
...
v4.17.0  governance chain observability + latency benchmarks
v4.18.0  end-to-end audit + bounded-state hardening
v4.19.0  RSA + JWKS for JWT authentication
v4.20.0  Prometheus exposition for governance metrics
```

Production-readiness gap status (from earlier audit):
- ✅ #3 JWKS/RSA — shipped in v4.19.0
- ✅ "in-process counters only" significant gap — Prometheus exposition shipped in v4.20.0
- ⏳ #1 Live deployment evidence — process work, requires actual production environment
- ⏳ #2 Single-process state — requires Redis + Postgres
- ⏳ #4 DB schema migrations — could be done locally, bigger design surface

---

## Honest assessment

v4.20 is a small (~115 lines source + ~270 lines tests) closing of one
specific operational gap: the v4.17 counters were great in-process but
opaque to fleet observability. This release plugs them into the
standard ecosystem.

The implementation pulls the format directly from the snapshot rather
than going through the stateful `PrometheusExporter` registration
class — simpler for one-shot exposition, and avoids the lock-on-read
contention that comes with using the existing exporter.

Cardinality decisions in this release:
- `runs_by_tenant_total` is included despite cardinality risk because
  per-tenant visibility is genuinely useful for SaaS operators tracing
  noisy-neighbor behavior. Operators who don't need it can drop it
  in scrape config.
- Histograms are not included because picking bucket boundaries
  without measured production latency profiles would be cargo-cult.
  v4.17's benchmark harness gives us 5–16μs typical; if real
  production traffic confirms that, the buckets become obvious. v4.21.

**We recommend:**
- Upgrade in place. v4.20 is additive.
- Wire `/musia/governance/metrics` into your existing Prometheus scrape job (admin token).
- On large fleets, drop the `_by_tenant_total` series at scrape time.
- After deploying, confirm `mullu_governance_chain_runs_total{verdict="exception"}` stays at 0 — non-zero means a guard is crashing in prod.

---

## Contributors

Same single architect, same Mullusi project. v4.20 closes the
"in-process counters only" significant gap from the v4.18 production
audit by exposing what's already collected.
