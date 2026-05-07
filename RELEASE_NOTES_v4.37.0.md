# Mullu Platform v4.37.0 — Primary Store Connection Pool (Audit F12 follow-up)

**Release date:** TBD
**Codename:** Pool II
**Migration required:** No (additive — default `pool_size=1` preserves single-conn behavior)

---

## What this release is

Closes the primary-store half of audit fracture **F12** (DB write throughput ceiling).

v4.36 closed F12 for the four governance stores (`postgres_governance_stores.py`). v4.37 applies the same `ThreadedConnectionPool` pattern to the primary persistence store (`postgres_store.py`) which holds:

- Ledger entries (proof receipts, governance decisions)
- Session records
- HTTP request audit
- LLM-invocation tracking

Pre-v4.37 `PostgresStore` accepted a `pool_size` kwarg but stored a single `psycopg2.connect` regardless — the default `pool_size=5` was advertising-only. Worse, the legacy single-conn path had **no thread-safety**: concurrent callers could race `self._conn.cursor()` on the shared connection, which is undefined behavior under libpq.

---

## What is new in v4.37.0

### `PostgresStore`: real pool + lock

Constructor unchanged (still accepts `pool_size`), but now actually uses it:

```python
PostgresStore(connection_string, pool_size=10)
```

Default changed from `5` → `1` to be explicit about the legacy posture. Operators previously passing `pool_size=5` (or relying on the default) will get a real 5-conn pool; behavior is strictly better (more parallelism), but if you want the old "single conn pretending to be a pool" behavior, pass `pool_size=1`.

### `_connection()` context manager

