# Design: cognitive outcome ledger (the D1 record-and-replay substrate)

Status: **IMPLEMENTED for the first file-backed D1 ledger slice; Postgres backing remains future.**
Author: Claude (Opus 4.7, 1M context).
Date: 2026-06-03.
Scope: the concrete architecture for the "D1 record-and-replay" decision left open by
[`COGNITIVE_LOOP_LIVE_WIRING.md`](COGNITIVE_LOOP_LIVE_WIRING.md). That doc named D1 and
recommended posture (a) — record-and-replay the loop trajectory via hash-bound events —
but was written before Stages A/B/C/D/E landed. This doc updates the context, locks the
first safe implementation posture, and records the audit gates that the shipped file-backed
ledger slice must keep satisfying.

## 0. Applied decision record (2026-06-03)

The implementation path is now fixed for the first code slice. These decisions replace the
open L1/L2/L3 questions at the bottom of the earlier draft.

| # | Decision | Applied answer | Why |
|---|---|---|---|
| L1 | Backing for v1 | **Option A — file-backed `HashChainStore` first** | Lowest-risk path, zero new runtime dependency, immediate restart safety, reuses existing tamper-evident persistence. |
| L2 | Stream shape | **Per-tenant ledger stream** | Preserves tenant isolation, bounds rehydrate scope, bounds lock contention, and avoids cross-tenant ordering coupling. |
| L3 | Rehydrate timeout posture | **Hard timeout + abort startup / fail-CLOSED** | A corrupted, incomplete, or slow ledger is integrity-critical. Serving with partial learned state is less safe than refusing startup. |
| L4 | Flag shape | **Split enable/backend knobs** | Use `MULLU_COGNITIVE_LOOP_LEDGER=0/1` for enablement and `MULLU_COGNITIVE_LOOP_LEDGER_BACKEND=file|postgres` for backend selection. Backend may be configured without enabling behavior. |

Implementation invariant:

```text
No ledger flag → byte-identical current behavior.
Ledger flag ON + invalid/corrupt/unrehydratable ledger → startup blocked.
Ledger append failure during LEARN → LEARN aborts before promoting partial state.
Per-tenant source stream → no cross-tenant replay, lock, or derived-memory bleed.
```

## 1. Campaign state (2026-06-03, code-grounded)

| Stage | Status | PR | Default |
|---|---|---|---|
| A — shadow OBSERVE (workflow seam) | MERGED | #1248/#1253/#1258 | OFF (`MULLU_COGNITIVE_LOOP_SHADOW`) |
| A — shadow OBSERVE read endpoint | MERGED | #1270 | OFF |
| B+C — enforce DECIDE + live LEARN (workflow seam) | MERGED | #1263 | OFF (`MULLU_COGNITIVE_LOOP_ENFORCE`, `_LEARN`) |
| B+C — agent_chain seam | MERGED | #1265 | OFF |
| D — plan-time organ read-back (assistant seam) | MERGED | #1271 | OFF (`MULLU_COGNITIVE_LOOP_PLAN_CONTEXT`) |
| Engine thread-safety (memory.py) | MERGED | #1267 | (no flag — defensive fix) |
| D1 — file-backed cognitive outcome ledger | MERGED | #1280 | OFF (`MULLU_COGNITIVE_LOOP_LEDGER`) |
| E — gate-enrichment (safety-positive) | MERGED | #1283 (supersedes closed #1274) | OFF (`MULLU_COGNITIVE_LOOP_GATE_ENRICHED`) |

What the campaign actually does today:
- **Writes** via Stage C: `CognitiveLearner` updates `meta_reasoning.update_confidence(...)`,
  admits a `cognitive_loop_outcome` `MemoryEntry` to `EpisodicMemory` on every verified success,
  and, when `MULLU_COGNITIVE_LOOP_LEDGER=1`, appends the same outcome to
  `FileBackedCognitiveOutcomeLedger`.
- **Reads** via Stage E and Stage D: the gate consults `episodic.list_entries(category="cognitive_loop_outcome")`
  per capability (Stage E); the planning reader consults the same at plan time (Stage D).
