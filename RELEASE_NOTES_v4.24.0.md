# Mullu Platform v4.24.0 — Per-Tenant Scrape Redaction

**Release date:** TBD
**Codename:** Slice
**Migration required:** No (additive — new endpoints, existing /stats /metrics unchanged)

---

## What this release is

Closes the per-tenant scrape redaction gap from v4.17/v4.18 audit.
Pre-v4.24, `/musia/governance/stats` and `/metrics` were admin-scoped
and exposed every tenant's data. Multi-org SaaS deployments need
per-customer visibility without leaking cross-tenant aggregates.

v4.24 adds tenant-scoped variants:
- `GET /musia/governance/stats/tenant` (JSON)
- `GET /musia/governance/metrics/tenant` (Prometheus)

Both use `musia.read` scope (a customer's normal credential), filter
to the authenticated tenant_id, and drop cross-tenant aggregates.

---

## What is new in v4.24.0

### Three-way (surface, tenant, verdict) index

[`musia_governance_metrics.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_metrics.py).

The pre-v4.24 registry tracked:
- `runs_by_surface_verdict` — totals across tenants
- `runs_by_surface_tenant` — totals across verdicts

To answer "for tenant T, what was the verdict breakdown?" required a
third index. v4.24 adds:

```python
runs_by_surface_tenant_verdict: dict[tuple[str, str, str], int]
```

Populated alongside the existing 2-way indices on every `record()`.
Existing consumers continue to read the 2-way fields unchanged; the
new field has an empty default in the snapshot dataclass for backward
compat.

### `GovernanceMetricsSnapshot.for_tenant(tenant_id)`

```python
snap = REGISTRY.snapshot()
acme_view = snap.for_tenant("acme")
# → a redacted snapshot containing ONLY acme's data
```

The per-tenant view exposes:
- `runs_by_surface_verdict` (reconstructed from the 3-way index — caller's verdict counts only)
- `runs_by_surface_tenant` (filtered to caller)
- `runs_by_surface_tenant_verdict` (filtered to caller)
- `denials_by_guard` (rebuilt from caller's filtered rejection events)
- `recent_rejections` (filtered to caller)

What's dropped (intentionally):
- `latency_by_surface` — platform-wide aggregate. Including it would
  let one tenant infer another's load from summed durations
- All other tenants' counts and rejection events

Empty `tenant_id` returns an empty snapshot (defense against the
always-true filter on `""`).

### `GET /musia/governance/stats/tenant`

```bash
curl -H "Authorization: Bearer $CUSTOMER_READ_TOKEN" \
     -H "X-Tenant-ID: acme" \
     https://mullu.example/musia/governance/stats/tenant
```

JSON response, same shape as `/stats` but tenant-scoped. `musia.read`
scope (vs. `musia.admin` for `/stats`). The customer's normal
read credential is sufficient; no admin token leak required for
self-service dashboards.

### `GET /musia/governance/metrics/tenant`

```bash
curl -H "Authorization: Bearer $CUSTOMER_READ_TOKEN" \
     -H "X-Tenant-ID: acme" \
     https://mullu.example/musia/governance/metrics/tenant
```

Prometheus exposition format (v0.0.4), tenant-scoped. Each customer
can wire their own Prometheus scrape job pointing at this endpoint
with their own credentials.

---

## Threat model

The point of the per-tenant view is to make tenant T1 unable to learn
about tenant T2 by reading the metrics endpoint. Concretely:

| Attack | Mitigation |
|---|---|
| T1 calls `/stats/tenant` with a token bound to T1 | Filter pins to authenticated tenant_id, not header X-Tenant-ID |
| T1 spoofs X-Tenant-ID header to T2 | `resolve_musia_auth` rejects tenant mismatch (existing v4.5 guard) |
| T1 reads aggregate latency to infer T2's load | `latency_by_surface` dropped from tenant view |
| T1 reads `total_runs` to infer fleet size | `total_runs` reflects T1's count only (sum of T1's verdict slice) |
| T1 reads `denials_by_guard` to learn other tenants' guard configs | `denials_by_guard` reconstructed from T1's rejections only |
| T1 reads `recent_rejections` to learn other tenants' policies | Filtered to T1's events |

Audit trail: any tenant's `for_tenant()` call is observable through
the existing access-log machinery; tenants requesting other tenants'
slices show up as 403 from `resolve_musia_auth` (X-Tenant-ID
mismatch), not as silent data leaks.

---

## Test counts

| Suite                                    | v4.23.0 | v4.24.0 |
| ---------------------------------------- | ------- | ------- |
| Prior governance suites (v4.17/v4.20/v4.21) | 65   | 65      |
| Per-tenant redaction (new)               | n/a     | 17      |

The 17 new tests in [`test_v4_24_per_tenant_metrics.py`](mullu-control-plane/mcoi/tests/test_v4_24_per_tenant_metrics.py) cover:

**3-way index (3)**
- `record()` populates the new index alongside the 2-way fields
- 2-way indices still aggregate correctly across tenants (backward compat)
- `reset()` clears the new index

**`for_tenant()` redaction (7)**
- Returns only the named tenant's per-tenant counts
- Reconstructs verdict breakdown without leaking cross-tenant verdict aggregates (50-tenant noisy-neighbor test)
- Filters recent_rejections (no other tenants' events leak)
- Reconstructs denials_by_guard from filtered events (other tenants' guards not visible)
- Drops latency_by_surface entirely
- Unknown tenant_id returns empty view
- Empty tenant_id returns empty view (defense)

**HTTP endpoints (7)**
- `/stats/tenant` returns only caller's data (string-search test confirms no other-tenant strings appear)
- Two tenants scrape independently; sums match admin global view
- `/metrics/tenant` returns Prometheus content type
- `/metrics/tenant` reflects per-tenant verdict breakdown (denial counts correct)
- `/metrics/tenant` omits latency histogram samples
- Admin `/metrics` unchanged by adding /tenant variants
- Unknown tenant gets empty-but-well-formed response

All 65 prior governance tests still pass — additive design.

---

## Compatibility

- **All v4.23.x callers work unchanged.** New endpoints are additive
- `GovernanceMetricsSnapshot` adds `runs_by_surface_tenant_verdict`
  field with empty default — frozen dataclass, but the field has a
  factory default so existing positional construction stays valid
- Existing `as_dict()` adds the new key in JSON output — Pydantic
  ignores unknown keys by default; strict-schema consumers may need
  an allow-list update
- `for_tenant()` is a new method — no existing call sites affected

---

## Production deployment guidance

### Wiring per-tenant scraping (SaaS)

For SaaS deployments where each customer runs their own dashboards:

```yaml
# customer's prometheus.yml
scrape_configs:
  - job_name: my_mullu_governance
    metrics_path: /musia/governance/metrics/tenant
    scheme: https
    static_configs:
      - targets: ['mullu.example:443']
    bearer_token_file: /etc/prometheus/my-customer-token
    # No need to drop _by_tenant_total — the tenant view contains
    # only this customer's data anyway
```

Each customer's token has `musia.read` scope and is bound (via JWT
claim or API key map) to their tenant_id. The endpoint filters
automatically.

### Self-service dashboards

For customer-facing admin consoles:

```javascript
// Customer's dashboard fetches their own slice
const stats = await fetch('/musia/governance/stats/tenant', {
  headers: { 'Authorization': `Bearer ${customerToken}` },
}).then(r => r.json());

// stats.total_runs, stats.total_denials, stats.recent_rejections — all theirs
```

### Combining with admin scraping

Admin operators continue scraping `/musia/governance/metrics` (no
`/tenant` suffix) for the unredacted fleet view. Both endpoint
families can run side-by-side without conflict.

---

## What v4.24.0 still does NOT include

- **Per-tenant histograms.** `latency_by_surface` is dropped from the
  tenant view because the registry only tracks platform-wide latency.
  Adding per-tenant latency would require `latency_by_surface_tenant`
  state with proportional cardinality cost. Future workstream if
  customers ask
- **Cross-customer scope (multi-tenant aggregator)** — `for_tenant()`
  takes one tenant_id, not a list. Operators wanting a per-business-
  unit view across multiple tenants can call the admin endpoint and
  filter at scrape time
- **Tenant-list listing endpoint** — there's no `/musia/governance/tenants`
  that returns "tenants with metric activity." Use `/musia/tenants`
  (admin scope) for that

---

## Production-readiness gap status

```
✅ #3 JWKS/RSA                       — v4.19.0
✅ "in-process counters only"         — v4.20.0
✅ "no latency histograms"            — v4.21.0
✅ CI Node.js 20 deprecation         — v4.22.0
✅ "cursor pagination missing"       — v4.23.0
✅ "per-tenant scrape redaction"     — v4.24.0
⏳ #1 Live deployment evidence        — needs real production environment
⏳ #2 Single-process state            — needs Redis + Postgres
⏳ #4 DB schema migrations            — could be done locally; bigger surface
```

---

## Honest assessment

v4.24 is small (~100 lines source + ~280 lines tests). The main
design decision was the 3-way index (surface, tenant, verdict) —
adding it to the existing record() loop costs one extra dict lookup
and bounded extra memory (`tenant_count × 6` series per tenant). For
deployments with up to 10K tenants, that's 60K entries — well within
in-process bounds.

The intentional drop of `latency_by_surface` from the tenant view
costs customers visibility into their own latency. If that becomes
a real complaint, v4.25 could add `latency_by_surface_tenant` —
but only after a customer asks, not preemptively.

**We recommend:**
- Upgrade in place. v4.24 is additive.
- If running SaaS: expose `/musia/governance/metrics/tenant` to your
  customers and document it in their integration guide.
- Keep admin-scoped `/metrics` for your own ops use; the two endpoints
  serve distinct audiences.
