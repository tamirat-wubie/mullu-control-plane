"""Phase 199B — PostgreSQL Production Backend.

Purpose: Durable PostgreSQL persistence for ledger, sessions, requests, and LLM invocations.
    Implements the same interface as SQLiteStore with production-grade features:
    connection pooling, schema migrations, and async-safe writes.
Governance scope: persistence backend only.
Dependencies: psycopg2 (or pure-Python fallback for testing).
Invariants:
  - Same API contract as SQLiteStore — drop-in replacement.
  - WAL equivalent via PostgreSQL's built-in WAL.
  - All writes are transactional.
  - Connection pooling is bounded.
  - Schema migrations are idempotent.
"""

from __future__ import annotations

import json
import logging as _logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Protocol


_log = _logging.getLogger(__name__)


def _bounded_store_migration_error(exc: Exception, index: int) -> RuntimeError:
    """Return a bounded PostgreSQL migration failure."""
    return RuntimeError(f"postgres schema migration {index} failed ({type(exc).__name__})")


def _bounded_store_failure(exc: Exception) -> str:
    """Return a type-only PostgreSQL store failure label."""
    return type(exc).__name__


class DatabaseConnection(Protocol):
    """Protocol for database connections — allows PostgreSQL or in-memory backends."""

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


# ═══ Schema Management ═══

SCHEMA_VERSION = 2  # Phase 199B schema

MIGRATIONS: list[str] = [
    # Migration 1: Base tables (compatible with SQLiteStore)
    """
    CREATE TABLE IF NOT EXISTS ledger (
        id SERIAL PRIMARY KEY,
        entry_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        content TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS requests (
        request_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        status_code INTEGER,
        governed INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ledger_tenant ON ledger(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_requests_tenant ON requests(tenant_id);
    """,

    # Migration 2: LLM invocation tracking table
    """
    CREATE TABLE IF NOT EXISTS llm_invocations (
        id SERIAL PRIMARY KEY,
        invocation_id TEXT NOT NULL UNIQUE,
        model_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        cost REAL NOT NULL DEFAULT 0.0,
        succeeded INTEGER NOT NULL DEFAULT 0,
        budget_id TEXT NOT NULL DEFAULT '',
        tenant_id TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_llm_tenant ON llm_invocations(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_llm_budget ON llm_invocations(budget_id);
    """,
]


# ═══ In-Memory Backend (for testing without PostgreSQL) ═══


