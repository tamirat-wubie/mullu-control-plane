"""Phase 1A/2D â€” PostgreSQL Governance Stores.

Purpose: Production-grade PostgreSQL implementations for governance
    externalization stores: BudgetStore, AuditStore, RateLimitStore,
    and TenantGatingStore. These replace the in-memory stubs, making
    governance state durable and consistent across replicas.
Governance scope: persistence backend only.
Dependencies: psycopg2 (optional â€” graceful fallback to no-op stubs).
Invariants:
  - Same interface contracts as the stub base classes.
  - All writes are transactional (auto-commit per operation).
  - Connection pooling follows existing PostgresStore pattern.
  - Schema migrations are idempotent (CREATE IF NOT EXISTS).
  - Thread-safe via cursor-per-operation pattern.
  - Graceful degradation if psycopg2 is unavailable.
"""

from __future__ import annotations

import json
import logging as _logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Iterator

from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.governance.audit.trail import (
    AuditCheckpoint,
    AuditEntry,
    AuditStore,
)
# v4.39.0 (audit F7 Phase 2): private helper imported directly from the
# implementation module. The shim layer in governance/ only re-exports
# the public API; reaching into private internals stays on the canonical
# core path. Phase 4 will move the implementation here too.
from mcoi_runtime.governance.audit.trail import _canonical_hash_v1
from mcoi_runtime.governance.guards.rate_limit import RateLimitStore
from mcoi_runtime.governance.guards.budget import BudgetStore
from mcoi_runtime.governance.guards.tenant_gating import TenantGate, TenantGatingStore, TenantStatus


# â•â•â• Schema Definitions â•â•â•

