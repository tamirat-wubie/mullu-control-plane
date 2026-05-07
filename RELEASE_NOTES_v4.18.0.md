# Mullu Platform v4.18.0 — End-to-End Audit + Hardening

**Release date:** TBD
**Codename:** Audit
**Migration required:** No (additive — every fix preserves prior behavior under default constructor args)

---

## What this release is

After 17 minor MUSIA releases (v4.0–v4.17), an end-to-end audit was
run rather than yet another feature. The audit surfaced four
unbounded-growth bugs in long-lived state, plus one orphaned schema
file that had been added during MUSIA work but never registered. v4.18
ships the fixes.

This is platform hardening, not MUSIA framework work. No new MUSIA
endpoints, no new constructs. Existing behavior is preserved when you
construct managers without the new parameters.

---

## What is fixed in v4.18.0

### `CorrelationManager._completed` — bounded ring buffer

[request_correlation.py](mullu-control-plane/mcoi/mcoi_runtime/core/request_correlation.py).

Before: `list[CorrelationContext]` appended on every `complete()` call.
Production OOM proportional to total request count.

Now: `deque(maxlen=DEFAULT_MAX_COMPLETED=10_000)`. Old entries evict in
O(1). All read paths (`completed_count`, `summary()`) work
unchanged. Constructor accepts `max_completed=...` for tuning.

```python
mgr = CorrelationManager(clock=now)                    # cap = 10_000
mgr = CorrelationManager(clock=now, max_completed=500)  # custom cap
```

### `CorrelationManager._active` — TTL sweep

Same module. Before: a request that crashed before calling `complete()`
left its context in `_active` forever. No TTL, no cleanup hook. Over
time, a high-traffic server with even occasional crashes would leak
without bound.

Now: a TTL-based sweep runs lazily on each `start()` and explicitly via
`cleanup_stale()`. Default TTL is 1 hour (`DEFAULT_ACTIVE_TTL_SECONDS`).
Set `active_ttl_seconds=None` to disable (legacy behavior).

```python
mgr = CorrelationManager(clock=now)                          # 1-hour TTL
mgr = CorrelationManager(clock=now, active_ttl_seconds=300)   # 5-minute
mgr = CorrelationManager(clock=now, active_ttl_seconds=None)  # disabled
mgr.cleanup_stale()  # explicit sweep, returns evicted count
```

Stale entries are dropped, NOT moved to `_completed` — they are
incomplete by definition. Completion is the contract for joining the
audit ring.

Implementation note: a parallel `_active_inserted_at` map stores
monotonic timestamps. Distinct from `CorrelationContext.created_at`
(string, audit-shaped, from user-supplied clock) because TTL math
needs a numeric monotonic source.

### `ReplayRecorder._completed` — bounded ring buffer

[execution_replay.py](mullu-control-plane/mcoi/mcoi_runtime/core/execution_replay.py).

Same shape as the CorrelationManager fix. `list[ReplayTrace]` →
`deque(maxlen=DEFAULT_MAX_COMPLETED_TRACES=1_000)`. The cap is tighter
than CorrelationManager's because trace bodies can be large
(per-frame input/output dicts).

`list_traces` previously used `[-limit:]` slicing which deque doesn't
support; that path now wraps with `list(...)` first. Bounded so the
temporary list can't exceed the cap.

```python
rec = ReplayRecorder(clock=now)                             # cap = 1_000
rec = ReplayRecorder(clock=now, max_completed=200)          # custom cap
```

`get_trace(evicted_id)` returns `None` after a trace falls outside the
window — that's the explicit contract. Operators wanting longer history
persist externally.

### `TenantedRegistryStore._tenants` — opt-in cap

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

Before: `get_or_create()` auto-provisions a fresh `TenantState` for any
unknown `tenant_id`. Fine when tenant_ids come from a closed admin set;
not fine when they come from arbitrary auth claims (where one rogue
client could explode tenant count).

Now: optional `max_tenants` parameter. When set, auto-provisioning past
the cap raises a new `TenantQuotaExceeded` exception. Existing tenants
are never blocked or evicted. Default `None` preserves v4.17.x
behavior.

```python
store = TenantedRegistryStore()                       # unbounded (legacy)
store = TenantedRegistryStore(max_tenants=1_000)      # capped
store.set_max_tenants(500)                            # tighten at runtime
store.set_max_tenants(None)                           # disable cap
```

Lowering the cap below the current tenant count is allowed — only NEW
auto-provisions are blocked. Eviction would lose data; that's a
deliberate non-feature.

```python
try:
    state = store.get_or_create(tenant_id)
except TenantQuotaExceeded as e:
    return JSONResponse(status_code=429, content={"detail": str(e)})
```

### Universal-construct schema registered

[universal_construct.schema.json](schemas/universal_construct.schema.json) +
[mullu_governance_protocol.manifest.json](schemas/mullu_governance_protocol.manifest.json).

The schema file existed on disk (added during MUSIA v4 work) but was
never registered in the protocol manifest. Three sub-fixes:

1. `$schema` field updated to draft 2020-12 (was draft-07)
2. `$id` updated to URN form `urn:mullusi:schema:universal-construct:1`
   (was a non-URN https URL)
3. Tuple-style `items: [...]` converted to `prefixItems: [...]` for
   2020-12 conformance
4. Added to `mullu_governance_protocol.manifest.json` (now 23 entries
   — `test_protocol_manifest` count assertion bumped accordingly)

The schema is the public contract for all 25 MUSIA universal
constructs. It was always intended to be public; the wiring was just
incomplete. The full repo test suite (47k+ tests) caught this; the
MUSIA-specific suite would not have.

---

## What v4.18.0 does NOT include

