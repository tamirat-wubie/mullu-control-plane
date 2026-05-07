# Atomic Store Doctrine Series — Handoff Plan

**Status:** Local uncommitted work on branch `fix/audit-f5-f6-tenant-binding`, mixed with user's tenant-binding + domain-adapter work.
**Goal:** Land the five doctrine fracture closures as separate, reviewable PRs without disturbing the user's parallel F5/F6 work.
**This document:** Self-contained — read top to bottom and execute. Delete it after the series ships.

---

## What's in the working tree

The branch has **two independent lines of work** that need separating before review:

### Doctrine series (the subject of this plan)

Five fracture closures + the doctrine itself. All currently uncommitted.

### User's tenant-binding / domain-adapter work (NOT covered here)

`gateway/causal_closure_kernel.py`, `command_spine.py`, `skill_dispatch.py`,
all `mcoi/mcoi_runtime/app/**` and `mcoi/mcoi_runtime/core/governance_guard.py`
modifications, `mcoi/mcoi_runtime/domain_adapters/**` (8 new files),
`mcoi/tests/test_v4_34_env_tenant_binding.py`, plus the modified
`test_domains_router.py` / `test_v4_12_*` / `test_v4_16_*` / `test_v4_26_*` /
gateway tests. **Leave this alone** — it's the user's concurrent work. The
`fix/audit-f5-f6-tenant-binding` branch is its home.

---

## Trunk state and version-number reconciliation

`main` currently holds through **v4.33** (JWT hardening). My local files are
named `v4.29` (F11 tenant), `v4.30` (F15), `v4.31` (F4), and `v4.34` (F11
identity). `v4.32` and `v4.33` were claimed by parallel work that landed
first.

**Recommendation: renumber the doctrine series to a contiguous post-trunk
range.** Suggested mapping:

| Local name | New name  | Fracture          |
| ---------- | --------- | ----------------- |
| v4.29      | **v4.34** | F11 tenant        |
| v4.30      | **v4.35** | F15               |
| v4.31      | **v4.36** | F4                |
| (doctrine) | **v4.37** | Atomic doctrine   |
| v4.34      | **v4.38** | F11 identity      |

Then rename:
- `RELEASE_NOTES_v4.29.0.md` → `RELEASE_NOTES_v4.34.0.md`
- `RELEASE_NOTES_v4.30.0.md` → `RELEASE_NOTES_v4.35.0.md`
- `RELEASE_NOTES_v4.31.0.md` → `RELEASE_NOTES_v4.36.0.md`
- create `RELEASE_NOTES_v4.37.0.md` for the doctrine PR
- `RELEASE_NOTES_v4.34.0.md` → `RELEASE_NOTES_v4.38.0.md`
- `mcoi/tests/test_v4_29_atomic_rate_limit.py` → `test_v4_34_atomic_rate_limit.py`
- `mcoi/tests/test_v4_30_atomic_hash_chain.py` → `test_v4_35_atomic_hash_chain.py`
- `mcoi/tests/test_v4_31_atomic_audit_append.py` → `test_v4_36_atomic_audit_append.py`
- `mcoi/tests/test_v4_34_atomic_identity_rate_limit.py` → `test_v4_38_atomic_identity_rate_limit.py`

(There's already a `test_v4_34_env_tenant_binding.py` from the user's
parallel work — that one stays put. The rename of my `test_v4_34_atomic_*`
file resolves the namespace collision.)

Also update version mentions inside each release-note body and inside the
test files' module docstrings (search-and-replace `v4.29`→`v4.34`,
`v4.30`→`v4.35`, etc.).

**Alternative: ship them at their current numbers.** Acceptable if the user
prefers — release notes don't need to be globally monotonic, just unique
within a major. Pick whichever is less work.

The PR breakdown below uses the **renumbered scheme** (v4.34–v4.38).

---

## PR breakdown — four PRs in dependency order

### PR 1 — F15 atomic hash chain append (v4.35)

**Smallest, most self-contained — ship first.**

Files:
- `mcoi/mcoi_runtime/persistence/hash_chain.py` (modified — single-fracture file)
- `mcoi/tests/test_v4_35_atomic_hash_chain.py` (new — renamed from `test_v4_30_*`)
- `RELEASE_NOTES_v4.35.0.md` (new — renamed from `RELEASE_NOTES_v4.30.0.md`)

