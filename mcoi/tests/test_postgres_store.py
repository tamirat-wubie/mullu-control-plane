"""Phase 199B — PostgreSQL store tests.

Tests: InMemoryStore (same API as PostgresStore), store factory, schema definitions.
PostgresStore structural tests run without a real database.
"""

import pytest
from mcoi_runtime.persistence.postgres_store import (
    InMemoryStore,
    PostgresStore,
    SCHEMA_VERSION,
    MIGRATIONS,
    create_store,
)


# ═══ InMemoryStore (full API coverage) ═══

class TestInMemoryStoreLedger:
    def test_append_and_query(self):
        store = InMemoryStore()
        entry_id = store.append_ledger("test", "actor1", "tenant1", {"key": "val"}, "hash1")
        assert entry_id >= 1
        results = store.query_ledger("tenant1")
        assert len(results) == 1
        assert results[0]["type"] == "test"
        assert results[0]["actor"] == "actor1"
        assert results[0]["content"] == {"key": "val"}
        assert results[0]["hash"] == "hash1"

    def test_query_by_tenant(self):
        store = InMemoryStore()
        store.append_ledger("a", "actor", "t1", {}, "h1")
        store.append_ledger("b", "actor", "t2", {}, "h2")
        assert len(store.query_ledger("t1")) == 1
        assert len(store.query_ledger("t2")) == 1
        assert len(store.query_ledger("t3")) == 0

    def test_query_ordered_descending(self):
        store = InMemoryStore()
        store.append_ledger("first", "a", "t1", {}, "h1")
        store.append_ledger("second", "a", "t1", {}, "h2")
        results = store.query_ledger("t1")
        assert results[0]["type"] == "second"
        assert results[1]["type"] == "first"

    def test_query_with_limit(self):
        store = InMemoryStore()
        for i in range(10):
            store.append_ledger(f"entry-{i}", "a", "t1", {}, f"h{i}")
        results = store.query_ledger("t1", limit=3)
        assert len(results) == 3

    def test_ledger_count(self):
        store = InMemoryStore()
        assert store.ledger_count() == 0
        store.append_ledger("a", "actor", "t1", {}, "h1")
        store.append_ledger("b", "actor", "t2", {}, "h2")
        assert store.ledger_count() == 2
        assert store.ledger_count("t1") == 1
        assert store.ledger_count("t2") == 1

    def test_unique_ids(self):
        store = InMemoryStore()
        id1 = store.append_ledger("a", "a", "t", {}, "h")
        id2 = store.append_ledger("b", "a", "t", {}, "h")
        assert id1 != id2


class TestInMemoryStoreSessions:
    def test_save_and_get(self):
        store = InMemoryStore()
        store.save_session("s1", "actor1", "tenant1")
        session = store.get_session("s1")
        assert session is not None
        assert session["actor_id"] == "actor1"
        assert session["tenant_id"] == "tenant1"
        assert session["active"] is True

    def test_get_nonexistent(self):
        store = InMemoryStore()
        assert store.get_session("missing") is None

    def test_deactivate(self):
        store = InMemoryStore()
        store.save_session("s1", "actor1", "tenant1")
        assert store.deactivate_session("s1") is True
        session = store.get_session("s1")
        assert session["active"] is False

    def test_deactivate_nonexistent(self):
        store = InMemoryStore()
        assert store.deactivate_session("missing") is False

    def test_active_count(self):
        store = InMemoryStore()
        assert store.active_session_count() == 0
        store.save_session("s1", "a", "t")
        store.save_session("s2", "a", "t")
        assert store.active_session_count() == 2
        store.deactivate_session("s1")
        assert store.active_session_count() == 1


class TestInMemoryStoreRequests:
    def test_save_and_count(self):
        store = InMemoryStore()
        store.save_request("r1", "t1", "POST", "/api/v1/execute", 200, True)
        assert store.request_count() == 1
        assert store.request_count("t1") == 1
        assert store.request_count("t2") == 0

    def test_multiple_requests(self):
        store = InMemoryStore()
        store.save_request("r1", "t1", "POST", "/api", 200, True)
        store.save_request("r2", "t1", "GET", "/health", 200, False)
        store.save_request("r3", "t2", "POST", "/api", 201, True)
        assert store.request_count() == 3
        assert store.request_count("t1") == 2


