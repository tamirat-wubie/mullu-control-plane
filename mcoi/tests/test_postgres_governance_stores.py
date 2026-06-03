"""Phase 1A — PostgreSQL Governance Stores tests.

Tests: InMemory governance stores (same API as PostgreSQL versions),
    factory function, schema definitions, integration with managers.
PostgreSQL structural tests run without a real database.
"""

import sys
from types import SimpleNamespace

import pytest
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.governance.audit.trail import AuditEntry, AuditTrail, AuditStore
from mcoi_runtime.governance.guards.rate_limit import RateLimiter, RateLimitConfig, RateLimitStore
from mcoi_runtime.governance.guards.budget import BudgetStore, TenantBudgetManager
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryBudgetStore,
    InMemoryAuditStore,
    InMemoryRateLimitStore,
    PostgresBudgetStore,
    PostgresAuditStore,
    PostgresRateLimitStore,
    GOVERNANCE_MIGRATIONS,
    create_governance_stores,
)


# ═══ InMemoryBudgetStore ═══


class TestInMemoryBudgetStore:
    def test_implements_budget_store(self):
        store = InMemoryBudgetStore()
        assert isinstance(store, BudgetStore)

    def test_load_returns_none_for_missing(self):
        store = InMemoryBudgetStore()
        assert store.load("nonexistent") is None

    def test_save_and_load(self):
        store = InMemoryBudgetStore()
        budget = LLMBudget(
            budget_id="tenant-t1", tenant_id="t1",
            max_cost=100.0, spent=25.0,
            max_tokens_per_call=4096, max_calls=500, calls_made=10,
        )
        store.save(budget)
        loaded = store.load("t1")
        assert loaded is not None
        assert loaded.budget_id == "tenant-t1"
        assert loaded.spent == 25.0
        assert loaded.calls_made == 10

    def test_save_overwrites_existing(self):
        store = InMemoryBudgetStore()
        b1 = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=100.0, spent=10.0)
        b2 = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=100.0, spent=50.0)
        store.save(b1)
        store.save(b2)
        loaded = store.load("t1")
        assert loaded.spent == 50.0

    def test_load_all_empty(self):
        store = InMemoryBudgetStore()
        assert store.load_all() == []

    def test_load_all_returns_sorted(self):
        store = InMemoryBudgetStore()
        store.save(LLMBudget(budget_id="b-z", tenant_id="z-tenant", max_cost=10.0))
        store.save(LLMBudget(budget_id="b-a", tenant_id="a-tenant", max_cost=20.0))
        all_budgets = store.load_all()
        assert len(all_budgets) == 2
        assert all_budgets[0].tenant_id == "a-tenant"
        assert all_budgets[1].tenant_id == "z-tenant"


# ═══ InMemoryAuditStore ═══


