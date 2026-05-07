"""v4.27.0 — atomic budget enforcement under concurrent writes (audit F2).

Pre-v4.27 the manager's ``record_spend`` was a read-modify-write pattern
on an in-memory dict, with the persistent store updated via UPSERT
that wrote whatever value Python computed. The audit's worked example:

  - Two replicas read ``spent=$5`` simultaneously.
  - Each computes ``$5 + $1 = $6`` independently.
  - Each UPSERT writes ``$6`` (last-write-wins).
  - Real spend is ``$7``; stored is ``$6``.
  - The hard limit was, in practice, soft by N replicas.

v4.27 introduces ``BudgetStore.try_record_spend`` that atomically does
test-and-update at the storage layer:

  - InMemoryBudgetStore: ``threading.Lock``-guarded compare-and-swap.
  - PostgresBudgetStore: ``UPDATE … WHERE spent + $1 <= max_cost
    RETURNING …``. DB row is the only source of truth.

The manager's ``record_spend`` prefers ``try_record_spend``. Stores
that don't override (the base class) fall through to the legacy path
for backward compatibility, but signal as such — production code uses
the atomic path.

These tests exercise the in-memory atomic path under thread concurrency.
The Postgres path is tested separately via integration tests against a
real DB (CI infrastructure not always present).
"""
from __future__ import annotations

import threading

import pytest

from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.governance.guards.budget import (
    BudgetStore,
    TenantBudgetManager,
    TenantBudgetPolicy,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryBudgetStore,
)


_FIXED_CLOCK = lambda: "2026-01-01T00:00:00Z"


# ============================================================
# BudgetStore base class
# ============================================================


def test_base_store_try_record_spend_returns_none():
    """The base class returns None — the manager treats this as
    'store doesn't implement atomic path' and falls back."""
    store = BudgetStore()
    assert store.try_record_spend("acme", 1.0) is None


def test_base_store_signals_legacy_fallback():
    """``record_spend`` on a manager with the BASE BudgetStore should
    succeed via the legacy path (read-modify-write in-memory)."""
    store = BudgetStore()  # base class with no atomic path
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=10.0),
    )
    # Manager auto-creates the budget — but the base store's save is a
    # no-op so the legacy path takes over for write
    out = mgr.record_spend("acme", 3.0)
    assert out.spent == 3.0
    assert out.calls_made == 1


# ============================================================
# InMemoryBudgetStore.try_record_spend semantics
# ============================================================


def _seed_budget(store: InMemoryBudgetStore, tenant: str, max_cost: float) -> None:
    store.save(LLMBudget(
        budget_id=f"bid-{tenant}",
        tenant_id=tenant,
        max_cost=max_cost,
        spent=0.0,
        max_tokens_per_call=4096,
        max_calls=1000,
        calls_made=0,
    ))


def test_in_memory_atomic_returns_updated_budget_on_success():
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 10.0)
    out = store.try_record_spend("acme", 3.0)
    assert out is not None
    assert out.spent == 3.0
    assert out.calls_made == 1


def test_in_memory_atomic_returns_none_when_exceeds_max():
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 5.0)
    store.try_record_spend("acme", 4.0)
    # Now spent=4. A 2.0 spend would push it to 6 > 5 → reject.
    out = store.try_record_spend("acme", 2.0)
    assert out is None
    # Existing state unchanged
    assert store.load("acme").spent == 4.0


def test_in_memory_atomic_returns_none_for_unknown_tenant():
    store = InMemoryBudgetStore()
    out = store.try_record_spend("never-seen", 1.0)
    assert out is None


def test_in_memory_atomic_exact_remaining_budget_succeeds():
    """spent + cost == max_cost is allowed (boundary check uses <=)."""
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 10.0)
    out = store.try_record_spend("acme", 10.0)
    assert out is not None
    assert out.spent == 10.0


def test_in_memory_atomic_one_cent_over_max_rejects():
    """spent + cost > max_cost is rejected even by a tiny margin."""
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 10.0)
    out = store.try_record_spend("acme", 10.0001)
    assert out is None


# ============================================================
# Concurrency: the F2 fix in action
# ============================================================


def test_concurrent_spends_sum_exactly_to_remaining_budget():
    """The audit's exact scenario: N concurrent replicas each calling
    record_spend should NOT overrun max_cost. Pre-v4.27 they could.

    Setup: 100 threads each try to spend $1. Budget is $10.
    Expected: exactly 10 succeed, exactly 90 see exhaustion.
    Final spent: exactly $10.
    """
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 10.0)

    successes: list[LLMBudget] = []
    failures: list[None] = []
    success_lock = threading.Lock()

    def worker():
        result = store.try_record_spend("acme", 1.0)
        with success_lock:
            if result is not None:
                successes.append(result)
            else:
                failures.append(None)

    threads = [threading.Thread(target=worker) for _ in range(100)]
    for t in threads: t.start()
    for t in threads: t.join()

    # The strong invariant: NO overrun
    final = store.load("acme")
    assert final.spent <= 10.0, f"OVERRUN: spent {final.spent} > max_cost 10.0"
    # Exactly 10 callers succeeded (each spending $1 from a $10 budget)
    assert len(successes) == 10
    assert len(failures) == 90
    # Final accounting matches
    assert final.spent == 10.0
    assert final.calls_made == 10


