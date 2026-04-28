# Mullu Platform v4.31.0 — Atomic Audit Append (Audit F4)

**Release date:** TBD
**Codename:** Linear
**Migration required:** No (additive — legacy stores fall through to existing path)

---

## What this release is

Closes audit fracture **F4**: every `AuditTrail` instance kept its
own `_sequence` counter starting at 0 and its own `_last_hash`
starting at genesis. Two workers (multi-process uvicorn, multi-replica)
writing to the same shared store each produced `sequence=1, 2, 3, ...`
independently, with each worker's `previous_hash` chain reflecting
only the entries **it** had written.

Result: a forked chain. The persisted log contained two distinct
entries at every sequence, each linked to a different predecessor.
External `verify_chain_from_entries` saw "previous_hash mismatch"
on the first cross-worker entry. The audit log was, in practice,
multiple parallel chains stitched together by sort-by-sequence
rather than one tamper-evident sequence.

The platform's stated invariant is **"hash chain links each entry
to the previous — tampering is detectable."** Pre-v4.31, that was
true within one worker, and false across workers.

This is the **fourth application** of the v4.27 atomic-test-and-update
pattern (after v4.27 budget, v4.29 rate limit, v4.30 hash chain).
Same shape: name the contract, override-detection dispatch,
in-memory atomic reference + tests, defer storage-backend to next PR.

---

## What is new in v4.31.0

### `AuditStore.try_append(*, action, actor_id, ..., recorded_at)`

[`audit_trail.py`](mullu-control-plane/mcoi/mcoi_runtime/core/audit_trail.py).

New optional method on the `AuditStore` base class. Implementations
override it to atomically allocate the next sequence, read the chain
head for `previous_hash`, compute `entry_hash` via the canonical v1
helper, persist the entry, and return it.

The base class returns `None` to signal "no atomic path; caller
falls through to the in-process per-AuditTrail counter."

### `InMemoryAuditStore.try_append` — `threading.Lock`-guarded

[`postgres_governance_stores.py`](mullu-control-plane/mcoi/mcoi_runtime/persistence/postgres_governance_stores.py).

```python
with self._append_lock:
    sequence = self._sequence + 1
    previous_hash = self._last_hash
    # ... compute entry_hash via _canonical_hash_v1 ...
    entry = AuditEntry(...)
    self._entries.append(entry)
    self._sequence = sequence
    self._last_hash = entry_hash
    return entry
```

The lock spans allocate-sequence, read-prev-hash, compute-entry-hash,
persist — so two callers strictly serialize at the store, never
both producing the same sequence with different `previous_hash`.
Single-process atomic. Cross-process replicas need `PostgresAuditStore`,
which is **not** included in v4.31.

### `AuditTrail._record_locked` prefers the atomic path

```python
store_owned = (
    self._store is not None
    and getattr(type(self._store), "try_append", AuditStore.try_append)
    is not AuditStore.try_append
)
if store_owned:
    entry = self._store.try_append(...)
    if entry is None:
        store_owned = False  # base sentinel — fall through

if not store_owned:
    # Existing in-process path: increment self._sequence,
    # compute hash from self._last_hash, build entry, write through.
    ...
else:
    # Store-allocated: sync local cache from response.
    self._sequence = entry.sequence
```

The `getattr` default with `AuditStore.try_append` as the fallback
covers duck-typed stores (no inheritance from `AuditStore`) — they
fall through to the in-process path unchanged. Same idiom as v4.29
RateLimitStore dispatch.

The legacy in-process path is **byte-identical** to pre-v4.31 for
deployments without a store-overriding `try_append`.

---

## Compatibility

### What stays the same

- `AuditTrail.record(...)` signature unchanged. Returns the same
  `AuditEntry`.
- The canonical entry-hash content layout (LEDGER_SPEC.md v1) is
  unchanged. The store's `try_append` calls the same
  `_canonical_hash_v1` helper the in-process path calls; writer/
  verifier drift remains structurally impossible.
- `verify_chain` and `verify_chain_from_entries` semantics unchanged.
- Pruning logic (F3 v4.28 anchor) unchanged — operates on
  `self._entries` regardless of who allocated the sequence.
