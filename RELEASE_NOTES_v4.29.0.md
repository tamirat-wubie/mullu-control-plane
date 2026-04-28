# Mullu Platform v4.29.0 — Atomic Rate Limit Enforcement (Audit F11)

**Release date:** TBD
**Codename:** Bucket
**Migration required:** No (additive — legacy stores fall through to existing path)

---

## What this release is

Closes audit fracture **F11**: the rate limiter was per-process. The
`RateLimiter` kept `TokenBucket` instances in `self._buckets` per
`(tenant, endpoint)`. Single-process atomicity was correct
(`TokenBucket` guards refill+check+decrement under a `threading.Lock`).
Across replicas/workers, each process held its own bucket — N replicas
effectively multiplied the configured `max_tokens` by N. The
`RateLimitStore` was an observability sink only (`record_decision`).

The platform's stated invariant is **"per-tenant rate limits — one
tenant cannot starve others."** Pre-v4.29, that was true within a
process; across replicas the limit became `N × max_tokens`.

v4.29 introduces the contract that closes the gap. The Postgres/Redis
implementation that fully closes F11 cross-replica is the next PR;
v4.29 lands the API, the in-memory atomic reference path, and the
dispatcher.

---

## What is new in v4.29.0

### `RateLimitStore.try_consume(bucket_key, tokens, config)`

[`rate_limiter.py`](mullu-control-plane/mcoi/mcoi_runtime/core/rate_limiter.py).

New optional method on the `RateLimitStore` base class. Implementations
provide atomic test-and-consume at the storage layer:

- Returns `(True, remaining)` when the consume succeeds.
- Returns `(False, remaining)` when the store enforces denial.
- Returns `None` to signal "store does not implement an atomic path;
  caller falls through to the in-memory `TokenBucket`."

The base class returns `None`. The `RateLimiter` uses the same MRO
override-detection idiom as v4.27 `BudgetStore.try_record_spend`:

```python
store_owned = (
    self._store is not None
    and getattr(type(self._store), "try_consume",
                RateLimitStore.try_consume)
    is not RateLimitStore.try_consume
)
```

The `getattr` default handles duck-typed stores (no inheritance from
`RateLimitStore`) — they fall through to the in-memory path
unchanged.

### `InMemoryRateLimitStore.try_consume` — `threading.Lock`-guarded bucket

[`postgres_governance_stores.py`](mullu-control-plane/mcoi/mcoi_runtime/persistence/postgres_governance_stores.py).

```python
def try_consume(self, bucket_key, tokens, config):
    if tokens > config.burst_limit:
        # ... return (False, current)
    with self._bucket_lock:
        # refill by elapsed time
        # if current >= tokens: decrement, return (True, current)
        # else: return (False, current)
```

Single-process atomic. The lock spans refill + check + decrement so
concurrent callers strictly serialize at the bucket — no
last-write-wins window. (Cross-process replicas need the Postgres or
Redis path, deferred to its own PR.)

### `RateLimiter.check` prefers the atomic path

```python
if store_owned:
    outcome = self._store.try_consume(tenant_key, tokens, tenant_config)
    if outcome is None:
        # An overriding store must not return None — that sentinel
        # is reserved for the base. Treat defensively as denied.
        allowed, remaining = False, 0.0
    else:
        allowed, remaining = outcome
else:
    # Legacy path: in-memory TokenBucket per (tenant, endpoint).
    ...
```

Identity-level dispatch (the dual-gate path) keeps the in-memory
`TokenBucket`. F11 for identity-level is its own PR.

---

## Compatibility

### What stays the same

- All `RateLimiter.check` callers continue to work. The signature is
  unchanged.
- `RateLimitStore` subclasses without `try_consume` fall through to
  the in-memory path automatically (verified by test).
