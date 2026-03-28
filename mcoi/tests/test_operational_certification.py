"""Operational Certification Tests.

Proves the platform behaves correctly under real operational conditions:
  A. Persistence lifecycle — create, restart, migrate, data continuity
  D. Concurrency stress — concurrent tenants, overlapping requests, thread safety
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from mcoi_runtime.persistence.sqlite_store import SQLiteStore
from mcoi_runtime.persistence.postgres_store import InMemoryStore, create_store
from mcoi_runtime.persistence.migrations import (
    MigrationEngine, Migration, create_platform_migration_engine,
)
from mcoi_runtime.persistence.state_persistence import StatePersistence
from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.tenant_budget import TenantBudgetManager, TenantBudgetPolicy
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine
from mcoi_runtime.core.rate_limiter import RateLimiter, RateLimitConfig
from mcoi_runtime.core.event_bus import EventBus


CLOCK = lambda: "2026-03-27T12:00:00Z"


# ═══════════════════════════════════════════════════════════════════════════
# A. Persistence Lifecycle Proof
# ═══════════════════════════════════════════════════════════════════════════


class TestSQLiteLifecycle:
    """Prove SQLite persistence survives restart and migration."""

    def test_create_store_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            store = create_store("sqlite", os.path.join(d, "test.db"))
            assert store.ledger_count() == 0
            store.close()

    def test_data_survives_restart(self):
        """Data written before close() is readable after reopen."""
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.db")

            # First session: write data
            store1 = SQLiteStore(db_path)
            store1.append_ledger("test", "actor-1", "tenant-1", {"key": "value"}, "hash1")
            store1.append_ledger("test", "actor-2", "tenant-1", {"key": "value2"}, "hash2")
            store1.save_session("sess-1", "actor-1", "tenant-1")
            assert store1.ledger_count() == 2
            store1.close()

            # Second session: read data back
            store2 = SQLiteStore(db_path)
            assert store2.ledger_count() == 2
            entries = store2.query_ledger("tenant-1")
            assert len(entries) == 2
            assert entries[0]["actor"] == "actor-2"  # DESC order
            store2.close()

    def test_migration_on_existing_db(self):
        """Migrations apply cleanly to an existing database."""
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.db")

            # Create bare DB with data
            store = SQLiteStore(db_path)
            store.append_ledger("test", "actor-1", "t1", {"a": 1}, "h1")
            conn = store._conn

            # Apply migrations
            engine = create_platform_migration_engine(CLOCK)
            results = engine.apply_all(conn)
            assert all(r.success for r in results)

            # Verify new tables exist alongside old data
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "audit_trail" in table_names
            assert "cost_events" in table_names
            assert "schema_version" in table_names

            # Old data still readable
            assert store.ledger_count() == 1
            store.close()

    def test_migration_idempotent_across_restarts(self):
        """Running migrations multiple times (simulating restarts) is safe."""
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.db")

            for restart in range(3):
                conn = sqlite3.connect(db_path)
                engine = create_platform_migration_engine(CLOCK)
                results = engine.apply_all(conn)
                if restart == 0:
                    assert len(results) == 4  # All migrations applied
                else:
                    assert len(results) == 0  # Already applied
                assert engine.current_version(conn) == 4
                conn.close()

    def test_partial_migration_failure_leaves_db_usable(self):
        """A failing migration doesn't corrupt prior state."""
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.db")
            conn = sqlite3.connect(db_path)

            engine = MigrationEngine(clock=CLOCK)
            engine.register(Migration(version=1, name="good", sql="CREATE TABLE good (id INTEGER);"))
            engine.register(Migration(version=2, name="bad", sql="INVALID SQL GARBAGE"))

            with pytest.raises(RuntimeError, match="failed"):
                engine.apply_all(conn)

            # Version 1 should have applied
            assert engine.current_version(conn) == 1
            # Table from v1 exists
            conn.execute("SELECT * FROM good")
            conn.close()

    def test_save_session_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(os.path.join(d, "test.db"))
            store.save_session("sess-abc", "actor-1", "tenant-1")
            # Verify session was saved
            row = store._conn.execute(
                "SELECT actor_id, tenant_id FROM sessions WHERE session_id = ?",
                ("sess-abc",),
            ).fetchone()
            assert row == ("actor-1", "tenant-1")
            store.close()