- `AuditStore` subclasses without `try_append` fall through to the
  legacy `append()` write-through path automatically (verified by
  test).
- Duck-typed stores (test fixtures, mocks, third-party adapters
  that don't inherit `AuditStore`) keep working.

### What changes

- `AuditStore` gains an optional method `try_append`. Base class
  default returns `None`.
- `InMemoryAuditStore` now owns sequence + chain-head state. When
  supplied to an `AuditTrail`, the trail delegates allocation to
  the store. Trail's local `_sequence` and `_last_hash` are synced
  from the store's response (cache).
- `InMemoryAuditStore.append` (the legacy write-through path)
  acquires the new `_append_lock` and updates `_sequence` /
  `_last_hash` if the appended entry is monotonic. This makes
  legacy and atomic paths share consistent storage state.
- `InMemoryAuditStore.__init__` now initializes `_sequence`,
  `_last_hash`, and `_append_lock` in addition to `_entries` and
  `_checkpoint`. No external API change.

### Cross-worker behavior

Single `InMemoryAuditStore` instance shared by multiple
`AuditTrail` instances (in tests / single-process multi-thread
scenarios) now produces a strictly linear chain under concurrency.
For genuine cross-process workers, the in-memory store is
single-process — `PostgresAuditStore.try_append` is the next PR.

The next PR will add SQL roughly:

```sql
WITH last AS (
    SELECT entry_hash FROM governance_audit_entries
    ORDER BY sequence DESC LIMIT 1 FOR UPDATE
)
INSERT INTO governance_audit_entries (
    sequence, previous_hash, entry_hash, ...
)
SELECT
    COALESCE((SELECT MAX(sequence) FROM governance_audit_entries), 0) + 1,
    COALESCE((SELECT entry_hash FROM last), $genesis_hash),
    $client_computed_entry_hash, ...
RETURNING ...
```

(Actual implementation will use `SERIAL`/identity for sequence and
compute `entry_hash` server-side via `pgcrypto`'s `digest()` to
avoid round-tripping the hash, but the structure is the same:
strict serialization at the chain head.)

---

## Test counts

| Suite                                    | v4.30.0 | v4.31.0 |
| ---------------------------------------- | ------- | ------- |
| Existing `test_audit_trail`              | 46      | 46      |
| New atomic audit append tests            | n/a     | 15      |

The 15 new tests in [`test_v4_31_atomic_audit_append.py`](mullu-control-plane/mcoi/tests/test_v4_31_atomic_audit_append.py) cover:

**Base class contract (2)**
- `AuditStore.try_append` returns None (signals legacy fallback)
- `AuditTrail` with base store falls through to in-process path

**`InMemoryAuditStore.try_append` semantics (4)**
- First append starts at sequence 1
- Subsequent append links `previous_hash` to predecessor's `entry_hash`
- `entry_hash` matches `_canonical_hash_v1` recomputation (writer/verifier parity)
- Entries persist in the store's internal list

**Concurrency — the F4 fix in action (3)**
- 50 threads × 1 `try_append` on one store → exactly 50 entries with
  sequences {1..50}, valid `previous_hash` linkage throughout
- **Two `AuditTrail` instances sharing one store** (the F4 worker
  scenario): 25 records each, concurrent → 50 distinct sequences,
  `verify_chain_from_entries` returns valid
- 100 threads through `AuditTrail.record` → 100 distinct sequences

**Dispatch (4)**
- Trail uses store when `try_append` is overridden; local
  `_sequence` and `_last_hash` sync from store's response
- Trail falls through to in-process path when store doesn't override
- Trail with no store uses in-process path (unchanged)
- Duck-typed store (no `AuditStore` inheritance) falls through

**Backward compatibility (2)**
- Direct `InMemoryAuditStore.append(entry)` (legacy write-through)
  still works
- `AuditTrail.record` signature unchanged

All 46 existing audit_trail tests still pass. Audit-related test
surface (605 tests across the codebase): all pass.

---

## Production deployment guidance

### In-memory / pilot deployments

The `InMemoryAuditStore` upgrade is automatic — no operator
action. `AuditTrail` instances using it gain store-owned sequence
allocation with single-process atomic guarantee.

### Postgres deployments

`PostgresAuditStore` does **not** yet override `try_append` in
v4.31. AuditTrails using it continue to allocate sequences
per-process. **Operator-visible behavior in v4.31 is unchanged**
for Postgres-backed deployments. Cross-worker F4 closure is
deferred to the next PR (which will include the schema-side
sequence allocation).

### Custom audit stores

If you have a forked `AuditStore` subclass:
1. Without changes: it falls through to the in-process path (works
   as before; `append()` write-through is unchanged).
2. To enable atomic enforcement: override `try_append` with a
   storage-appropriate atomic primitive (Postgres `FOR UPDATE` +
   conditional INSERT, Redis Lua INCR + SET, etc.).

---

## What v4.31.0 still does NOT include

Audit fractures explicitly NOT closed by this PR:

- **F4 (Postgres path)** — schema + atomic SQL for cross-replica
  sequence allocation. Next PR.
- **F11 (Postgres path)** — atomic SQL UPDATE for cross-replica
  rate limit enforcement.
- **F11 (identity-level)** — dual-gate dispatch through the store.
- **F1** routers without `/api/` prefix bypass middleware
- **F8** MAF substrate disconnect
- **F9/F10** webhook SSRF + DNS rebinding (in progress on this
  branch — separate work)
- **F12** per-store mutex throughput ceiling — different shape
  (throughput, not atomicity); needs connection pooling
- **JWT module hardening**

(F2 closed in v4.27. F3 closed in v4.28. F11-tenant API closed in
v4.29. F15 closed in v4.30.)

---

## Honest assessment — fourth example, pattern crystallizes

v4.31 is small (~80 LoC source + ~290 LoC tests). It does **not**
fully close F4 — it lands the contract and the in-memory reference.
The Postgres path that closes the cross-process window is its own
PR (a non-trivial schema decision around `SERIAL` vs explicit
allocation, plus server-side hash computation via `pgcrypto`).

This is now the **fourth application** of the same pattern across
four structurally distinct stores:

| Fracture | Release | Store kind        | Atomic primitive                      |
| -------- | ------- | ----------------- | ------------------------------------- |
| F2       | v4.27   | Money bucket      | `BudgetStore.try_record_spend`        |
| F11      | v4.29   | Token bucket      | `RateLimitStore.try_consume`          |
| F15      | v4.30   | Filesystem chain  | `HashChainStore.try_append`           |
| F4       | v4.31   | Audit log chain   | `AuditStore.try_append`               |

**Shared shape**: the high-level operation reads state, computes a
new state, and writes — but two callers can race the read-write
window. The fix in every case is:

1. Name the atomic primitive `try_*` on the base class.
2. Base class returns a sentinel (`None`) for "no atomic path."
3. Detect override via MRO with a `getattr` default for duck-typed
   subclasses.
4. The high-level operation either delegates to the override or
   falls through to the legacy in-process path.
5. Tests exercise the primitive deterministically; concurrency
   tests prove the legacy fork no longer happens.

At four examples this is no longer "applying a clever idea" — it's
a doctrine. v4.32+ should consider:

- Extracting a `ContractTestSuite[T]` mixin that any
  override-providing store must pass. Same suite runs against
  InMemory + Postgres + future Redis. Contract violations show up
  at test time, not in production.
- A `docs/ATOMIC_STORE_DOCTRINE.md` that codifies the five steps
  above for future fractures (F12 throughput ceiling won't fit; F8
  MAF substrate is structurally different; but anything else that
  reduces to "atomic test-and-update at storage layer" should
  follow this doctrine).

**We recommend:**
- Upgrade in place. v4.31 is additive.
- In-memory deployments get the store-owned chain automatically.
- Postgres deployments are unchanged in v4.31; expect the cross-
  process closure in the next release.
- Custom `AuditStore` subclasses should audit whether `try_append`
  should be overridden (it should, for production multi-worker).
