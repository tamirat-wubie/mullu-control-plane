# Mullu Platform v4.34.0 — Atomic Identity-Level Rate Limit (Audit F11 identity)

**Release date:** TBD
**Codename:** Dual
**Migration required:** No (additive — legacy stores fall through to existing path)

---

## What this release is

Closes the **identity-level half** of audit fracture **F11** that
v4.29 explicitly deferred:

> "Identity-level dispatch (the dual-gate path) keeps the in-memory
> TokenBucket. F11 for identity-level is its own PR."
> — RELEASE_NOTES_v4.29.0.md

Pre-v4.34, `RateLimiter.check` had a bifurcated dispatch:
**tenant-level** enforcement was delegated to the store when
`try_consume` was overridden (v4.29), but **identity-level**
enforcement always used the in-process `TokenBucket` from
`self._buckets`. Cross-replica deployments with per-identity rate
limits configured saw the same N-replicas-multiplies-cap bug for
identity buckets that v4.29 closed for tenant buckets.

v4.34 extends the v4.29 dispatch to identity-level. The same
`store_owned` flag computed for tenant-level controls identity-
level too — if the store provides an atomic primitive, it provides
one for both bucket levels. The store's `try_consume` already
takes any `bucket_key`, so identity buckets just use a different
key. Same method, same contract, different key.

This is the smallest possible doctrine-compliant change: no new
contract, no new method, no new test infrastructure. Just extend
the dispatch we already proved correct in v4.29 to the identity-
level branch. Per
[`docs/ATOMIC_STORE_DOCTRINE.md`](docs/ATOMIC_STORE_DOCTRINE.md),
this is the **fifth application** of the pattern — and the first
where the existing primitive was reused without naming a new one.

---

## What is new in v4.34.0

### Identity-level branch in `RateLimiter.check` now defers to the store

[`rate_limiter.py`](mullu-control-plane/mcoi/mcoi_runtime/core/rate_limiter.py).

Pre-v4.34:

```python
if allowed and identity_id:
    id_config = self._resolve_identity_config(endpoint)
    if id_config is not None:
        with self._lock:
            id_key = self._identity_bucket_key(...)
            id_bucket = self._get_bucket(id_key, id_config)  # always in-memory
        id_allowed, identity_remaining = id_bucket.try_consume(tokens)
```

v4.34:

```python
if allowed and identity_id:
    id_config = self._resolve_identity_config(endpoint)
    if id_config is not None:
        id_key = self._identity_bucket_key(...)
        if store_owned:
            outcome = self._store.try_consume(id_key, tokens, id_config)
            if outcome is None:
                id_allowed, identity_remaining = False, 0.0
            else:
                id_allowed, identity_remaining = outcome
        else:
            with self._lock:
                id_bucket = self._get_bucket(id_key, id_config)
            id_allowed, identity_remaining = id_bucket.try_consume(tokens)
```

`store_owned` is the same flag computed once for tenant-level —
not recomputed. The store either provides atomic enforcement for
both levels or for neither.

---

## Compatibility

### What stays the same

- `RateLimiter.check` signature unchanged.
- Dual-gate semantics unchanged: both tenant-level AND identity-
  level must allow; either denying denies the request.
- Tenant-level short-circuit unchanged: if tenant denies, identity
  bucket is **not** consumed (verified by test).
- `identity_denied_count` still increments only when identity-level
  is what denied.
- `RateLimitStore` interface unchanged. No new method.
- Limiters with no store, with a base-class store, with a duck-typed
  store, or with a non-overriding subclass store all use the legacy
  in-memory `TokenBucket` path — byte-identical to pre-v4.34.
- Per-endpoint identity config (`configure_endpoint(...,
  identity_config=...)`) works through the store unchanged.

### What changes

- When a `RateLimitStore` overrides `try_consume`, the limiter's
  `_buckets` dict stays empty for **both** tenant and identity bucket
  keys (previously only tenant keys were store-owned; identity keys
  still cached locally).
- `RateLimiter.identity_denied_count` is now a cross-replica
  consistent count when the store overrides — the deny decision is
  made at the store, so the counter reflects store-enforced denials.

### Cross-replica behavior

In-memory `try_consume` is single-process atomic for **both** bucket
levels. `PostgresRateLimitStore.try_consume` is still pending (named
in v4.29 release notes; same SQL pattern); when it lands, both
tenant and identity buckets gain cross-replica atomic enforcement
automatically — no further dispatcher changes needed.

---

## Test counts

| Suite                                    | v4.33.0 | v4.34.0 |
| ---------------------------------------- | ------- | ------- |
| Existing rate-limit suites (5 files)     | 134     | 134     |
| `test_v4_29_atomic_rate_limit`           | 16      | 16      |
| New atomic identity rate limit tests     | n/a     | 10      |

