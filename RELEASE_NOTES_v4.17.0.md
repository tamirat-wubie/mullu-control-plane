# Mullu Platform v4.17.0 — MUSIA Runtime (Governance Chain Observability)

**Release date:** TBD
**Codename:** Headlights
**Migration required:** No (additive — counters start empty and accrue with chain activity)

---

## What this release is

v4.15.0 attached the existing platform's `GovernanceGuardChain` to MUSIA
writes. v4.16.0 extended that gate to domain runs. Both shipped without
any aggregate visibility — every chain rejection showed up in the
rejected request's response, but operators couldn't answer simple
fleet-level questions:

- How often is the chain saying yes vs. no?
- Which guard rejects the most? Which never fires?
- Are denials concentrated on a single tenant?
- Did our last deploy change rejection rate?

v4.17.0 adds the counters and an admin endpoint to scrape them.

---

## What is new in v4.17.0

### `mcoi_runtime.app.routers.musia_governance_metrics`

New module: [musia_governance_metrics.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_metrics.py).

A thread-safe, in-process registry that records every chain
invocation. Mirrors the existing `substrate/metrics.py` pattern (RLock
+ frozen-dataclass snapshot).

```python
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY as METRICS,
    SURFACE_WRITE,
    SURFACE_DOMAIN_RUN,
)

snap = METRICS.snapshot()
snap.runs_by_surface_verdict
# → {("write", "allowed"): 142, ("write", "denied"): 8, ("domain_run", "allowed"): 31, ...}

snap.denials_by_guard
# → {"rate_limit": 5, "boundary_lockdown": 3}

snap.recent_rejections
# → tuple of last ≤50 RejectionEvent(timestamp, surface, tenant_id, blocking_guard, reason)
```

The bridge call sites — `chain_to_validator` (write surface) and
`gate_domain_run` (domain-run surface) — record on every invocation:
allow → counter increment; deny → counter + guard tally + ring-buffer
event; exception → counter + ring-buffer event (without guard tally,
since denials_by_guard is denial-only).

### `/musia/governance/stats` admin endpoint

```bash
GET /musia/governance/stats
```

JSON-shaped (tuple keys flattened to ``"<surface>:<verdict>"`` /
``"<surface>:<tenant>"`` strings):

```json
{
  "runs_by_surface_verdict": {
    "write:allowed": 142, "write:denied": 8,
    "domain_run:allowed": 31, "domain_run:denied": 2
  },
  "runs_by_surface_tenant": {
    "write:acme": 100, "write:bigco": 50, "domain_run:acme": 33
  },
  "denials_by_guard": {"rate_limit": 5, "boundary_lockdown": 3, "policy": 2},
  "recent_rejections": [
    {
      "timestamp": 1745628401.42,
      "surface": "write",
      "tenant_id": "acme",
      "blocking_guard": "rate_limit",
      "reason": "rate limited"
    }
  ],
  "total_runs": 183,
  "total_denials": 10
}
```

```bash
POST /musia/governance/stats/reset
```

204 No Content. Resets all counters. Useful before/after a deploy to
isolate a window.

Both endpoints require `musia.admin` scope — the same scope as
`/musia/tenants/*`.

### What gets recorded

| Event                                | Counters bumped                                                                                       |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Chain attached, allowed              | `runs_by_surface_verdict[(surface,"allowed")]++`, `runs_by_surface_tenant[(surface,tenant)]++`         |
| Chain attached, denied               | `runs_by_surface_verdict[(surface,"denied")]++`, `runs_by_surface_tenant[(surface,tenant)]++`, `denials_by_guard[guard]++`, ring-buffer event added |
| Chain attached, exception            | `runs_by_surface_verdict[(surface,"exception")]++`, `runs_by_surface_tenant[(surface,tenant)]++`, ring-buffer event added (NOT in `denials_by_guard`) |
| Chain detached (no invocation)       | nothing — absence-of-activity is the signal                                                            |

The "detached → no record" choice is deliberate: counters reflect
*chain decisions*, not request flow. A tenant whose deployment runs
without a chain has zero entries; a tenant whose chain perfectly
allows all traffic also has entries (under the `allowed` verdict).
Operators distinguish these by presence-of-counter, not by needing a
dedicated `detached` bucket.