class TestInMemoryAuditStore:
    def test_implements_audit_store(self):
        store = InMemoryAuditStore()
        assert isinstance(store, AuditStore)

    def test_append_and_count(self):
        store = InMemoryAuditStore()
        assert store.count() == 0
        entry = AuditEntry(
            entry_id="audit-1", sequence=1, action="test.action",
            actor_id="actor1", tenant_id="t1", target="/api/test",
            outcome="success", detail={"key": "val"},
            entry_hash="abc123", previous_hash="genesis", recorded_at="2026-01-01T00:00:00Z",
        )
        store.append(entry)
        assert store.count() == 1

    def test_query_no_filters(self):
        store = InMemoryAuditStore()
        for i in range(5):
            store.append(AuditEntry(
                entry_id=f"audit-{i}", sequence=i, action="test",
                actor_id="actor", tenant_id="t1", target="/api",
                outcome="success", detail={},
                entry_hash=f"h{i}", previous_hash=f"h{i-1}", recorded_at="2026-01-01",
            ))
        results = store.query()
        assert len(results) == 5

    def test_query_by_tenant(self):
        store = InMemoryAuditStore()
        store.append(AuditEntry(
            entry_id="a1", sequence=1, action="test", actor_id="a",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h1", previous_hash="g", recorded_at="2026-01-01",
        ))
        store.append(AuditEntry(
            entry_id="a2", sequence=2, action="test", actor_id="a",
            tenant_id="t2", target="/", outcome="success", detail={},
            entry_hash="h2", previous_hash="h1", recorded_at="2026-01-01",
        ))
        assert len(store.query(tenant_id="t1")) == 1
        assert len(store.query(tenant_id="t2")) == 1
        assert len(store.query(tenant_id="t3")) == 0

    def test_query_by_action(self):
        store = InMemoryAuditStore()
        store.append(AuditEntry(
            entry_id="a1", sequence=1, action="llm.complete", actor_id="a",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h1", previous_hash="g", recorded_at="2026-01-01",
        ))
        store.append(AuditEntry(
            entry_id="a2", sequence=2, action="session.create", actor_id="a",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h2", previous_hash="h1", recorded_at="2026-01-01",
        ))
        assert len(store.query(action="llm.complete")) == 1

    def test_query_by_outcome(self):
        store = InMemoryAuditStore()
        store.append(AuditEntry(
            entry_id="a1", sequence=1, action="test", actor_id="a",
            tenant_id="t1", target="/", outcome="denied", detail={},
            entry_hash="h1", previous_hash="g", recorded_at="2026-01-01",
        ))
        store.append(AuditEntry(
            entry_id="a2", sequence=2, action="test", actor_id="a",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h2", previous_hash="h1", recorded_at="2026-01-01",
        ))
        assert len(store.query(outcome="denied")) == 1

    def test_query_with_limit(self):
        store = InMemoryAuditStore()
        for i in range(10):
            store.append(AuditEntry(
                entry_id=f"a{i}", sequence=i, action="test", actor_id="a",
                tenant_id="t1", target="/", outcome="success", detail={},
                entry_hash=f"h{i}", previous_hash=f"h{i-1}", recorded_at="2026-01-01",
            ))
        results = store.query(limit=3)
        assert len(results) == 3
        # Returns last 3 (most recent)
        assert results[0].sequence == 7

    def test_query_combined_filters(self):
        store = InMemoryAuditStore()
        store.append(AuditEntry(
            entry_id="a1", sequence=1, action="llm.complete", actor_id="user1",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h1", previous_hash="g", recorded_at="2026-01-01",
        ))
        store.append(AuditEntry(
            entry_id="a2", sequence=2, action="llm.complete", actor_id="user2",
            tenant_id="t1", target="/", outcome="denied", detail={},
            entry_hash="h2", previous_hash="h1", recorded_at="2026-01-01",
        ))
        results = store.query(action="llm.complete", outcome="denied")
        assert len(results) == 1
        assert results[0].actor_id == "user2"


# ═══ InMemoryRateLimitStore ═══