GOVERNANCE_MIGRATIONS: list[str] = [
    # Migration 1: Budget table
    """
    CREATE TABLE IF NOT EXISTS governance_budgets (
        tenant_id TEXT PRIMARY KEY,
        budget_id TEXT NOT NULL,
        max_cost DOUBLE PRECISION NOT NULL,
        spent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        max_tokens_per_call INTEGER NOT NULL DEFAULT 4096,
        max_calls INTEGER NOT NULL DEFAULT 1000,
        calls_made INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    );
    """,

    # Migration 2: Audit entries table
    """
    CREATE TABLE IF NOT EXISTS governance_audit_entries (
        entry_id TEXT PRIMARY KEY,
        sequence INTEGER NOT NULL UNIQUE,
        action TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        target TEXT NOT NULL,
        outcome TEXT NOT NULL,
        detail JSONB NOT NULL DEFAULT '{}',
        entry_hash TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_gov_audit_tenant
        ON governance_audit_entries(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_gov_audit_sequence
        ON governance_audit_entries(sequence);
    CREATE INDEX IF NOT EXISTS idx_gov_audit_action
        ON governance_audit_entries(action);
    CREATE INDEX IF NOT EXISTS idx_gov_audit_outcome
        ON governance_audit_entries(outcome);
    """,

    # Migration 3: Rate limit decisions table
    """
    CREATE TABLE IF NOT EXISTS governance_rate_decisions (
        bucket_key TEXT PRIMARY KEY,
        allowed_count INTEGER NOT NULL DEFAULT 0,
        denied_count INTEGER NOT NULL DEFAULT 0,
        last_updated TEXT NOT NULL
    );
    """,

    # Migration 4: Tenant gating table
    """
    CREATE TABLE IF NOT EXISTS governance_tenant_gates (
        tenant_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'active',
        reason TEXT NOT NULL DEFAULT '',
        gated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_gov_gate_status
        ON governance_tenant_gates(status);
    """,
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

_log = _logging.getLogger(__name__)


def _bounded_detail_crypto_error(phase: str, exc: Exception) -> RuntimeError:
    """Return a bounded audit-detail failure without leaking backend text."""
    return RuntimeError(f"audit detail {phase} failed ({type(exc).__name__})")


def _bounded_store_failure(exc: Exception) -> str:
    """Return a type-only failure label for operator-visible store warnings."""
    return type(exc).__name__


class _PostgresBase:
    """Shared base for PostgreSQL governance stores.

    Provides connection management, migration execution, and safe
    query execution with reconnection on failure.

    v4.36.0 (audit F12): optional ``ThreadedConnectionPool`` for write
    throughput. Pre-v4.36 every governance store opened a single
    PostgreSQL connection and serialized every operation behind
    ``self._lock``. Under N concurrent writers the effective
    throughput was bounded by 1 connection × 1 cursor at a time.

    When ``pool_size > 1`` the base class allocates a
    ``psycopg2.pool.ThreadedConnectionPool`` and acquires a connection
    per operation via ``self._connection()``. The atomic SQL
    primitives shipped in v4.27 (budget) / v4.29 (rate-limit) /
    v4.30 (hash chain) / v4.31 (audit append) handle concurrency at
    the DB level, so the Python-side global lock is no longer needed
    on the pool path. Single-connection (legacy) deployments keep
    ``self._lock`` to serialize cursor creation on the shared conn.
    """

    _connection_string: str
    _conn: Any
    _pool: Any
    _pool_size: int
    _available: bool
    _lock: threading.Lock

    # Class-level defaults so subclasses constructed without _base_init
    # (e.g. test fixtures that hand-build state) still have the
    # attributes the v4.36 pool path checks.
    _pool = None
    _pool_size = 1

    def _base_init(
        self,
        connection_string: str,
        migration_index: int,
        auto_migrate: bool = True,
        pool_size: int = 1,
    ) -> None:
        self._connection_string = connection_string
        self._conn = None
        self._pool = None
        self._pool_size = max(1, int(pool_size))
        self._available = False
        self._lock = threading.Lock()
        self._migration_index = migration_index

        try:
            import psycopg2  # noqa: F401
            self._available = True
        except ImportError:
            pass

        if self._available:
            try:
                self._connect()
                if auto_migrate:
                    self._run_migration()
            except Exception as exc:
                _log.warning(
                    "governance store connection failed (%s)",
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
        """Open a connection or pool depending on ``pool_size``.

        v4.36.0 (audit F12): when ``pool_size > 1``, a
        ``ThreadedConnectionPool`` is created with the requested cap
        and a single connection is held in ``self._conn`` for back-
        compat reads (e.g. ``self._conn is None`` checks throughout
        the store implementations). Each operation acquires its own
        connection via ``self._connection()``.
        """
        import psycopg2
        if self._pool_size > 1:
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=self._pool_size,
                dsn=self._connection_string,
            )
            # Keep a placeholder connection for ``is None`` checks and
            # for the legacy single-conn migration path. It is NOT used
            # for runtime ops once the pool is online.
            self._conn = self._pool.getconn()
            self._conn.autocommit = False
            self._pool.putconn(self._conn)
        else:
            self._conn = psycopg2.connect(self._connection_string)
            self._conn.autocommit = False

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        """Yield a connection — pooled if configured, single otherwise.

        On the pool path the connection is returned to the pool on
        context exit (success or exception). On the single-conn path
        the global ``self._lock`` serializes cursor creation; the
        connection is yielded as-is.
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
                        "governance store pool putconn failed (%s)",
                        _bounded_store_failure(exc),
                    )
        else:
            with self._lock:
                yield self._conn

    def _reconnect(self) -> bool:
        """Attempt to reconnect after a connection failure.

        v4.36.0: on the pool path, closes the existing pool and opens
        a fresh one. On single-conn, closes and reopens ``self._conn``.
        """
        try:
            if self._pool is not None:
                try:
                    self._pool.closeall()
                except Exception as exc:
                    _log.warning(
                        "governance store pool closeall failed during reconnect (%s)",
                        _bounded_store_failure(exc),
                    )
                self._pool = None
            if self._conn is not None and self._pool is None:
                try:
                    self._conn.close()
                except Exception as exc:
                    _log.warning(
                        "governance store connection close failed during reconnect (%s)",
                        _bounded_store_failure(exc),
                    )
            self._connect()
            return True
        except Exception as exc:
            _log.warning(
                "governance store reconnection failed (%s)",
                _bounded_store_failure(exc),
            )
            self._conn = None
            self._pool = None
            return False

    def _run_migration(self) -> None:
        # v4.36.0 (audit F12): migrations run on a connection acquired
        # via the same _connection() helper as runtime ops, so the pool
        # path is exercised end-to-end and the single-conn path keeps
        # holding self._lock. Migrations are idempotent + run once at
        # startup, so this is concurrency-safe regardless.
        if self._conn is None:
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(GOVERNANCE_MIGRATIONS[self._migration_index])
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    _log.warning(
                        "governance migration %d failed (%s)",
                        self._migration_index,
                        _bounded_store_failure(exc),
                    )

    def _safe_execute(self, fn: Any) -> Any:
        """Execute a function with automatic reconnection on failure."""
        try:
            return fn()
        except Exception:
            if self._reconnect():
                try:
                    return fn()
                except Exception as exc:
                    _log.warning(
                        "governance store operation failed after reconnect (%s)",
                        _bounded_store_failure(exc),
                    )
            return None

    def close(self) -> None:
        # v4.36.0 (audit F12): close pool first if present, then the
        # placeholder single connection.
        if self._pool is not None:
            try:
                self._pool.closeall()
            except Exception as exc:
                _log.warning(
                    "governance store pool close failed (%s)",
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
                    "governance store close failed (%s)",
                    _bounded_store_failure(exc),
                )
            finally:
                self._conn = None


# â•â•â• PostgresBudgetStore â•â•â•


class PostgresBudgetStore(_PostgresBase, BudgetStore):
    """PostgreSQL-backed budget store.

    Persists tenant budgets via UPSERT. Thread-safe via cursor-per-operation.
    Falls back to no-op stubs if psycopg2 is unavailable.
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
        pool_size: int = 1,
    ) -> None:
        self._base_init(connection_string, migration_index=0, auto_migrate=auto_migrate, pool_size=pool_size)

    def load(self, tenant_id: str) -> LLMBudget | None:
        if self._conn is None:
            return None
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT budget_id, tenant_id, max_cost, spent, "
                    "max_tokens_per_call, max_calls, calls_made "
                    "FROM governance_budgets WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return LLMBudget(
            budget_id=row[0],
            tenant_id=row[1],
            max_cost=float(row[2]),
            spent=float(row[3]),
            max_tokens_per_call=int(row[4]),
            max_calls=int(row[5]),
            calls_made=int(row[6]),
        )

    def save(self, budget: LLMBudget) -> None:
        if self._conn is None:
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO governance_budgets "
                    "(tenant_id, budget_id, max_cost, spent, max_tokens_per_call, "
                    "max_calls, calls_made, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET "
                    "budget_id = EXCLUDED.budget_id, "
                    "max_cost = EXCLUDED.max_cost, "
                    "spent = EXCLUDED.spent, "
                    "max_tokens_per_call = EXCLUDED.max_tokens_per_call, "
                    "max_calls = EXCLUDED.max_calls, "
                    "calls_made = EXCLUDED.calls_made, "
                    "updated_at = EXCLUDED.updated_at",
                    (
                        budget.tenant_id, budget.budget_id, budget.max_cost,
                        budget.spent, budget.max_tokens_per_call,
                        budget.max_calls, budget.calls_made, _now_iso(),
                    ),
                )
                conn.commit()

    def try_record_spend(
        self,
        tenant_id: str,
        cost: float,
        tokens: int = 0,
    ) -> LLMBudget | None:
        """v4.27.0+ (audit F2 fix): atomic budget enforcement.

        Pre-v4.27 the manager called ``record_spend`` (read in-memory
        snapshot, compute new value, save via UPSERT). The UPSERT
        wrote ``EXCLUDED.spent = <python-computed-value>`` with no
        ``WHERE spent + cost <= max_cost`` clause. Two replicas could
        both read ``spent=$5``, both compute ``$5 + $1 = $6``, both
        UPSERT ``$6``. Real spend ``$7``, stored ``$6``. The hard limit
        was, in practice, soft by N (replicas × in-flight requests).

        v4.27 replaces this with a single ``UPDATE … WHERE spent + $1 <=
        max_cost RETURNING …``. The DB row is the only source of truth;
        in-memory snapshots are out of the write path. Two replicas can
        now race a transaction, but at most ``floor((max_cost -
        current_spent) / cost)`` succeed — every other call sees zero
        rows returned and treats it as exhaustion.
        """
        if self._conn is None:
            return None
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE governance_budgets "
                    "SET spent = spent + %s, "
                    "    calls_made = calls_made + 1, "
                    "    updated_at = %s "
                    "WHERE tenant_id = %s "
                    "  AND spent + %s <= max_cost "
                    "RETURNING budget_id, tenant_id, max_cost, spent, "
                    "          max_tokens_per_call, max_calls, calls_made",
                    (cost, _now_iso(), tenant_id, cost),
                )
                row = cur.fetchone()
                conn.commit()
        if row is None:
            # Either no row exists, or the WHERE clause rejected
            # (spent + cost > max_cost). Both are "exhaustion" from the
            # caller's perspective — the manager pre-flighted the row
            # via ensure_budget so no-row case shouldn't arise in
            # practice.
            return None
        return LLMBudget(
            budget_id=row[0],
            tenant_id=row[1],
            max_cost=float(row[2]),
            spent=float(row[3]),
            max_tokens_per_call=int(row[4]),
            max_calls=int(row[5]),
            calls_made=int(row[6]),
        )

    def load_all(self) -> list[LLMBudget]:
        if self._conn is None:
            return []
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT budget_id, tenant_id, max_cost, spent, "
                    "max_tokens_per_call, max_calls, calls_made "
                    "FROM governance_budgets ORDER BY tenant_id"
                )
                rows = cur.fetchall()
        return [
            LLMBudget(
                budget_id=r[0], tenant_id=r[1], max_cost=float(r[2]),
                spent=float(r[3]), max_tokens_per_call=int(r[4]),
                max_calls=int(r[5]), calls_made=int(r[6]),
            )
            for r in rows
        ]