### Bounded memory: rejection ring buffer

`MAX_RECENT_REJECTIONS = 50`. The buffer is a `deque(maxlen=50)`, so a
denial-storm cannot OOM the process — old events evict in O(1). For
full history, operators scrape into a TSDB at intervals.

Counter dicts are bounded by tenant count × surface (2) × guard count,
all of which are bounded in deployment (chain ordering caps guard count
to a handful; tenant count is bounded by the platform).

### Snapshot is immutable

`snapshot()` returns a `frozen=True` dataclass. Mutating its dicts has
no effect on the registry — verified by test. Callers can pass the
snapshot to any consumer without defensive copying.

### Exception is a separate verdict

A guard that raises gets caught by the bridge's defensive try/except
and recorded under `runs_by_surface_verdict[(surface, "exception")]`.
It is *not* counted under `denials_by_guard` because that view answers
"which guard is the most aggressive denier?" — exception counts would
distort it. Exceptions still surface in the rejection ring buffer for
forensic visibility ("this guard is crashing in production").

---

## Test counts

| Suite                                    | v4.16.0 | v4.17.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 736     | 760     |
| governance metrics tests (new)           | n/a     | 24      |

The 24 new tests cover:

**Registry contract (12)**
- Empty snapshot has zero totals
- Allowed-only increments runs but not denials
- Denied increments runs + guard tally + ring buffer
- Denial with no guard name records as "unknown"
- Exception verdict separates from denied verdict
- Invalid surface raises
- Multiple records accumulate
- Ring buffer hard-capped at MAX_RECENT_REJECTIONS
- Ring preserves chronology
- Reset clears everything
- Snapshot mutation does not affect future snapshots
- as_dict flattens tuple keys to colon strings

**Bridge wiring — write surface (3)**
- chain_to_validator records allow
- chain_to_validator records deny with guard name
- chain_to_validator records exception (separate verdict)

**Bridge wiring — domain-run surface (4)**
- gate_domain_run records allow
- gate_domain_run records deny
- Detached chain does not record (absence-of-activity)
- gate_domain_run records exception

**Surface separation (1)**
- Single chain, both surfaces, counters separate by surface key

**HTTP endpoint (4)**
- GET /stats empty returns zeros
- GET /stats after activity reflects all surfaces (write + domain_run)
- POST /stats/reset → 204 + counters cleared
- recent_rejections JSON carries full forensic detail (timestamp, surface, tenant, guard, reason)

---

## Compatibility

- All v4.16.0 endpoints unchanged in URL or shape
- `chain_to_validator` and `gate_domain_run` return the same `(bool, str)` tuple as before — counter recording is a side effect that does not alter return values
- The bridge's `(False, "chain_exception:<Type>")` denial format is unchanged; only the *verdict bucket* in metrics is distinct ("exception" vs. "denied")
- Detached chain (default) preserves v4.16.0 behavior exactly — and records nothing, so existing test fixtures see no surprise counter activity
- Snapshot dataclass is `frozen=True` — adding fields in future releases will break code that uses positional construction, but JSON consumers (the `as_dict()` body) are stable
- New `/musia/governance/stats` and `/musia/governance/stats/reset` endpoints; both admin-scoped, no clash with existing routes

---

## Production deployment guidance

### Wiring scrapers

The endpoint returns plain JSON; any HTTP scraper works.

```bash
# Manual spot-check
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://mullu.example/musia/governance/stats | jq .

# Periodic scrape into Prometheus pushgateway / TSDB
* * * * * curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://mullu.example/musia/governance/stats \
   | tools/forward_to_tsdb.sh
```

### Read flows operators care about

| Operational question                       | Metric to read                                                       |
| ------------------------------------------ | -------------------------------------------------------------------- |
| Is the chain rejecting too much?           | `total_denials / total_runs`                                          |
| Which guard does the most blocking?        | `denials_by_guard` — sort descending                                 |
| Did a deploy change rejection patterns?    | reset before deploy, snapshot after                                  |
| Which tenant is the most chain-blocked?    | `runs_by_surface_tenant`, denials slice                              |
| Is a guard crashing instead of deciding?   | `runs_by_surface_verdict[("write","exception")]` and ring buffer events with stack-trace-y guard names |
| Which writes vs. domain runs are gated?    | compare `("write",*)` vs `("domain_run",*)` in `runs_by_surface_verdict` |

