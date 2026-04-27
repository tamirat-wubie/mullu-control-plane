# Mullu Platform v4.28.0 — Audit Chain Checkpoint Anchor (Audit F3)

**Release date:** TBD
**Codename:** Anchor
**Migration required:** No (additive — anchor defaults to genesis until first prune)

---

## What this release is

Closes audit fracture **F3**: `verify_chain()` returned False
permanently after the first prune. The audit's worked example:

> `AuditTrail` prunes from the front when `len(entries) > max_entries`;
> `_verify_chain_locked` always starts at `sha256(b"genesis")`. After
> the first prune (entry 500,001), `verify_chain()` returns
> `(False, …)` forever. Verifier and pruner are mutually inconsistent.

The platform's stated invariant is **"hash-chain audit trail —
tampering detectable."** Pre-v4.28, that wasn't true past the first
prune (~weeks of moderate traffic at default `max_entries=500_000`).
v4.28 fixes it.

---

## What is new in v4.28.0

### `AuditCheckpoint` dataclass

[`audit_trail.py`](mullu-control-plane/mcoi/mcoi_runtime/core/audit_trail.py).

```python
@dataclass(frozen=True, slots=True)
class AuditCheckpoint:
    at_sequence: int       # Sequence of the LAST pruned entry
    chain_hash: str        # That entry's entry_hash — anchors the chain
    recorded_at: str
```

### Anchor state on `AuditTrail`

```python
self._anchor_hash: str = sha256(b"genesis").hexdigest()
self._anchor_sequence: int = 0
```

The anchor is what the first surviving in-memory entry's
`previous_hash` must equal for the chain to verify. Initialized to
genesis; updated on every prune to the entry_hash of the LAST entry
pruned. The first surviving entry's `previous_hash` was set at record
time to that exact value, so the verifier matches.

### `_verify_chain_locked()` starts from anchor, not genesis

```python
def _verify_chain_locked(self) -> tuple[bool, int]:
    if not self._entries:
        return True, 0
    expected_prev = self._anchor_hash  # was: sha256(b"genesis").hexdigest()
    for entry in self._entries:
        if entry.previous_hash != expected_prev:
            return False, entry.sequence
        expected_prev = entry.entry_hash
    return True, len(self._entries)
```

One-line change to the verifier; the rest is anchor maintenance.

### Prune path captures the boundary entry's hash

```python
if len(self._entries) > self._max_entries:
    prune_count = len(self._entries) - self._max_entries
    boundary = self._entries[prune_count - 1]  # LAST entry being pruned
    self._anchor_hash = boundary.entry_hash
    self._anchor_sequence = boundary.sequence
    self._entries = self._entries[prune_count:]
    if self._store is not None:
        self._store.store_checkpoint(AuditCheckpoint(...))
```

The boundary entry's `entry_hash` becomes the new anchor. The first
entry in the post-prune window has `previous_hash == boundary.entry_hash`
(set at record time) — so the invariant holds without any
re-computation.

### Optional `AuditStore` persistence

```python
class AuditStore:
    def store_checkpoint(self, checkpoint: AuditCheckpoint) -> None: ...
    def latest_checkpoint(self) -> AuditCheckpoint | None: ...
```

Base class default no-ops; `AuditTrail` calls them but works with
stores that don't override. `InMemoryAuditStore` stores the most
recent checkpoint and returns it on `latest_checkpoint()`. On
process restart, `AuditTrail.__init__` calls `latest_checkpoint()`
to restore the anchor — durability across restart for stores that
implement persistence.

`PostgresAuditStore` checkpoint persistence is **not** in this
release — F4 (per-worker chain forks) is a deeper coordination
problem that needs DB-side sequencing first. The in-process anchor
restored from `InMemoryAuditStore` is sufficient for single-process
correctness.

---

## What stays the same

- `verify_chain()` signature unchanged
- `AuditEntry` shape unchanged
- `AuditStore` base class methods all backward-compatible
- The 46 pre-existing `test_audit_trail.py` tests pass unchanged
- Tamper detection remains as before — any in-window entry whose
  `previous_hash` doesn't link correctly fails verification. The fix
  only addresses the prune-boundary false-negative; it doesn't
  weaken any tamper guarantee

---

## Test counts

| Suite                                    | v4.27.0 | v4.28.0 |
| ---------------------------------------- | ------- | ------- |
| Existing `test_audit_trail`              | 46      | 46      |
| New checkpoint anchor tests              | n/a     | 17      |