# â•â•â• PostgresAuditStore â•â•â•


class PostgresAuditStore(_PostgresBase, AuditStore):
    """PostgreSQL-backed audit entry store.

    Append-only: entries are inserted, never updated or deleted.
    Hash chain integrity is preserved exactly as provided by AuditTrail.
    Thread-safe via cursor-per-operation.

    When a field_encryptor is provided, the detail JSONB field is encrypted
    at rest. The entry_hash and previous_hash remain unencrypted for chain
    verification without decryption.
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
        field_encryptor: Any | None = None,
        pool_size: int = 1,
    ) -> None:
        self._field_encryptor = field_encryptor
        self._base_init(connection_string, migration_index=1, auto_migrate=auto_migrate, pool_size=pool_size)

    def _encrypt_detail(self, detail: dict[str, Any]) -> str:
        """Encrypt detail dict if encryptor is available, else return JSON."""
        detail_json = json.dumps(detail, sort_keys=True, default=str)
        if self._field_encryptor is not None:
            try:
                return self._field_encryptor.encrypt(detail_json)
            except Exception as exc:
                raise _bounded_detail_crypto_error("encryption", exc) from exc
        return detail_json

    def _decrypt_detail(self, stored: str) -> dict[str, Any]:
        """Decrypt detail string if encrypted, else parse as JSON."""
        if self._field_encryptor is not None:
            try:
                if self._field_encryptor.is_encrypted(stored):
                    decrypted = self._field_encryptor.decrypt(stored)
                    return json.loads(decrypted)
            except Exception as exc:
                raise _bounded_detail_crypto_error("decryption", exc) from exc
        if isinstance(stored, str):
            try:
                return json.loads(stored)
            except Exception as exc:
                raise _bounded_detail_crypto_error("parse", exc) from exc
        return stored  # Already parsed (psycopg2 JSONB)

    def append(self, entry: AuditEntry) -> None:
        if self._conn is None:
            return
        detail_stored = self._encrypt_detail(entry.detail)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO governance_audit_entries "
                    "(entry_id, sequence, action, actor_id, tenant_id, target, "
                    "outcome, detail, entry_hash, previous_hash, recorded_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (entry_id) DO NOTHING",
                    (
                        entry.entry_id, entry.sequence, entry.action,
                        entry.actor_id, entry.tenant_id, entry.target,
                        entry.outcome, detail_stored,
                        entry.entry_hash, entry.previous_hash, entry.recorded_at,
                    ),
                )
                conn.commit()

    def query(self, **kwargs: Any) -> list[AuditEntry]:
        if self._conn is None:
            return []

        conditions: list[str] = []
        params: list[Any] = []
        for key in ("tenant_id", "action", "outcome", "actor_id"):
            if key in kwargs and kwargs[key] is not None:
                conditions.append(f"{key} = %s")
                params.append(kwargs[key])

        limit = kwargs.get("limit", 50)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT entry_id, sequence, action, actor_id, tenant_id, target, "
            f"outcome, detail, entry_hash, previous_hash, recorded_at "
            f"FROM governance_audit_entries{where} "
            f"ORDER BY sequence DESC LIMIT %s"
        )
        params.append(limit)

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()

        # Return in ascending sequence order (matches AuditTrail.query behavior)
        entries = [
            AuditEntry(
                entry_id=r[0], sequence=r[1], action=r[2], actor_id=r[3],
                tenant_id=r[4], target=r[5], outcome=r[6],
                detail=self._decrypt_detail(r[7]),
                entry_hash=r[8], previous_hash=r[9], recorded_at=r[10],
            )
            for r in rows
        ]
        entries.sort(key=lambda e: e.sequence)
        return entries

    def count(self) -> int:
        if self._conn is None:
            return 0
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM governance_audit_entries")
                return cur.fetchone()[0]


# â•â•â• PostgresRateLimitStore â•â•â•


class PostgresRateLimitStore(_PostgresBase, RateLimitStore):
    """PostgreSQL-backed rate limit decision store.

    Records allowed/denied decision counts per bucket key (tenant:endpoint).
    Uses UPSERT with atomic increment for thread safety.
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
        pool_size: int = 1,
    ) -> None:
        self._base_init(connection_string, migration_index=2, auto_migrate=auto_migrate, pool_size=pool_size)

    def record_decision(self, bucket_key: str, allowed: bool) -> None:
        if self._conn is None:
            return
        col = "allowed_count" if allowed else "denied_count"
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO governance_rate_decisions "
                    f"(bucket_key, allowed_count, denied_count, last_updated) "
                    f"VALUES (%s, %s, %s, %s) "
                    f"ON CONFLICT (bucket_key) DO UPDATE SET "
                    f"{col} = governance_rate_decisions.{col} + 1, "
                    f"last_updated = EXCLUDED.last_updated",
                    (
                        bucket_key,
                        1 if allowed else 0,
                        0 if allowed else 1,
                        _now_iso(),
                    ),
                )
                conn.commit()

    def get_counters(self) -> dict[str, int]:
        if self._conn is None:
            return {"allowed": 0, "denied": 0}
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(allowed_count), 0), "
                    "COALESCE(SUM(denied_count), 0) "
                    "FROM governance_rate_decisions"
                )
                row = cur.fetchone()
        return {"allowed": int(row[0]), "denied": int(row[1])}


