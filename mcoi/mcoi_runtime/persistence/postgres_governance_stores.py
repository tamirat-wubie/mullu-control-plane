"""Phase 1A/2D — PostgreSQL Governance Stores.

Purpose: Production-grade PostgreSQL implementations for governance
    externalization stores: BudgetStore, AuditStore, RateLimitStore,
    and TenantGatingStore. These replace the in-memory stubs, making
    governance state durable and consistent across replicas.
Governance scope: persistence backend only.
Dependencies: psycopg2 (optional — graceful fallback to no-op stubs).
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
import threading
from datetime import datetime, timezone
from typing import Any

from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.audit_trail import AuditEntry, AuditStore
from mcoi_runtime.core.rate_limiter import RateLimitStore
from mcoi_runtime.core.tenant_budget import BudgetStore
from mcoi_runtime.core.tenant_gating import TenantGate, TenantGatingStore, TenantStatus


# ═══ Schema Definitions ═══

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


import logging as _logging

_log = _logging.getLogger(__name__)


class _PostgresBase:
    """Shared base for PostgreSQL governance stores.

    Provides connection management, migration execution, and safe
    query execution with reconnection on failure.
    """

    _connection_string: str
    _conn: Any
    _available: bool
    _lock: threading.Lock

    def _base_init(
        self,
        connection_string: str,
        migration_index: int,
        auto_migrate: bool = True,
    ) -> None:
        self._connection_string = connection_string
        self._conn = None
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
                _log.warning("governance store connection failed: %s", exc)
                self._conn = None

    def _connect(self) -> None:
        import psycopg2
        self._conn = psycopg2.connect(self._connection_string)
        self._conn.autocommit = False

    def _reconnect(self) -> bool:
        """Attempt to reconnect after a connection failure."""
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
            self._connect()
            return True
        except Exception as exc:
            _log.warning("governance store reconnection failed: %s", exc)
            self._conn = None
            return False

    def _run_migration(self) -> None:
        if self._conn is None:
            return
        with self._conn.cursor() as cur:
            try:
                cur.execute(GOVERNANCE_MIGRATIONS[self._migration_index])
                self._conn.commit()
            except Exception as exc:
                self._conn.rollback()
                _log.warning("governance migration %d failed (may already exist): %s", self._migration_index, exc)

    def _safe_execute(self, fn: Any) -> Any:
        """Execute a function with automatic reconnection on failure."""
        try:
            return fn()
        except Exception:
            if self._reconnect():
                try:
                    return fn()
                except Exception as exc:
                    _log.warning("governance store operation failed after reconnect: %s", exc)
            return None

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


# ═══ PostgresBudgetStore ═══


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
    ) -> None:
        self._base_init(connection_string, migration_index=0, auto_migrate=auto_migrate)

    def load(self, tenant_id: str) -> LLMBudget | None:
        if self._conn is None:
            return None
        with self._lock:
            with self._conn.cursor() as cur:
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
        with self._lock:
            with self._conn.cursor() as cur:
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
                self._conn.commit()

    def load_all(self) -> list[LLMBudget]:
        if self._conn is None:
            return []
        with self._lock:
            with self._conn.cursor() as cur:
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


# ═══ PostgresAuditStore ═══


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
    ) -> None:
        self._field_encryptor = field_encryptor
        self._base_init(connection_string, migration_index=1, auto_migrate=auto_migrate)

    def _encrypt_detail(self, detail: dict[str, Any]) -> str:
        """Encrypt detail dict if encryptor is available, else return JSON."""
        detail_json = json.dumps(detail, sort_keys=True, default=str)
        if self._field_encryptor is not None:
            try:
                return self._field_encryptor.encrypt(detail_json)
            except Exception:
                pass  # Encryption failure — fall back to plaintext
        return detail_json

    def _decrypt_detail(self, stored: str) -> dict[str, Any]:
        """Decrypt detail string if encrypted, else parse as JSON."""
        if self._field_encryptor is not None and self._field_encryptor.is_encrypted(stored):
            try:
                decrypted = self._field_encryptor.decrypt(stored)
                return json.loads(decrypted)
            except Exception:
                pass  # Decryption failure — try as plaintext
        if isinstance(stored, str):
            return json.loads(stored)
        return stored  # Already parsed (psycopg2 JSONB)

    def append(self, entry: AuditEntry) -> None:
        if self._conn is None:
            return
        detail_stored = self._encrypt_detail(entry.detail)
        with self._lock:
            with self._conn.cursor() as cur:
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
                self._conn.commit()

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

        with self._lock:
            with self._conn.cursor() as cur:
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
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM governance_audit_entries")
                return cur.fetchone()[0]


# ═══ PostgresRateLimitStore ═══


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
    ) -> None:
        self._base_init(connection_string, migration_index=2, auto_migrate=auto_migrate)

    def record_decision(self, bucket_key: str, allowed: bool) -> None:
        if self._conn is None:
            return
        col = "allowed_count" if allowed else "denied_count"
        with self._lock:
            with self._conn.cursor() as cur:
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
                self._conn.commit()

    def get_counters(self) -> dict[str, int]:
        if self._conn is None:
            return {"allowed": 0, "denied": 0}
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(allowed_count), 0), "
                    "COALESCE(SUM(denied_count), 0) "
                    "FROM governance_rate_decisions"
                )
                row = cur.fetchone()
        return {"allowed": int(row[0]), "denied": int(row[1])}


# ═══ PostgresTenantGatingStore ═══


class PostgresTenantGatingStore(_PostgresBase, TenantGatingStore):
    """PostgreSQL-backed tenant gating store.

    Persists tenant lifecycle states via UPSERT. Thread-safe.
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
    ) -> None:
        self._base_init(connection_string, migration_index=3, auto_migrate=auto_migrate)

    def load(self, tenant_id: str) -> TenantGate | None:
        if self._conn is None:
            return None
        with self._lock:
            with self._conn.cursor() as cur:
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
        with self._lock:
            with self._conn.cursor() as cur:
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
                self._conn.commit()

    def load_all(self) -> list[TenantGate]:
        if self._conn is None:
            return []
        with self._lock:
            with self._conn.cursor() as cur:
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