class TestInMemoryRateLimitStore:
    def test_implements_rate_limit_store(self):
        store = InMemoryRateLimitStore()
        assert isinstance(store, RateLimitStore)

    def test_initial_counters(self):
        store = InMemoryRateLimitStore()
        counters = store.get_counters()
        assert counters == {"allowed": 0, "denied": 0}

    def test_record_allowed(self):
        store = InMemoryRateLimitStore()
        store.record_decision("t1:endpoint", True)
        store.record_decision("t1:endpoint", True)
        counters = store.get_counters()
        assert counters["allowed"] == 2
        assert counters["denied"] == 0

    def test_record_denied(self):
        store = InMemoryRateLimitStore()
        store.record_decision("t1:endpoint", False)
        counters = store.get_counters()
        assert counters["allowed"] == 0
        assert counters["denied"] == 1

    def test_record_mixed(self):
        store = InMemoryRateLimitStore()
        store.record_decision("t1:/api/a", True)
        store.record_decision("t1:/api/a", True)
        store.record_decision("t1:/api/a", False)
        store.record_decision("t2:/api/b", True)
        store.record_decision("t2:/api/b", False)
        counters = store.get_counters()
        assert counters["allowed"] == 3
        assert counters["denied"] == 2

    def test_multiple_buckets_aggregate(self):
        store = InMemoryRateLimitStore()
        for i in range(5):
            store.record_decision(f"t{i}:endpoint", True)
        for i in range(3):
            store.record_decision(f"t{i}:other", False)
        counters = store.get_counters()
        assert counters["allowed"] == 5
        assert counters["denied"] == 3

    # --- Bounded growth (audit F11 follow-up) ---

    def test_bucket_count_bounded_by_max_buckets(self):
        # When the store owns bucket state, the limiter's LRU cap is
        # bypassed — the store must self-bound, else _buckets leaks
        # one entry per unique key forever.
        store = InMemoryRateLimitStore(max_buckets=3)
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001, burst_limit=10)
        for key in ("a", "b", "c", "d", "e"):
            store.try_consume(key, 1, cfg)
        assert len(store._buckets) == 3

    def test_eviction_is_lru(self):
        store = InMemoryRateLimitStore(max_buckets=3)
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001, burst_limit=10)
        for key in ("a", "b", "c"):
            store.try_consume(key, 1, cfg)
        # Touch "a" so it's most-recently-used; "b" becomes the LRU.
        store.try_consume("a", 1, cfg)
        store.try_consume("d", 1, cfg)  # forces one eviction
        assert "b" not in store._buckets
        assert set(store._buckets.keys()) == {"a", "c", "d"}

    def test_eviction_does_not_break_per_bucket_cap(self):
        # Eviction must not weaken enforcement for retained buckets.
        store = InMemoryRateLimitStore(max_buckets=100)
        cfg = RateLimitConfig(max_tokens=3, refill_rate=0.0001, burst_limit=5)
        results = [store.try_consume("x", 1, cfg)[0] for _ in range(5)]
        assert results == [True, True, True, False, False]

    def test_max_buckets_floor_is_one(self):
        # A degenerate cap must not make the store evict the just-added
        # key and become a no-op.
        store = InMemoryRateLimitStore(max_buckets=0)
        cfg = RateLimitConfig(max_tokens=2, refill_rate=0.0001, burst_limit=5)
        allowed, _ = store.try_consume("only", 1, cfg)
        assert allowed is True
        assert len(store._buckets) == 1

    def test_burst_guard_path_does_not_grow_buckets(self):
        # Oversized requests are rejected without creating a bucket.
        store = InMemoryRateLimitStore(max_buckets=100)
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001, burst_limit=5)
        allowed, _ = store.try_consume("k", 999, cfg)
        assert allowed is False
        assert len(store._buckets) == 0


# ═══ Integration: Budget Store with TenantBudgetManager ═══


class TestBudgetStoreIntegration:
    def _clock(self) -> str:
        return "2026-01-01T00:00:00Z"

    def test_manager_uses_store_for_persistence(self):
        store = InMemoryBudgetStore()
        mgr = TenantBudgetManager(clock=self._clock, store=store)
        budget = mgr.ensure_budget("t1")
        assert budget.tenant_id == "t1"
        # Store should have the budget
        stored = store.load("t1")
        assert stored is not None
        assert stored.tenant_id == "t1"

    def test_manager_loads_from_store(self):
        store = InMemoryBudgetStore()
        # Pre-populate store
        existing = LLMBudget(
            budget_id="tenant-t1", tenant_id="t1",
            max_cost=50.0, spent=12.5, calls_made=5,
        )
        store.save(existing)

        mgr = TenantBudgetManager(clock=self._clock, store=store)
        budget = mgr.ensure_budget("t1")
        assert budget.spent == 12.5
        assert budget.calls_made == 5

    def test_manager_writes_through_on_spend(self):
        store = InMemoryBudgetStore()
        mgr = TenantBudgetManager(clock=self._clock, store=store)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 5.0)
        stored = store.load("t1")
        assert stored.spent == 5.0
        assert stored.calls_made == 1

    def test_manager_writes_through_on_multiple_spends(self):
        store = InMemoryBudgetStore()
        mgr = TenantBudgetManager(clock=self._clock, store=store)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 1.0)
        mgr.record_spend("t1", 2.0)
        mgr.record_spend("t1", 3.0)
        stored = store.load("t1")
        assert stored.spent == 6.0
        assert stored.calls_made == 3


# ═══ Integration: Audit Store with AuditTrail ═══


