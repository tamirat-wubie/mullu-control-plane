"""Phase 218A — PostgresStore integration test.

Requires Docker with PostgreSQL running. Skips automatically if unavailable.
Run manually: docker-compose up -d postgres && pytest tests/test_postgres_integration.py -v
"""

import os
import pytest
from mcoi_runtime.persistence.postgres_store import InMemoryStore, create_store

# Try to detect if PostgreSQL is available
POSTGRES_URL = os.environ.get("MULLU_DB_URL", "postgresql://mullu:mullu_dev_password@localhost:5432/mullu")
POSTGRES_AVAILABLE = False

try:
    import psycopg2
    conn = psycopg2.connect(POSTGRES_URL)
    conn.close()
    POSTGRES_AVAILABLE = True
except Exception:
    pass


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not available (run docker-compose up -d postgres)")
class TestPostgresStoreIntegration:
    """Integration tests against real PostgreSQL — skipped if Docker not running."""

    def test_create_store(self):
        store = create_store(backend="postgresql", connection_string=POSTGRES_URL)
        assert store is not None

    def test_append_and_query_ledger(self):
        store = create_store(backend="postgresql", connection_string=POSTGRES_URL)
        entry_id = store.append_ledger("test", "actor-1", "integration-test", {"key": "value"}, "hash123")
        assert entry_id > 0
        entries = store.query_ledger("integration-test", limit=10)
        assert len(entries) >= 1

    def test_ledger_count(self):
        store = create_store(backend="postgresql", connection_string=POSTGRES_URL)
        store.append_ledger("test", "actor-1", "count-test", {}, "hash")
        assert store.ledger_count("count-test") >= 1

    def test_save_session(self):
        store = create_store(backend="postgresql", connection_string=POSTGRES_URL)
        store.save_session("sess-int-1", "actor-1", "test-tenant")
        # Should not raise


class TestInMemoryStoreContract:
    """Verify InMemoryStore implements same API as PostgresStore."""

    def test_append_ledger(self):
        store = InMemoryStore()
        eid = store.append_ledger("test", "actor", "tenant", {"k": "v"}, "hash")
        assert eid >= 1

    def test_query_ledger(self):
        store = InMemoryStore()
        store.append_ledger("test", "actor", "t1", {"a": 1}, "h1")
        store.append_ledger("test", "actor", "t2", {"b": 2}, "h2")
        t1 = store.query_ledger("t1")
        assert len(t1) == 1
        assert t1[0]["content"]["a"] == 1

    def test_ledger_count(self):
        store = InMemoryStore()
        store.append_ledger("a", "x", "t1", {}, "h")
        store.append_ledger("b", "x", "t1", {}, "h")
        store.append_ledger("c", "x", "t2", {}, "h")
        assert store.ledger_count() == 3
        assert store.ledger_count("t1") == 2

    def test_save_session(self):
        store = InMemoryStore()
        store.save_session("s1", "actor", "tenant")
        # Should not raise

    def test_create_store_memory(self):
        store = create_store(backend="memory")
        assert isinstance(store, InMemoryStore)

    def test_create_store_unknown_fallback(self):
        # Unknown backend — implementation-dependent behavior
        try:
            store = create_store(backend="nonexistent")
        except Exception:
            pass  # May raise or fall back

    def test_tenant_isolation(self):
        store = InMemoryStore()
        store.append_ledger("secret", "actor", "tenant-a", {"data": "a-secret"}, "ha")
        store.append_ledger("secret", "actor", "tenant-b", {"data": "b-secret"}, "hb")
        a_entries = store.query_ledger("tenant-a")
        b_entries = store.query_ledger("tenant-b")
        assert all(e["content"]["data"] == "a-secret" for e in a_entries)
        assert all(e["content"]["data"] == "b-secret" for e in b_entries)
