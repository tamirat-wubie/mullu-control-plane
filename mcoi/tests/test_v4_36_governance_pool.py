"""v4.36.0 — governance store connection pool (audit F12).

Pre-v4.36 every governance store opened a single PostgreSQL connection
and serialized every operation behind ``self._lock``. With N concurrent
writers, effective write throughput was bounded by 1 connection × 1
cursor at a time. Audit fracture F12 called this out as the production
write-throughput ceiling.

v4.36 introduces an opt-in ``ThreadedConnectionPool`` per store via
``pool_size > 1``. Each operation goes through ``_PostgresBase.
_connection()`` which acquires from the pool, yields, and returns the
connection on context exit. The atomic SQL primitives shipped in v4.27
(budget) / v4.29 (rate-limit) / v4.30 (hash chain) / v4.31 (audit
append) handle concurrency at the DB level, so the Python-side global
lock is no longer needed on the pool path.

These tests mock ``psycopg2.pool.ThreadedConnectionPool`` so we don't
need a live PostgreSQL — they verify wiring, lifecycle, and that
operations actually go through the pool when configured.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_psycopg2(monkeypatch, fake_pool_cls=None, fake_connect=None):
    """Install a stub ``psycopg2`` module in ``sys.modules``.

    The store's ``_base_init`` does ``import psycopg2`` to detect
    availability. Tests want availability + a controllable pool/connect
    surface. This installs a minimal stub.
    """
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
# Pool initialization
# ---------------------------------------------------------------------------


class TestPoolInit:
    def test_pool_size_1_uses_single_connection_path(self, monkeypatch):
        """pool_size=1 keeps the legacy single-conn behavior."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=1,
        )
        assert store._pool is None
        assert store._conn is fake_conn
        fake_connect.assert_called_once_with("postgresql://x/y")

    def test_pool_size_gt_1_creates_threaded_pool(self, monkeypatch):
        """pool_size > 1 allocates ThreadedConnectionPool."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_instance = MagicMock()
        fake_pool_instance.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool_instance)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=8,
        )
        assert store._pool is fake_pool_instance
        fake_pool_cls.assert_called_once_with(
            minconn=1, maxconn=8, dsn="postgresql://x/y",
        )

    def test_pool_size_zero_clamped_to_one(self, monkeypatch):
        """pool_size=0 is clamped to 1 to avoid undefined behavior."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_connect = MagicMock(return_value=MagicMock())
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=0,
        )
        assert store._pool_size == 1
        assert store._pool is None

    def test_negative_pool_size_clamped(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_connect = MagicMock(return_value=MagicMock())
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=-3,
        )
        assert store._pool_size == 1


# ---------------------------------------------------------------------------
# Pool acquire / release
# ---------------------------------------------------------------------------


class TestPoolAcquireRelease:
    def test_connection_context_acquires_and_releases(self, monkeypatch):
        """Each call to _connection() pulls from the pool and returns it."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_instance = MagicMock()
        fake_pool_instance.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool_instance)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=4,
        )
        # Reset call counts after init (init also does getconn/putconn
        # for the placeholder).
        fake_pool_instance.reset_mock()

        with store._connection() as conn:
            assert conn is fake_conn
        fake_pool_instance.getconn.assert_called_once()
        fake_pool_instance.putconn.assert_called_once_with(fake_conn)

    def test_connection_context_releases_on_exception(self, monkeypatch):
        """A raise inside the context still returns the conn to the pool."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_instance = MagicMock()
        fake_pool_instance.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool_instance)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=4,
        )
        fake_pool_instance.reset_mock()

        with pytest.raises(RuntimeError, match="boom"):
            with store._connection():
                raise RuntimeError("boom")
        fake_pool_instance.putconn.assert_called_once_with(fake_conn)

    def test_legacy_path_uses_self_lock_serialization(self, monkeypatch):
        """When pool_size=1, _connection() yields the shared conn under self._lock."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        _stub_psycopg2(monkeypatch, fake_connect=fake_connect)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=1,
        )
        with store._connection() as conn:
            assert conn is fake_conn
        # Lock acquired and released — verify by re-acquiring (would
        # block if not released).
        assert store._lock.acquire(blocking=False)
        store._lock.release()


# ---------------------------------------------------------------------------
# Lifecycle: close / reconnect
# ---------------------------------------------------------------------------


class TestPoolLifecycle:
    def test_close_calls_pool_closeall(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_instance = MagicMock()
        fake_pool_instance.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool_instance)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=4,
        )
        store.close()
        fake_pool_instance.closeall.assert_called_once()
        assert store._pool is None
        assert store._conn is None

    def test_reconnect_replaces_pool(self, monkeypatch):
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_a = MagicMock()
        fake_pool_a.getconn.return_value = fake_conn
        fake_pool_b = MagicMock()
        fake_pool_b.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(side_effect=[fake_pool_a, fake_pool_b])
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        store = pg.PostgresBudgetStore(
            "postgresql://x/y", auto_migrate=False, pool_size=4,
        )
        assert store._pool is fake_pool_a

        ok = store._reconnect()
        assert ok is True
        assert store._pool is fake_pool_b
        fake_pool_a.closeall.assert_called_once()


# ---------------------------------------------------------------------------
# Factory wiring
# ---------------------------------------------------------------------------


class TestFactoryPoolSize:
    def test_create_governance_stores_passes_pool_size(self, monkeypatch):
        """create_governance_stores forwards pool_size to each store."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_pool_instance = MagicMock()
        fake_pool_instance.getconn.return_value = fake_conn
        fake_pool_cls = MagicMock(return_value=fake_pool_instance)
        _stub_psycopg2(monkeypatch, fake_pool_cls=fake_pool_cls)

        bundle = pg.create_governance_stores(
            backend="postgresql",
            connection_string="postgresql://x/y",
            pool_size=6,
        )
        # 4 stores × 1 ThreadedConnectionPool each. Each pool was
        # constructed with maxconn=6.
        assert fake_pool_cls.call_count == 4
        for call in fake_pool_cls.call_args_list:
            assert call.kwargs["maxconn"] == 6
        bundle.close()

    def test_create_governance_stores_default_pool_size_one(self, monkeypatch):
        """Default pool_size=1 keeps legacy single-conn path."""
        import mcoi_runtime.persistence.postgres_governance_stores as pg

        fake_conn = MagicMock()
        fake_connect = MagicMock(return_value=fake_conn)
        fake_pool_cls = MagicMock()
        _stub_psycopg2(
            monkeypatch,
            fake_pool_cls=fake_pool_cls,
            fake_connect=fake_connect,
        )

        bundle = pg.create_governance_stores(
            backend="postgresql",
            connection_string="postgresql://x/y",
        )
        assert fake_pool_cls.call_count == 0
        # 4 stores × 1 connect each
        assert fake_connect.call_count == 4
        bundle.close()