- **Latency observability for the chain** — chain runs in microseconds
  (measured 5–16μs typical via [test_v4_17_chain_latency_bench.py](mullu-control-plane/mcoi/tests/test_v4_17_chain_latency_bench.py));
  histograms could land in v4.19 if anyone needs them, but the counter
  trichotomy in v4.17 was the load-bearing part.
- **Multi-process correlation** — TTL is per-process. Distributed
  cleanup needs Redis or similar; out of scope.
- **JWKS-with-RSA, distributed rate limits, S3/postgres backend, Rust port** — still ahead.

---

## Test counts

| Suite                                    | v4.17.0 | v4.18.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific                           | 760     | 771     |
| TenantedRegistryStore cap (new)          | n/a     | 11      |
| Pre-existing core hardening tests (new)  | n/a     | 18      |

The 11 new tests in [test_v4_18_hardening.py](mullu-control-plane/mcoi/tests/test_v4_18_hardening.py) cover:
- Default unbounded behavior preserved
- Cap honored on construction and at runtime via setter
- Auto-provision past cap raises `TenantQuotaExceeded` with detailed message
- Existing tenants survive cap (no eviction)
- Lowering cap below current count blocks new but keeps old
- `get()` (vs `get_or_create`) never creates, so cap never raises
- `reset_tenant` frees capacity
- Empty tenant_id still ValueError (validation order)
- Thread-safe under concurrent provisioning (50 racers, exactly 10 survive)
- `TenantQuotaExceeded` is `Exception`-catchable

The 18 new tests in [test_request_correlation.py](mullu-control-plane/mcoi/tests/test_request_correlation.py) and [test_execution_replay.py](mullu-control-plane/mcoi/tests/test_execution_replay.py) cover the bounded-ring caps + TTL sweep:
- Default caps and custom caps respected
- Eviction is FIFO; oldest drop, newest survive
- Reads after eviction (list_traces, summary) work correctly
- TTL sweep evicts crashed entries on next start()
- TTL=None disables sweep (legacy)
- Explicit cleanup_stale() returns count for ops dashboards
- complete() keeps timestamp map in lockstep
- Stale entries are dropped, not moved to _completed

---

## Compatibility

- All existing API shapes preserved
- All v4.17.x constructions work unchanged (new parameters are optional with safe defaults)
- `CorrelationManager` and `ReplayRecorder` API unchanged for current callers — only the internal storage type changed (list → deque) and that is hidden behind property accessors
- New `TenantQuotaExceeded` exception is opt-in (only thrown when `max_tenants` is set)
- Schema URN change: any external consumer that pinned `$id` to the legacy https URL will need to update to `urn:mullusi:schema:universal-construct:1`. The schema was unregistered, so this is unlikely to affect anyone in practice.

---

## Production deployment guidance

### Recommended settings for typical deployments

```python
# CorrelationManager — default settings are production-safe
mgr = CorrelationManager(clock=now)
# This gives you: 10_000 completed history, 1-hour active TTL.

# ReplayRecorder — same; default cap is conservative
rec = ReplayRecorder(clock=now)

# TenantedRegistryStore — set a cap if tenant_ids come from auth claims
STORE = TenantedRegistryStore(max_tenants=10_000)
# If a tenant onboarding flow pre-creates entries via admin, the cap
# can equal your max-customer count.
```

### Watch in metrics

For governance metrics (v4.17.0):
- `chain_runs_total` should grow proportional to traffic
- `total_denials` should grow much slower than `total_runs` — if it doesn't, your chain is too aggressive
- `runs_by_surface_verdict[("write", "exception")]` should be zero — non-zero means a guard is crashing

For correlation:
- `completed_count` saturates at `max_completed`; exceed → bump cap or scrape faster
- `active_count` should stay near 0 between requests; large => leaks (TTL will catch them but the count signal still surfaces the bug)

For tenants:
- `len(STORE.list_tenants())` should be bounded by your customer count (or by `max_tenants` if set)

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
v4.17.0  governance chain observability + latency benchmarks
v4.18.0  end-to-end audit + bounded-state hardening
```

---

## Honest assessment

v4.18 is the result of a pause-and-pressure-test cycle, not new
feature work. The original recommendation was "stop building, run the
full repo suite, see what breaks." It surfaced one actual bug
(orphaned schema) and four unbounded-growth issues. All four had been
present long before MUSIA — they're in `core/` modules that pre-date
v4.0.0 — but the audit only triggered when MUSIA's own clean
test surface gave us nothing left to find.

The fixes are deliberately conservative. None changes default
behavior; all add optional bounds with sensible defaults. A deployment
that picks no new arguments sees the same memory footprint that was
there before, but with a cap that prevents the worst-case unbounded
growth.

What it is not: structural reform. The pre-existing pattern of
"unbounded list, append on every event, no cap" appears in several
other modules ([governance_metrics.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_metrics.py)
proper bounds it; older modules may not). A more thorough cleanup
would audit every long-lived collection in `core/`. v4.18 hits the
worst three found in this audit pass; v4.19 or later could continue.

**We recommend:**
- Upgrade in place. v4.18.0 is additive; defaults preserve v4.17.x behavior.
- Set explicit `max_tenants` if your tenant_ids come from auth claims.
- Leave the new `active_ttl_seconds` at default unless you have a reason; 1 hour is the right balance of "long enough for slow requests" and "short enough that crashes get cleaned up."
- Keep the rest of your `_completed` history scraping into a TSDB; the in-memory ring is for local visibility, not history.

---

## Contributors

Same single architect, same Mullusi project. v4.18 is the post-MUSIA
hardening cycle — closes findings from the v4.17.x audit before
moving on to whatever comes next.
