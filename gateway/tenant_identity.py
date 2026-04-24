"""Gateway Tenant Identity Store - durable channel identity binding.

Purpose: Resolves external channel subjects to governed tenant identities
    before command creation, policy evaluation, approval, or dispatch.
Governance scope: gateway identity boundary only.
Dependencies: standard-library dataclasses, JSON serialization, optional psycopg2.
Invariants:
  - Channel identity is never inferred from message content.
  - Revoked identities do not resolve.
  - Production deployments can persist bindings in PostgreSQL.
  - Local tests retain deterministic in-memory behavior.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TenantMapping:
    """Maps a channel subject to a governed tenant identity."""

    channel: str
    sender_id: str
    tenant_id: str
    identity_id: str
    roles: tuple[str, ...] = ()
    approval_authority: bool = False
    created_at: str = ""
    revoked_at: str = ""
    policy_version: str = "tenant-identity-v1"
    metadata: dict[str, Any] = field(default_factory=dict)


class TenantIdentityConfigurationError(ValueError):
    """Raised when gateway identity persistence violates deployment policy."""


class TenantIdentityStore:
    """Persistence contract for gateway tenant identity mappings."""

    def save(self, mapping: TenantMapping) -> None:
        """Persist one channel subject binding."""
        raise NotImplementedError

    def resolve(self, channel: str, sender_id: str) -> TenantMapping | None:
        """Resolve a non-revoked channel subject binding."""
        raise NotImplementedError

    def count(self) -> int:
        """Return number of active known bindings."""
        return 0

    def status(self) -> dict[str, Any]:
        """Return store status for gateway health."""
        return {"backend": "unknown", "persistent": False, "available": False}


class InMemoryTenantIdentityStore(TenantIdentityStore):
    """In-memory tenant identity store for local development and tests."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._mappings: dict[str, TenantMapping] = {}

    @staticmethod
    def _key(channel: str, sender_id: str) -> str:
        return f"{channel}:{sender_id}"

    def save(self, mapping: TenantMapping) -> None:
        created_at = mapping.created_at or self._clock()
        stored = TenantMapping(
            channel=mapping.channel,
            sender_id=mapping.sender_id,
            tenant_id=mapping.tenant_id,
            identity_id=mapping.identity_id,
            roles=tuple(mapping.roles),
            approval_authority=mapping.approval_authority,
            created_at=created_at,
            revoked_at=mapping.revoked_at,
            policy_version=mapping.policy_version,
            metadata=dict(mapping.metadata),
        )
        self._mappings[self._key(stored.channel, stored.sender_id)] = stored

    def resolve(self, channel: str, sender_id: str) -> TenantMapping | None:
        mapping = self._mappings.get(self._key(channel, sender_id))
        if mapping is None or mapping.revoked_at:
            return None
        return mapping

    def count(self) -> int:
        return sum(1 for mapping in self._mappings.values() if not mapping.revoked_at)

    def status(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "persistent": False,
            "active_mappings": self.count(),
            "available": True,
        }


