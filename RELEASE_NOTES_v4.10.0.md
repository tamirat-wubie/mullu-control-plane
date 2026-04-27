# Mullu Platform v4.10.0 — MUSIA Runtime (Sliding Window Rate Limits + Quota Persistence)

**Release date:** TBD
**Codename:** Cadence
**Migration required:** No (additive — old snapshots read fine, defaults are unlimited)

---

## What this release is

Two completion-shaped pieces:

1. **Sliding-window write rate limits** — v4.9.0 shipped lifetime construct count quotas. v4.10.0 adds time-windowed write rate limits per tenant. A tenant with `max_writes_per_window=100, window_seconds=60` can write at most 100 constructs in any 60-second window; the 101st write returns HTTP 429 with `Retry-After: <seconds>`.

2. **Quota persistence** — v4.4.0 persisted the construct graph but not the quota. v4.10.0 includes the quota in the same snapshot file. Old snapshots (no quota field) load cleanly with default unlimited quota.

---

## What is new in v4.10.0

### `TenantQuota` rate limit fields

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

```python
@dataclass
class TenantQuota:
    max_constructs: int | None = None         # v4.9.0: lifetime cap
    max_writes_per_window: int | None = None  # v4.10.0: rate cap
    window_seconds: int = 3600                # v4.10.0: window size (default 1h)
```

`TenantState.check_rate_limit_for_write()` returns `(ok, retry_after_seconds, reason)`. The implementation uses a `deque[float]` of write timestamps per tenant, with O(amortized) eviction of expired entries.

`TenantState.record_write()` is called after a successful write to consume a slot. Rate-limited writes do NOT consume a slot — only writes that actually register a construct.

### Write-path checks (cheapest first)

`_governed_write` in constructs.py now runs three gates in order:

1. **Lifetime construct quota** — HTTP 429, `Retry-After: 0` (operator action required to clear)
2. **Sliding-window rate limit** — HTTP 429, `Retry-After: <seconds>` (auto-clears)
3. **Φ_gov / Φ_agent** — HTTP 403 on policy rejection

Cheapest first: a constant-time count check fails before a deque scan, which fails before a Φ_gov evaluation.

### `Retry-After` header carries time-to-availability

For rate-limit 429s, the header carries the integer seconds until the oldest in-window timestamp expires:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 47
Content-Type: application/json

{
  "detail": {
    "error": "tenant rate limit exceeded",
    "reason": "max_writes_per_window quota reached: 100/100 in last 3600s",
    "retry_after_seconds": 47,
    "tenant_id": "acme-corp"
  }
}
```

For lifetime-quota 429s, `Retry-After: 0` since the cap doesn't auto-clear.

### `QuotaPayload` + `QuotaSnapshot` extended

```
PUT /musia/tenants/{id}/quota
{
  "max_constructs": 10000,
  "max_writes_per_window": 100,
  "window_seconds": 60
}
```

`QuotaSnapshot` now reports:
- `max_constructs`, `current_constructs`, `headroom` (v4.9.0)
- `max_writes_per_window`, `window_seconds`, `writes_in_current_window` (v4.10.0)

`writes_in_current_window` reflects post-eviction count — the snapshot endpoint runs a stale-eviction pass before reading the deque length.

### Quota persistence

[persistence.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/persistence.py).

`snapshot_graph()` now accepts an optional `quota=` kwarg. When supplied, the JSON includes:

```json
{
  "quota": {
    "max_constructs": 10000,
    "max_writes_per_window": 100,
    "window_seconds": 60
  }
}
```

`FileBackedPersistence` adds:
- `save(tenant_id, graph, *, quota=None)` — extends the existing `save` with an optional quota
- `load_with_quota(tenant_id) -> tuple[graph, quota_or_None]` — new method returning both
- `load(tenant_id)` (v4.4.0+) still works, returning graph only — back-compat

`TenantedRegistryStore.snapshot_tenant()` and `.load_tenant()` use the new methods if the backend supports them, falling back to v4.4-style graph-only ops if not.

### What is NOT persisted

The deque of recent write timestamps is **transient state**. After a process restart, the deque is empty and rate limits effectively reset. This is the right tradeoff: persisting potentially thousands of timestamps per tenant per hour is not worth the cost, and a process restart is rare relative to write rate.

`test_recent_writes_not_persisted` asserts this invariant.

---

## Test counts

| Suite                                    | v4.9.0  | v4.10.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 585     | 610     |
| Rate limit + quota persistence (new)     | n/a     | 25      |

The 25 new tests cover:
- TenantQuota rate field validation (negatives rejected, zero window rejected)
- Sliding window unit behavior (unlimited, threshold, retry-after calc, eviction, partial eviction, rejected-writes-don't-consume)
- HTTP 429 with retry-after header on rate exhaustion
- Construct quota vs rate limit distinct paths
- Construct quota takes priority when both would block
- Per-tenant rate limit isolation
- QuotaSnapshot includes rate fields
- QuotaPayload Pydantic validation (negative max_writes, zero window)
- Snapshot omits quota field when None
- Snapshot includes quota field when supplied
- restore_quota_from_payload with present/absent quota
- File backend round-trip with and without quota
- Store snapshot/load round-trips quota
- Old (v4.4–v4.9) snapshots load cleanly with default quota
- Recent writes not persisted across snapshot/load

Doc/code consistency check passes.

---

## Compatibility

- All v4.9.0 endpoints unchanged in URL or shape
- `QuotaPayload` extended with optional fields; old single-field payloads still work
- `QuotaSnapshot` extended with new fields; clients that read by-key still find old keys
- `FileBackedPersistence.load()` (graph-only) preserved; new `load_with_quota()` is additive
- v4.4–v4.9 snapshot files load without modification (no `quota` field → default unlimited)
- All 568 v4.9.0 tests pass without modification

---

## Production deployment guidance

### Rate limit provisioning

```python
from mcoi_runtime.substrate.registry_store import STORE, TenantQuota