# â•â•â• PostgresTenantGatingStore â•â•â•


class PostgresTenantGatingStore(_PostgresBase, TenantGatingStore):
    """PostgreSQL-backed tenant gating store.

    Persists tenant lifecycle states via UPSERT. Thread-safe.
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
        pool_size: int = 1,
    ) -> None:
        self._base_init(connection_string, migration_index=3, auto_migrate=auto_migrate, pool_size=pool_size)

    def load(self, tenant_id: str) -> TenantGate | None:
        if self._conn is None:
            return None
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, status, reason, gated_at "
                    "FROM governance_tenant_gates WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return TenantGate(
            tenant_id=row[0],
            status=TenantStatus(row[1]),
            reason=row[2],
            gated_at=row[3],
        )

    def save(self, gate: TenantGate) -> None:
        if self._conn is None:
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO governance_tenant_gates "
                    "(tenant_id, status, reason, gated_at) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET "
                    "status = EXCLUDED.status, "
                    "reason = EXCLUDED.reason, "
                    "gated_at = EXCLUDED.gated_at",
                    (gate.tenant_id, gate.status.value, gate.reason, gate.gated_at),
                )
                conn.commit()

    def load_all(self) -> list[TenantGate]:
        if self._conn is None:
            return []
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, status, reason, gated_at "
                    "FROM governance_tenant_gates ORDER BY tenant_id"
                )
                rows = cur.fetchall()
        return [
            TenantGate(
                tenant_id=r[0], status=TenantStatus(r[1]),
                reason=r[2], gated_at=r[3],
            )
            for r in rows
        ]


# â•â•â• In-Memory Governance Stores (for testing without PostgreSQL) â•â•â•


class InMemoryBudgetStore(BudgetStore):
    """In-memory budget store for testing.

    v4.27.0+: ``try_record_spend`` provides atomic test-and-update under
    a store-wide ``threading.Lock``. Concurrent callers from multiple
    threads cannot race past ``max_cost``. (The lock is single-process;
    cross-process replicas would need PostgresBudgetStore.)
    """

    def __init__(self) -> None:
        from threading import Lock
        self._budgets: dict[str, LLMBudget] = {}
        self._lock = Lock()

    def load(self, tenant_id: str) -> LLMBudget | None:
        return self._budgets.get(tenant_id)

    def save(self, budget: LLMBudget) -> None:
        self._budgets[budget.tenant_id] = budget

    def load_all(self) -> list[LLMBudget]:
        return sorted(self._budgets.values(), key=lambda b: b.tenant_id)

    def try_record_spend(
        self,
        tenant_id: str,
        cost: float,
        tokens: int = 0,
    ) -> LLMBudget | None:
        """Atomic test-and-update under store-wide lock.

        Returns the updated budget on success; None if the spend
        would exceed max_cost or no budget row exists.
        """
        with self._lock:
            current = self._budgets.get(tenant_id)
            if current is None:
                return None
            new_spent = current.spent + cost
            if new_spent > current.max_cost:
                return None
            updated = LLMBudget(
                budget_id=current.budget_id,
                tenant_id=current.tenant_id,
                max_cost=current.max_cost,
                spent=new_spent,
                max_tokens_per_call=current.max_tokens_per_call,
                max_calls=current.max_calls,
                calls_made=current.calls_made + 1,
            )
            self._budgets[tenant_id] = updated
            return updated


class InMemoryAuditStore(AuditStore):
    """In-memory audit store for testing.

    v4.28.0+ (audit F3): also persists checkpoints. Single most recent
    checkpoint is kept (matches the ``AuditTrail._anchor`` semantics —
    each new prune supersedes the previous anchor).

    v4.31.0+ (audit F4): owns sequence allocation and chain-head
    linkage via ``try_append``. ``threading.Lock``-guarded
    test-and-allocate makes a single store instance safe under
    concurrent writes from multiple AuditTrail/worker callers within
    one process. Cross-process replicas need PostgresAuditStore.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._checkpoint: AuditCheckpoint | None = None
        self._sequence: int = 0
        self._last_hash: str = sha256(b"genesis").hexdigest()
        self._append_lock = threading.Lock()

    def append(self, entry: AuditEntry) -> None:
        # Pre-v4.31 callers compute their own sequence/hash. Keep the
        # lock around the list mutation so concurrent legacy and
        # try_append paths share consistent storage.
        with self._append_lock:
            self._entries.append(entry)
            # Track chain state if the appended entry is monotonic —
            # otherwise the legacy caller is responsible for its own
            # sequencing.
            if entry.sequence > self._sequence:
                self._sequence = entry.sequence
                self._last_hash = entry.entry_hash

    def query(self, **kwargs: Any) -> list[AuditEntry]:
        results = self._entries
        for key in ("tenant_id", "action", "outcome", "actor_id"):
            if key in kwargs and kwargs[key] is not None:
                results = [e for e in results if getattr(e, key) == kwargs[key]]
        limit = kwargs.get("limit", 50)
        return results[-limit:]

    def count(self) -> int:
        return len(self._entries)

    def store_checkpoint(self, checkpoint: AuditCheckpoint) -> None:
        self._checkpoint = checkpoint

    def try_append(
        self,
        *,
        action: str,
        actor_id: str,
        tenant_id: str,
        target: str,
        outcome: str,
        detail: dict[str, Any],
        recorded_at: str,
    ) -> AuditEntry | None:
        # F4: store-owned sequence + chain head, lock-guarded so
        # concurrent AuditTrail callers (multiple workers, threads)
        # cannot fork the chain. The lock spans allocate-sequence,
        # read-prev-hash, compute-entry-hash, persist — so two
        # callers strictly serialize at the store, never both
        # producing the same sequence with different previous_hash.
        # Cross-process atomicity needs PostgresAuditStore.
        with self._append_lock:
            sequence = self._sequence + 1
            previous_hash = self._last_hash
            source = {
                "sequence": sequence,
                "action": action,
                "actor_id": actor_id,
                "tenant_id": tenant_id,
                "target": target,
                "outcome": outcome,
                "detail": detail,
                "previous_hash": previous_hash,
                "recorded_at": recorded_at,
            }
            entry_hash = _canonical_hash_v1(source)
            entry = AuditEntry(
                entry_id=f"audit-{sequence}",
                sequence=sequence,
                action=action,
                actor_id=actor_id,
                tenant_id=tenant_id,
                target=target,
                outcome=outcome,
                detail=detail,
                entry_hash=entry_hash,
                previous_hash=previous_hash,
                recorded_at=recorded_at,
            )
            self._entries.append(entry)
            self._sequence = sequence
            self._last_hash = entry_hash
            return entry

    def latest_checkpoint(self) -> AuditCheckpoint | None:
        return self._checkpoint


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit store for testing.

    v4.29 (audit F11): also owns token-bucket state, exposing an
    atomic test-and-consume via ``try_consume`` guarded by a
    ``threading.Lock``. Single-process atomic. Cross-process replicas
    need the Postgres/Redis backend.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, dict[str, int]] = {}
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._bucket_lock = threading.Lock()

    def record_decision(self, bucket_key: str, allowed: bool) -> None:
        if bucket_key not in self._decisions:
            self._decisions[bucket_key] = {"allowed": 0, "denied": 0}
        if allowed:
            self._decisions[bucket_key]["allowed"] += 1
        else:
            self._decisions[bucket_key]["denied"] += 1

    def get_counters(self) -> dict[str, int]:
        total_allowed = sum(d["allowed"] for d in self._decisions.values())
        total_denied = sum(d["denied"] for d in self._decisions.values())
        return {"allowed": total_allowed, "denied": total_denied}

    def try_consume(
        self,
        bucket_key: str,
        tokens: int,
        config: "RateLimitConfig",
    ) -> tuple[bool, float] | None:
        # F11: store-owned bucket state with single-process atomicity.
        # The lock spans refill + check + decrement so concurrent
        # callers strictly serialize at the bucket — no last-write-wins
        # window. Cross-process atomicity needs PostgresRateLimitStore.
        if tokens > config.burst_limit:
            with self._bucket_lock:
                current, _ = self._buckets.get(
                    bucket_key, (float(config.max_tokens), time.monotonic())
                )
                return False, current
        with self._bucket_lock:
            now = time.monotonic()
            current, last_refill = self._buckets.get(
                bucket_key, (float(config.max_tokens), now)
            )
            elapsed = now - last_refill
            current = min(
                float(config.max_tokens),
                current + elapsed * config.refill_rate,
            )
            if current >= tokens:
                current -= tokens
                self._buckets[bucket_key] = (current, now)
                return True, current
            self._buckets[bucket_key] = (current, now)
            return False, current