def test_concurrent_spends_with_uneven_costs():
    """Mixed cost amounts. Budget=$20, ten threads × $1 + ten threads × $5.
    The first ten succeed at $1 ($10 used). Of the ten $5 attempts, only
    two more can fit ($10 + $5 + $5 = $20). Remaining 8 fail.
    """
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 20.0)

    success_count = [0]
    fail_count = [0]
    lock = threading.Lock()

    def worker(cost: float):
        result = store.try_record_spend("acme", cost)
        with lock:
            if result is not None:
                success_count[0] += 1
            else:
                fail_count[0] += 1

    threads = []
    for _ in range(10):
        threads.append(threading.Thread(target=worker, args=(1.0,)))
    for _ in range(10):
        threads.append(threading.Thread(target=worker, args=(5.0,)))
    for t in threads: t.start()
    for t in threads: t.join()

    final = store.load("acme")
    # The strong invariant: never overrun
    assert final.spent <= 20.0


def test_concurrent_already_exhausted_all_calls_fail():
    """Budget pre-exhausted; 50 concurrent attempts all fail."""
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 10.0)
    # Pre-exhaust
    store.try_record_spend("acme", 10.0)
    failures = [0]
    lock = threading.Lock()

    def worker():
        result = store.try_record_spend("acme", 0.5)
        with lock:
            if result is None:
                failures[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert failures[0] == 50
    assert store.load("acme").spent == 10.0  # unchanged


def test_concurrent_spends_across_tenants_dont_interfere():
    """Two tenants' budgets are independent under concurrent load."""
    store = InMemoryBudgetStore()
    _seed_budget(store, "acme", 5.0)
    _seed_budget(store, "bigco", 5.0)

    def worker(tenant: str):
        store.try_record_spend(tenant, 1.0)

    threads = []
    for _ in range(10):
        threads.append(threading.Thread(target=worker, args=("acme",)))
    for _ in range(10):
        threads.append(threading.Thread(target=worker, args=("bigco",)))
    for t in threads: t.start()
    for t in threads: t.join()

    # Each tenant capped at $5 independently
    assert store.load("acme").spent == 5.0
    assert store.load("bigco").spent == 5.0


# ============================================================
# Manager-level integration: record_spend uses atomic path
# ============================================================


def test_manager_record_spend_uses_atomic_store_path():
    """When the store implements try_record_spend, the manager uses it."""
    store = InMemoryBudgetStore()
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=10.0),
    )
    # First call: ensure_budget creates a row, then try_record_spend
    # increments it atomically.
    result = mgr.record_spend("acme", 3.0)
    assert result.spent == 3.0
    assert result.calls_made == 1


def test_manager_record_spend_raises_on_exhaustion():
    """When the atomic path returns None (exhaustion), the manager
    raises ``ValueError("budget exhausted")``."""
    store = InMemoryBudgetStore()
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=5.0),
    )
    mgr.record_spend("acme", 4.0)  # spent = 4
    with pytest.raises(ValueError, match="budget exhausted"):
        mgr.record_spend("acme", 2.0)  # would push to 6 > 5


def test_manager_concurrent_record_spend_does_not_overrun():
    """End-to-end: 50 threads through manager.record_spend; budget=$10,
    cost=$1; exactly 10 succeed, 40 raise budget_exhausted."""
    store = InMemoryBudgetStore()
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=10.0),
    )

    successes = [0]
    exhaustions = [0]
    other_errors: list[str] = []
    lock = threading.Lock()

    def worker():
        try:
            mgr.record_spend("acme", 1.0)
            with lock:
                successes[0] += 1
        except ValueError as exc:
            with lock:
                if "budget exhausted" in str(exc):
                    exhaustions[0] += 1
                else:
                    other_errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert other_errors == []
    assert successes[0] == 10  # exactly fills the $10 budget
    assert exhaustions[0] == 40
    final = store.load("acme")
    assert final.spent == 10.0
    assert final.calls_made == 10


# ============================================================
# Backward compatibility: a custom store that doesn't override
# try_record_spend still works via legacy path
# ============================================================


class _LegacyStore(BudgetStore):
    """Custom store with NO atomic path override — exercises the
    manager's legacy fallback. Must inherit from BudgetStore for
    the type-check fallback signal to fire."""

    def __init__(self) -> None:
        self._budgets: dict[str, LLMBudget] = {}

    def load(self, tenant_id: str) -> LLMBudget | None:
        return self._budgets.get(tenant_id)

    def save(self, budget: LLMBudget) -> None:
        self._budgets[budget.tenant_id] = budget


def test_legacy_store_falls_through_to_read_modify_write():
    """Pre-v4.27 stores that don't override try_record_spend continue
    to work. The manager detects no-atomic-path via type check on
    ``try_record_spend`` and falls back."""
    store = _LegacyStore()
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=10.0),
    )
    out = mgr.record_spend("acme", 3.0)
    assert out.spent == 3.0
    # Persistent write happened via legacy save
    assert store.load("acme").spent == 3.0


def test_legacy_store_still_blocks_at_max_cost():
    """Legacy path still enforces max_cost, just not atomically across
    replicas. Single-process correctness preserved."""
    store = _LegacyStore()
    mgr = TenantBudgetManager(
        clock=_FIXED_CLOCK,
        store=store,
        default_policy=TenantBudgetPolicy(tenant_id="__default__", max_cost=5.0),
    )
    mgr.record_spend("acme", 4.0)
    with pytest.raises(ValueError, match="budget exhausted"):
        mgr.record_spend("acme", 2.0)