- **Durable substrate**: the default-off file-backed D1 ledger rehydrates `meta_reasoning` and
  `EpisodicMemory` before runtime deps are published. `EpisodicMemory` remains the in-process
  derived read model; the ledger is the restart-safe source stream. Multi-host production sharing
  still needs the later Postgres backend.

  The implemented file-backed slice closes the single-host restart-safety gap. The remaining
  open gap is shared multi-host coherence beyond a shared filesystem.

## 2. Goal — what "ledger" means concretely

A **durable, append-only, ordered, hash-chained record of every `cognitive_loop_outcome`** so:

1. **Restart-safe**: a worker restart rehydrates `meta_reasoning` confidence and `episodic_memory`
   from the ledger before serving traffic. Identical sequence of past outcomes ⇒ identical
   organ state.
2. **Multi-worker-coherent**: every worker reads the same ordered event stream, so the gate's
   enrichment counts (`prior_outcomes_count`, `prior_success_count`) and the learner's confidence
   running rate are consistent across workers (eventually, depending on backing — see §4).
3. **Tamper-evident**: each event hash-chains to the prior, so a corrupted file or a malicious
   edit is detectable (mirrors `persistence/hash_chain.py::HashChainStore`).
4. **Replayable for audit / debug**: given the recorded trajectory, a developer can replay the
   exact decision sequence offline. Today's organ state is a deterministic fold over the ledger.

What the ledger does NOT do:
- Replace `EpisodicMemory` as the in-process query store. The ledger is the **source of truth**;
  `EpisodicMemory` is the **derived index** for fast in-process reads (the gate's per-capability
  filter today is O(N) over episodic; an index in front of the ledger is fine).
- Capture every Stage A shadow observation. Shadow is high-volume + read-only-with-no-consequence;
  a separate, sampled trace store fits better. (`#1270` already exposes a `recent_reports` reader
  for the in-memory deque.)
- Replace the existing UAO command ledger (`universal_action_kernel` records dispatch + governance
  events). The cognitive outcome ledger is a **sibling** focused on the LEARN-phase event class.

## 3. The shape of one event

A single ledger entry is the **`LearnRecord`** the Stage-C learner already produces, plus the
chain metadata. Fields (frozen, hashable, ordered for byte-identical replay):

```
sequence: int            # monotone per-ledger; the chain index
event_id: str            # stable_identifier("cognitive-outcome-event", ...)
ts: str                  # learner's injected clock (RFC3339 UTC)
tenant_id: str           # explicit partition key; no implicit global stream
capability_id: str
succeeded: bool
verified: bool
source_ref: str          # the caller's unique workflow_id / chain_id
prior_confidence: float  # the confidence the learner READ before update_confidence
next_confidence: float   # the confidence the learner WROTE after update_confidence
admitted_entry_id: str | None  # episodic admission outcome (None when not admitted)
content_hash: str        # SHA-256 over the canonical-serialised body above
chain_hash: str          # SHA-256 over (tenant_id, sequence, content_hash, previous_chain_hash)
previous_chain_hash: str # links to the prior event in that tenant stream; genesis = 64 zeros
```

