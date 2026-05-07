# Atomic Store Doctrine — v1

**Status:** Doctrine, distilled from four shipped fracture closures (v4.27, v4.29, v4.30, v4.31).
**Companion documents:** `docs/LEDGER_SPEC.md`, `docs/GOVERNANCE_GUARD_CHAIN.md`
**Last updated:** v4.31.0 (2026-04)

## Purpose

The platform repeatedly hits the same shape of bug:

> Two callers each read state, each compute a new state, each write
> what they computed. They observe the same baseline so they compute
> the same delta. The last writer's value sticks. The "hard"
> invariant the code claimed to enforce was, in practice, soft by
> N callers.

Four audit fractures had this shape:

| Fracture | Release | Stored object       | Lost invariant                             |
| -------- | ------- | ------------------- | ------------------------------------------ |
| F2       | v4.27   | LLM budget          | hard cost cap                              |
| F11      | v4.29   | Rate limit bucket   | per-tenant tokens-per-second               |
| F15      | v4.30   | Filesystem chain    | linear append-only sequence                |
| F4       | v4.31   | Audit log chain     | tamper-evident hash linkage                |

Four examples is enough to call it a pattern. This document codifies
the recipe so a fifth fracture (or a custom store added by a fork)
follows the same shape without rediscovering it.

This is **not** a generic "use locks for concurrency" pamphlet. It
applies specifically to **stores whose contract is "given some
input, atomically test some condition against current state and
update if allowed."** Section 4 names the cases where this doctrine
does NOT apply.

---

## 1. The recipe — five steps

### Step 1. Name the atomic primitive on the base class

Add a method named `try_*` to the store's abstract base class. Its
signature takes the inputs needed to make the atomic decision; its
return type encodes both outcomes (allowed / rejected) and a
sentinel for "this base class doesn't implement an atomic path."

```python
class FooStore:
    def try_record(self, *, ...inputs...) -> ResultType | None:
        """Atomic test-and-update at the storage layer.

        Implementations override this to provide cross-replica
        atomic enforcement. The base class returns ``None`` to
        signal "no atomic path; caller falls through to the
        legacy in-process path."
        """
        return None
```

The sentinel is `None`. The success type carries enough information
for the caller to update its own cache (the new state, the assigned
sequence, the resulting record).

### Step 2. Implement the atomic primitive in concrete stores

Each backend overrides `try_*` with a storage-appropriate atomic
operation:

- **In-memory**: `threading.Lock`-guarded read-check-write.
- **Postgres**: conditional `UPDATE ... WHERE invariant RETURNING ...`,
  or `SELECT ... FOR UPDATE` + INSERT for chain-head allocation.
- **Redis**: Lua script for compound test-and-update.
- **Filesystem**: `O_CREAT | O_EXCL` for create-or-fail semantics.

The lock or atomic primitive **must span** the entire test-and-update
window. Splitting "test" and "update" across two atomic operations
re-introduces the TOCTOU.

The override **must not** return `None` for any reason other than the
"impossible" case where the storage layer has no atomic path —
which never happens for a real implementation. Return the success
type for "allowed," and either return a "denied" success-type
variant or raise for "rejected." `None` is reserved.

### Step 3. Dispatch via MRO override-detection with `getattr` default

The high-level operation prefers the atomic path when the store
overrides `try_*`. Detect override status without inheritance
requirements:

```python
store_owned = (
    self._store is not None
    and getattr(type(self._store), "try_record", FooStore.try_record)
    is not FooStore.try_record
)
```

The `getattr` default is the critical detail: it lets duck-typed
stores (no `FooStore` inheritance) fall through to the legacy path.
Test fixtures, mocks, and third-party adapters that don't subclass
`FooStore` keep working unchanged. Capability is **detected**, not
declared.

`is not` (identity) compares the function objects — not equality.
Subclasses that override get a different function object on the
class; subclasses that inherit get the base class's function object.

### Step 4. The high-level operation either delegates or falls through

```python
if store_owned:
    result = self._store.try_record(...)
    if result is None:
        # Defensive: a real override returned the base sentinel.
        # Treat as denied or fall through, depending on operation
        # semantics. Document the choice.
        ...
    else:
        return result
else:
    # Legacy in-process path: byte-identical to pre-doctrine
    # behavior for callers without a store-overriding try_*.
    ...
```