class TestAuditStoreIntegration:
    def _clock(self) -> str:
        return "2026-01-01T00:00:00Z"

    def test_trail_writes_through_to_store(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=self._clock, store=store)
        trail.record(
            action="test.action", actor_id="user1",
            tenant_id="t1", target="/api/test", outcome="success",
        )
        assert store.count() == 1

    def test_trail_writes_all_entries_to_store(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=self._clock, store=store)
        for i in range(10):
            trail.record(
                action=f"action-{i}", actor_id="user1",
                tenant_id="t1", target="/api/test", outcome="success",
            )
        assert store.count() == 10

    def test_store_entries_have_correct_hash_chain(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=self._clock, store=store)
        trail.record(action="first", actor_id="a", tenant_id="t1", target="/", outcome="success")
        trail.record(action="second", actor_id="a", tenant_id="t1", target="/", outcome="success")
        entries = store.query()
        assert len(entries) == 2
        # Second entry's previous_hash should be first entry's entry_hash
        assert entries[1].previous_hash == entries[0].entry_hash

    def test_store_query_filters_match_trail(self):
        store = InMemoryAuditStore()
        trail = AuditTrail(clock=self._clock, store=store)
        trail.record(action="llm.complete", actor_id="a", tenant_id="t1", target="/", outcome="success")
        trail.record(action="session.create", actor_id="a", tenant_id="t1", target="/", outcome="denied")
        # Query store directly
        assert len(store.query(action="llm.complete")) == 1
        assert len(store.query(outcome="denied")) == 1


# ═══ Integration: RateLimitStore with RateLimiter ═══


class TestRateLimitStoreIntegration:
    def test_limiter_writes_through_to_store(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=60, refill_rate=1.0),
            store=store,
        )
        result = limiter.check("t1", "/api/test")
        assert result.allowed is True
        counters = store.get_counters()
        assert counters["allowed"] == 1

    def test_limiter_records_denied_decisions(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.001),
            store=store,
        )
        # Exhaust tokens
        limiter.check("t1", "/api/test")
        limiter.check("t1", "/api/test")
        limiter.check("t1", "/api/test")  # This should be denied
        counters = store.get_counters()
        assert counters["allowed"] == 2
        assert counters["denied"] == 1


# ═══ PostgreSQL Store Structural Tests ═══


class TestPostgresBudgetStoreStructure:
    def test_inherits_budget_store(self):
        assert issubclass(PostgresBudgetStore, BudgetStore)

    def test_graceful_without_psycopg2(self):
        # PostgresBudgetStore should handle missing psycopg2 gracefully
        # (it tries to import and sets _available flag)
        store = PostgresBudgetStore.__new__(PostgresBudgetStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        # All operations should return defaults
        assert store.load("t1") is None
        store.save(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0))
        assert store.load_all() == []

    def test_has_close_method(self):
        store = PostgresBudgetStore.__new__(PostgresBudgetStore)
        store._conn = None
        store.close()  # Should not raise


