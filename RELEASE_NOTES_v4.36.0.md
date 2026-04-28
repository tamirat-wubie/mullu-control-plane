# Mullu Platform v4.36.0 — Governance Store Connection Pool (Audit F12)

**Release date:** TBD
**Codename:** Pool
**Migration required:** No (additive — default `pool_size=1` preserves single-conn behavior)

---

## What this release is

Closes the governance-store half of audit fracture **F12** (DB write throughput ceiling).

Pre-v4.36 every PostgreSQL governance store opened a single connection at construction and serialized every read + write behind `self._lock`:

```python
class _PostgresBase:
    def _connect(self) -> None:
        self._conn = psycopg2.connect(self._connection_string)

    # every method:
    with self._lock:
        with self._conn.cursor() as cur:
            cur.execute(...)
            self._conn.commit()
```

Under N concurrent writers (request handlers, audit appends, rate-limit decisions, budget atomic updates) the effective write throughput was bounded by **1 connection × 1 cursor at a time**, regardless of how many vCPUs PostgreSQL had or how many replicas the platform ran. The `self._lock` serialized at the Python layer; the single TCP connection serialized at the libpq layer.

The atomic SQL primitives shipped in v4.27 (budget) / v4.29 (rate limit) / v4.30 (hash chain append) / v4.31 (audit append) all push correctness to the DB. The Python lock was protecting cursor lifecycle on the shared connection — a layer that becomes redundant once each writer has its own connection.

---

## What is new in v4.36.0

### `_PostgresBase`: optional `ThreadedConnectionPool`

Constructors gain a `pool_size: int = 1` keyword:

```python
PostgresBudgetStore(connection_string, pool_size=8)
PostgresAuditStore(connection_string, pool_size=8, field_encryptor=...)
PostgresRateLimitStore(connection_string, pool_size=8)
PostgresTenantGatingStore(connection_string, pool_size=8)
```

Behavior:

| `pool_size` | Behavior |
|---|---|
| `1` (default) | Legacy: single `psycopg2.connect`, all ops serialized via `self._lock` |
| `> 1` | `psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=pool_size)`; `self._connection()` acquires per-op |

`pool_size=0` or negative is clamped to 1.

### `_connection()` context manager

```python
@contextmanager
def _connection(self) -> Iterator[Any]:
    if self._pool is not None:
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
    else:
        with self._lock:
            yield self._conn
```

Every store method that touched `self._conn.cursor()` now does:

```python
with self._connection() as conn:
    with conn.cursor() as cur:
        cur.execute(...)
        conn.commit()
```

13 call sites refactored across `_run_migration` + Budget/Audit/RateLimit/TenantGating store implementations.

### Bootstrap wiring: `MULLU_DB_POOL_SIZE`

`bootstrap_governance_runtime` reads `MULLU_DB_POOL_SIZE` from the runtime env and passes it to `create_governance_stores`:

```yaml
env:
  - MULLU_ENV: production
  - MULLU_ENV_REQUIRED: "true"        # v4.35
  - MULLU_DB_BACKEND: postgresql
  - MULLU_DB_URL: postgresql://...
  - MULLU_DB_POOL_SIZE: "10"          # v4.36
```

Invalid / non-numeric values fall back to 1 with no error (resilience over rigidity for an opt-in performance flag).

### Lifecycle: pool-aware `close` and `_reconnect`

`close()`:
```python
if self._pool is not None:
    self._pool.closeall()
elif self._conn is not None:
    self._conn.close()
```

`_reconnect()` rebuilds the pool from scratch when present (closes old → reopens with same `pool_size`).

---

## What this release is NOT

This PR scopes F12 to the **governance stores** (`postgres_governance_stores.py`). The legacy `postgres_store.py` (ledger / sessions / requests / LLM invocations) keeps single-connection semantics for now. That surface has lower write rates than the governance hot paths and a separate migration plan.

If your deployment writes heavily to `ledger` or `requests`, the legacy bottleneck remains. Watch for `postgres_store.py` in a follow-up release.

---

## Compatibility

- **Default `pool_size=1` is byte-identical to v4.35 behavior.** No change needed for existing deployments.
- The `_PostgresBase._connection()` context manager replaces all direct `self._conn.cursor()` accesses inside the governance stores. External callers don't touch this path.
- Test fixtures that hand-build `_PostgresBase` subclasses without calling `_base_init` work because `_pool` and `_pool_size` have class-level defaults (`None` and `1` respectively).
- `psycopg2.pool` is part of the `psycopg2-binary` package — no new dependency.

