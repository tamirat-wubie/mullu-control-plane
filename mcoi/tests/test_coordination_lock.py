"""Coordination Lock Tests — Tenant-scoped resource locking."""

import threading
import time

import pytest
from mcoi_runtime.core.coordination_lock import (
    CoordinationLockManager,
    LockInfo,
    LockResult,
)


# ── Basic acquire/release ──────────────────────────────────────

class TestBasicLocking:
    def test_acquire_and_release(self):
        mgr = CoordinationLockManager()
        result = mgr.acquire("t1", "account:123", holder_id="s1")
        assert result.acquired is True
        assert result.resource_key == "account:123"
        assert mgr.is_locked("t1", "account:123") is True
        assert mgr.release("t1", "account:123", holder_id="s1") is True
        assert mgr.is_locked("t1", "account:123") is False

    def test_acquire_conflict(self):
        mgr = CoordinationLockManager(default_timeout=0.0)
        mgr.acquire("t1", "order:1", holder_id="s1")
        result = mgr.acquire("t1", "order:1", holder_id="s2")
        assert result.acquired is False
        assert "timed out" in result.error

    def test_release_wrong_holder(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        assert mgr.release("t1", "res:1", holder_id="s2") is False
        assert mgr.is_locked("t1", "res:1") is True

    def test_release_not_held(self):
        mgr = CoordinationLockManager()
        assert mgr.release("t1", "res:1", holder_id="s1") is False

    def test_double_release(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        assert mgr.release("t1", "res:1", holder_id="s1") is True
        assert mgr.release("t1", "res:1", holder_id="s1") is False


# ── Tenant isolation ───────────────────────────────────────────

class TestTenantIsolation:
    def test_same_resource_different_tenants(self):
        mgr = CoordinationLockManager()
        r1 = mgr.acquire("t1", "account:123", holder_id="s1")
        r2 = mgr.acquire("t2", "account:123", holder_id="s2")
        assert r1.acquired is True
        assert r2.acquired is True  # Different tenants, no conflict

    def test_tenant_locks_independent(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        assert mgr.is_locked("t1", "res:1") is True
        assert mgr.is_locked("t2", "res:1") is False


# ── TTL expiration ─────────────────────────────────────────────

class TestTTLExpiration:
    def test_expired_lock_released(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            default_ttl=1.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:1", holder_id="s1")
        assert mgr.is_locked("t1", "res:1") is True
        now[0] = 2.0  # Advance past TTL
        assert mgr.is_locked("t1", "res:1") is False

    def test_expired_lock_allows_new_holder(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            default_ttl=1.0, default_timeout=0.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:1", holder_id="s1")
        now[0] = 2.0  # Expire
        result = mgr.acquire("t1", "res:1", holder_id="s2")
        assert result.acquired is True

    def test_custom_ttl(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            default_ttl=10.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:1", holder_id="s1", ttl=0.5)
        now[0] = 1.0  # Past custom TTL but within default
        assert mgr.is_locked("t1", "res:1") is False

    def test_expired_count_tracked(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            default_ttl=1.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:1", holder_id="s1")
        now[0] = 2.0
        mgr.is_locked("t1", "res:1")  # Triggers reap
        status = mgr.status()
        assert status["total_expired"] >= 1


# ── Reentrant locking ─────────────────────────────────────────

class TestReentrantLocking:
    def test_same_holder_reacquires(self):
        mgr = CoordinationLockManager()
        r1 = mgr.acquire("t1", "res:1", holder_id="s1")
        r2 = mgr.acquire("t1", "res:1", holder_id="s1")
        assert r1.acquired is True
        assert r2.acquired is True  # Reentrant

    def test_reacquire_refreshes_ttl(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            default_ttl=2.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:1", holder_id="s1")
        now[0] = 1.5  # Close to expiry
        mgr.acquire("t1", "res:1", holder_id="s1")  # Refresh
        now[0] = 3.0  # Past original TTL but within refreshed
        assert mgr.is_locked("t1", "res:1") is True


# ── Context manager ────────────────────────────────────────────

class TestContextManager:
    def test_lock_context_manager(self):
        mgr = CoordinationLockManager()
        with mgr.lock("t1", "res:1", holder_id="s1") as result:
            assert result.acquired is True
            assert mgr.is_locked("t1", "res:1") is True
        assert mgr.is_locked("t1", "res:1") is False  # Auto-released

    def test_lock_context_manager_on_exception(self):
        mgr = CoordinationLockManager()
        with pytest.raises(ValueError):
            with mgr.lock("t1", "res:1", holder_id="s1"):
                raise ValueError("oops")
        assert mgr.is_locked("t1", "res:1") is False  # Still released

    def test_lock_context_manager_conflict_raises(self):
        mgr = CoordinationLockManager(default_timeout=0.0)
        mgr.acquire("t1", "res:1", holder_id="s1")
        with pytest.raises(RuntimeError, match="failed to acquire"):
            with mgr.lock("t1", "res:1", holder_id="s2"):
                pass  # Should not reach here


# ── Concurrent access ──────────────────────────────────────────

class TestConcurrentAccess:
    def test_concurrent_acquire_one_wins(self):
        mgr = CoordinationLockManager(default_timeout=0.1)
        results: list[LockResult] = []

        def try_acquire(holder):
            r = mgr.acquire("t1", "res:1", holder_id=holder)
            results.append(r)

        t1 = threading.Thread(target=try_acquire, args=("h1",))
        t2 = threading.Thread(target=try_acquire, args=("h2",))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        acquired = [r for r in results if r.acquired]
        assert len(acquired) == 1  # Exactly one wins

    def test_waiter_acquires_after_release(self):
        mgr = CoordinationLockManager(default_timeout=5.0)
        acquired_order: list[str] = []

        def holder1():
            mgr.acquire("t1", "res:1", holder_id="h1")
            acquired_order.append("h1")
            time.sleep(0.05)
            mgr.release("t1", "res:1", holder_id="h1")

        def holder2():
            time.sleep(0.01)  # Let h1 acquire first
            result = mgr.acquire("t1", "res:1", holder_id="h2")
            if result.acquired:
                acquired_order.append("h2")
                mgr.release("t1", "res:1", holder_id="h2")

        t1 = threading.Thread(target=holder1)
        t2 = threading.Thread(target=holder2)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert acquired_order == ["h1", "h2"]


# ── Capacity and bounding ─────────────────────────────────────

class TestCapacity:
    def test_bounded_locks(self):
        mgr = CoordinationLockManager(max_locks=5, default_timeout=0.0)
        for i in range(5):
            r = mgr.acquire("t1", f"res:{i}", holder_id="s1")
            assert r.acquired is True
        r = mgr.acquire("t1", "res:5", holder_id="s1")
        assert r.acquired is False
        assert "capacity" in r.error

    def test_capacity_freed_by_release(self):
        mgr = CoordinationLockManager(max_locks=2, default_timeout=0.0)
        mgr.acquire("t1", "res:0", holder_id="s1")
        mgr.acquire("t1", "res:1", holder_id="s1")
        mgr.release("t1", "res:0", holder_id="s1")
        r = mgr.acquire("t1", "res:2", holder_id="s1")
        assert r.acquired is True

    def test_capacity_freed_by_expiry(self):
        now = [0.0]
        mgr = CoordinationLockManager(
            max_locks=2, default_ttl=1.0,
            default_timeout=0.0,
            clock=lambda: now[0],
        )
        mgr.acquire("t1", "res:0", holder_id="s1")
        mgr.acquire("t1", "res:1", holder_id="s1")
        now[0] = 2.0  # All expired
        r = mgr.acquire("t1", "res:2", holder_id="s1")
        assert r.acquired is True


# ── Query helpers ──────────────────────────────────────────────

class TestQueryHelpers:
    def test_lock_holder(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="agent-7")
        assert mgr.lock_holder("t1", "res:1") == "agent-7"
        assert mgr.lock_holder("t1", "res:2") is None

    def test_held_locks_all(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        mgr.acquire("t1", "res:2", holder_id="s2")
        mgr.acquire("t2", "res:3", holder_id="s3")
        assert len(mgr.held_locks()) == 3

    def test_held_locks_by_tenant(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        mgr.acquire("t2", "res:2", holder_id="s2")
        assert len(mgr.held_locks(tenant_id="t1")) == 1

    def test_held_locks_by_holder(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="agent-1")
        mgr.acquire("t1", "res:2", holder_id="agent-1")
        mgr.acquire("t1", "res:3", holder_id="agent-2")
        assert len(mgr.held_locks(holder_id="agent-1")) == 2

    def test_force_release(self):
        mgr = CoordinationLockManager()
        mgr.acquire("t1", "res:1", holder_id="s1")
        assert mgr.force_release("t1", "res:1") is True
        assert mgr.is_locked("t1", "res:1") is False

    def test_force_release_not_held(self):
        mgr = CoordinationLockManager()
        assert mgr.force_release("t1", "res:1") is False


# ── Status ─────────────────────────────────────────────────────

class TestStatus:
    def test_status_fields(self):
        mgr = CoordinationLockManager(default_ttl=5.0, default_timeout=0.0)
        mgr.acquire("t1", "res:1", holder_id="s1")
        mgr.acquire("t1", "res:1", holder_id="s2")  # Denied
        status = mgr.status()
        assert status["active_locks"] == 1
        assert status["total_acquired"] == 1
        assert status["total_denied"] == 1
        assert status["default_ttl"] == 5.0


# ── Validation ─────────────────────────────────────────────────

class TestValidation:
    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError, match="default_ttl"):
            CoordinationLockManager(default_ttl=-1.0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValueError, match="default_timeout"):
            CoordinationLockManager(default_timeout=-1.0)

    def test_zero_timeout_means_no_wait(self):
        mgr = CoordinationLockManager(default_timeout=0.0)
        mgr.acquire("t1", "res:1", holder_id="s1")
        result = mgr.acquire("t1", "res:1", holder_id="s2")
        assert result.acquired is False
        assert result.waited_seconds < 0.1
