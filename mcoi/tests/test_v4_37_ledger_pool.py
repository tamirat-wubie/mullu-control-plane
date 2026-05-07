"""v4.37.0 — primary store (ledger / sessions / requests) connection pool.

Audit fracture F12 follow-up. v4.36 closed F12 for the governance stores
(``postgres_governance_stores.py``); v4.37 applies the same
``ThreadedConnectionPool`` pattern to the primary persistence store
(``postgres_store.py``) which holds ledger entries, session records,
HTTP request audit, and LLM-invocation tracking.

Pre-v4.37 ``PostgresStore`` accepted a ``pool_size`` kwarg but stored a
single ``psycopg2.connect`` regardless. The legacy path also had no
locking, so concurrent callers could race ``self._conn.cursor()`` —
undefined behavior under libpq.

v4.37:
  - ``pool_size > 1`` allocates a real ``ThreadedConnectionPool``
  - ``pool_size == 1`` (default) keeps single conn but adds
    ``self._lock`` to serialize cursor creation
  - ``MULLU_DB_POOL_SIZE`` env var flows through ``bootstrap_primary_store``
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _stub_psycopg2(monkeypatch, fake_pool_cls=None, fake_connect=None):
    pool_module = SimpleNamespace(
        ThreadedConnectionPool=fake_pool_cls or MagicMock(),
    )
    psycopg2_module = SimpleNamespace(
        connect=fake_connect or MagicMock(),
        pool=pool_module,
    )
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2_module)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_module)
    return psycopg2_module


# ---------------------------------------------------------------------------
# Pool init
# ---------------------------------------------------------------------------


class TestPoolInit:
    def test_default_pool_size_one_uses_single_connection(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = PostgresStore("postgresql://x/y", auto_migrate=False)
        assert store._pool is None
        assert store._conn is fake_conn
        fake_connect.assert_called_once_with("postgresql://x/y")

    def test_pool_size_gt_1_creates_threaded_pool(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = PostgresStore(
            "postgresql://x/y", pool_size=10, auto_migrate=False,
        )
        assert store._pool is fake_pool
        fake_pool_cls.assert_called_once_with(
            minconn=1, maxconn=10, dsn="postgresql://x/y",
        )

    @pytest.mark.parametrize("size", [0, -1, -100])
    def test_pool_size_clamped_to_one(self, monkeypatch, size):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_connect = MagicMock(return_value=MagicMock())
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = PostgresStore(
            "postgresql://x/y", pool_size=size, auto_migrate=False,
        )
        assert store._pool_size == 1
        assert store._pool is None


# ---------------------------------------------------------------------------
# Acquire / release
# ---------------------------------------------------------------------------


class TestPoolAcquireRelease:
    def test_pool_path_acquires_and_releases(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = PostgresStore(
            "postgresql://x/y", pool_size=4, auto_migrate=False,
        )
        fake_pool.reset_mock()  # clear init's getconn/putconn

        with store._connection() as conn:
            assert conn is fake_conn
        fake_pool.getconn.assert_called_once()
        fake_pool.putconn.assert_called_once_with(fake_conn)

    def test_pool_path_releases_on_exception(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = PostgresStore(
            "postgresql://x/y", pool_size=4, auto_migrate=False,
        )
        fake_pool.reset_mock()

        with pytest.raises(RuntimeError, match="boom"):
            with store._connection():
                raise RuntimeError("boom")
        fake_pool.putconn.assert_called_once_with(fake_conn)

    def test_legacy_path_uses_lock_serialization(self, monkeypatch):
        """pool_size=1 yields shared conn under self._lock so
        concurrent cursor creation is serialized (libpq requirement)."""
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = PostgresStore("postgresql://x/y", auto_migrate=False)
        with store._connection() as conn:
            assert conn is fake_conn
        # Lock released after context exit
        assert store._lock.acquire(blocking=False)
        store._lock.release()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestPoolLifecycle:
    def test_close_calls_pool_closeall(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = PostgresStore(
            "postgresql://x/y", pool_size=4, auto_migrate=False,
        )
        store.close()
        fake_pool.closeall.assert_called_once()
        assert store._pool is None
        assert store._conn is None

    def test_close_legacy_closes_single_conn(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = PostgresStore("postgresql://x/y", auto_migrate=False)
        store.close()
        fake_conn.close.assert_called_once()
        assert store._conn is None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactoryWiring:
    def test_create_store_passes_pool_size(self, monkeypatch):
        from mcoi_runtime.persistence import postgres_store as ps

        fake_conn = MagicMock()
        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = ps.create_store(
            backend="postgresql",
            connection_string="postgresql://x/y",
            pool_size=8,
        )
        assert store._pool is fake_pool
        fake_pool_cls.assert_called_once_with(
            minconn=1, maxconn=8, dsn="postgresql://x/y",
        )


# ---------------------------------------------------------------------------
# Bootstrap env wiring
# ---------------------------------------------------------------------------


class TestBootstrapEnvWiring:
    def test_mullu_db_pool_size_routed_to_create_store(self):
        from mcoi_runtime.app.server_platform import bootstrap_primary_store

        captured: dict = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(_conn=None)

        bootstrap_primary_store(
            env="local_dev",
            runtime_env={
                "MULLU_DB_BACKEND": "postgresql",
                "MULLU_DB_URL": "postgresql://h/db",
                "MULLU_DB_POOL_SIZE": "12",
            },
            clock=lambda: "2026-04-28T00:00:00Z",
            validate_db_backend_for_env=lambda b, e: None,
            create_store_fn=fake_create,
        )
        assert captured["pool_size"] == 12
        assert captured["backend"] == "postgresql"

    def test_pool_size_not_passed_for_memory_backend(self):
        """In-memory store doesn't accept pool_size; bootstrap omits it."""
        from mcoi_runtime.app.server_platform import bootstrap_primary_store

        captured: dict = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(_conn=None)

        bootstrap_primary_store(
            env="local_dev",
            runtime_env={
                "MULLU_DB_BACKEND": "memory",
                "MULLU_DB_POOL_SIZE": "5",  # ignored for memory
            },
            clock=lambda: "2026-04-28T00:00:00Z",
            validate_db_backend_for_env=lambda b, e: None,
            create_store_fn=fake_create,
        )
        assert "pool_size" not in captured

    def test_invalid_pool_size_falls_back(self):
        from mcoi_runtime.app.server_platform import bootstrap_primary_store

        captured: dict = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(_conn=None)

        bootstrap_primary_store(
            env="local_dev",
            runtime_env={
                "MULLU_DB_BACKEND": "postgresql",
                "MULLU_DB_POOL_SIZE": "garbage",
            },
            clock=lambda: "2026-04-28T00:00:00Z",
            validate_db_backend_for_env=lambda b, e: None,
            create_store_fn=fake_create,
        )
        assert captured["pool_size"] == 1