---

## Test counts

14 new tests in [`test_v4_36_governance_pool.py`](mullu-control-plane/mcoi/tests/test_v4_36_governance_pool.py):

- `TestPoolInit` — 4 tests (pool_size=1 single conn; pool_size>1 ThreadedConnectionPool; clamping for 0 and negative)
- `TestPoolAcquireRelease` — 3 tests (acquire/release on pool path; release-on-exception; legacy lock serialization)
- `TestPoolLifecycle` — 2 tests (close calls closeall; reconnect rebuilds pool)
- `TestFactoryPoolSize` — 2 tests (factory passes pool_size to all 4 stores; default pool_size=1)
- `TestBootstrapEnvWiring` — 3 tests (`MULLU_DB_POOL_SIZE=12`, invalid value falls back to 1, unset → 1)

Full mcoi suite: **48,605 passed, 26 skipped, 0 failures** (no regression vs v4.35 baseline). The pool path is exercised end-to-end via mocked `psycopg2.pool`.

---

## Production deployment guidance

### Sizing the pool

- `MULLU_DB_POOL_SIZE` defaults to `1`. Set it explicitly for production
- Reasonable starting point: `2 × expected_concurrent_writers / 4 stores` ≈ 5–10 per store
- **Total PostgreSQL connections = 4 stores × pool_size** — make sure your PostgreSQL `max_connections` budget covers this across all replicas
- Example: 3 replicas × 4 stores × pool_size=10 = 120 connections to PG. Most managed PostgreSQL services default to 100–200; Aurora can go higher

### Watch for

- Connection pool exhaustion → `getconn` blocks. Monitor `governance store pool putconn failed` / `governance store pool close failed` in logs
- Long-running transactions holding pool connections → other callers wait. Audit queries that don't commit promptly
- PostgreSQL `idle_in_transaction_session_timeout` > pool keepalive → pool may serve stale connections

### Rolling forward

1. Deploy v4.36 with `MULLU_DB_POOL_SIZE` unset (or `=1`) — byte-identical to v4.35
2. Confirm release stability for at least one bake period
3. Set `MULLU_DB_POOL_SIZE=5` (small bump). Watch DB connection metrics
4. Increase to your tuned target

---

## Production-readiness gap status

```
✅ F2  atomic budget                   — v4.27.0
✅ F3  audit checkpoint anchor         — v4.28.0
✅ F11 atomic rate limit (tenant)      — v4.29.0
✅ F15 atomic hash chain append        — v4.30.0
✅ F4  atomic audit append             — v4.31.0
✅ F9 + F10 unified SSRF + pin         — v4.32.0
✅ JWT hardening (Audit Part 3)        — v4.33.0
✅ F11 atomic rate limit (identity)    — v4.34.0  (parallel track)
✅ F5 + F6 env + tenant binding        — v4.35.0
✅ F12 governance store pool           — v4.36.0  ← this PR
⏳ F12 ledger/requests pool            — follow-up
⏳ F7 governance module sprawl         — architectural
⏳ F8 MAF substrate disconnect         — README mitigated; PyO3 weeks
```

Governance hot path now scales horizontally. Remaining open: legacy ledger/requests pool (smaller scope follow-up), F7 module sprawl (architectural), F8 MAF (PyO3 work).

---

## Honest assessment

v4.36 is moderate (~150 LoC source + ~330 LoC tests). The actual change is small once the pattern is in place — the surface area is the 13 call sites that all do the same thing. The interesting design decision was making the lock semantics fall out automatically:

- Pool path: no `self._lock` (each conn is independent; atomic SQL handles correctness)
- Single-conn path: `self._lock` lives inside `_connection()` so callers don't need to know

This means `_connection()` is the only place that knows about pooling. Every store method is uniform regardless of mode. Test coverage rides the same code path for both.

The lesson: **the v4.27/v4.29/v4.30/v4.31 atomic-SQL series weren't just about correctness under contention — they were the prerequisite that lets us drop the Python global lock in favor of per-connection isolation.** Without the atomic UPDATEs, dropping the lock would race writers against the same row in the same transaction window. With them, the DB is the source of truth and the pool is purely a throughput multiplier.

**We recommend:**
- Upgrade in place. Default `pool_size=1` is identical to v4.35
- Bake for one release cycle, then opt into `MULLU_DB_POOL_SIZE` in production
- Plan a follow-up for the legacy `postgres_store.py` (ledger / sessions / requests) on the same pattern