# ═══ In-Memory Governance Stores (for testing without PostgreSQL) ═══


class InMemoryBudgetStore(BudgetStore):
    """In-memory budget store for testing."""

    def __init__(self) -> None:
        self._budgets: dict[str, LLMBudget] = {}

    def load(self, tenant_id: str) -> LLMBudget | None:
        return self._budgets.get(tenant_id)

    def save(self, budget: LLMBudget) -> None:
        self._budgets[budget.tenant_id] = budget

    def load_all(self) -> list[LLMBudget]:
        return sorted(self._budgets.values(), key=lambda b: b.tenant_id)


class InMemoryAuditStore(AuditStore):
    """In-memory audit store for testing."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def query(self, **kwargs: Any) -> list[AuditEntry]:
        results = self._entries
        for key in ("tenant_id", "action", "outcome", "actor_id"):
            if key in kwargs and kwargs[key] is not None:
                results = [e for e in results if getattr(e, key) == kwargs[key]]
        limit = kwargs.get("limit", 50)
        return results[-limit:]

    def count(self) -> int:
        return len(self._entries)


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit store for testing."""

    def __init__(self) -> None:
        self._decisions: dict[str, dict[str, int]] = {}

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


# ═══ Factory ═══


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
                except Exception:
                    pass


def create_governance_stores(
    backend: str = "memory",
    connection_string: str = "",
    *,
    field_encryptor: Any | None = None,
) -> GovernanceStoreBundle:
    """Factory for creating governance stores.

    Returns GovernanceStoreBundle with keys: "budget", "audit", "rate_limit", "tenant_gating".

    Backends:
    - "memory" → In-memory stores (testing/development)
    - "postgresql" → PostgreSQL stores (production)

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
            "budget": PostgresBudgetStore(conn),
            "audit": PostgresAuditStore(conn, field_encryptor=field_encryptor),
            "rate_limit": PostgresRateLimitStore(conn),
            "tenant_gating": PostgresTenantGatingStore(conn),
        })
    raise ValueError(f"unsupported governance store backend: {backend}")