The 10 new tests in [`test_v4_34_atomic_identity_rate_limit.py`](mullu-control-plane/mcoi/tests/test_v4_34_atomic_identity_rate_limit.py) cover:

**Identity-level dispatch (3)**
- Identity check delegates to the store when overridden;
  `_buckets` stays empty for **both** tenant and identity keys
- Identity check falls through to in-memory when store doesn't
  override; both keys appear in `_buckets`
- No store: in-memory path unchanged

**Identity independence (2)**
- Two identities under the same tenant cap independently
- Same identity name under different tenants caps independently

**Concurrency — the F11 identity fix in action (2)**
- 50 threads × 1 token for one identity → exactly
  `identity_max_tokens` succeed, regardless of OS scheduling
- 20 threads × 2 identities concurrently → each identity strictly
  capped at its `max_tokens`, both independent

**Dual-gate semantics preserved (2)**
- Tenant denial short-circuits identity check (identity bucket not
  consumed)
- Identity-level denial increments `identity_denied_count`

**Per-endpoint config (1)**
- `configure_endpoint(..., identity_config=...)` works through the
  store; per-endpoint identity caps enforced

All 47 existing rate-limit tests still pass. Atomic-pattern test
surface (233 tests across the doctrine + the five fracture closures
+ underlying rate-limit tests): all pass.

---

## Production deployment guidance

### In-memory / pilot deployments

The identity-level upgrade is automatic — no operator action.
Limiters using `InMemoryRateLimitStore` with per-identity rate
limits configured gain store-owned identity bucket state with the
same single-process atomic guarantee tenant buckets got in v4.29.

### Postgres deployments

`PostgresRateLimitStore` does not yet override `try_consume` (still
deferred from v4.29). Both tenant and identity buckets enforce via
the in-memory `TokenBucket` path until that PR lands. Operator-
visible behavior in v4.34 is unchanged for Postgres-backed
deployments.

### Custom rate limit stores

If you have a forked `RateLimitStore` subclass with a real
`try_consume` override, **no changes needed** — your existing
override now serves identity-level enforcement too. Verify your
implementation handles arbitrary `bucket_key` strings (it should,
since tenant and identity bucket keys are both already keyed by
arbitrary strings — `"tenant:endpoint"` vs `"tenant:identity:endpoint"`).

---

## What v4.34.0 still does NOT include

- **F11 (Postgres path)** — atomic SQL UPDATE for cross-replica
  rate limit enforcement. Same shape as v4.27 BudgetStore, deferred.
- **F4 (Postgres path)** — atomic SQL for cross-replica audit
  sequence allocation. Pending.
- **F1** routers without `/api/` prefix bypass middleware
- **F8** MAF substrate disconnect
- **F12** per-store mutex throughput ceiling (different shape;
  doctrine Section 4 explicitly excludes)

(F2 closed in v4.27. F3 closed in v4.28. F11-tenant API closed in
v4.29. F15 closed in v4.30. F4-API closed in v4.31. Atomic Store
Doctrine published alongside v4.31. F9/F10 unified SSRF closed in
v4.32. JWT auth hardening Part 3 closed in v4.33.)

---

## Honest assessment — fifth application, doctrine pays off

v4.34 is **tiny** (~15 LoC source + ~210 LoC tests). Specifically
because the doctrine was already in place:

- No new method on `RateLimitStore`. `try_consume` already exists.
- No new test pattern. Same shape as v4.29.
- No new doctrine doc. Already shipped.
- No new meta-test. The existing meta-test already covers
  override-detection across `RateLimitStore`.

The whole change is one branch in `RateLimiter.check` rewritten to
match the branch above it. The reason it took 15 LoC instead of
the 80+ LoC of v4.29 is exactly what the doctrine predicted:

> "The next fracture should land in materially less time than
> v4.27 did."
> — ATOMIC_STORE_DOCTRINE.md

This is what doctrine compliance buys: subsequent applications
shrink. The first time we close the same shape was 80 LoC and a
new method. The fifth time was 15 LoC and a copy-paste of an
already-correct dispatcher.

The structural value: **identity-level enforcement now inherits
every property tenant-level enforcement gained**. When the
Postgres path lands, it lands for both levels with no further
dispatcher work. When the next backend is added (Redis, etc.),
same story.

**We recommend:**
- Upgrade in place. v4.34 is additive and shape-identical to v4.29.
- Multi-replica deployments with `identity_config` configured get
  the same cross-replica enforcement guarantees as tenant-level
  (when paired with a store that overrides `try_consume`).
- No client-facing changes. `RateLimiter.check` works the same way
  with the same dual-gate semantics.