class PostgresTenantIdentityStore(TenantIdentityStore):
    """PostgreSQL tenant identity store for gateway deployments."""

    _MIGRATION = """
    CREATE TABLE IF NOT EXISTS gateway_tenant_identities (
        channel TEXT NOT NULL,
        external_subject_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        identity_id TEXT NOT NULL,
        roles JSONB NOT NULL DEFAULT '[]',
        approval_authority BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL,
        revoked_at TEXT NOT NULL DEFAULT '',
        policy_version TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}',
        PRIMARY KEY (channel, external_subject_id)
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_identity_tenant
        ON gateway_tenant_identities(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_identity_identity
        ON gateway_tenant_identities(identity_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_identity_revoked
        ON gateway_tenant_identities(revoked_at);
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        clock: Callable[[], str] | None = None,
        auto_migrate: bool = True,
    ) -> None:
        self._connection_string = connection_string
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._conn: Any | None = None
        self._lock = threading.Lock()
        self._available = False
        self._operation_failures = 0
        self._rollback_failures = 0
        self._close_failures = 0
        try:
            import psycopg2  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False

        if self._available:
            try:
                self._connect()
                if auto_migrate:
                    self._run_migration()
            except Exception as exc:
                _log.warning("tenant identity postgres bootstrap failed (%s)", type(exc).__name__)
                self._conn = None

    def _connect(self) -> None:
        import psycopg2
        self._conn = psycopg2.connect(self._connection_string)
        self._conn.autocommit = False

    def _run_migration(self) -> None:
        if self._conn is None:
            return
        with self._conn.cursor() as cur:
            cur.execute(self._MIGRATION)
            self._conn.commit()

    def _safe_execute(self, operation: Callable[[], Any]) -> Any:
        if self._conn is None:
            return None
        try:
            return operation()
        except Exception as exc:
            self._operation_failures += 1
            try:
                self._conn.rollback()
            except Exception as rollback_exc:
                self._rollback_failures += 1
                _log.warning(
                    "tenant identity postgres rollback failed (%s)",
                    type(rollback_exc).__name__,
                )
            _log.warning("tenant identity postgres operation failed (%s)", type(exc).__name__)
            return None

    def save(self, mapping: TenantMapping) -> None:
        created_at = mapping.created_at or self._clock()

        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_tenant_identities "
                        "(channel, external_subject_id, tenant_id, identity_id, roles, "
                        "approval_authority, created_at, revoked_at, policy_version, metadata) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (channel, external_subject_id) DO UPDATE SET "
                        "tenant_id = EXCLUDED.tenant_id, "
                        "identity_id = EXCLUDED.identity_id, "
                        "roles = EXCLUDED.roles, "
                        "approval_authority = EXCLUDED.approval_authority, "
                        "revoked_at = EXCLUDED.revoked_at, "
                        "policy_version = EXCLUDED.policy_version, "
                        "metadata = EXCLUDED.metadata",
                        (
                            mapping.channel,
                            mapping.sender_id,
                            mapping.tenant_id,
                            mapping.identity_id,
                            json.dumps(tuple(mapping.roles), sort_keys=True, default=str),
                            mapping.approval_authority,
                            created_at,
                            mapping.revoked_at,
                            mapping.policy_version,
                            json.dumps(mapping.metadata, sort_keys=True, default=str),
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def resolve(self, channel: str, sender_id: str) -> TenantMapping | None:
        def _read() -> TenantMapping | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT channel, external_subject_id, tenant_id, identity_id, "
                        "roles, approval_authority, created_at, revoked_at, policy_version, metadata "
                        "FROM gateway_tenant_identities "
                        "WHERE channel = %s AND external_subject_id = %s AND revoked_at = ''",
                        (channel, sender_id),
                    )
                    row = cur.fetchone()
            if row is None:
                return None
            roles = row[4]
            metadata = row[9]
            if isinstance(roles, str):
                roles = json.loads(roles)
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            return TenantMapping(
                channel=row[0],
                sender_id=row[1],
                tenant_id=row[2],
                identity_id=row[3],
                roles=tuple(str(role) for role in roles),
                approval_authority=bool(row[5]),
                created_at=row[6],
                revoked_at=row[7],
                policy_version=row[8],
                metadata=dict(metadata),
            )

        result = self._safe_execute(_read)
        return result if isinstance(result, TenantMapping) else None

    def count(self) -> int:
        def _count() -> int:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM gateway_tenant_identities WHERE revoked_at = ''")
                    row = cur.fetchone()
            return int(row[0])

        result = self._safe_execute(_count)
        return result if isinstance(result, int) else 0

    def status(self) -> dict[str, Any]:
        return {
            "backend": "postgresql",
            "persistent": True,
            "available": self._conn is not None,
            "driver_available": self._available,
            "active_mappings": self.count(),
            "operation_failures": self._operation_failures,
            "rollback_failures": self._rollback_failures,
            "close_failures": self._close_failures,
        }

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as exc:
                self._close_failures += 1
                _log.warning("tenant identity postgres close failed (%s)", type(exc).__name__)
            self._conn = None


def build_tenant_identity_store_from_env(
    *,
    clock: Callable[[], str] | None = None,
) -> TenantIdentityStore:
    """Create a tenant identity store using gateway persistence environment."""
    import os

    gateway_env = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    require_persistent = _truthy_env(
        os.environ.get("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "")
    )
    if not os.environ.get("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY"):
        require_persistent = gateway_env in {"pilot", "pilot_prod", "prod", "production"}

    backend = os.environ.get("MULLU_TENANT_IDENTITY_BACKEND", "")
    if not backend:
        backend = os.environ.get("MULLU_DB_BACKEND", "memory")
    backend = backend.strip().lower()
    if require_persistent and backend != "postgresql":
        raise TenantIdentityConfigurationError("persistent tenant identity store required")
    if backend == "postgresql":
        connection_string = os.environ.get("MULLU_TENANT_IDENTITY_DB_URL", "")
        if not connection_string:
            connection_string = os.environ.get("MULLU_DB_URL", "")
        store = PostgresTenantIdentityStore(
            connection_string or "postgresql://localhost:5432/mullu",
            clock=clock,
        )
        status = store.status()
        if require_persistent and not status.get("available"):
            close = getattr(store, "close", None)
            if callable(close):
                close()
            raise TenantIdentityConfigurationError("persistent tenant identity store unavailable")
        return store
    if backend == "memory":
        return InMemoryTenantIdentityStore(clock=clock)
    raise ValueError("unsupported tenant identity backend")


def _truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