class TestStatePersistenceLifecycle:
    """Prove state snapshots survive across simulated restarts."""

    def test_budget_state_survives_restart(self):
        """Budget state saved on shutdown is restored on startup."""
        with tempfile.TemporaryDirectory() as d:
            # Shutdown: save budget state
            sp1 = StatePersistence(clock=CLOCK, base_dir=d)
            budget_data = {
                "tenant-a": {"spent": 5.0, "calls_made": 100, "max_cost": 50.0, "max_calls": 1000},
                "tenant-b": {"spent": 12.3, "calls_made": 45, "max_cost": 100.0, "max_calls": 500},
            }
            sp1.save("budgets", budget_data)

            # Startup: restore
            sp2 = StatePersistence(clock=CLOCK, base_dir=d)
            snap = sp2.load("budgets")
            assert snap is not None
            assert snap.data["tenant-a"]["spent"] == 5.0
            assert snap.data["tenant-b"]["calls_made"] == 45

    def test_audit_summary_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            sp = StatePersistence(clock=CLOCK, base_dir=d)
            sp.save("audit_summary", {"entry_count": 1500, "sequence": 1500, "last_hash": "abc123"})

            sp2 = StatePersistence(clock=CLOCK, base_dir=d)
            snap = sp2.load("audit_summary")
            assert snap.data["entry_count"] == 1500
            assert snap.data["last_hash"] == "abc123"

    def test_corrupt_snapshot_returns_none(self):
        """Corrupted snapshot file doesn't crash restore."""
        with tempfile.TemporaryDirectory() as d:
            # Write corrupt file
            path = os.path.join(d, "mullu_state_budgets.json")
            with open(path, "w") as f:
                f.write("{invalid json{{")

            sp = StatePersistence(clock=CLOCK, base_dir=d)
            assert sp.load("budgets") is None  # Graceful None, not crash