# ---------------------------------------------------------------------------
# Operation wiring: every call site goes through _connection()
# ---------------------------------------------------------------------------


class TestOperationsUseConnection:
    """Smoke-check that every public method actually uses _connection()
    so the pool path is exercised end-to-end."""

    def _store_with_pool(self, monkeypatch):
        from mcoi_runtime.persistence.postgres_store import PostgresStore

        fake_cur = MagicMock()
        fake_cur.__enter__ = lambda s: s
        fake_cur.__exit__ = MagicMock(return_value=False)
        fake_cur.fetchone.return_value = (1,)
        fake_cur.fetchall.return_value = []

        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cur

        fake_pool = MagicMock()
        fake_pool.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = PostgresStore(
            "postgresql://x/y", pool_size=4, auto_migrate=False,
        )
        fake_pool.reset_mock()
        return store, fake_pool, fake_conn, fake_cur

    def test_append_ledger_uses_pool(self, monkeypatch):
        store, pool, _, _ = self._store_with_pool(monkeypatch)
        store.append_ledger("t", "a", "tn", {"k": "v"}, "h")
        assert pool.getconn.called
        assert pool.putconn.called

    def test_save_session_uses_pool(self, monkeypatch):
        store, pool, _, _ = self._store_with_pool(monkeypatch)
        store.save_session("s1", "a", "tn")
        assert pool.getconn.called
        assert pool.putconn.called

    def test_save_request_uses_pool(self, monkeypatch):
        store, pool, _, _ = self._store_with_pool(monkeypatch)
        store.save_request("r1", "tn", "GET", "/", 200, True)
        assert pool.getconn.called
        assert pool.putconn.called

    def test_save_llm_invocation_uses_pool(self, monkeypatch):
        store, pool, _, _ = self._store_with_pool(monkeypatch)
        store.save_llm_invocation(
            "inv1", "claude", "anthropic", 100, 50, 0.1, True,
            budget_id="b1", tenant_id="tn", content_hash="h",
        )
        assert pool.getconn.called
        assert pool.putconn.called

    def test_query_ledger_uses_pool(self, monkeypatch):
        store, pool, _, _ = self._store_with_pool(monkeypatch)
        store.query_ledger("tn")
        assert pool.getconn.called
        assert pool.putconn.called