The legacy path is preserved unchanged. Existing single-process
deployments see no behavior change. New cross-process semantics
are opt-in via the override.

### Step 5. Test the contract

Four test classes per fracture, mirroring the structure of
`test_v4_27_atomic_budget.py` / `test_v4_29_atomic_rate_limit.py` /
`test_v4_30_atomic_hash_chain.py` / `test_v4_31_atomic_audit_append.py`:

1. **Base class contract** — base `try_*` returns None; high-level
   operation with base store falls through to the legacy path.
2. **Atomic primitive semantics** — direct `try_*` calls under
   single-thread; boundary conditions; rejected state.
3. **Concurrency** — N threads × M operations, the invariant the
   pre-doctrine code lost is now strictly enforced (exact cap
   reached, no fork, no overrun).
4. **Dispatch** — override is preferred; non-overriding subclass
   falls through; duck-typed store falls through; no-store case
   uses legacy.
5. **Backward compatibility** — pre-existing API surface intact,
   pre-existing legacy callers work unchanged.

A meta-test (`test_atomic_store_doctrine.py`) asserts steps 1, 3
(getattr-detection), and 4 (dispatch shape) across **all four**
existing stores in one place — catches doctrine violations if
someone breaks the idiom in any of them.

---

## 2. Worked examples

Each closed fracture is a reference implementation. New
implementations should follow whichever example most closely
matches their storage shape.

### Example 1 — F2 / v4.27: `BudgetStore.try_record_spend`

**Shape**: monetary cap. Inputs: `tenant_id`, `cost`, `tokens`.
Returns: `LLMBudget | None`. Postgres path: `UPDATE governance_budgets
SET spent = spent + $1 WHERE spent + $1 <= max_cost RETURNING ...`
— the WHERE clause atomically rejects spends that would exceed
`max_cost`. Reference: [RELEASE_NOTES_v4.27.0.md](../RELEASE_NOTES_v4.27.0.md).

**Notable**: the Postgres path was implemented in the same PR. Path
of least resistance for buckets whose state is a single number.

### Example 2 — F11 / v4.29: `RateLimitStore.try_consume`

**Shape**: token bucket with refill. Inputs: `bucket_key`, `tokens`,
`config`. Returns: `(allowed, remaining) | None`. In-memory path:
`threading.Lock`-guarded refill+check+decrement, store-owned bucket
state. Reference: [RELEASE_NOTES_v4.29.0.md](../RELEASE_NOTES_v4.29.0.md).

**Notable**: bucket state can live either in the limiter or in the
store. When the store overrides, state migrates to the store; the
limiter's `_buckets` dict stays empty for store-owned keys. The
Postgres path was deferred — needs schema migration for `tokens` /
`last_refill` columns.

### Example 3 — F15 / v4.30 + v4.40: `HashChainStore.try_append`

**Shape**: append-only filesystem chain. Inputs: `content_hash`.
Returns: `HashChainEntry | None`. Filesystem atomicity via
`tempfile.mkstemp` + `os.link` — the temp file is fully populated
before being made visible at the target path; `os.link` is atomic
and raises `FileExistsError` on collision (same O_EXCL semantic for
"already exists"). References:
[RELEASE_NOTES_v4.30.0.md](../RELEASE_NOTES_v4.30.0.md),
[RELEASE_NOTES_v4.40.0.md](../RELEASE_NOTES_v4.40.0.md).

**Notable** (1): the only example so far where the high-level
operation (`append`) is a **bounded retry loop** on top of
`try_append`. If two writers compute the same target sequence, the
loser sees `None`, re-reads `latest()`, and retries with the next
sequence. The retry loop is observable, bounded (64 attempts), and
replaceable — callers can use `try_append` directly for strict-fail
semantics.

**Notable** (2 — added v4.40): the v4.30 implementation initially
used `os.open(O_CREAT | O_EXCL | O_WRONLY)` followed by `os.write`.
That left a window between the syscall that created the empty file
and the syscall that wrote bytes — concurrent `latest()` readers
saw a zero-byte file and raised `CorruptedDataError`. v4.40 fixed
this by writing to a temp file first and then `os.link`-ing it to
the target. The lesson generalizes: see Section 5's "Don't conflate
destination existence atomicity with content visibility atomicity."