class InMemoryStore:
    """In-memory persistence backend implementing the same API as PostgresStore.

    Used for testing and development without a real database.
    All data is lost when the process exits.
    """

    def __init__(self) -> None:
        self._ledger: list[dict[str, Any]] = []
        self._sessions: dict[str, dict[str, Any]] = {}
        self._requests: dict[str, dict[str, Any]] = {}
        self._llm_invocations: list[dict[str, Any]] = []
        self._next_id = 1

    def append_ledger(
        self, entry_type: str, actor_id: str, tenant_id: str, content: dict[str, Any], content_hash: str
    ) -> int:
        entry_id = self._next_id
        self._next_id += 1
        self._ledger.append({
            "id": entry_id,
            "entry_type": entry_type,
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "content": content,
            "content_hash": content_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return entry_id

    def query_ledger(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        entries = [e for e in self._ledger if e["tenant_id"] == tenant_id]
        entries.sort(key=lambda e: e["id"], reverse=True)
        return [
            {"id": e["id"], "type": e["entry_type"], "actor": e["actor_id"],
             "content": e["content"], "hash": e["content_hash"], "at": e["created_at"]}
            for e in entries[:limit]
        ]

    def ledger_count(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            return sum(1 for e in self._ledger if e["tenant_id"] == tenant_id)
        return len(self._ledger)

    def save_session(self, session_id: str, actor_id: str, tenant_id: str) -> None:
        self._sessions[session_id] = {
            "session_id": session_id,
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._sessions.get(session_id)

    def deactivate_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions[session_id]["active"] = False
            return True
        return False

    def active_session_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s["active"])

    def save_request(
        self, request_id: str, tenant_id: str, method: str, path: str, status_code: int, governed: bool
    ) -> None:
        self._requests[request_id] = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "governed": governed,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def request_count(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            return sum(1 for r in self._requests.values() if r["tenant_id"] == tenant_id)
        return len(self._requests)

    def save_llm_invocation(
        self,
        invocation_id: str,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        succeeded: bool,
        budget_id: str = "",
        tenant_id: str = "",
        content_hash: str = "",
    ) -> int:
        entry_id = self._next_id
        self._next_id += 1
        self._llm_invocations.append({
            "id": entry_id,
            "invocation_id": invocation_id,
            "model_name": model_name,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "succeeded": succeeded,
            "budget_id": budget_id,
            "tenant_id": tenant_id,
            "content_hash": content_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return entry_id

    def query_llm_invocations(self, tenant_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        entries = self._llm_invocations
        if tenant_id:
            entries = [e for e in entries if e["tenant_id"] == tenant_id]
        entries = sorted(entries, key=lambda e: e["id"], reverse=True)
        return entries[:limit]

    def llm_total_cost(self, tenant_id: str = "") -> float:
        entries = self._llm_invocations
        if tenant_id:
            entries = [e for e in entries if e["tenant_id"] == tenant_id]
        return sum(e["cost"] for e in entries)

    def llm_invocation_count(self, tenant_id: str = "") -> int:
        if tenant_id:
            return sum(1 for e in self._llm_invocations if e["tenant_id"] == tenant_id)
        return len(self._llm_invocations)

    def close(self) -> None:
        pass  # No-op for in-memory store


# ═══ PostgreSQL Store ═══


class PostgresStore:
    """PostgreSQL persistence backend for production deployment.

    Features:
    - Connection pooling (bounded by ``pool_size``)
    - Idempotent schema migrations
    - Same API as SQLiteStore + LLM invocation tracking
    - Transactional writes with auto-commit

    Requires psycopg2: pip install psycopg2-binary

    v4.37.0 (audit F12 follow-up): pool path is now actually used. Pre-
    v4.37 the constructor accepted ``pool_size`` but stored a single
    ``psycopg2.connect`` regardless. ``pool_size > 1`` now allocates a
    real ``psycopg2.pool.ThreadedConnectionPool`` and acquires a
    connection per operation via ``self._connection()``.

    The legacy single-conn path also gains thread-safety via
    ``self._lock``. Pre-v4.37 concurrent callers could race
    ``self._conn.cursor()`` on the shared connection — undefined
    behavior under libpq. The lock fixes that for ``pool_size=1``
    deployments without changing externally observable behavior.
    """

    # Class-level defaults so test fixtures that hand-build instances
    # (without calling __init__) still have the v4.37 pool attributes.
    _pool: Any = None
    _pool_size: int = 1

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        pool_size: int = 1,
        *,
        auto_migrate: bool = True,
    ) -> None:
        self._connection_string = connection_string
        # v4.37.0: clamp to >= 1 so 0/negative don't invoke
        # ThreadedConnectionPool(maxconn=0) which raises.
        self._pool_size = max(1, int(pool_size))
        self._conn: Any = None
        self._pool: Any = None
        self._lock = threading.Lock()
        self._psycopg2_available = False

        try:
            import psycopg2  # noqa: F401
            self._psycopg2_available = True
        except ImportError:
            pass

        if self._psycopg2_available:
            try:
                self._connect()
                if auto_migrate:
                    self._run_migrations()
            except Exception as exc:
                _log.warning(
                    "postgres store connection failed (%s)",
                    _bounded_store_failure(exc),
                )
                self._conn = None
                if self._pool is not None:
                    try:
                        self._pool.closeall()
                    except Exception:
                        pass
                    self._pool = None

    def _connect(self) -> None:
        """Open a single connection or pool depending on ``pool_size``.

        v4.37.0 (audit F12): mirrors the v4.36 ``_PostgresBase`` pattern
        from ``postgres_governance_stores.py``. ``pool_size > 1``
        creates a ``ThreadedConnectionPool``; the placeholder
        ``self._conn`` keeps the existing ``self._conn is None``
        availability check semantics.
        """
        import psycopg2
        if self._pool_size > 1:
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=self._pool_size,
                dsn=self._connection_string,
            )
            self._conn = self._pool.getconn()
            self._conn.autocommit = False
            self._pool.putconn(self._conn)
        else:
            self._conn = psycopg2.connect(self._connection_string)
            self._conn.autocommit = False

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        """Yield a connection — pooled if configured, single otherwise.

        Pool path: get/put from ``ThreadedConnectionPool`` per call.
        Legacy path: acquire ``self._lock`` so concurrent callers
        don't race ``self._conn.cursor()`` (libpq is not safe under
        concurrent cursor creation on the same connection).
        """
        if self._pool is not None:
            conn = self._pool.getconn()
            try:
                yield conn
            finally:
                try:
                    self._pool.putconn(conn)
                except Exception as exc:
                    _log.warning(
                        "postgres store pool putconn failed (%s)",
                        _bounded_store_failure(exc),
                    )
        else:
            # Lazy-init for test fixtures that bypass __init__ via
            # __new__ + manual attribute set.
            lock = getattr(self, "_lock", None)
            if lock is None:
                lock = threading.Lock()
                self._lock = lock
            with lock:
                yield self._conn

    def _run_migrations(self) -> None:
        """Run idempotent schema migrations."""
        if self._conn is None:
            return
        with self._connection() as conn, conn.cursor() as cur:
            for index, migration_sql in enumerate(MIGRATIONS, start=1):
                try:
                    cur.execute(migration_sql)
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    raise _bounded_store_migration_error(exc, index) from exc
                    # Migration already applied or table exists — idempotent

    def append_ledger(
        self, entry_type: str, actor_id: str, tenant_id: str, content: dict[str, Any], content_hash: str
    ) -> int:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ledger (entry_type, actor_id, tenant_id, content, content_hash, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (entry_type, actor_id, tenant_id, json.dumps(content, sort_keys=True),
                 content_hash, datetime.now(timezone.utc).isoformat()),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
        return row_id

    def query_ledger(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, entry_type, actor_id, content, content_hash, created_at "
                "FROM ledger WHERE tenant_id = %s ORDER BY id DESC LIMIT %s",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "type": r[1], "actor": r[2], "content": json.loads(r[3]), "hash": r[4], "at": r[5]}
            for r in rows
        ]

    def ledger_count(self, tenant_id: str | None = None) -> int:
        with self._connection() as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT COUNT(*) FROM ledger WHERE tenant_id = %s", (tenant_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM ledger")
            count = cur.fetchone()[0]
        return count

    def save_request(
        self, request_id: str, tenant_id: str, method: str, path: str, status_code: int, governed: bool
    ) -> None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO requests (request_id, tenant_id, method, path, status_code, governed, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (request_id) DO UPDATE SET status_code = EXCLUDED.status_code",
                (request_id, tenant_id, method, path, status_code, 1 if governed else 0,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def save_session(self, session_id: str, actor_id: str, tenant_id: str) -> None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (session_id, actor_id, tenant_id, active, created_at) "
                "VALUES (%s, %s, %s, 1, %s) ON CONFLICT (session_id) DO UPDATE SET active = 1",
                (session_id, actor_id, tenant_id, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT session_id, actor_id, tenant_id, active, created_at FROM sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "session_id": row[0], "actor_id": row[1], "tenant_id": row[2],
            "active": bool(row[3]), "created_at": row[4],
        }

    def deactivate_session(self, session_id: str) -> bool:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE sessions SET active = 0 WHERE session_id = %s", (session_id,))
            affected = cur.rowcount
            conn.commit()
        return affected > 0

    def active_session_count(self) -> int:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sessions WHERE active = 1")
            count = cur.fetchone()[0]
        return count

    def request_count(self, tenant_id: str | None = None) -> int:
        with self._connection() as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT COUNT(*) FROM requests WHERE tenant_id = %s", (tenant_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM requests")
            count = cur.fetchone()[0]
        return count

    def save_llm_invocation(
        self,
        invocation_id: str,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        succeeded: bool,
        budget_id: str = "",
        tenant_id: str = "",
        content_hash: str = "",
    ) -> int:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO llm_invocations (invocation_id, model_name, provider, input_tokens, output_tokens, "
                "cost, succeeded, budget_id, tenant_id, content_hash, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (invocation_id, model_name, provider, input_tokens, output_tokens,
                 cost, 1 if succeeded else 0, budget_id, tenant_id, content_hash,
                 datetime.now(timezone.utc).isoformat()),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
        return row_id

    def query_llm_invocations(self, tenant_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute(
                    "SELECT id, invocation_id, model_name, provider, input_tokens, output_tokens, "
                    "cost, succeeded, budget_id, tenant_id, content_hash, created_at "
                    "FROM llm_invocations WHERE tenant_id = %s ORDER BY id DESC LIMIT %s",
                    (tenant_id, limit),
                )
            else:
                cur.execute(
                    "SELECT id, invocation_id, model_name, provider, input_tokens, output_tokens, "
                    "cost, succeeded, budget_id, tenant_id, content_hash, created_at "
                    "FROM llm_invocations ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
        return [
            {
                "id": r[0], "invocation_id": r[1], "model_name": r[2], "provider": r[3],
                "input_tokens": r[4], "output_tokens": r[5], "cost": r[6],
                "succeeded": bool(r[7]), "budget_id": r[8], "tenant_id": r[9],
                "content_hash": r[10], "created_at": r[11],
            }
            for r in rows
        ]

    def llm_total_cost(self, tenant_id: str = "") -> float:
        with self._connection() as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT COALESCE(SUM(cost), 0) FROM llm_invocations WHERE tenant_id = %s", (tenant_id,))
            else:
                cur.execute("SELECT COALESCE(SUM(cost), 0) FROM llm_invocations")
            cost = cur.fetchone()[0]
        return float(cost)

    def llm_invocation_count(self, tenant_id: str = "") -> int:
        with self._connection() as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT COUNT(*) FROM llm_invocations WHERE tenant_id = %s", (tenant_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM llm_invocations")
            count = cur.fetchone()[0]
        return count

    def close(self) -> None:
        # v4.37.0 (audit F12 follow-up): close pool first if present,
        # then the placeholder single connection. Mirrors the v4.36
        # ``_PostgresBase`` close pattern.
        if self._pool is not None:
            try:
                self._pool.closeall()
            except Exception as exc:
                _log.warning(
                    "postgres store pool close failed (%s)",
                    _bounded_store_failure(exc),
                )
            finally:
                self._pool = None
                self._conn = None
        elif self._conn is not None:
            try:
                self._conn.close()
            except Exception as exc:
                _log.warning(
                    "postgres store close failed (%s)",
                    _bounded_store_failure(exc),
                )
            finally:
                self._conn = None


# ═══ Store Factory ═══


def create_store(backend: str = "memory", connection_string: str = "", **kwargs: Any) -> InMemoryStore | PostgresStore:
    """Factory for creating persistence stores based on deployment profile.

    backends:
    - "memory" → InMemoryStore (testing/development)
    - "sqlite" → SQLiteStore (pilot) — import from persistence.sqlite_store
    - "postgresql" → PostgresStore (production)
    """
    if backend == "memory":
        return InMemoryStore()
    if backend == "sqlite":
        from mcoi_runtime.persistence.sqlite_store import SQLiteStore
        return SQLiteStore(db_path=connection_string or "mullu.db")
    if backend == "postgresql":
        return PostgresStore(connection_string, **kwargs)
    raise ValueError("unsupported persistence backend")