class TestPostgresAuditStoreStructure:
    def test_inherits_audit_store(self):
        assert issubclass(PostgresAuditStore, AuditStore)

    def test_graceful_without_connection(self):
        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        entry = AuditEntry(
            entry_id="a1", sequence=1, action="test", actor_id="a",
            tenant_id="t1", target="/", outcome="success", detail={},
            entry_hash="h", previous_hash="g", recorded_at="2026-01-01",
        )
        store.append(entry)  # Should not raise
        assert store.query() == []
        assert store.count() == 0

    def test_try_append_overrides_base(self):
        # F4 cross-replica path: doctrine override-detection must see
        # PostgresAuditStore.try_append as a real override.
        assert PostgresAuditStore.try_append is not AuditStore.try_append

    def test_try_append_returns_none_without_connection(self):
        # Fail-closed when disconnected — the dispatcher treats None as
        # denial, which is governance-correct when the backend is down.
        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        result = store.try_append(
            action="a", actor_id="x", tenant_id="t", target="/",
            outcome="success", detail={}, recorded_at="2026-01-01",
        )
        assert result is None

    def test_encrypt_detail_fails_closed_when_encryptor_breaks(self):
        class BrokenEncryptor:
            def encrypt(self, _detail_json: str) -> str:
                raise RuntimeError("secret encryption backend failure")

        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._field_encryptor = BrokenEncryptor()

        with pytest.raises(RuntimeError, match="audit detail encryption failed \\(RuntimeError\\)") as exc_info:
            store._encrypt_detail({"secret": "value"})

        assert "RuntimeError" in str(exc_info.value)
        assert "secret encryption backend failure" not in str(exc_info.value)
        assert "encryption failed" in str(exc_info.value)

    def test_encrypt_detail_rejects_non_finite_values_before_storage(self):
        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._field_encryptor = None

        with pytest.raises(RuntimeError, match=r"^audit detail serialization failed \(ValueError\)$") as exc_info:
            store._encrypt_detail({"secret_metric": float("nan")})

        message = str(exc_info.value)
        assert "secret_metric" not in message
        assert "nan" not in message.lower()
        assert "serialization failed" in message

    def test_decrypt_detail_fails_closed_when_ciphertext_is_broken(self):
        class BrokenDecryptor:
            def is_encrypted(self, _stored: str) -> bool:
                return True

            def decrypt(self, _stored: str) -> str:
                raise ValueError("ciphertext backend failure")

        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._field_encryptor = BrokenDecryptor()

        with pytest.raises(RuntimeError, match="audit detail decryption failed \\(ValueError\\)") as exc_info:
            store._decrypt_detail("enc:v1:broken")

        assert "ValueError" in str(exc_info.value)
        assert "ciphertext backend failure" not in str(exc_info.value)
        assert "decryption failed" in str(exc_info.value)

    def test_decrypt_detail_bounds_invalid_plaintext_json(self):
        class PlaintextEncryptor:
            def is_encrypted(self, _stored: str) -> bool:
                return False

        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._field_encryptor = PlaintextEncryptor()

        with pytest.raises(RuntimeError, match="audit detail parse failed \\(JSONDecodeError\\)") as exc_info:
            store._decrypt_detail("not-json")

        assert "JSONDecodeError" in str(exc_info.value)
        assert "not-json" not in str(exc_info.value)
        assert "parse failed" in str(exc_info.value)

    def test_decrypt_detail_rejects_non_standard_json_constants(self):
        class PlaintextEncryptor:
            def is_encrypted(self, _stored: str) -> bool:
                return False

        store = PostgresAuditStore.__new__(PostgresAuditStore)
        store._field_encryptor = PlaintextEncryptor()

        with pytest.raises(RuntimeError, match=r"^audit detail parse failed \(ValueError\)$") as exc_info:
            store._decrypt_detail('{"secret_metric":NaN}')

        message = str(exc_info.value)
        assert "secret_metric" not in message
        assert "NaN" not in message
        assert "parse failed" in message