### Example 4 — F4 / v4.31: `AuditStore.try_append`

**Shape**: hash-chained append-only log with sequence + entry hash.
Inputs: `action`, `actor_id`, `tenant_id`, `target`, `outcome`,
`detail`, `recorded_at`. Returns: `AuditEntry | None`. In-memory
path: `threading.Lock`-guarded sequence allocation + chain head
read + canonical hash computation + persist. Reference:
[RELEASE_NOTES_v4.31.0.md](../RELEASE_NOTES_v4.31.0.md).

**Notable**: the writer/verifier-parity invariant
(`_canonical_hash_v1` is the single source of truth for entry-hash
content layout) is preserved by having the store call the same
helper the in-process path calls. Doctrine compliance does not
relax the LEDGER_SPEC.md hash-content contract.

---

## 3. When this doctrine applies

The pattern fits when **all** of the following are true:

1. The store represents state that a caller **reads, computes a
   delta against, and writes back**.
2. Two concurrent callers can both read the same baseline and both
   compute their delta against it.
3. The bug is **last-write-wins** or **chain-fork**, not a
   throughput / ordering / availability problem.
4. There exists a storage-layer atomic primitive (lock,
   conditional UPDATE, file syscall) that can perform the
   test-and-update in one indivisible step.

If you can express the fix as "give the store an atomic
test-and-update primitive and let the high-level operation defer to
it," this doctrine is the right shape.

---

## 4. When this doctrine does NOT apply

Three audit fractures look related but are NOT the same shape.
Reaching for the doctrine here would create the wrong abstraction.

### F12 — per-store mutex throughput ceiling (closed in v4.36.0 — confirms the doctrine boundary)

**Why it doesn't fit**: F12 was a throughput problem, not an
atomicity problem. Each store wrapped every operation in a single
`threading.Lock`, which serialized all callers regardless of
whether their operations actually conflicted. The fix was **connection
pooling** (multiple connections handle concurrent requests), not an
atomic primitive.

The doctrine's `try_*` primitive would not have helped — the lock
was already held; what was missing was concurrency, not atomicity.