The 17 new tests in [`test_v4_28_audit_checkpoint.py`](mullu-control-plane/mcoi/tests/test_v4_28_audit_checkpoint.py) cover:

**Pre-prune (3)**
- Empty trail verifies
- Unpruned chain verifies (anchor = genesis)
- First entry's previous_hash equals genesis

**Post-prune — F3 fix in action (5)**
- Post-prune chain still verifies (the core fix)
- Anchor advances correctly across multiple prune cycles
- Anchor's chain_hash matches first surviving entry's previous_hash
- Tamper detection still catches in-window forgeries
- Anchor tampering itself caught (anchor invariant enforced)

**Persistence (4)**
- Anchor restored from store on bootstrap
- No checkpoint → genesis anchor (legacy behavior)
- Prune persists checkpoint to store
- Process restart inherits anchor across new `AuditTrail` instance

**Backward compat (2)**
- Stores without checkpoint method overrides still work
- `summary()` reports `chain_valid=True` after prune (v4.27 reported False)

**Edge cases (3)**
- At capacity (no prune) → anchor stays at genesis
- One-over-max → single prune updates anchor to first entry's hash
- Record-then-verify immediately after prune → valid chain

All 46 existing audit_trail tests pass unchanged.

---

## Compatibility

- All v4.27.x callers work unchanged
- Stores not implementing `store_checkpoint`/`latest_checkpoint` use the
  base class no-ops (in-process anchor still works)
- The chain-hash format is identical (still SHA-256 over the same content)
- Operators relying on `verify_chain()` returning `(True, N)` post-prune
  now actually get that — pre-v4.28 they got `(False, sequence)` silently

---

## Production deployment guidance

### Behavior change at runtime

Pre-v4.28: `summary()["chain_valid"]` was True until first prune,
False thereafter. Operators monitoring this field would see a "chain
broken" alert ~weeks into deployment that was actually a
self-inflicted false positive from the verifier-pruner mismatch.

Post-v4.28: `chain_valid` stays True as long as no actual tampering
has occurred. Operators with alerts wired to this signal will stop
seeing the false positive.

### Default `max_entries` unchanged

Still 500,000. Operators wanting more aggressive pruning to bound
memory can lower this; the anchor advances correctly regardless.

### Multi-process / multi-replica

The in-process anchor is single-process. Multi-worker uvicorn or
multi-replica deployments still face F4 (each worker has its own
chain). v4.28 doesn't fix F4 — it only restores the per-process
chain integrity that was claimed.

For multi-replica deployments, the audit trail's tamper-evidence
claim should be scoped to "per-process" until F4 lands. Operators
needing global ordering should run a single-instance audit
collector and forward all entries to it. Documented honestly in
[`docs/LEDGER_SPEC.md`](mullu-control-plane/docs/LEDGER_SPEC.md).

---

## What v4.28.0 still does NOT include

- **F4** — per-worker chain forks. Each FastAPI worker still has its
  own `_sequence` counter and `_anchor`. Two workers reaching
  sequence 42 simultaneously both produce `entry_id="audit-42"` and
  Postgres `ON CONFLICT DO NOTHING` silently drops one. Needs DB-side
  sequence + DB-side previous_hash chain. Own PR.
- **PostgresAuditStore checkpoint persistence** — per-process anchor
  is durable in `InMemoryAuditStore` only. Postgres deployments
  benefit from anchor restore across restart only when paired with
  DB-side schema changes for the checkpoint table. Bundled with F4.

---

## Honest assessment

v4.28 is small (~50 LoC source + ~330 LoC tests). The fix is a
one-line change to the verifier plus the anchor maintenance code in
the prune path. The bug existed because the verifier and pruner
were written by different mental models — the verifier assumed
"start from genesis"; the pruner assumed "tail-truncate is fine."
Both assumptions held in isolation; their composition didn't.

The structural lesson: when two operations together preserve a
property that neither preserves alone, write a test that exercises
the composition. Pre-v4.28 the existing 46 audit_trail tests
covered each operation but not their interaction at the prune
boundary.

**We recommend:**
- Upgrade in place. v4.28 is additive.
- Deployments with `verify_chain()` wired to monitoring will stop
  seeing false-positive alerts that started ~weeks into operation.
- Multi-replica deployments: still run a single audit collector;
  F4 (cross-worker chain consolidation) is the next planned fix
  in the audit-response track.