`prior_confidence` + `next_confidence` are added so a replay can detect a corrupted-state restart
(if rehydrated confidence doesn't match `next_confidence`, the chain integrity check fails closed).
`tenant_id` is explicit so downstream replay, incident reports, and forensic exports never infer
partitioning from file path alone.

## 4. Backing options (the architecture decision)

### Option A — file-backed `HashChainStore` (selected for v1)

**Use the existing `persistence/hash_chain.py::HashChainStore` substrate**. A per-tenant JSONL
file at `data/cognitive_outcome_ledger/{tenant}.jsonl`. Each event is one line:
`{tenant_id, sequence, ts, content_hash, chain_hash, previous_chain_hash, body}`.

| Aspect | This option |
|---|---|
| Restart-safe | ✅ — JSONL on disk, atomic write, validated on rehydrate |
| Multi-worker (single host) | ✅ — file-level locks + retry-on-contention already in `HashChainStore` |
| Multi-host | ⚠️ — file shares need shared FS (NFS / EFS); not horizontal |
| Tamper-evident | ✅ — SHA-256 hash chain (free) |
| Replay | ✅ — read the JSONL forward |
| Throughput | ~kHz/host (limited by fsync); acceptable for cognitive LEARN volume |
| Dependencies | none new (uses existing `_atomic_write` + chain helpers) |
| Code reuse | composes the existing `HashChainStore` API one-to-one |

**Pros**: zero new dependency, mirrors a proven pattern, immediate restart-safety, the same
tamper-evident chain that protects audit trails today.
**Cons**: not horizontal across hosts without a shared filesystem. For pilot / single-host prod
this is sufficient; multi-host needs Option B.

### Option B — Postgres (`PostgresCandidateLedgerStore` mirror — see project_solver_forge memory)

**Reuse the `persistence/postgres_store.py` lazy-psycopg2 pattern**. A
`cognitive_outcome_ledger` table with `(tenant_id, sequence)` primary key, an append trigger
that enforces sequence-monotonicity per tenant, and a per-row chain_hash column.

| Aspect | This option |
|---|---|
| Restart-safe | ✅ |
| Multi-worker (multi-host) | ✅ — Postgres is the coordination point |
| Multi-host | ✅ |
| Tamper-evident | ✅ (same chain semantics; DB-side trigger enforces append-only) |
| Replay | ✅ — `SELECT * ORDER BY sequence` |
| Throughput | high; bounded by DB connection pool + commit fsync |
| Dependencies | psycopg2 + DB connection + migrations (Solver Forge precedent in PR #891) |
| Code reuse | mirrors `PostgresCandidateLedgerStore` (project_solver_forge) |

**Pros**: horizontal, fits prod ops; the `PostgresCandidateLedgerStore` work in PR #891 is the
identical pattern (lazy import, injected-fake-conn for CI).
**Cons**: requires DB infra to enable; raises the bar for "default-OFF flips to ON".

### Option C — in-process deque (rejected; no durability)

Today's effective behavior. Listed for completeness — explicitly NOT a ledger. Restart loses
state; multi-worker is incoherent; no audit trail.

### Option D — externalize to UAO command ledger (rejected; wrong event class)

Append cognitive LEARN events to the existing `universal_action_kernel` orchestration record
stream. **Reject** — UAO records are governance/dispatch events with their own schema and
hash-chaining; mixing event classes muddies replay and complicates governance audit. The
cognitive ledger is a SIBLING substrate.

### Applied recommendation

**Ship Option A (file-backed `HashChainStore`) first**, behind `MULLU_COGNITIVE_LOOP_LEDGER`
(default-OFF), with `MULLU_COGNITIVE_LOOP_LEDGER_BACKEND=file` as the selected backend. When
the flag is on AND the Stage-C learner is on, the learner writes a chain entry as its FINAL
step inside `_lock`-serialised admission (rollback-safe: a write failure aborts the LEARN
without partial state). When the flag is on AND a worker starts, a rehydrate helper reads the
per-tenant JSONL forward and replays each event into `meta_reasoning` + `episodic_memory`
BEFORE the server starts serving traffic.

Then **add Option B (Postgres backing) as an additive backend implementation** behind the same
`CognitiveOutcomeLedger` Protocol. The swap is a deps wiring change, not a behavior rewrite.

## 5. Integration points (where the code goes)

```
mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py    # NEW: Protocol + FileBackedCognitiveOutcomeLedger
                                                              # (uses hash_chain.HashChainStore internally)
mcoi/mcoi_runtime/core/cognitive_live.py                     # CognitiveLearner gains optional ledger param
                                                              # writes inside the existing _lock-serialised path
mcoi/mcoi_runtime/app/cognitive_live_integration.py          # MULLU_COGNITIVE_LOOP_LEDGER flag
                                                              # MULLU_COGNITIVE_LOOP_LEDGER_BACKEND=file|postgres
                                                              # build_learner reads ledger path, constructs ledger
                                                              # build_cognitive_runtime_rehydrate(...) replays
mcoi/mcoi_runtime/app/cognitive_runtime_integration.py       # on bootstrap, run rehydrate BEFORE deps.set
                                                              # (no traffic served against a partial rebuild)
mcoi/tests/test_cognitive_outcome_ledger.py                  # NEW: append-only / sequence-monotone / hash-chain
                                                              # / replay-equivalence / corrupted-file / dup-suppress
```

`EpisodicMemory.admit` is **unchanged** — the ledger writes alongside it (under the same lock).
Restart-rehydrate replays admit + `update_confidence` in original order. The rehydrate function
is the only new "must-run-before-serving" startup step; it has its own timeout + fail-closed
behavior (a corrupted chain refuses to serve, mirroring the live cognitive gate's fail-OPEN
posture for run-time errors but fail-CLOSED for startup integrity).

## 6. Determinism / replay semantics

- **Write-time determinism**: each event has a SHA-256 content hash + chain hash. The clock is
  the learner's injected clock — the SAME determinism contract the rest of the cognitive loop
  already inherits.
- **Replay-time determinism**: given a ledger byte-stream, the rehydrate function produces a
  byte-identical `meta_reasoning.get_confidence(...)` + `episodic.list_entries(...)` snapshot
  before serving the first request. Test: `replay(ledger) == replay(ledger)` (idempotence) and
  `state_after_ledger.append(e) == state_after_replay(ledger + e)` (composability).
- **Multi-worker convergence** (Option A, single host): writes are serialised through
  `HashChainStore` file-level locks; readers see eventual-consistency snapshots via the periodic
  rehydrate refresh OR via the live in-process index (each worker's `EpisodicMemory` mirror of
  the ledger). A "tail" subscriber pattern is OPTIONAL; v1 ships with rehydrate-on-startup +
  in-process append (each worker writes its own LEARN events).
- **Cross-worker write-ordering** (Option A): two workers writing concurrently are serialised at
  the file lock. Their `sequence` numbers are monotone per tenant, allocated under the lock.
- **Tenant-local replay**: rehydrate accepts a tenant scope and must never read a sibling tenant
  file into the active tenant's organs. Tests should construct two ledgers with overlapping
  `source_ref` and `capability_id` values to prove no bleed.

## 7. Test plan (first implementation PR)

1. **Pure append + chain integrity**: write N events, validate chain forward and backward,
   detect a tampered entry mid-chain.
2. **Restart-rehydrate equivalence**: write events, snapshot `meta_reasoning` confidence per
   capability + `episodic.list_entries`. Reset organs. Replay ledger. Assert byte-identical
   snapshot.
3. **Dup-suppress**: replaying an already-applied event must be a no-op (idempotent), so a
   partial restart doesn't double-apply.
4. **Concurrent-write serialisation**: 8 threads each LEARN 100 events; assert sequence is
   strictly monotone per tenant and the chain validates end-to-end.
5. **Corrupted-file refuses to serve**: a flipped byte in the JSONL must cause rehydrate to
   raise (fail-CLOSED), and the server start must abort. Same posture as
   `HashChainStore.validate`.
6. **Default-OFF byte-identical**: with `MULLU_COGNITIVE_LOOP_LEDGER=0`, the LEARN path is
   byte-identical to today (no ledger writes, no rehydrate, no behavior change).
7. **Per-tenant isolation**: tenant A's ledger cannot affect tenant B's confidence, episodic
   outcome count, Stage-D planning context, or Stage-E gate enrichment.
8. **Append failure atomicity**: injected ledger write failure leaves no promoted episodic entry
   and no updated confidence that lacks a matching ledger event.
9. **Timeout fail-CLOSED**: injected slow/corrupt rehydrate exceeds the hard cap and blocks
   bootstrap before deps are published.
10. **Backend selector default safety**: `MULLU_COGNITIVE_LOOP_LEDGER_BACKEND=postgres` with no
    implementation or no DB available must not affect default-OFF behavior and must fail clearly
    when the ledger flag is enabled.

## 8. Admission / audit gates for code PR

The first code PR is admissible only if it satisfies all gates below.

| Gate | Required witness |
|---|---|
| Default-off preservation | Byte-identical LEARN + bootstrap path with `MULLU_COGNITIVE_LOOP_LEDGER=0`. |
| Capability boundary | New persistence surface is internal-only, no new public route, no OpenAPI delta unless explicitly justified. |
| Tenant isolation | Per-tenant path construction is sanitized; no tenant value may escape `data/cognitive_outcome_ledger/`. |
| Startup integrity | Rehydrate validates chain before publishing runtime deps; corruption blocks startup. |
| Atomic LEARN | Ledger append, confidence update, and episodic admission cannot leave half-promoted state. |
| Replay determinism | Replaying the same ledger produces the same meta confidence and episodic outcome projection. |
| Negative controls | Tests fail against a deliberately tampered chain, duplicated sequence, cross-tenant replay, and injected append failure. |
| Concurrency | Multi-thread append preserves monotone sequence and valid chain per tenant. |
| No UAO mixing | Cognitive outcome ledger remains disjoint from governance/dispatch UAO event classes. |
| Release hygiene | `ruff`, `py_compile`, reflective contracts, proof matrix, and strict release-status validators stay green. |

## 9. Fracture audit and mitigations

| Fracture | Risk | Mitigation now required |
|---|---|---|
| Memory-state confusion | Old in-process `EpisodicMemory` could be treated as source of truth. | Ledger is source of truth; episodic is a derived index after rehydrate. |
| Cross-tenant bleed | Single stream or unsafe path joins could mix learned outcomes across tenants. | Per-tenant stream, explicit `tenant_id`, path sanitization, isolation tests. |
| Partial promotion | Ledger write failure after confidence/episodic mutation could create unverifiable learning. | Write/admit/update ordering must be tested with injected failure; no partial state allowed. |
| Startup split-brain | Worker serves before rehydrate completes or after corrupt chain is detected. | Rehydrate before deps publish; hard timeout; fail-CLOSED. |
| Horizontal illusion | File backend might be mistaken for multi-host production coherence. | Document Option A as single-host/shared-FS only; Postgres is required for true multi-host. |
| Event-class mixing | Appending LEARN events into UAO would muddy governance audit. | Keep cognitive ledger as sibling, not replacement or extension of UAO. |
| Silent behavior drift | Flag accidentally changes live path before validation. | Default-OFF byte-identical test is mandatory. |
| Overgeneralized learning | Learned outcomes may influence future decisions without provenance. | Every outcome is hash-bound, replayable, and tenant-scoped; policy changes remain separate. |

## 10. What I will NOT do without a follow-up implementation PR

- Land ledger code without the audit gates in §8.
- Touch the LEARN path's existing `_lock`-serialised admission semantics beyond adding an optional
  ledger dependency and atomic failure handling.
- Change `EpisodicMemory.admit` — the ledger writes ALONGSIDE it.
- Add a Postgres dependency to default-mode startup before the file backend has shipped behind
  the flag and run cleanly in pilot.
- Enable the ledger flag by default before restart, corruption, timeout, concurrency, and
  tenant-isolation witnesses are green.

## 11. Relationship to other open work

- **#1267 (engine thread-safety)** is merged — the ledger's writer holds the
  `CognitiveLearner._lock`, and `EpisodicMemory` itself is safe to mutate from the
  rehydrate path without racing the still-in-flight first request.
- **#1283 (Stage E)** is merged — the enrichment reads episodic but writes nothing. A
  ledger-backed episodic is a drop-in for Stage E's reader. Closed #1274 is superseded by
  the merged Stage E implementation.
- **PR #1271's `CognitivePlanningReader`** consumes the same surface (`episodic.list_entries`).
  A ledger-backed episodic is transparent to it.
- **`HashChainStore`** is reused as-is; no new persistence dependency.
- The **UAO command ledger** is a sibling and stays disjoint (governance vs cognitive event
  classes).

---

*Resume*: keep the selected file-backed, per-tenant, fail-CLOSED ledger behind
`MULLU_COGNITIVE_LOOP_LEDGER` as the D1 source stream. The next implementation slice is the
Postgres/shared-stream backend when multi-host production coherence becomes the target.