- Duck-typed stores (test fixtures, mocks, third-party adapters that
  don't inherit `RateLimitStore`) keep working — `getattr` with a
  default treats them as "no override."
- `record_decision` and `get_counters` semantics are unchanged. The
  observability path runs alongside the enforcement path.
- Identity-level enforcement uses the in-memory `TokenBucket`. No
  behavior change.

### What changes

- `RateLimitStore` gains an optional method `try_consume`. Base class
  default returns `None`.
- `InMemoryRateLimitStore` now owns token-bucket state. When supplied
  to a `RateLimiter`, the limiter delegates tenant-level enforcement
  to the store. Limiter `_buckets` stays empty for store-owned keys.
- The pre-v4.29 in-memory enforcement path remains for: (a) limiters
  with no store, (b) limiters with stores that don't override
  `try_consume`. Behavior in those configurations is byte-identical.

### Cross-replica behavior

In-memory `try_consume` is single-process atomic.
`PostgresRateLimitStore` does **not** yet override `try_consume` in
v4.29 — it remains a counter sink. Cross-replica enforcement requires
the next PR, which will add:

```sql
UPDATE governance_rate_buckets
SET tokens = LEAST($max_tokens,
                   tokens + EXTRACT(EPOCH FROM ($now - last_refill)) * $refill_rate)
              - $consume,
    last_refill = $now
WHERE bucket_key = $key
  AND LEAST($max_tokens,
            tokens + EXTRACT(EPOCH FROM ($now - last_refill)) * $refill_rate)
      >= $consume
RETURNING tokens
```

The DB row becomes the only source of truth; `WHERE` enforces atomic
denial. Schema migration adds `governance_rate_buckets(bucket_key,
tokens, last_refill)`.

---

## Test counts

| Suite                                    | v4.28.0 | v4.29.0 |
| ---------------------------------------- | ------- | ------- |
| Existing rate-limit suites (5 files)     | 134     | 134     |
| New atomic rate limit tests              | n/a     | 16      |

The 16 new tests in [`test_v4_29_atomic_rate_limit.py`](mullu-control-plane/mcoi/tests/test_v4_29_atomic_rate_limit.py) cover:

**Base class contract (2)**
- `RateLimitStore.try_consume` returns None (signals legacy fallback)
- Limiter with base store falls through to in-memory bucket

**`InMemoryRateLimitStore` semantics (5)**
- Initial call initializes a full bucket
- Drain then deny
- Burst limit rejects oversized consumes
- Independent keys do not interfere
- Refill over time restores capacity (capped at `max_tokens`)

**Concurrency (the F11 fix in action) (4)**
- 100 threads × 1 token against `max_tokens=10` → exactly 10 succeed
- Two keys' buckets stay independent under shared concurrency
- Pre-exhausted bucket: 50 concurrent attempts all fail
- 50 threads through `RateLimiter.check` exactly cap at 10

**Dispatch (3)**
- Limiter uses the store when overridden; `_buckets` stays empty
- Limiter falls through to in-memory when store doesn't override
- Limiter with no store uses in-memory path (unchanged)

**Backward compatibility (2)**
- Existing `InMemoryRateLimitStore.record_decision` semantics intact
- Legacy subclass without `try_consume` override falls through

All 134 existing rate-limit tests still pass. Full mcoi suite:
**47,927 passed, 26 skipped** — no regressions.

---

## Production deployment guidance

### In-memory / pilot deployments

The `InMemoryRateLimitStore` upgrade is automatic — no operator
action. Limiters that already use it gain store-owned bucket state
with the same single-process atomic guarantee the previous
`TokenBucket` path provided.

### Postgres deployments

`PostgresRateLimitStore` does not yet override `try_consume`.
Limiters using it continue to enforce via the in-memory `TokenBucket`
path (per-process). Cross-replica F11 closure is deferred to the
next PR. **Operator-visible behavior in v4.29 is unchanged** for
Postgres-backed deployments.

### Custom rate limit stores

If you have a forked `RateLimitStore` subclass:
1. Without changes: it falls through to the in-memory path (works as
   before).
2. To enable atomic enforcement: override `try_consume` with a
   storage-appropriate atomic primitive (Redis Lua script, SQL
   conditional UPDATE, optimistic locking).

---

## What v4.29.0 still does NOT include

Audit fractures explicitly NOT closed by this PR:

- **F11 (Postgres path)** — schema + atomic SQL UPDATE for cross-replica
  enforcement. Next PR.
- **F11 (identity-level)** — dual-gate dispatch through the store for
  per-identity buckets. Next PR.
- **F1** routers without `/api/` prefix bypass middleware
- **F4** audit chain forks per worker
- **F8** MAF substrate disconnect
- **F9/F10** webhook SSRF + DNS rebinding
- **F12** per-store mutex throughput ceiling
- **F15** filesystem hash chain TOCTOU
- **JWT module hardening**

(F2 closed in v4.27. F3 closed in v4.28.)

---

## Honest assessment

v4.29 is small (~70 LoC source + ~270 LoC tests). It does **not**
fully close F11 — it lands the contract and the in-memory reference
implementation. The Postgres/Redis path that closes the cross-replica
window is its own PR (a non-trivial schema migration + atomic SQL
that needs its own integration test surface).

The structural value: storage-layer atomicity for rate limits is now
a **named contract** in the `RateLimitStore` API, not an unstated
expectation. Stores that can provide it do; ones that can't say so by
leaving the base method unoverridden. The duck-typed `getattr` default
in the dispatcher means third-party stores without `RateLimitStore`
inheritance keep working unchanged — capability is detected, not
declared.

This is the v4.27 pattern, applied to a structurally identical
fracture: budget enforcement (F2, money bucket) and rate limit
enforcement (F11, token bucket) both reduce to "atomic test-and-update
at the storage layer." Once one is named, the other becomes the same
shape.

**We recommend:**
- Upgrade in place. v4.29 is additive.
- In-memory deployments get the store-owned bucket automatically.
- Postgres deployments are unchanged in v4.29; expect the cross-replica
  closure in the next release.
- If you have a custom `RateLimitStore`, audit whether `try_consume`
  should be overridden (it should, for production multi-replica).