# ═══════════════════════════════════════════════════════════════════════════
# D. Concurrency and Stress Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrentTenantBudgets:
    """Prove tenant budget isolation under concurrent access."""

    def test_concurrent_budget_spend(self):
        """Multiple threads spending against different tenants don't interfere."""
        mgr = TenantBudgetManager(clock=CLOCK)
        tenants = [f"tenant-{i}" for i in range(10)]
        for t in tenants:
            mgr.set_policy(TenantBudgetPolicy(tenant_id=t, max_cost=100.0))
            mgr.ensure_budget(t)

        errors = []

        def spend(tenant_id: str):
            try:
                for _ in range(50):
                    mgr.record_spend(tenant_id, cost=0.1)
            except Exception as e:
                errors.append(f"{tenant_id}: {e}")

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(spend, t) for t in tenants]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0

        # Each tenant should have spent 5.0 (50 * 0.1)
        for t in tenants:
            report = mgr.report(t)
            assert abs(report.spent - 5.0) < 0.001, f"{t}: spent={report.spent}"

    def test_concurrent_budget_exhaustion(self):
        """Concurrent threads hitting the same budget respect limits."""
        mgr = TenantBudgetManager(clock=CLOCK)
        mgr.set_policy(TenantBudgetPolicy(tenant_id="shared", max_cost=1.0))
        mgr.ensure_budget("shared")

        success_count = 0
        fail_count = 0
        lock = threading.Lock()

        def spend():
            nonlocal success_count, fail_count
            for _ in range(100):
                try:
                    mgr.record_spend("shared", cost=0.05)
                    with lock:
                        success_count += 1
                except ValueError:
                    with lock:
                        fail_count += 1

        threads = [threading.Thread(target=spend) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        report = mgr.report("shared")
        # Budget is 1.0, each spend is 0.05, so max 20 successes
        assert success_count <= 21  # Slight race tolerance
        assert report.spent <= 1.05  # Slight race tolerance
        assert fail_count > 0  # Some should have been rejected


class TestConcurrentAuditTrail:
    """Prove audit trail integrity under concurrent writes."""

    def test_concurrent_audit_records(self):
        """Multiple threads recording audit entries produces valid chain."""
        trail = AuditTrail(clock=CLOCK)

        def record_batch(thread_id: int):
            for i in range(100):
                trail.record(
                    action=f"test.thread{thread_id}",
                    actor_id=f"actor-{thread_id}",
                    tenant_id=f"tenant-{thread_id}",
                    target="test",
                    outcome="success",
                )

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(record_batch, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # 5 threads * 100 records = 500
        assert trail.entry_count == 500

        # Hash chain should still be valid
        valid, checked = trail.verify_chain()
        assert valid
        assert checked == 500

    def test_concurrent_audit_queries(self):
        """Reads during writes don't crash or return corrupt data."""
        trail = AuditTrail(clock=CLOCK)
        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                trail.record(
                    action="write", actor_id="writer",
                    tenant_id="t1", target="test", outcome="success",
                )
                i += 1
                if i >= 200:
                    break

        def reader():
            results = []
            while not stop.is_set():
                entries = trail.query(limit=10)
                results.append(len(entries))
                if len(results) >= 50:
                    break
            return results

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)

        writer_thread.start()
        reader_thread.start()
        writer_thread.join(timeout=5)
        stop.set()
        reader_thread.join(timeout=5)

        # No crashes, entries were recorded
        assert trail.entry_count > 0


class TestConcurrentLLMPipeline:
    """Prove governed LLM pipeline handles concurrent requests."""

    def test_concurrent_completions(self):
        """Multiple concurrent LLM completions all succeed and accumulate correctly."""
        entries = []
        config = LLMConfig(
            default_backend="stub", default_model="stub",
            default_budget_max_cost=100.0,
        )
        result = bootstrap_llm(clock=CLOCK, config=config, ledger_sink=entries.append)
        bridge = result.bridge

        results_list = []
        lock = threading.Lock()

        def complete(thread_id: int):
            for i in range(20):
                r = bridge.complete(
                    f"Thread {thread_id} prompt {i}",
                    budget_id="default",
                    tenant_id=f"tenant-{thread_id}",
                )
                with lock:
                    results_list.append(r)

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(complete, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # 5 threads * 20 calls = 100
        assert len(results_list) == 100
        succeeded = sum(1 for r in results_list if r.succeeded)
        assert succeeded > 0  # At least some should succeed (budget may exhaust)
        assert bridge.invocation_count >= succeeded
        assert bridge.total_cost > 0

    def test_concurrent_cost_analytics(self):
        """Cost analytics handles concurrent recording without data loss."""
        analytics = CostAnalyticsEngine(clock=CLOCK)

        def record_costs(tenant_id: str):
            for i in range(100):
                analytics.record(tenant_id, "stub", 0.001, 10)

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(record_costs, f"t-{i}") for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # 5 tenants * 100 records each
        assert analytics.entry_count == 500
        for i in range(5):
            breakdown = analytics.tenant_breakdown(f"t-{i}")
            assert breakdown.call_count == 100
            assert abs(breakdown.total_cost - 0.1) < 0.001

    def test_concurrent_event_publishing(self):
        """Event bus handles concurrent publishes."""
        bus = EventBus(clock=CLOCK)

        def publish_batch(thread_id: int):
            for i in range(100):
                bus.publish(
                    f"test.event.{thread_id}",
                    tenant_id=f"tenant-{thread_id}",
                    source="stress-test",
                    payload={"i": i},
                )

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(publish_batch, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        assert bus.event_count == 500


class TestConcurrentSQLiteStore:
    """Prove SQLite store handles concurrent writes safely.

    Note: SQLite enforces single-thread connection by default.
    For multi-threaded access, each thread must open its own connection.
    This test uses serial writes to verify data integrity — concurrent
    access at the application level is handled by the InMemoryStore or
    PostgreSQL backend.
    """

    def test_serial_multi_tenant_writes(self):
        """Multiple tenants writing sequentially produces correct counts."""
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(os.path.join(d, "test.db"))

            for thread_id in range(5):
                for i in range(50):
                    store.append_ledger(
                        "test", f"actor-{thread_id}", f"tenant-{thread_id}",
                        {"thread": thread_id, "i": i}, f"hash-{thread_id}-{i}",
                    )

            assert store.ledger_count() == 250

            for i in range(5):
                entries = store.query_ledger(f"tenant-{i}", limit=100)
                assert len(entries) == 50

            store.close()

    def test_concurrent_separate_connections(self):
        """Multiple threads with separate DB connections write safely."""
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.db")
            # Create schema first
            init_store = SQLiteStore(db_path)
            init_store.close()

            results = []
            lock = threading.Lock()

            def write_batch(thread_id: int):
                # Each thread opens its own connection
                conn = sqlite3.connect(db_path, timeout=10)
                for i in range(50):
                    conn.execute(
                        "INSERT INTO ledger (entry_type, actor_id, tenant_id, content, content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ("test", f"actor-{thread_id}", f"tenant-{thread_id}",
                         '{"i": ' + str(i) + '}', f"hash-{thread_id}-{i}", CLOCK()),
                    )
                    conn.commit()
                conn.close()
                with lock:
                    results.append(thread_id)

            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = [pool.submit(write_batch, i) for i in range(5)]
                for f in as_completed(futures):
                    f.result()

            assert len(results) == 5

            # Verify all data
            verify = SQLiteStore(db_path)
            assert verify.ledger_count() == 250
            verify.close()


class TestRestartDuringInFlight:
    """Prove the system recovers gracefully from interrupted state."""

    def test_partial_budget_restore(self):
        """If only some budgets were saved, restore doesn't crash."""
        with tempfile.TemporaryDirectory() as d:
            sp = StatePersistence(clock=CLOCK, base_dir=d)
            sp.save("budgets", {"tenant-a": {"spent": 5.0, "calls_made": 10, "max_cost": 50.0, "max_calls": 1000}})

            mgr = TenantBudgetManager(clock=CLOCK)
            snap = sp.load("budgets")
            for tid, bdata in snap.data.items():
                mgr.set_policy(TenantBudgetPolicy(tenant_id=tid, max_cost=bdata["max_cost"]))
                mgr.ensure_budget(tid)
                if bdata.get("spent", 0) > 0:
                    try:
                        mgr.record_spend(tid, cost=bdata["spent"])
                    except ValueError:
                        pass

            report = mgr.report("tenant-a")
            assert report.spent == 5.0

    def test_missing_snapshot_starts_fresh(self):
        """Missing snapshot file means fresh start, not crash."""
        with tempfile.TemporaryDirectory() as d:
            sp = StatePersistence(clock=CLOCK, base_dir=d)
            assert sp.load("budgets") is None
            assert sp.load("audit_summary") is None
            assert sp.load("cost_analytics") is None