# Tier 1: 100 writes/min
STORE.get_or_create("tenant-tier-1").quota = TenantQuota(
    max_writes_per_window=100,
    window_seconds=60,
)

# Tier 2: 1000 writes/hr (default window)
STORE.get_or_create("tenant-tier-2").quota = TenantQuota(
    max_writes_per_window=1000,
)
```

Or via HTTP at runtime:

```bash
curl -X PUT https://api/musia/tenants/acme-corp/quota \
     -H "Authorization: Bearer <admin-key>" \
     -d '{"max_writes_per_window": 100, "window_seconds": 60}'
```

### Persistence is now quota-aware

If you previously called `STORE.snapshot_all()` to flush state to disk, **no change is required** — the call now also persists per-tenant quotas. Old snapshot files keep working.

If you call `FileBackedPersistence.save()` directly (Python API), pass the quota explicitly:

```python
backend.save(tenant_id, state.graph, quota=state.quota)
```

The store's snapshot methods do this automatically.

---

## What v4.10.0 still does NOT include

- **JWKS-with-RSA support** — multi-authenticator covers symmetric secret rotation; OIDC-with-asymmetric is a separate workstream.
- **Multi-process backend** — `FileBackedPersistence` is single-process. S3 / postgres backends slot into the same `save/load/load_with_quota` interface.
- **Φ_gov ↔ existing `governance_guard.py`** integration.
- **Rust port** of substrate constructs.
- **Persisting domain runs to construct registry**.
- **Migration runner integration with the live audit log shape**.

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
```

610 MUSIA tests; 102 docs; six domains over HTTP; multi-tenant +
multi-auth-with-rotation + persistent (graph + quota) + scope-enforced +
quota-bounded + rate-limited.

---

## Honest assessment

v4.10.0 closes the rate-limiting gap that v4.9.0 left open. With both
quotas now persistent and rate limits enforced, a deployment can:
- restart without losing per-tenant policy
- bound a misbehaving tenant in both lifetime size and write rate
- expose `Retry-After` to clients so they can back off correctly

What it is not, yet: distributed. The deque is per-process. A
multi-process deployment behind a load balancer would each track its
own deque, so the effective rate would be N × `max_writes_per_window`
for N processes. Single-process or sticky-routed deployments are fine.
True distributed rate limits need a shared counter (Redis, etc.) and
are a separate workstream.

**We recommend:**
- Upgrade in place. v4.10.0 is additive; old snapshots load.
- Provision rate limits at tenant tier creation, not when problems surface.
- For multi-process deployments, plan for the per-process behavior or wait for the distributed-rate-limits release.

---

## Contributors

Same single architect, same Mullusi project. v4.10.0 closes two specific
gaps from v4.9.0 — the rate-limiting half-mention and the quota
persistence omission — without scope creep.