Same shape as v4.36's `_PostgresBase._connection()`:

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
        # Lazy-init self._lock for test fixtures that bypass __init__
        lock = getattr(self, "_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._lock = lock
        with lock:
            yield self._conn
```

14 call sites refactored from `with self._conn.cursor() as cur:` to `with self._connection() as conn, conn.cursor() as cur:`.

### Thread-safety on legacy path

Previously `PostgresStore` had no `self._lock`. Concurrent callers — request middleware, audit appends, LLM invocation logging — could race cursor creation. v4.37 adds the lock for `pool_size=1` deployments.

The lazy-init pattern means tests that hand-build `PostgresStore` via `__new__` (skipping `__init__`) still work — `_connection()` creates the lock on first use.

### `MULLU_DB_POOL_SIZE` applies to the primary store too

`bootstrap_primary_store` now reads the same env var as v4.36:

```yaml
env:
  - MULLU_DB_BACKEND: postgresql
  - MULLU_DB_URL: postgresql://...
  - MULLU_DB_POOL_SIZE: "10"        # both governance + primary stores
```

Memory backend ignores `pool_size` (kwarg not passed for `backend="memory"`).

### Pool-aware `close()`

```python
def close(self):
    if self._pool is not None:
        self._pool.closeall()
    elif self._conn is not None:
        self._conn.close()
```

---

## Compatibility

- **Default `pool_size=1`** is byte-identical to v4.36 (single connection). Combined with the new lock, this is *strictly safer* than v4.36 — concurrent callers no longer race.
- The previous default `pool_size=5` was advertising-only (single conn was always used). Operators who explicitly set `pool_size=5` will now get a real 5-connection pool. This is the intent that was always documented; the implementation just caught up.
- Total PG connections under v4.36 + v4.37: `(4 governance stores + 1 primary store) × pool_size = 5 × pool_size`. Size your PG `max_connections` accordingly.
- `psycopg2.pool.ThreadedConnectionPool` ships with `psycopg2-binary` — no new dependency.

---

## Test counts

19 new tests in [`test_v4_37_ledger_pool.py`](mullu-control-plane/mcoi/tests/test_v4_37_ledger_pool.py):

- `TestPoolInit` — 5 tests (default → single conn; `pool_size > 1` → ThreadedConnectionPool; clamping for 0 and negative parametrized)
- `TestPoolAcquireRelease` — 3 tests (acquire/release on pool path; release-on-exception; legacy lock serialization)
- `TestPoolLifecycle` — 2 tests (close calls `closeall`; legacy close calls `_conn.close()`)
- `TestFactoryWiring` — 1 test (`create_store` forwards `pool_size`)
- `TestBootstrapEnvWiring` — 3 tests (`MULLU_DB_POOL_SIZE=12`, memory-backend skip, invalid value falls back)
- `TestOperationsUseConnection` — 5 smoke tests (every public mutation method actually goes through `_connection()`)

All 33 pre-existing `test_postgres_store` tests still pass; 53 governance-store tests still pass; full mcoi suite at 48,632 passed (up from 48,605 baseline).

---

## Production deployment guidance

### After upgrading from v4.36 → v4.37

Same env var (`MULLU_DB_POOL_SIZE`) now controls both governance and primary store pools. Total connection footprint:

```
total_pg_connections = replicas × (4 + 1) × MULLU_DB_POOL_SIZE
```

For a 3-replica deployment with `MULLU_DB_POOL_SIZE=10`: `3 × 5 × 10 = 150` connections to PostgreSQL.

### Watch for

- `postgres store pool putconn failed` — connection unhealthy, pool tried to return it
- `postgres store pool close failed` — pool closeall raised during shutdown
- `postgres store connection failed` — initial connect failed; store falls back to `_conn = None` (operations no-op)

---

## Production-readiness gap status

```
✅ F2  atomic budget                   — v4.27.0
✅ F3  audit checkpoint anchor         — v4.28.0
✅ F4  atomic audit append             — v4.31.0
✅ F5 + F6 env + tenant binding        — v4.35.0
✅ F9 + F10 unified SSRF + pin         — v4.32.0
✅ F11 atomic rate limit (tenant)      — v4.29.0
✅ F11 atomic rate limit (identity)    — v4.34.0
✅ F12 governance store pool           — v4.36.0
✅ F12 primary store pool              — v4.37.0  ← this PR
✅ F15 atomic hash chain append        — v4.30.0
✅ F16 musia_auth wiring               — v4.26.0
✅ JWT hardening (Audit Part 3)        — v4.33.0
⏳ F7 governance module sprawl         — architectural
⏳ F8 MAF substrate disconnect         — README mitigated; PyO3 weeks
```

**F12 fully closed.** Both governance + primary stores now scale via per-store connection pools controlled by a single env var.

Remaining open: F7 (architectural — module reorganization), F8 (PyO3 substrate bridge — multi-week effort). Both are out-of-scope for the contained-fracture autopilot loop.

---

## Honest assessment

v4.37 is small (~80 LoC source + ~310 LoC tests) — almost a copy-paste of v4.36, applied to a sibling file with the same shape. The substantive value comes in three places:

1. **The `pool_size` default went from advertising (`5`) to honest (`1`).** Operators who set it explicitly will see real parallelism for the first time.
2. **The legacy path got a lock.** Cursor creation on a shared connection is undefined behavior; the missing lock was a pre-existing thread-safety bug. The fact that no test caught it means concurrent access patterns in existing deployments were rarely contested — but the bug was real.
3. **Single env var controls all 5 pools.** No per-store tuning needed for typical deployments; one `MULLU_DB_POOL_SIZE` covers governance + primary.

The lesson, restating v4.36's: **the v4.27/v4.29/v4.30/v4.31 atomic-SQL series is what makes pool-based scale-out safe.** Without atomic UPDATEs, dropping the global lock for parallel writers would race them on the same row in the same transaction. With them, the DB is the source of truth and the pool is purely a throughput multiplier.

**We recommend:**
- Upgrade in place. Default `pool_size=1` is byte-identical to v4.36 plus thread-safety
- Operators using `MULLU_DB_POOL_SIZE > 1` should now see real parallelism on ledger / session / request writes (not just governance)
- Plan PG `max_connections` for `replicas × 5 × pool_size`
- After v4.37, the autopilot loop has closed every contained audit fracture. Remaining work is architectural (F7) or multi-week infrastructure (F8 MAF substrate)