class TestPostgresRateLimitStoreStructure:
    def test_inherits_rate_limit_store(self):
        assert issubclass(PostgresRateLimitStore, RateLimitStore)

    def test_graceful_without_connection(self):
        store = PostgresRateLimitStore.__new__(PostgresRateLimitStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        store.record_decision("key", True)  # Should not raise
        assert store.get_counters() == {"allowed": 0, "denied": 0}

    def test_try_consume_overrides_base(self):
        # F11 cross-replica path: doctrine override-detection must see
        # PostgresRateLimitStore.try_consume as a real override.
        assert PostgresRateLimitStore.try_consume is not RateLimitStore.try_consume

    def test_try_consume_returns_none_without_connection(self):
        # Within burst limit + disconnected → None (fail-closed denial).
        store = PostgresRateLimitStore.__new__(PostgresRateLimitStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        result = store.try_consume("k", 1, RateLimitConfig(max_tokens=10))
        assert result is None

    def test_try_consume_burst_guard_rejects_without_connection(self):
        # A request larger than the burst limit is rejected before any
        # DB touch — returns (False, 0.0), never None, never raises.
        store = PostgresRateLimitStore.__new__(PostgresRateLimitStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        allowed, remaining = store.try_consume(
            "k", 999, RateLimitConfig(max_tokens=10, burst_limit=5)
        )
        assert allowed is False
        assert remaining == 0.0

    def test_prune_stale_buckets_noop_without_connection(self):
        # Bounded-growth cleanup: safe no-op (returns 0) when the store
        # is disconnected. Atomic DELETE semantics are exercised in the
        # gated integration suite.
        store = PostgresRateLimitStore.__new__(PostgresRateLimitStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        assert store.prune_stale_buckets(3600) == 0


class TestPostgresBaseWarnings:
    def test_base_init_bounds_connection_warning(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        warnings: list[str] = []

        class DummyStore(pg._PostgresBase):
            def _connect(self) -> None:
                raise RuntimeError("postgres://secret-backend")

        monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace())
        monkeypatch.setattr(pg._log, "warning", lambda message, *args: warnings.append(message % args))

        store = DummyStore()
        store._base_init("postgresql://secret-host/db", migration_index=0, auto_migrate=False)

        assert store._conn is None
        assert warnings
        assert "RuntimeError" in warnings[0]
        assert "secret-backend" not in warnings[0]
        assert "secret-host" not in warnings[0]

    def test_reconnect_bounds_warning(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        warnings: list[str] = []

        class BrokenConn:
            def close(self) -> None:
                return None

        class DummyStore(pg._PostgresBase):
            def _connect(self) -> None:
                raise RuntimeError("postgres://secret-reconnect")

        monkeypatch.setattr(pg._log, "warning", lambda message, *args: warnings.append(message % args))

        store = DummyStore()
        store._conn = BrokenConn()

        assert store._reconnect() is False
        assert warnings
        assert "RuntimeError" in warnings[0]
        assert "secret-reconnect" not in warnings[0]

    def test_safe_execute_bounds_reconnect_failure_warning(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        warnings: list[str] = []

        class DummyStore(pg._PostgresBase):
            def _reconnect(self) -> bool:
                return True

        monkeypatch.setattr(pg._log, "warning", lambda message, *args: warnings.append(message % args))

        store = DummyStore()

        def boom():
            raise RuntimeError("query-secret")

        assert store._safe_execute(boom) is None
        assert warnings
        assert "RuntimeError" in warnings[0]
        assert "query-secret" not in warnings[0]

    def test_close_bounds_warning(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        warnings: list[str] = []

        class BrokenConn:
            def close(self) -> None:
                raise RuntimeError("postgres://secret-close")

        class DummyStore(pg._PostgresBase):
            pass

        monkeypatch.setattr(pg._log, "warning", lambda message, *args: warnings.append(message % args))

        store = DummyStore()
        store._conn = BrokenConn()

        store.close()

        assert store._conn is None
        assert warnings
        assert "RuntimeError" in warnings[0]
        assert "secret-close" not in warnings[0]

    def test_bundle_close_bounds_warning(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        warnings: list[str] = []

        class BrokenStore:
            def close(self) -> None:
                raise RuntimeError("postgres://secret-bundle-close")

        monkeypatch.setattr(pg._log, "warning", lambda message, *args: warnings.append(message % args))

        bundle = pg.GovernanceStoreBundle({"broken": BrokenStore()})
        bundle.close()

        assert warnings
        assert "RuntimeError" in warnings[0]
        assert "secret-bundle-close" not in warnings[0]


# ═══ Schema Definitions ═══


class TestGovernanceMigrations:
    def test_migrations_count(self):
        assert len(GOVERNANCE_MIGRATIONS) == 4

    def test_budget_migration_creates_table(self):
        assert "governance_budgets" in GOVERNANCE_MIGRATIONS[0]
        assert "tenant_id TEXT PRIMARY KEY" in GOVERNANCE_MIGRATIONS[0]

    def test_audit_migration_creates_table_and_indexes(self):
        assert "governance_audit_entries" in GOVERNANCE_MIGRATIONS[1]
        assert "idx_gov_audit_tenant" in GOVERNANCE_MIGRATIONS[1]
        assert "idx_gov_audit_sequence" in GOVERNANCE_MIGRATIONS[1]
        assert "idx_gov_audit_action" in GOVERNANCE_MIGRATIONS[1]

    def test_rate_limit_migration_creates_table(self):
        assert "governance_rate_decisions" in GOVERNANCE_MIGRATIONS[2]
        assert "bucket_key TEXT PRIMARY KEY" in GOVERNANCE_MIGRATIONS[2]


# ═══ Factory ═══


class TestCreateGovernanceStores:
    def test_memory_backend(self):
        stores = create_governance_stores("memory")
        assert isinstance(stores["budget"], InMemoryBudgetStore)
        assert isinstance(stores["audit"], InMemoryAuditStore)
        assert isinstance(stores["rate_limit"], InMemoryRateLimitStore)

    def test_returns_all_four_keys(self):
        stores = create_governance_stores("memory")
        assert set(stores.keys()) == {"budget", "audit", "rate_limit", "tenant_gating"}

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match=r"^unsupported governance store backend$") as excinfo:
            create_governance_stores("redis")
        assert "redis" not in str(excinfo.value)

    def test_memory_stores_are_independent(self):
        stores = create_governance_stores("memory")
        # Each store should be a distinct object
        assert stores["budget"] is not stores["audit"]
        assert stores["audit"] is not stores["rate_limit"]