F12 shipped in v4.36.0 (`fix(audit-f12): governance store connection
pool`, #404) with exactly the connection-pool shape this section
predicted. That's a useful confirmation: the doctrine's "Section 4"
exclusion criteria are operationally meaningful, not just
hand-waving — F12 needed a structurally different cure, the
platform built that cure, and the atomic-store doctrine and the
connection-pool doctrine coexist without overlap.

### F8 — MAF substrate disconnect

**Why it doesn't fit**: F8 is an architectural decision about how
the Rust certifying substrate (MAF) and the Python governed runtime
(MCOI) communicate proof capsules. There's no shared state being
read-and-written; the "fracture" is that the two substrates are
designed to be loosely coupled and the integration surface is
underdetermined.

### F1 — routers without `/api/` prefix bypass middleware

**Why it doesn't fit**: F1 is a routing/dispatch bug, not an
atomicity bug. Two callers don't race; one caller takes the wrong
path. The fix is structural (mount middleware on all routers, or
remove the bypassing routes).

---

## 5. Pattern hygiene

These are the failure modes observed (or anticipated) when applying
the doctrine. Avoid them.

### Don't return `None` from a real override

The `None` sentinel is reserved for the base class. A real override
that returns `None` defeats MRO override-detection — the caller
sees `None` and assumes "no atomic path," falls through to the
legacy path, and now both paths run for the same operation.

If your override needs to signal a state besides "allowed," use a
domain-specific value: `(False, remaining)` for rate limit denial,
`None` only for the "impossible" case, and raise for genuinely
exceptional conditions (DB connection lost, schema mismatch).

### Don't split the atomic operation across two storage calls

A `read_state()` followed by a separate `write_if_unchanged()` is
not atomic — TOCTOU is back. The override must collapse the
test-and-update into one storage primitive (one SQL statement, one
held lock, one syscall).

### Don't conflate destination-existence atomicity with content-visibility atomicity

A primitive that atomically *creates* the destination but not its
*content* (e.g., `O_CREAT | O_EXCL` followed by a separate `write`)
leaves a visibility window: the destination exists but is empty or
half-written, and a concurrent reader sees the partial state.

Two distinct properties:

- **Destination existence atomicity**: at any instant, the
  destination either exists or doesn't. Provided by `O_EXCL`,
  `INSERT` against a `UNIQUE` constraint, `os.link`,
  `rename`-from-temp.
- **Content visibility atomicity**: when the destination becomes
  visible, its full content is visible. Provided by writing into a
  temp/staging area first and then atomically swapping it to the
  destination — not by `O_CREAT | O_EXCL` + `write`.

The fix shape: stage the content fully before making the
destination visible. v4.30 had this bug; v4.40 closed it via
`tempfile.mkstemp` + `os.link`. The same applies beyond filesystems —
any backend where create and populate are separate operations
(legacy `INSERT` of a row with `NULL`/default columns, then
`UPDATE` to fill them) has the same shape, with the same fix
(populate fully before insert, or use a single
`INSERT … RETURNING …` that produces the row complete).

Test for it explicitly: a concurrent reader should never see a
state that the writer doesn't intend to be visible.

### Don't widen the override's input contract over time

Once `try_record(*, a, b, c)` is shipped, adding a required
parameter `d` is a breaking change for forks that already
overrode the method. Add new optional parameters with default
values, or version the method (`try_record_v2`) and dispatch.

### Document the retry semantics for the caller

When the high-level operation retries on `None` (as v4.30
`append`), document the bound (max attempts), the failure mode
(raise after exhaustion vs. return None vs. silent), and the
backoff (none / exponential / jittered).

### Don't apply the doctrine speculatively

If a store has no observed concurrency bug **and** no plausible
multi-replica deployment story, adding `try_*` is overhead. Wait
for a real fracture or a real deployment requirement before
introducing the contract. Three of the four examples were closed
in response to named audit fractures, not preemptively.

---

## 6. The meta-test

[`mcoi/tests/test_atomic_store_doctrine.py`](../mcoi/tests/test_atomic_store_doctrine.py)
asserts the following across all four shipped stores:

1. The base class's `try_*` method exists and returns `None`.
2. The concrete in-memory store overrides `try_*` (the function
   object differs from the base class's).
3. A duck-typed store (no inheritance) is correctly detected as
   "no override" via the `getattr` default idiom.
4. A subclass that does NOT override `try_*` is correctly detected
   as "no override" via inheritance.

This catches doctrine drift — if someone refactors any of the four
stores in a way that breaks the override-detection idiom (e.g.,
removes the base method, renames it, makes the dispatcher use a
different detection idiom), the meta-test fails immediately.

The meta-test is **not** a substitute for the per-fracture test
files. Each fracture's test file still owns its concurrency tests
and dispatch semantics. The meta-test owns the shape.

---

## 7. Future fractures

Candidates that look like they fit the doctrine:

- **F11 (Postgres path)** — atomic SQL UPDATE for cross-replica rate
  limit enforcement. Fits exactly. Pending schema migration.
- **F11 (identity-level)** — extend `RateLimiter.check`'s identity
  dispatch through the store (currently uses in-memory TokenBucket).
  Fits exactly.
- **F4 (Postgres path)** — atomic SQL for cross-replica audit
  sequence allocation. Fits — needs `SERIAL`/identity column +
  `FOR UPDATE` on chain-head row, or server-side hash via
  `pgcrypto`. Pending.
- **TenantGate state transitions** — if `TenantGatingStore` ever
  needs cross-replica conditional state changes (e.g., "gate to
  paused only if currently active"), the same doctrine applies.

Fractures that look related but don't fit:

- **F12** — connection pooling, shipped in v4.36.0 (Section 4).
- **F8** — architectural (Section 4).
- **F1** — routing (Section 4).

---

## Summary

Pattern → name `try_*`, return `None` from base, dispatch with
`getattr`, override per backend, test the contract.

Read [RELEASE_NOTES_v4.27.0.md](../RELEASE_NOTES_v4.27.0.md) once
to see how it landed the first time. Read v4.29, v4.30, v4.31 to
see the same shape in three different storage substrates. Apply
the recipe in Section 1 to a fifth fracture in less time than it
took to read this doc.
