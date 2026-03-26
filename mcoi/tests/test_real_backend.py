"""Phase 198 — Real Backend Integration Tests."""
import pytest
import tempfile
import os

class TestSQLiteStore:
    def test_create_and_query_ledger(self):
        from mcoi_runtime.persistence.sqlite_store import SQLiteStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = SQLiteStore(path)
            rid = store.append_ledger("dispatch", "actor-1", "tenant-1", {"action": "test"}, "hash123")
            assert rid >= 1
            entries = store.query_ledger("tenant-1")
            assert len(entries) == 1
            assert entries[0]["type"] == "dispatch"
            assert entries[0]["actor"] == "actor-1"
            store.close()
        finally:
            os.unlink(path)

    def test_ledger_count(self):
        from mcoi_runtime.persistence.sqlite_store import SQLiteStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = SQLiteStore(path)
            store.append_ledger("a", "actor", "t1", {}, "h1")
            store.append_ledger("b", "actor", "t1", {}, "h2")
            store.append_ledger("c", "actor", "t2", {}, "h3")
            assert store.ledger_count("t1") == 2
            assert store.ledger_count() == 3
            store.close()
        finally:
            os.unlink(path)

    def test_save_request(self):
        from mcoi_runtime.persistence.sqlite_store import SQLiteStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = SQLiteStore(path)
            store.save_request("req-1", "t1", "POST", "/api/execute", 200, True)
            store.close()
        finally:
            os.unlink(path)

    def test_tenant_isolation_in_ledger(self):
        from mcoi_runtime.persistence.sqlite_store import SQLiteStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = SQLiteStore(path)
            store.append_ledger("x", "a1", "t1", {"data": 1}, "h1")
            store.append_ledger("y", "a2", "t2", {"data": 2}, "h2")
            t1_entries = store.query_ledger("t1")
            t2_entries = store.query_ledger("t2")
            assert len(t1_entries) == 1
            assert len(t2_entries) == 1
            assert t1_entries[0]["actor"] == "a1"
            assert t2_entries[0]["actor"] == "a2"
            store.close()
        finally:
            os.unlink(path)

class TestDockerfile:
    def test_dockerfile_exists(self):
        assert os.path.exists("Dockerfile") or os.path.exists("../Dockerfile") or os.path.exists("../../Dockerfile")

class TestServerModule:
    def test_server_importable(self):
        """Verify server module can be imported (FastAPI may not be installed in test env)."""
        try:
            from mcoi_runtime.app import server
            assert hasattr(server, 'app')
        except ImportError:
            pytest.skip("FastAPI not installed in test environment")