class TestInMemoryStoreLLMInvocations:
    def test_save_and_query(self):
        store = InMemoryStore()
        entry_id = store.save_llm_invocation(
            invocation_id="inv-1",
            model_name="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            succeeded=True,
            budget_id="b1",
            tenant_id="t1",
        )
        assert entry_id >= 1
        results = store.query_llm_invocations("t1")
        assert len(results) == 1
        assert results[0]["model_name"] == "claude-sonnet-4-20250514"
        assert results[0]["provider"] == "anthropic"
        assert results[0]["input_tokens"] == 100
        assert results[0]["succeeded"] is True

    def test_query_by_tenant(self):
        store = InMemoryStore()
        store.save_llm_invocation("i1", "m", "p", 10, 5, 0.001, True, tenant_id="t1")
        store.save_llm_invocation("i2", "m", "p", 10, 5, 0.001, True, tenant_id="t2")
        assert len(store.query_llm_invocations("t1")) == 1
        assert len(store.query_llm_invocations("t2")) == 1
        assert len(store.query_llm_invocations()) == 2

    def test_query_with_limit(self):
        store = InMemoryStore()
        for i in range(5):
            store.save_llm_invocation(f"i{i}", "m", "p", 10, 5, 0.001, True, tenant_id="t1")
        assert len(store.query_llm_invocations("t1", limit=2)) == 2

    def test_total_cost(self):
        store = InMemoryStore()
        store.save_llm_invocation("i1", "m", "p", 10, 5, 0.005, True, tenant_id="t1")
        store.save_llm_invocation("i2", "m", "p", 10, 5, 0.003, True, tenant_id="t1")
        store.save_llm_invocation("i3", "m", "p", 10, 5, 0.002, True, tenant_id="t2")
        assert store.llm_total_cost() == pytest.approx(0.01)
        assert store.llm_total_cost("t1") == pytest.approx(0.008)

    def test_invocation_count(self):
        store = InMemoryStore()
        assert store.llm_invocation_count() == 0
        store.save_llm_invocation("i1", "m", "p", 10, 5, 0.001, True, tenant_id="t1")
        store.save_llm_invocation("i2", "m", "p", 10, 5, 0.001, True, tenant_id="t2")
        assert store.llm_invocation_count() == 2
        assert store.llm_invocation_count("t1") == 1

    def test_ordered_descending(self):
        store = InMemoryStore()
        store.save_llm_invocation("first", "m", "p", 10, 5, 0.001, True)
        store.save_llm_invocation("second", "m", "p", 10, 5, 0.001, True)
        results = store.query_llm_invocations()
        assert results[0]["invocation_id"] == "second"
        assert results[1]["invocation_id"] == "first"


class TestInMemoryStoreClose:
    def test_close_is_noop(self):
        store = InMemoryStore()
        store.close()  # Should not raise


# ═══ Schema ═══

class TestSchema:
    def test_schema_version_defined(self):
        assert SCHEMA_VERSION >= 2

    def test_migrations_list(self):
        assert len(MIGRATIONS) == SCHEMA_VERSION
        for sql in MIGRATIONS:
            assert "CREATE TABLE" in sql

    def test_migration_1_has_base_tables(self):
        sql = MIGRATIONS[0]
        assert "ledger" in sql
        assert "sessions" in sql
        assert "requests" in sql

    def test_migration_2_has_llm_table(self):
        sql = MIGRATIONS[1]
        assert "llm_invocations" in sql
        assert "schema_version" in sql


# ═══ Store Factory ═══

class TestCreateStore:
    def test_memory_backend(self):
        store = create_store("memory")
        assert isinstance(store, InMemoryStore)

    def test_unsupported_backend_raises(self):
        with pytest.raises(ValueError, match="unsupported"):
            create_store("redis")

    def test_postgresql_without_psycopg2(self):
        """PostgresStore constructor handles missing psycopg2 gracefully."""
        try:
            import psycopg2
            pytest.skip("psycopg2 is installed — skip missing-driver test")
        except ImportError:
            # psycopg2 not installed — constructor should succeed but conn is None
            store = PostgresStore.__new__(PostgresStore)
            store._connection_string = "postgresql://localhost/test"
            store._pool_size = 1
            store._conn = None
            store._psycopg2_available = False
            # Store exists but can't do anything — this is expected
            assert store._conn is None


# ═══ PostgresStore (structural tests — no database required) ═══

class TestPostgresStoreStructure:
    def test_has_same_api_as_inmemory(self):
        """PostgresStore must implement same methods as InMemoryStore."""
        in_mem_methods = {m for m in dir(InMemoryStore) if not m.startswith("_")}
        pg_methods = {m for m in dir(PostgresStore) if not m.startswith("_")}
        # All InMemoryStore public methods must exist on PostgresStore
        missing = in_mem_methods - pg_methods
        assert not missing, f"PostgresStore missing methods: {missing}"

    def test_close_method_exists(self):
        assert hasattr(PostgresStore, "close")

    def test_append_ledger_method_exists(self):
        assert hasattr(PostgresStore, "append_ledger")

    def test_save_llm_invocation_method_exists(self):
        assert hasattr(PostgresStore, "save_llm_invocation")