### Reset cadence

Most deployments will *never* reset — counters are monotonic and a TSDB
takes deltas at scrape time, so absolute totals just keep climbing
harmlessly. Reset is reserved for ad-hoc windowed debugging:
"reset, run my synthetic load, snapshot, see only that load."

### Scope

`/musia/governance/stats` is admin-scoped because it includes per-tenant
counts (one tenant could otherwise infer another tenant's usage
patterns). If a deployment wants per-tenant self-service visibility,
that's a future workstream — guard-name and recent_rejections fields
would need redaction.

---

## What v4.17.0 still does NOT include

- **Histograms / latency** — counter cardinality only. Per-guard latency p50/p95
  would need a histogram type and chain-level instrumentation; not
  free. v4.18 candidate.
- **Detached-chain visibility** — absence is the signal. If operators want a
  "chain attached?" flag they can check `configured_chain() is not None`
  via a separate endpoint.
- **Per-tenant scrape redaction** — current endpoint exposes all tenants to
  any admin caller. Multi-org deployments wanting per-org visibility
  would need a tenant-scoped variant.
- **Persistence** — counters reset on process restart. Acceptable for
  fleet observability (TSDBs handle the long history); not appropriate
  for billing / audit, which has its own audit trail.
- **JWKS-with-RSA, distributed rate limits, multi-process backend, Rust port** — still ahead.

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
v4.3.0   multi-tenant registry isolation
v4.3.1   auth-derived tenant resolution
v4.4.0   persistent tenant state
v4.5.0   auto-snapshot + JWT + scope enforcement
v4.6.0   scientific_research + bulk migration runner
v4.7.0   manufacturing + healthcare + education adapters
v4.8.0   /domains HTTP surface + adapter cleanup
v4.9.0   JWT rotation + tenant construct count quotas
v4.10.0  sliding-window rate limits + quota persistence
v4.11.0  persist_run audit trail + run_id queries
v4.12.0  run metadata enrichment + bulk delete + runs listing
v4.13.0  indexed run lookup + run export endpoint
v4.14.0  opt-in pagination across list endpoints
v4.14.1  import cycle fixes (patch)
v4.15.0  Φ_gov ↔ GovernanceGuardChain bridge (writes)
v4.16.0  per-domain chain gating
v4.17.0  governance chain observability
```

760 MUSIA tests; 110 docs; six domains over HTTP with full chain
governance on writes AND domain runs AND aggregate observability;
multi-tenant + multi-auth + persistent + scope-enforced +
size-and-rate-bounded + run-traceable + run-cleanable + run-exportable +
paginated + chain-gated + chain-observable.

---

## Honest assessment

v4.17.0 is small (~270 lines including tests) and that smallness is
again the point. The bridge contracts from v4.15 and v4.16 already
funneled every chain decision through two known call sites; v4.17
just instrumented those sites and exposed an admin scrape. No
new contracts.

The shape decision worth flagging is the verdict trichotomy
(allowed | denied | exception). Lumping exceptions into denials
is *operationally* tempting — both are "the request didn't go through" —
but *diagnostically* misleading: a chain that crashes 1% of the time
and a chain that denies 1% of the time mean very different things
(broken guard vs. tight policy). Keeping them separate makes the
distinction discoverable from the metrics alone.

What it is not, yet: histograms / latency. The cost of a chain run is
already on the request critical path; a slow guard is a real concern.
But adding histograms requires more thought than counters (cardinality
explosion, percentile estimation strategy) and is a separate workstream.

**We recommend:**
- Upgrade in place. v4.17.0 is additive; counters start empty.
- Wire `/musia/governance/stats` into your existing scrape job (admin token).
- After a deploy that changes guard ordering, reset counters to isolate the new window.
- Watch `runs_by_surface_verdict[(surface,"exception")]` — non-zero means a guard is crashing in prod, which the bridge masks as denial; fix the guard.

---

## Contributors

Same single architect, same Mullusi project. v4.17.0 closes the
"chain operates blind" gap that v4.15+v4.16 introduced — instrumenting
two call sites and exposing the registry over admin HTTP.
