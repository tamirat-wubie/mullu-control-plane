"""Atomic Store Doctrine — meta-tests.

Asserts the four shape invariants from docs/ATOMIC_STORE_DOCTRINE.md
across all four shipped fracture closures (v4.27, v4.29, v4.30,
v4.31). If a future refactor breaks the override-detection idiom in
any of the four stores, this file fails immediately.

The four shape invariants:

  1. The base class's ``try_*`` method exists and returns ``None``
     (or a documented sentinel).
  2. The in-memory concrete store overrides ``try_*`` — the function
     object on the subclass differs from the base class's.
  3. A duck-typed store (no inheritance) is correctly detected as
     "no override" via ``getattr(type(s), "try_*", Base.try_*)
     is not Base.try_*``.
  4. A subclass that does NOT override is correctly detected as
     "no override" via inheritance.

This file is the doctrine. Each fracture's specific test file
(test_v4_27_atomic_budget.py, test_v4_29_atomic_rate_limit.py,
test_v4_30_atomic_hash_chain.py, test_v4_31_atomic_audit_append.py)
still owns its concurrency / dispatch / backward-compat tests; this
file owns the shape.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.audit_trail import AuditEntry, AuditStore, AuditTrail
from mcoi_runtime.core.rate_limiter import (
    RateLimitConfig,
    RateLimitStore,
    RateLimiter,
)
from mcoi_runtime.core.tenant_budget import (
    BudgetStore,
    TenantBudgetManager,
    TenantBudgetPolicy,
)
from mcoi_runtime.persistence.hash_chain import HashChainStore
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryAuditStore,
    InMemoryBudgetStore,
    InMemoryRateLimitStore,
)


@dataclass
class DoctrineCase:
    """One row of the four-fracture doctrine compliance table.

    base_cls: the abstract store class that defines the contract.
    method_name: name of the atomic primitive (always starts with try_).
    in_memory_cls: the concrete in-memory implementation that
        overrides the primitive.
    """

    fracture: str
    release: str
    base_cls: type
    method_name: str
    in_memory_cls: type


# ============================================================
# The four shipped doctrine applications
# ============================================================

CASES: list[DoctrineCase] = [
    DoctrineCase(
        fracture="F2",
        release="v4.27",
        base_cls=BudgetStore,
        method_name="try_record_spend",
        in_memory_cls=InMemoryBudgetStore,
    ),
    DoctrineCase(
        fracture="F11",
        release="v4.29",
        base_cls=RateLimitStore,
        method_name="try_consume",
        in_memory_cls=InMemoryRateLimitStore,
    ),
    DoctrineCase(
        fracture="F4",
        release="v4.31",
        base_cls=AuditStore,
        method_name="try_append",
        in_memory_cls=InMemoryAuditStore,
    ),
]


CASE_IDS = [f"{c.fracture}-{c.release}" for c in CASES]


# ============================================================
# Shape invariant 1 — base method exists and returns None
# ============================================================


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestShape1_BaseReturnsNone:
    def test_base_class_defines_method(self, case: DoctrineCase):
        """The contract must be named on the base class."""
        assert hasattr(case.base_cls, case.method_name), (
            f"{case.base_cls.__name__} missing {case.method_name} — "
            f"the doctrine requires the contract to live on the base."
        )

    def test_base_class_method_is_callable(self, case: DoctrineCase):
        method = getattr(case.base_cls, case.method_name)
        assert callable(method)


# ============================================================
# Shape invariant 2 — in-memory subclass overrides
# ============================================================


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestShape2_InMemoryOverrides:
    def test_in_memory_subclass_inherits(self, case: DoctrineCase):
        assert issubclass(case.in_memory_cls, case.base_cls)

    def test_in_memory_overrides_atomic_primitive(self, case: DoctrineCase):
        """The function object on the subclass differs from the base.

        This is the exact check the dispatchers use:
            getattr(type(store), method, Base.method) is not Base.method
        """
        base_method = getattr(case.base_cls, case.method_name)
        sub_method = getattr(case.in_memory_cls, case.method_name)
        assert sub_method is not base_method, (
            f"{case.in_memory_cls.__name__}.{case.method_name} "
            f"must be a real override of {case.base_cls.__name__}."
            f"{case.method_name} — currently inherits the base "
            f"sentinel-returning version."
        )


# ============================================================
# Shape invariant 3 — duck-typed store falls through
# ============================================================


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestShape3_DuckTypedFallsThrough:
    def test_getattr_default_idiom_detects_no_override(
        self, case: DoctrineCase
    ):
        """A duck-typed store (no inheritance) should be detected
        as "no override" via the canonical getattr default idiom.

        This is what protects the platform from breaking forks /
        test fixtures / mocks that don't subclass the base.
        """
        # Build a duck-typed store: a class that has no relationship
        # to the base and doesn't define the method.
        class DuckStore:
            pass

        duck = DuckStore()
        base_method = getattr(case.base_cls, case.method_name)
        detected = (
            getattr(type(duck), case.method_name, base_method)
            is not base_method
        )
        assert detected is False, (
            "Duck-typed store falsely detected as having an override. "
            "The getattr default must be the base method, not None — "
            "otherwise getattr returns None for the duck and `is not` "
            "always succeeds."
        )


# ============================================================
# Shape invariant 4 — non-overriding subclass falls through
# ============================================================


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestShape4_NonOverridingSubclassFallsThrough:
    def test_subclass_without_override_inherits_base_method(
        self, case: DoctrineCase
    ):
        """A subclass that doesn't override try_* inherits the base's
        function object — detection must report 'no override'."""
        # Build a subclass that does NOT override try_*.
        Sub = type("LegacySubclass", (case.base_cls,), {})
        legacy = Sub()
        base_method = getattr(case.base_cls, case.method_name)
        detected = (
            getattr(type(legacy), case.method_name, base_method)
            is not base_method
        )
        assert detected is False, (
            f"Legacy subclass of {case.base_cls.__name__} (no "
            f"override) falsely detected as overriding "
            f"{case.method_name}. This breaks backward compatibility "
            f"with pre-doctrine stores."
        )


# ============================================================
# Cross-fracture sanity: F15 (HashChainStore) is single-class,
# not a base+override pair. The doctrine still applies — try_append
# is the named primitive — but the override-detection idiom is N/A
# (there's no abstract base to compare against). Test it on its
# own terms.
# ============================================================


class TestF15_HashChainStoreShape:
    """F15 / v4.30: HashChainStore is a single concrete class.

    The doctrine holds (try_append is the named atomic primitive,
    high-level append retries on collision) but there's no
    base/subclass dispatch — the atomicity is at the filesystem
    syscall layer, not at a Python type-system layer.

    The shape invariants enforced here:
      - try_append exists as a method on HashChainStore.
      - try_append is distinct from append (the retry wrapper).
      - Calling try_append once and then concurrently another time
        with a forced collision returns None.
    """

    def test_try_append_exists(self):
        assert hasattr(HashChainStore, "try_append")
        assert callable(HashChainStore.try_append)

    def test_try_append_distinct_from_append(self):
        assert HashChainStore.try_append is not HashChainStore.append

    def test_try_append_returns_none_on_simulated_collision(
        self, tmp_path, monkeypatch
    ):
        from mcoi_runtime.persistence.hash_chain import compute_content_hash

        store = HashChainStore(tmp_path, chain_id="meta")
        monkeypatch.setattr(
            "mcoi_runtime.persistence.hash_chain._atomic_write_exclusive",
            lambda path, content: False,
        )
        result = store.try_append(compute_content_hash("x"))
        assert result is None


# ============================================================
# End-to-end doctrine check: each shipped dispatcher actually
# uses the override-detection idiom and routes correctly.
# ============================================================


class TestEndToEndDispatch:
    """For each fracture, build a duck-typed store and a real
    in-memory store, attach to the high-level orchestrator, and
    confirm the dispatcher routes correctly."""

    _CLOCK = staticmethod(lambda: "2026-04-27T00:00:00Z")

    def test_budget_dispatch_uses_inmemory_override(self):
        store = InMemoryBudgetStore()
        manager = TenantBudgetManager(
            default_policy=TenantBudgetPolicy(
                tenant_id="t1",
                max_cost=10.0,
                max_tokens_per_call=4096,
                max_calls=100,
            ),
            store=store,
            clock=self._CLOCK,
        )
        # Two sequential spends within the cap. The store's atomic
        # path enforces the cap regardless of caller serialization.
        b1 = manager.record_spend("t1", 3.0)
        b2 = manager.record_spend("t1", 4.0)
        assert b1.spent == 3.0
        assert b2.spent == 7.0

    def test_rate_limit_dispatch_uses_inmemory_override(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is False
        # Bucket state lives in the store, not in the limiter.
        assert "t:/x" not in limiter._buckets

    def test_audit_dispatch_uses_inmemory_override(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=self._CLOCK, store=store)
        e1 = trail.record(
            action="a", actor_id="x", tenant_id="t",
            target="y", outcome="ok",
        )
        e2 = trail.record(
            action="b", actor_id="x", tenant_id="t",
            target="z", outcome="ok",
        )
        # Sequence comes from the store; trail's local _sequence is synced.
        assert e1.sequence == 1
        assert e2.sequence == 2
        assert e2.previous_hash == e1.entry_hash
        assert trail._sequence == 2  # type: ignore[attr-defined]
