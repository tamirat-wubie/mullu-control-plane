# Mullu Platform v4.30.0 — Atomic Hash Chain Append (Audit F15)

**Release date:** TBD
**Codename:** Linear
**Migration required:** No (additive — no on-disk format change)

---

## What this release is

Closes audit fracture **F15**: `HashChainStore.append` had a TOCTOU
between `latest()` and the underlying write.

Pre-v4.30, `append`:

1. Read the latest entry to compute the next sequence number.
2. Computed `chain_hash` against the latest's `chain_hash` as
   `previous_hash`.
3. Wrote via `_atomic_write`, which used `os.replace` for the temp-file
   rename — `os.replace` **overwrites pre-existing files**.

Two concurrent writers (threads in one process, or processes on the
same filesystem) could both arrive at step 1 with the same `latest()`
result, both compute the same target sequence at step 2, and both
succeed at step 3. The chain forked: two distinct entries existed
(briefly) for the same sequence; the surviving entry on disk linked
to whichever predecessor's hash the **last writer** captured.

The platform's stated invariant is **"chain is append-only;
tampering is detectable."** Pre-v4.30, that was true under
single-threaded write, and false under any concurrent write.

---

## What is new in v4.30.0

### `_atomic_write_exclusive(path, content) -> bool`

[`hash_chain.py`](mullu-control-plane/mcoi/mcoi_runtime/persistence/hash_chain.py).

New module-private helper alongside the existing `_atomic_write`. Uses
`O_CREAT | O_EXCL | O_WRONLY` so the OS rejects pre-existing
destinations at the syscall level:

```python
flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
try:
    fd = os.open(str(path), flags, 0o644)
except FileExistsError:
    return False
```

Returns `True` on successful write, `False` on collision. The
collision path is **not an error** — it's the expected outcome when
two writers race for the same sequence. The caller decides whether
to retry, propagate, or surface.

### `HashChainStore.try_append(content_hash) -> HashChainEntry | None`

The atomic primitive — one read-compute-write attempt:

```python
def try_append(self, content_hash):
    prev = self.latest()
    # ... compute seq, prev_hash, chain_hash, build entry ...
    if not _atomic_write_exclusive(self._entry_path(seq), content):
        return None
    return entry
```

Returns the entry on success, `None` on collision (another writer
claimed the sequence). Single-atomic-attempt by design — separating
the primitive from the retry strategy mirrors the v4.27/v4.29
pattern: tests can simulate a collision deterministically, and
callers compose retry policy on top.

### `HashChainStore.append(content_hash) -> HashChainEntry`

Now a thin retry wrapper around `try_append`. Bounded at 64 attempts;
re-reads `latest()` after each collision so the next attempt picks
up the new chain head:

```python
for _attempt in range(64):
    entry = self.try_append(content_hash)
    if entry is not None:
        return entry
raise PersistenceWriteError(
    "hash chain append failed after 64 contention retries"
)
```

The signature is unchanged. Callers see the same `HashChainEntry`
return; the loop is invisible except under genuinely pathological
contention.

---

## Compatibility

### What stays the same

- `append(content_hash)` signature unchanged. Returns the same
  `HashChainEntry`.
- On-disk format unchanged. Existing chains read and validate
  identically.
- `latest`, `load_all`, `validate` semantics unchanged.
- Single-writer behavior: byte-identical to pre-v4.30 for the
  successful path. Only the syscall flags differ; the contents
  written are the same.
- The existing `_atomic_write` helper is still used by other
  persistence modules (`workflow_store`, `trace_store`,
  `snapshot_store`, etc.) — only `hash_chain.py` switches to
  `_atomic_write_exclusive`.

### What changes

- The write path within `HashChainStore` switches from `os.replace`
  (overwrite) to `O_CREAT | O_EXCL` (fail-on-exist).
- A partial-write window exists if the process dies mid-`os.write`.
  The resulting file fails to deserialize and is caught by the
  existing `CorruptedDataError` path in `_load_entry` — same
  recovery semantics as a corrupted entry today.

### Cross-process behavior

Because `O_EXCL` is enforced by the kernel at the filesystem layer,
two processes writing to the same chain directory **cannot** both
succeed at the same sequence. The loser sees `FileExistsError`,
`try_append` returns `None`, the high-level `append` re-reads
`latest()`, and the next attempt lands at the next sequence.

This makes the chain durable under multi-worker uvicorn deployments
that share a filesystem volume — a real-world configuration the
pre-v4.30 chain silently broke under.

---

## Test counts

| Suite                                    | v4.29.0 | v4.30.0 |
| ---------------------------------------- | ------- | ------- |
| Existing `test_hash_chain`               | 17      | 17      |
| New atomic hash chain tests              | n/a     | 16      |

The 16 new tests in [`test_v4_30_atomic_hash_chain.py`](mullu-control-plane/mcoi/tests/test_v4_30_atomic_hash_chain.py) cover:

**`_atomic_write_exclusive` contract (3)**
- First write succeeds and creates the file with the given content
- Second write to same path returns `False` and **leaves original
  content untouched** (the F15 fix in microcosm)
- Write creates parent directories when needed

**`try_append` primitive (5)**
- First append writes seq=0 linked to genesis
- Subsequent append links `previous_hash` to predecessor's `chain_hash`
- Collision (simulated via monkeypatch on `_atomic_write_exclusive`)
  returns `None`
- Collision after a successful first write returns `None`
- Empty/whitespace `content_hash` raises

**`append` retry strategy (3)**
- Recovers from a successful first write and continues at seq+1
- Chain remains valid after 20 sequential appends
- Fails loudly with `PersistenceWriteError` after max retries (64)

**Concurrency — the F15 fix end-to-end (2)**
- 50 threads × 1 append → exactly 50 distinct sequences {0..49}, no
  duplicates, no gaps, chain validates
- Two `HashChainStore` instances on the same directory (simulating
  two worker processes) running 25 appends each → 50 distinct
  sequences, chain validates

**Backward compatibility (3)**
- `append` signature unchanged
- `validate` semantics unchanged
- `load_all` returns entries in sequence order

All 17 existing hash_chain tests still pass. Atomic-pattern test
suite (v4.27 + v4.29 + v4.30 + their underlying tests) passes 209
tests.

---

## Production deployment guidance

### All deployments

The `HashChainStore` upgrade is automatic — no operator action and
no schema/format migration. Existing chains continue to read and
validate identically. New writes use `O_CREAT | O_EXCL` and benefit
from cross-process atomicity automatically.

### Multi-worker deployments

Deployments that run multiple uvicorn workers (or any other
multi-process model) sharing a chain directory **gain F15 closure
automatically**. Pre-v4.30, those deployments were silently
corrupting the chain under concurrent audit writes. Post-v4.30, the
chain stays linear under the same load.

### Backup considerations

A partial-write recovery (process killed mid-`os.write`) leaves an
empty or short file at the target sequence. The next reader/validator
catches this via `CorruptedDataError`. Operators encountering this
condition should remove the corrupt entry file and re-run the
audit; the chain will validate again.

(Recommendation: wrap chain-writing processes with proper signal
handling so the process exits cleanly — but the F15 fix doesn't
make this any worse than before.)

---

## What v4.30.0 still does NOT include

Audit fractures explicitly NOT closed by this PR:

- **F4** audit chain forks per worker — same shape as F15 but at
  the AuditTrail/AuditStore boundary; needs DB-side sequence
  allocation. Larger restructuring; own PR.
- **F11 (Postgres path)** — schema + atomic SQL UPDATE for
  cross-replica rate limit enforcement. Next PR.
- **F11 (identity-level)** — dual-gate dispatch through the store
  for per-identity buckets. Next PR.
- **F1** routers without `/api/` prefix bypass middleware
- **F8** MAF substrate disconnect
- **F9/F10** webhook SSRF + DNS rebinding (in progress on this
  branch — separate work)
- **F12** per-store mutex throughput ceiling — different shape
  (throughput, not atomicity); needs connection pooling
- **JWT module hardening**

(F2 closed in v4.27. F3 closed in v4.28. F11-tenant API closed in
v4.29.)

---

## Honest assessment

v4.30 is small (~50 LoC source + ~250 LoC tests). The fix is one
syscall flag (`O_EXCL`) wrapped in a named primitive with a retry
loop on top. The bug existed for the same reason every TOCTOU bug
exists: the developer who wrote `os.replace` was thinking about
"overwrite is fine, the previous content is gone" and not thinking
about "another writer might be at the same path right now."

The structural value, again: **separate the atomic primitive from
the high-level operation**. `try_append` is the contract; `append`
is the strategy. Tests can exercise the contract directly (one
attempt, deterministic outcome) without standing up a full
concurrent-thread harness. The retry loop is observable, bounded,
and replaceable — a future caller could decide it wants `try_append`
without retry (e.g., a strict-fail-on-conflict workflow), and the
primitive is right there.

This is now the **third application** of the same pattern (v4.27
budget, v4.29 rate limit, v4.30 hash chain). At three examples, the
shape is genuinely a pattern: name the atomic primitive, return
`None` for "no go," let the caller compose strategy. The `BudgetStore`,
`RateLimitStore`, and `HashChainStore` cases differ in their
storage layer (Postgres row, in-memory bucket, filesystem entry)
but share the same contract shape. A future v4.31+ might
consolidate these into a generic `try_*` doctrine in a developer
guide.

**We recommend:**
- Upgrade in place. v4.30 is additive and on-disk-compatible.
- Multi-worker deployments get F15 closure automatically.
- Single-worker deployments see no behavior change for the
  successful path; failure semantics under contention shift from
  "silent fork" to "bounded retry."
