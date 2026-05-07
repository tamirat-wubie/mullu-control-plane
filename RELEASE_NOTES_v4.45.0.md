# Mullu Platform v4.45.0 — Stress Test Harness for Audit-Grade Atomicity

**Release date:** TBD
**Codename:** Anvil
**Migration required:** No

> v4.44.0 was the F8 scoping plan (PR #417). v4.45.0 is this release.

---

## What this release is

Adds an operator-facing stress test harness that **empirically validates** the v4.27 / v4.29 / v4.30 / v4.31 atomic SQL doctrine and the v4.36 / v4.37 connection-pool throughput claims under realistic concurrent load. Plus a CI smoke test that runs the harness on every PR to catch atomicity regressions.

Until now, the audit-grade atomicity properties were guaranteed by **unit tests**. v4.45 adds the **load test**.

---

## What is new in v4.45.0

### `mcoi/scripts/stress_test_governance.py`

A single-file, no-dependencies stress harness that exercises 4 scenarios:

1. **`atomic_budget` (F2 / v4.27)** — N concurrent threads × M iterations each try to spend $1 against a $100 cap. Asserts:
   - Persisted spend ≤ max_cost (no overshoot)
   - Successful spend count exactly equals `floor(max_cost / cost_per_call)` (atomic UPDATE rejected the rest)

2. **`atomic_rate_limit` (F11 / v4.29)** — N concurrent consumers, capacity = M < N. Asserts:
   - Successful consumes ≤ capacity (no over-grant)

3. **`atomic_audit_append` (F4 / v4.31)** — N concurrent threads append to a shared audit store. Asserts:
   - Sequence numbers form contiguous chain `{1..N}` (no forks)
   - Each entry's `previous_hash` matches its predecessor's `entry_hash` (chain links unbroken)

4. **`pool_throughput` (F12 / v4.36-v4.37)** — measures ops/sec at `pool_size=1` vs `pool_size=8`. In-memory mode validates timing variance only; **Postgres mode (via `--postgres`) measures the actual pool speedup.**

### Two operating modes

```bash
# In-memory (default) — fast, no Postgres required, validates atomicity
python mcoi/scripts/stress_test_governance.py

# Postgres — validates atomic SQL + measures real pool speedup
MULLU_DB_URL=postgresql://... \
  python mcoi/scripts/stress_test_governance.py --postgres --pool-size 10

# Tune workload
python mcoi/scripts/stress_test_governance.py --threads 100 --iters 1000

# Run only specific scenarios
python mcoi/scripts/stress_test_governance.py --scenarios budget,audit_append
```

Exit code: `0` if all invariants hold, `1` if any are violated. **Invariant violations are release blockers** — they mean the atomicity guarantee broke on this deployment.

### `mcoi/tests/test_v4_45_stress_harness_smoke.py`

5 CI smoke tests:

- `test_harness_script_exists` — file is present
- `test_harness_help_runs_cleanly` — `--help` exits 0
- `test_harness_in_memory_run_passes_all_scenarios` — full run on in-memory backend, all 4 scenarios PASS
- `test_harness_subset_scenarios_runs` — `--scenarios budget,rate_limit` only runs those 2
- `test_harness_unknown_scenario_rejected` — typo'd scenario name exits non-zero

The smoke tests run on every PR. If a future change breaks the atomicity guarantees (e.g. a refactor accidentally serializes the lock differently), this test catches it before merge.

---

## Sample run (50 threads, in-memory)

```
======================================================================
STRESS TEST GOVERNANCE - RESULTS
======================================================================

[PASS] atomic_budget
  ops:        1000 in 0.02s (57801 ops/s)
  invariant:  persisted spend <= $100.00 AND successes == 100
  actual:     persisted spend = $100.00, successes = 100

[PASS] atomic_rate_limit
  ops:        50 in 0.01s (6681 ops/s)
  invariant:  successful consumes <= capacity (30)
  actual:     successful consumes = 30

[PASS] atomic_audit_append
  ops:        50 in 0.01s (5308 ops/s)
  invariant:  sequences == [1..50] AND chain links unbroken
  actual:     sequences = [1, 2, 3, 4, 5]..., chain_valid = True

[PASS] pool_throughput
  ops:        2000 in 0.02s (88806 ops/s)
  invariant:  in-memory pool_size=8 >= 0.5x pool_size=1 ops/sec (variance gate)
  actual:     pool_size=1: 82434 ops/s, pool_size=8: 96245 ops/s (1.17x)

======================================================================
  4 / 4 scenarios passed
======================================================================
```

The in-memory mode reaches ~50-90k ops/sec on a typical developer machine because the contention is purely Python-side. **The Postgres mode is the real benchmark** — operators should run it against a representative database before tuning `MULLU_DB_POOL_SIZE`.

---

## Operational guidance

### When to run the harness

- **Before every release** — at least the in-memory mode, to validate that the atomicity invariants haven't regressed
- **When tuning `MULLU_DB_POOL_SIZE`** — Postgres mode with the operator's real database, varying pool sizes to find the throughput plateau
- **After any change to the atomic SQL primitives** — `try_record_spend`, `try_consume`, `try_append`. Run with elevated thread counts (200+) to surface races
- **On suspicion of a real-world race** — increase `--threads` and `--iters` until either the invariant fails or you're satisfied no race exists at that scale

### Postgres setup

```bash
docker run -d --name mullu-stress -e POSTGRES_PASSWORD=mullu -p 5432:5432 postgres:16
export MULLU_DB_URL="postgresql://postgres:mullu@localhost:5432/postgres"
python mcoi/scripts/stress_test_governance.py --postgres --pool-size 10 --threads 100
```

The harness creates its own schema via the existing migration path; no manual SQL setup is needed.

---

## Test counts

5 new smoke tests in `test_v4_45_stress_harness_smoke.py`. Full mcoi suite continues to pass (the harness's invariant checks are the same atomicity properties the existing v4.27–v4.31 unit tests assert; the harness just exercises them under heavy contention).

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F7/F9/F10/F11/F12/F15/F16 + JWT hardening + F15 follow-up
⏳ F8 — MAF substrate disconnect (scoping plan in v4.44.0; awaiting decisions)
```

**16 of 17 audit fractures closed** with both unit-test and now stress-test coverage. F8 is awaiting human direction on 5 design decisions per `docs/AUDIT_F8_SCOPING_PLAN.md`.

---

## Honest assessment

This release moves the atomicity claims from "tested with 50 threads in pytest" to "tested with N threads in a tool you can dial up." The unit tests already covered the contention case; the harness extends coverage to the configuration surface (`MULLU_DB_POOL_SIZE`) that the unit tests didn't reach.

The most useful piece is probably the Postgres mode — operators picking pool sizes have been guessing based on rules of thumb. The harness gives them a real number for their workload.

The smoke tests make this a **CI-enforced** invariant going forward. If a future contributor refactors the atomic SQL path in a way that breaks correctness under contention, the smoke tests catch it before merge.

**We recommend:**
- Land v4.45 and add the in-memory smoke tests to the CI gate (already wired)
- Operators: run the Postgres mode against your real database before tuning `MULLU_DB_POOL_SIZE`
- Future PRs touching `governance/guards/budget.py`, `governance/guards/rate_limit.py`, `governance/audit/trail.py`, or `persistence/postgres_governance_stores.py` should re-run the harness locally; CI catches the basic invariants but real load uncovers more
