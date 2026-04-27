# Mullu Platform v4.27.0 — Atomic Budget Enforcement (Audit F2)

**Release date:** TBD
**Codename:** Atomic
**Migration required:** No (additive — legacy stores fall through to existing path)

---

## What this release is

Closes audit fracture **F2**: budget enforcement was last-write-wins
under concurrent writes. The audit's worked example:

> Two replicas read `spent=$5` simultaneously, each compute `$5 + $1 =
> $6`, each UPSERT `$6`. Real spend `$7`, stored `$6`. The hard limit
> was, in practice, soft by N (replicas × in-flight requests).

The platform's stated invariant is **"hard budget enforcement — no
soft limits."** Pre-v4.27, that wasn't enforced under concurrency.
v4.27 enforces it.

---

## What is new in v4.27.0

### `BudgetStore.try_record_spend(tenant_id, cost, tokens)`

[`tenant_budget.py`](mullu-control-plane/mcoi/mcoi_runtime/core/tenant_budget.py).

New optional method on the `BudgetStore` base class. Implementations
provide atomic test-and-update at the storage layer:

- Returns `LLMBudget` reflecting post-update state when the spend is allowed.
- Returns `None` when `current_spent + cost > max_cost` (exhaustion).
- Concurrent callers race the underlying atomic primitive. At most
  `floor((max_cost - initial_spent) / cost)` succeed; the rest see
  `None`.

The base class default returns `None` to signal "store doesn't
implement the atomic path"; the manager falls back to the legacy
read-modify-write path. Production stores override.

### `InMemoryBudgetStore.try_record_spend` — `threading.Lock`-guarded CAS

[`postgres_governance_stores.py`](mullu-control-plane/mcoi/mcoi_runtime/persistence/postgres_governance_stores.py).

```python
def try_record_spend(self, tenant_id, cost, tokens=0):
    with self._lock:
        current = self._budgets.get(tenant_id)
        if current is None or current.spent + cost > current.max_cost:
            return None
        # ... build updated, store, return
```

Single-process atomic. (Cross-process replicas need the Postgres path.)

### `PostgresBudgetStore.try_record_spend` — atomic SQL UPDATE

```sql
UPDATE governance_budgets
SET spent = spent + $1,
    calls_made = calls_made + 1,
    updated_at = $2
WHERE tenant_id = $3
  AND spent + $1 <= max_cost
RETURNING budget_id, tenant_id, max_cost, spent,
          max_tokens_per_call, max_calls, calls_made
```

The DB row is the only source of truth. The `WHERE` clause atomically
rejects spends that would exceed `max_cost`. `RETURNING` gives the
caller the post-update state in the same statement. Zero rows
returned → exhaustion.

The pre-v4.27 UPSERT (`spent = EXCLUDED.spent`) wrote whatever value
Python computed; this UPDATE never trusts the Python snapshot for the
write decision.

### `TenantBudgetManager.record_spend` prefers the atomic path

```python
def record_spend(self, tenant_id, cost, tokens=0):
    if cost < 0.0:
        raise ValueError("cost must be non-negative")
    self.ensure_budget(tenant_id)  # auto-create the row

    if self._store is not None:
        updated = self._store.try_record_spend(tenant_id, cost, tokens)
        if updated is not None:
            self._budgets[tenant_id] = updated  # refresh cache
            return updated
        # None means: real implementation rejected → exhausted,
        # OR base class signaling "no atomic path" → fall through.
        # Distinguished by: did this store override try_record_spend?
        if type(self._store).try_record_spend is not BudgetStore.try_record_spend:
            raise ValueError("budget exhausted")
    # Legacy path: read-modify-write
    ...
```

---

## Compatibility

### What stays the same

- All `record_spend` callers continue to work. The signature is unchanged.
- `BudgetStore` subclasses that don't override `try_record_spend` fall through
  to the legacy path automatically (verified by test).
- The legacy path still enforces `max_cost` correctly under single-process
  load — it just isn't atomic across replicas. That part of the contract
  was always there; the atomic path is strictly stronger.

### What changes

- `BudgetStore` gains an optional method `try_record_spend`. Existing
  custom subclasses (in pilots / forks / tests) without this method
  inherit the base class no-op implementation. The manager's type
  check (`type(self._store).try_record_spend is not BudgetStore.try_record_spend`)
  detects override status and routes accordingly.
- `PostgresBudgetStore` no longer goes through `save()` for `record_spend`.
  External callers that explicitly call `save()` to persist a manually
  constructed `LLMBudget` continue to work — the UPSERT path is
  unchanged. Only the manager's spend-recording path uses the new atomic
  UPDATE.

### Cross-replica behavior

The pre-v4.27 cross-replica race window collapses to zero with
`PostgresBudgetStore.try_record_spend`: the SQL `WHERE spent + $1 <=
max_cost` is enforced by the DB, no matter how many replicas race.
The audit's worked example ($5 baseline, $1 spend, two replicas) now
results in:

- Replica A: `UPDATE … WHERE 5 + 1 <= 10` → succeeds, returns `spent=6`
- Replica B: `UPDATE … WHERE 6 + 1 <= 10` → succeeds, returns `spent=7` (or fails if max=6)

Strict serialization at the DB row.

### In-memory single-process

The `threading.Lock` in `InMemoryBudgetStore.try_record_spend` makes
the in-memory path race-free within one process. Tests verify 100
concurrent threads × $1 against a $10 budget result in exactly $10
final spent — no overrun, regardless of OS scheduling.

---

## Test counts

| Suite                                    | v4.26.0 | v4.27.0 |
| ---------------------------------------- | ------- | ------- |
| Existing `test_tenant_budget`            | 17      | 17      |
| New atomic budget concurrency tests      | n/a     | 16      |

The 16 new tests in [`test_v4_27_atomic_budget.py`](mullu-control-plane/mcoi/tests/test_v4_27_atomic_budget.py) cover:

**Base class contract (2)**
- `BudgetStore.try_record_spend` returns None (signals legacy fallback)
- Manager with base store falls back to legacy path successfully

**`InMemoryBudgetStore` semantics (5)**
- Returns updated budget on success
- Returns None on `would-exceed-max`
- Returns None for unknown tenant
- Boundary: `spent + cost == max_cost` succeeds (uses `<=`)
- Boundary: `spent + cost > max_cost` by 0.0001 rejects

**Concurrency (the F2 fix in action) (4)**
- 100 threads × $1 against $10 → exactly 10 succeed, 90 fail, final = $10
- Mixed costs ($1 + $5) under contention never overruns
- Pre-exhausted budget: 50 concurrent attempts all fail
- Two tenants' budgets independent under shared concurrency

**Manager-level integration (3)**
- `record_spend` uses atomic store path when available
- Manager raises `budget exhausted` when atomic path returns None
- 50 threads through `manager.record_spend` exactly cap at $10

**Backward compatibility (2)**
- Custom legacy store (no `try_record_spend` override) falls through
- Legacy path still enforces `max_cost` (single-process correctness)

All 17 existing tenant_budget tests still pass.

---

## Production deployment guidance

### Postgres deployments

The `PostgresBudgetStore` change is automatic — no operator action.
The new atomic UPDATE replaces the read-modify-write path that pre-v4.27
deployments were silently using.

The DB schema is unchanged. The new SQL uses existing columns
(`spent`, `max_cost`, `calls_made`, `updated_at`).

### SQLite / in-memory deployments

The `InMemoryBudgetStore` is the default for single-instance pilot
deployments. The new atomic path is single-process; multi-worker
uvicorn or multi-replica deployments need the Postgres backend to
get cross-process atomicity.

### Custom budget stores

If you have a forked `BudgetStore` subclass:
1. Without changes: it falls through to the legacy path (works as before).
2. To enable atomic enforcement: override `try_record_spend` with a
   storage-appropriate atomic primitive (compare-and-swap, conditional
   UPDATE, optimistic locking).

---

## What v4.27.0 still does NOT include

Audit fractures explicitly NOT closed by this PR (each gets its own
dedicated PR):

- **F1** routers without `/api/` prefix bypass middleware (mostly closed
  by v4.26 musia_auth wiring; remaining cleanup is structural)
- **F3** audit chain `verify_chain` invalid after first prune (needs
  checkpoint hash table)
- **F4** audit chain forks per worker (needs DB-side sequence)
- **F8** MAF substrate disconnect (architectural decision, not a fix)
- **F9/F10** webhook SSRF + DNS rebinding (security hardening)
- **F11** per-process rate limiter (needs Redis or DB-backed token bucket)
- **F12** per-store mutex throughput ceiling (needs connection pooling)
- **F15** filesystem hash chain TOCTOU (needs flock or SQLite-backed)
- **JWT module hardening** (empty-claim reject, HTTPS-only `jwks_url`,
  `iat` validation)

---

## Honest assessment

v4.27 is small (~80 LoC source + ~310 LoC tests). The fix being small
makes the bug worse, again — this is an audit-recommended one-line SQL
change wrapped in a tiny method, with most of the diff being tests.
The bug existed because the read-modify-write pattern in `record_spend`
treated the in-memory snapshot as authoritative, which is wrong under
any non-trivial concurrency.

The structural lesson: storage-layer atomicity is a contract that
should be **stated** in the `BudgetStore` API. Pre-v4.27 the API
implied "stores will somehow keep data consistent"; v4.27 names the
guarantee explicitly with `try_record_spend`. Storages that can
provide it do; ones that can't say so by leaving the base method
unoverridden.

**We recommend:**
- Upgrade in place. v4.27 is additive.
- Postgres deployments get the fix automatically.
- If you have a custom `BudgetStore` subclass, audit it for whether
  `try_record_spend` should be overridden (it should, for production).