class InMemoryTenantGatingStore(TenantGatingStore):
    """In-memory tenant gating store for testing."""

    def __init__(self) -> None:
        self._gates: dict[str, TenantGate] = {}

    def load(self, tenant_id: str) -> TenantGate | None:
        return self._gates.get(tenant_id)

    def save(self, gate: TenantGate) -> None:
        self._gates[gate.tenant_id] = gate

    def load_all(self) -> list[TenantGate]:
        return sorted(self._gates.values(), key=lambda g: g.tenant_id)


# â•â•â• Factory â•â•â•


class GovernanceStoreBundle:
    """Bundle of all governance stores with shared lifecycle management.

    Provides a single close() method that cleanly shuts down all stores.
    """

    def __init__(self, stores: dict[str, Any]) -> None:
        self._stores = stores

    def __getitem__(self, key: str) -> Any:
        return self._stores[key]

    def __contains__(self, key: str) -> bool:
        return key in self._stores

    def keys(self) -> Any:
        return self._stores.keys()

    def items(self) -> Any:
        return self._stores.items()

    def close(self) -> None:
        """Close all store connections."""
        for _key, store in self._stores.items():
            if hasattr(store, "close"):
                try:
                    store.close()
                except Exception as exc:
                    _log.warning(
                        "governance store bundle close failed (%s)",
                        _bounded_store_failure(exc),
                    )