# ---------------------------------------------------------------------------
# Bootstrap wiring (env var → pool_size)
# ---------------------------------------------------------------------------


class TestBootstrapEnvWiring:
    def test_mullu_db_pool_size_env_var_routed(self):
        """MULLU_DB_POOL_SIZE flows from runtime_env to create_governance_stores."""
        from mcoi_runtime.app.server_platform import bootstrap_governance_runtime

        captured: dict = {}

        def fake_create_stores(**kwargs):
            captured.update(kwargs)
            # Return a minimal bundle that the rest of bootstrap can use
            from mcoi_runtime.persistence.postgres_governance_stores import (
                GovernanceStoreBundle, InMemoryAuditStore, InMemoryBudgetStore,
                InMemoryRateLimitStore, InMemoryTenantGatingStore,
            )
            return GovernanceStoreBundle({
                "budget": InMemoryBudgetStore(),
                "audit": InMemoryAuditStore(),
                "rate_limit": InMemoryRateLimitStore(),
                "tenant_gating": InMemoryTenantGatingStore(),
            })

        bootstrap_governance_runtime(
            env="local_dev",
            runtime_env={"MULLU_DB_POOL_SIZE": "12"},
            db_backend="memory",
            clock=lambda: "2026-04-28T00:00:00Z",
            field_encryptor=None,
            allow_unknown_tenants=True,
            create_governance_stores_fn=fake_create_stores,
        )
        assert captured["pool_size"] == 12

    def test_invalid_pool_size_falls_back_to_one(self):
        from mcoi_runtime.app.server_platform import bootstrap_governance_runtime

        captured: dict = {}

        def fake_create_stores(**kwargs):
            captured.update(kwargs)
            from mcoi_runtime.persistence.postgres_governance_stores import (
                GovernanceStoreBundle, InMemoryAuditStore, InMemoryBudgetStore,
                InMemoryRateLimitStore, InMemoryTenantGatingStore,
            )
            return GovernanceStoreBundle({
                "budget": InMemoryBudgetStore(),
                "audit": InMemoryAuditStore(),
                "rate_limit": InMemoryRateLimitStore(),
                "tenant_gating": InMemoryTenantGatingStore(),
            })

        bootstrap_governance_runtime(
            env="local_dev",
            runtime_env={"MULLU_DB_POOL_SIZE": "not-a-number"},
            db_backend="memory",
            clock=lambda: "2026-04-28T00:00:00Z",
            field_encryptor=None,
            allow_unknown_tenants=True,
            create_governance_stores_fn=fake_create_stores,
        )
        assert captured["pool_size"] == 1

    def test_default_pool_size_one_when_unset(self):
        from mcoi_runtime.app.server_platform import bootstrap_governance_runtime

        captured: dict = {}

        def fake_create_stores(**kwargs):
            captured.update(kwargs)
            from mcoi_runtime.persistence.postgres_governance_stores import (
                GovernanceStoreBundle, InMemoryAuditStore, InMemoryBudgetStore,
                InMemoryRateLimitStore, InMemoryTenantGatingStore,
            )
            return GovernanceStoreBundle({
                "budget": InMemoryBudgetStore(),
                "audit": InMemoryAuditStore(),
                "rate_limit": InMemoryRateLimitStore(),
                "tenant_gating": InMemoryTenantGatingStore(),
            })

        bootstrap_governance_runtime(
            env="local_dev",
            runtime_env={},
            db_backend="memory",
            clock=lambda: "2026-04-28T00:00:00Z",
            field_encryptor=None,
            allow_unknown_tenants=True,
            create_governance_stores_fn=fake_create_stores,
        )
        assert captured["pool_size"] == 1