Suggested commit message:
```
fix(audit-f15): v4.35.0 — atomic hash chain append via O_EXCL

Pre-v4.35 HashChainStore.append used os.replace() which overwrote
pre-existing files, allowing two concurrent writers at the same
sequence to silently fork the chain. v4.35 adds try_append (the
atomic primitive using O_CREAT|O_EXCL) and turns append() into a
bounded retry wrapper. Cross-process atomicity now enforced at the
kernel level.

16 new tests; 17 existing hash_chain tests still pass.
```

No dependencies on other PRs in this series.

### PR 2 — F11 atomic rate limit (v4.34, both tenant and identity bundled)

**One PR for both halves of F11.** Tenant-level dispatch (originally local
v4.29) and identity-level dispatch (local v4.34) ship together — they touch
the same file and the second is a 15-LoC extension of the first.

Files:
- `mcoi/mcoi_runtime/core/rate_limiter.py` (full diff — both dispatch branches)
- `mcoi/mcoi_runtime/persistence/postgres_governance_stores.py` (selective hunks — see below)
- `mcoi/tests/test_v4_34_atomic_rate_limit.py` (renamed from local `test_v4_29_*`)
- `mcoi/tests/test_v4_38_atomic_identity_rate_limit.py` (renamed from local `test_v4_34_*`)
- `RELEASE_NOTES_v4.34.0.md` (renamed from local `v4.29`)
- `RELEASE_NOTES_v4.38.0.md` (renamed from local `v4.34`)

(Or merge the two release-note files into one combined `v4.34.0.md`
covering both halves — your call.)

**postgres_governance_stores.py hunk selection**: stage only the
`InMemoryRateLimitStore` and rate-limit-related hunks. Skip the
`InMemoryAuditStore` hunks (those go in PR 3). Use `git add -p` and answer
`y` to:

- The new `from hashlib import sha256` import (also needed by PR 3, keep it
  here since it doesn't hurt) — **OR** stage it in PR 3 and skip here.
- The `import time` (needed for `try_consume`).
- The `InMemoryRateLimitStore.__init__` change (adds `_buckets` and
  `_bucket_lock`).
- The `InMemoryRateLimitStore.try_consume` method addition.
- The class docstring update mentioning `try_consume`.

Skip:
- The `_canonical_hash_v1` import (for PR 3).
- The `InMemoryAuditStore.__init__` changes (sequence/last_hash/lock).
- The `InMemoryAuditStore.append` changes (lock + monotonic update).
- The `InMemoryAuditStore.try_append` method addition.

Suggested commit message:
```
fix(audit-f11): v4.34.0 — atomic rate limit enforcement under concurrent writes

RateLimitStore.try_consume names the atomic test-and-consume primitive;
RateLimiter.check delegates to the store when overridden via MRO
detection with a getattr default for duck-typed stores. This PR
closes both the tenant-level and identity-level dispatch — identity
buckets now share the same store-owned enforcement that tenant
buckets get.

InMemoryRateLimitStore.try_consume is the in-memory reference
implementation. PostgresRateLimitStore.try_consume is deferred to a
follow-on PR (needs schema migration for tokens/last_refill columns
and an atomic UPDATE WHERE conditional).

26 new tests (16 tenant + 10 identity); 47 existing rate-limit tests
still pass.
```

No dependencies. Ships independently of PR 1.

### PR 3 — F4 atomic audit append (v4.36)

**Smaller than PR 2.** Touches `audit_trail.py` and the audit-store-related
hunks of `postgres_governance_stores.py`.

Files:
- `mcoi/mcoi_runtime/core/audit_trail.py`
- `mcoi/mcoi_runtime/persistence/postgres_governance_stores.py` (selective hunks — the InMemoryAuditStore changes)
- `mcoi/tests/test_v4_36_atomic_audit_append.py` (renamed from local `test_v4_31_*`)
- `RELEASE_NOTES_v4.36.0.md` (renamed from local `v4.31`)

**postgres_governance_stores.py hunk selection** (the complement of PR 2):
stage only the `InMemoryAuditStore` hunks, the `_canonical_hash_v1` import,
and `from hashlib import sha256` if not already in PR 2.

Suggested commit message:
```
fix(audit-f4): v4.36.0 — atomic audit append under cross-worker concurrency

Pre-v4.36 each AuditTrail kept its own _sequence counter starting
at 0 and its own _last_hash starting at genesis — N workers writing
to one shared store produced a forked chain with N entries per
sequence linking to N different predecessors.

AuditStore.try_append names the atomic primitive that owns sequence
allocation and chain-head linkage. AuditTrail._record_locked
delegates via MRO detection (getattr default for duck-typed stores).
The canonical writer/verifier hash (LEDGER_SPEC.md v1) is unchanged —
the store calls the same _canonical_hash_v1 helper the in-process
path calls.

InMemoryAuditStore.try_append is the in-memory reference. Postgres
path deferred (needs SERIAL/identity column or FOR UPDATE on chain
head row).

15 new tests; 46 existing audit_trail tests still pass.
```

No dependencies. Ships independently of PRs 1 and 2.

### PR 4 — Atomic Store Doctrine + meta-tests (v4.37)

**Depends on PRs 1, 2, and 3 being merged.** The meta-test imports from all
four atomic-store files and asserts shape compliance across them.

Files:
- `docs/ATOMIC_STORE_DOCTRINE.md`
- `mcoi/tests/test_atomic_store_doctrine.py`
- `RELEASE_NOTES_v4.37.0.md` (new — write fresh; doctrine doesn't currently have a release note)

Suggested commit message:
```
docs(doctrine): v4.37.0 — atomic store doctrine + cross-fracture meta-tests

Distills v4.27 (F2 budget), v4.34 (F11 rate limit), v4.35 (F15 hash
chain), and v4.36 (F4 audit append) into a single five-step recipe.
Names when the doctrine applies (atomic test-and-update at storage
layer) and when it does not (F12 throughput, F8 architectural,
F1 routing).

The meta-test (test_atomic_store_doctrine.py) parametrizes shape
invariants across all four shipped stores — if a future refactor
breaks the override-detection idiom or drops the getattr default in
any of them, the meta-test fails immediately.

24 new tests (parametrized across 3-4 stores per shape invariant).
```

Suggested target: ship after PRs 1–3 land in trunk, so the meta-test imports
all resolve.

---

## Execution recipe

These commands assume the user starts on `fix/audit-f5-f6-tenant-binding`
with the working tree as it currently stands. Adjust branch names to your
convention.

### Phase 1 — Stash all doctrine-series files off the current branch

```bash
git stash push -m "doctrine-series-staging" -- \
  mcoi/mcoi_runtime/persistence/hash_chain.py \
  mcoi/mcoi_runtime/persistence/postgres_governance_stores.py \
  mcoi/mcoi_runtime/core/rate_limiter.py \
  mcoi/mcoi_runtime/core/audit_trail.py \
  RELEASE_NOTES_v4.29.0.md \
  RELEASE_NOTES_v4.30.0.md \
  RELEASE_NOTES_v4.31.0.md \
  RELEASE_NOTES_v4.34.0.md \
  docs/ATOMIC_STORE_DOCTRINE.md \
  mcoi/tests/test_atomic_store_doctrine.py \
  mcoi/tests/test_v4_29_atomic_rate_limit.py \
  mcoi/tests/test_v4_30_atomic_hash_chain.py \
  mcoi/tests/test_v4_31_atomic_audit_append.py \
  mcoi/tests/test_v4_34_atomic_identity_rate_limit.py
```

This keeps the user's tenant-binding work in the working tree and saves the
doctrine-series files in a stash entry.

### Phase 2 — Make each PR branch off `main`

```bash
git fetch origin main
# PR 1
git checkout -b fix/audit-f15-atomic-hash-chain origin/main
git stash apply --index  # bring back all doctrine files
# Now unstage everything not in PR 1, then commit.
git reset HEAD .
git add mcoi/mcoi_runtime/persistence/hash_chain.py \
        mcoi/tests/test_v4_30_atomic_hash_chain.py \
        RELEASE_NOTES_v4.30.0.md
# Rename per the recommended renumbering before staging if desired.
git commit -m "fix(audit-f15): v4.35.0 — atomic hash chain append via O_EXCL ..."
# Push and open PR.
```

Repeat for PRs 2, 3, 4 — each time:
- Branch off `origin/main` (or whatever the trunk is at PR-open time)
- `git stash apply --index` to bring back all the files
- `git reset HEAD .` then `git add` only the files for that PR
- For `postgres_governance_stores.py` / `rate_limiter.py`, use `git add -p`
  and select hunks per the guidance in PR 2 / PR 3 above
- Commit, push, open PR
- After all PRs are open, `git stash drop` the staging entry

### Phase 3 — After all four PRs merge

The user's `fix/audit-f5-f6-tenant-binding` branch still has its tenant-
binding work. That gets reviewed and merged on its own cadence. Drop the
stash entry once the doctrine series is fully merged.

---

## Pre-merge verification

For each PR, before pushing, run:

```bash
# In the mcoi/ directory:
python -m pytest tests/test_atomic_store_doctrine.py \
                tests/test_v4_27_atomic_budget.py \
                tests/test_v4_*_atomic_*.py \
                tests/test_audit_trail.py \
                tests/test_hash_chain.py \
                tests/test_rate_limiter.py \
                tests/test_identity_rate_limit.py \
                tests/test_tenant_budget.py -q
```

Expected (with all four PRs applied locally): 233 tests pass. Each
intermediate PR should pass its own slice (PR 1: 33 tests; PR 2: 73 tests;
PR 3: 61 tests; PR 4: 24 tests; full series: 233 tests).

---

## Risks and rollback

- **Risk 1**: forgetting to rename a `v4.29` reference inside a moved file.
  Mitigation: after rename, `grep -rn "v4\.29" mcoi/tests/test_v4_34_*` (or
  whatever the new filename is) — should return zero hits.
- **Risk 2**: hunk-stage-and-miss for `postgres_governance_stores.py`.
  Mitigation: after staging PR 2, run `git diff --cached` and confirm the
  diff contains `RateLimitStore` / `InMemoryRateLimitStore` references but
  NOT `InMemoryAuditStore`. Same in reverse for PR 3.
- **Risk 3**: stash apply conflicts with the user's tenant-binding work.
  None of the doctrine-series files overlap with user files (verified by
  reading the file lists above), so `stash apply` should be clean. If
  conflicts surface, the file lists in this document let you reason about
  which side to keep.
- **Rollback**: `git stash drop` only after all four PRs are merged. The
  stash is the safety net.

---

## Coverage check

Every uncommitted file the doctrine series touched is accounted for above:

**Modified (4 files):**
- ✅ `mcoi/mcoi_runtime/core/audit_trail.py` → PR 3
- ✅ `mcoi/mcoi_runtime/core/rate_limiter.py` → PR 2 (both halves)
- ✅ `mcoi/mcoi_runtime/persistence/hash_chain.py` → PR 1
- ✅ `mcoi/mcoi_runtime/persistence/postgres_governance_stores.py` → PR 2 + PR 3 (split by hunk)

**Untracked (10 files):**
- ✅ `RELEASE_NOTES_v4.29.0.md` → PR 2 (rename to v4.34.0)
- ✅ `RELEASE_NOTES_v4.30.0.md` → PR 1 (rename to v4.35.0)
- ✅ `RELEASE_NOTES_v4.31.0.md` → PR 3 (rename to v4.36.0)
- ✅ `RELEASE_NOTES_v4.34.0.md` → PR 2 (rename to v4.38.0)
- ✅ `docs/ATOMIC_STORE_DOCTRINE.md` → PR 4
- ✅ `mcoi/tests/test_atomic_store_doctrine.py` → PR 4
- ✅ `mcoi/tests/test_v4_29_atomic_rate_limit.py` → PR 2 (rename to v4.34)
- ✅ `mcoi/tests/test_v4_30_atomic_hash_chain.py` → PR 1 (rename to v4.35)
- ✅ `mcoi/tests/test_v4_31_atomic_audit_append.py` → PR 3 (rename to v4.36)
- ✅ `mcoi/tests/test_v4_34_atomic_identity_rate_limit.py` → PR 2 (rename to v4.38)

All 14 doctrine-series files mapped. The remaining 35 modified/untracked
files in the working tree belong to the user's parallel work and are
explicitly not covered by this plan.