def create_governance_stores(
    backend: str = "memory",
    connection_string: str = "",
    *,
    field_encryptor: Any | None = None,
    pool_size: int = 1,
) -> GovernanceStoreBundle:
    """Factory for creating governance stores.

    Returns GovernanceStoreBundle with keys: "budget", "audit", "rate_limit", "tenant_gating".

    Backends:
    - "memory" â†’ In-memory stores (testing/development)
    - "postgresql" â†’ PostgreSQL stores (production)

    v4.36.0 (audit F12): ``pool_size > 1`` enables a
    ``ThreadedConnectionPool`` per store for write-throughput scaling.
    Each of the 4 stores gets its own pool with the configured cap;
    operators sizing should account for ``4 × pool_size`` total
    connections to PostgreSQL. Default 1 preserves legacy single-conn
    behavior (one shared connection per store, serialized via
    ``self._lock``).

    When field_encryptor is provided, audit entry detail fields are encrypted at rest.
    """
    if backend == "memory":
        return GovernanceStoreBundle({
            "budget": InMemoryBudgetStore(),
            "audit": InMemoryAuditStore(),
            "rate_limit": InMemoryRateLimitStore(),
            "tenant_gating": InMemoryTenantGatingStore(),
        })
    if backend == "postgresql":
        conn = connection_string or "postgresql://localhost:5432/mullu"
        return GovernanceStoreBundle({
            "budget": PostgresBudgetStore(conn, pool_size=pool_size),
            "audit": PostgresAuditStore(
                conn, field_encryptor=field_encryptor, pool_size=pool_size,
            ),
            "rate_limit": PostgresRateLimitStore(conn, pool_size=pool_size),
            "tenant_gating": PostgresTenantGatingStore(conn, pool_size=pool_size),
        })
    raise ValueError("unsupported governance store backend")


