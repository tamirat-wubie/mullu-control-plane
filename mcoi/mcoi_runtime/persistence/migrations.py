"""Schema migration engine for SQLite and PostgreSQL.

Purpose: Apply versioned schema migrations at startup. Each migration is
    a numbered SQL file or inline definition. The engine tracks applied
    migrations in a `schema_version` table and applies pending ones in order.

Invariants:
  - Migrations are idempotent (CREATE IF NOT EXISTS, etc.)
  - Migration history is append-only
  - Startup fails fast if a migration fails (no partial state)
  - Version table created automatically on first run
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


def _bounded_migration_error(operation: str, exc: Exception) -> RuntimeError:
    """Return a bounded migration failure without leaking backend detail."""
    return RuntimeError(f"{operation} failed ({type(exc).__name__})")


@dataclass(frozen=True, slots=True)
class Migration:
    """A single schema migration."""
    version: int
    name: str
    sql: str  # SQLite-compatible SQL (default)
    sql_pg: str = ""  # PostgreSQL-specific SQL (used when dialect="postgresql")
    description: str = ""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Result of applying a migration."""
    version: int
    name: str
    success: bool
    error: str = ""


class DBConnection(Protocol):
    """Minimal DB connection interface for migrations."""
    def execute(self, sql: str, params: tuple = ()) -> Any: ...
    def executescript(self, sql: str) -> None: ...
    def commit(self) -> None: ...


class MigrationEngine:
    """Applies schema migrations in order, tracking progress."""

    VERSION_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
    """

    def __init__(self, *, clock: Callable[[], str], dialect: str = "sqlite") -> None:
        self._clock = clock
        self._dialect = dialect  # "sqlite" or "postgresql"
        self._migrations: list[Migration] = []

    def register(self, migration: Migration) -> None:
        """Register a migration. Must be called in version order."""
        if self._migrations and migration.version <= self._migrations[-1].version:
            raise ValueError(
                f"Migration version {migration.version} must be > {self._migrations[-1].version}"
            )
        self._migrations.append(migration)

    @property
    def migration_count(self) -> int:
        return len(self._migrations)

    def current_version(self, conn: DBConnection) -> int:
        """Get the current schema version from the database."""
        try:
            conn.execute(self.VERSION_TABLE_SQL)
            conn.commit()
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] if row and row[0] is not None else 0
        except Exception as exc:
            raise _bounded_migration_error("migration state lookup", exc) from exc

    def pending(self, conn: DBConnection) -> list[Migration]:
        """List migrations that haven't been applied yet."""
        current = self.current_version(conn)
        return [m for m in self._migrations if m.version > current]

    def apply_all(self, conn: DBConnection) -> list[MigrationResult]:
        """Apply all pending migrations. Fails fast on first error."""
        import hashlib

        # Ensure version table exists
        conn.execute(self.VERSION_TABLE_SQL)
        conn.commit()

        results: list[MigrationResult] = []
        for migration in self.pending(conn):
            try:
                sql = (migration.sql_pg if self._dialect == "postgresql" and migration.sql_pg else migration.sql)
                conn.executescript(sql)
                checksum = hashlib.sha256(migration.sql.encode()).hexdigest()[:16]
                placeholder = "%s" if self._dialect == "postgresql" else "?"
                conn.execute(
                    f"INSERT INTO schema_version (version, name, applied_at, checksum) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (migration.version, migration.name, self._clock(), checksum),
                )
                conn.commit()
                results.append(MigrationResult(
                    version=migration.version, name=migration.name, success=True,
                ))
            except Exception as e:
                bounded_error = f"migration execution failed ({type(e).__name__})"
                results.append(MigrationResult(
                    version=migration.version, name=migration.name,
                    success=False, error=bounded_error,
                ))
                raise RuntimeError(
                    f"Migration {migration.version} ({migration.name}) failed ({type(e).__name__})"
                ) from e

        return results

    def history(self, conn: DBConnection) -> list[dict[str, Any]]:
        """Get migration history from the database."""
        try:
            conn.execute(self.VERSION_TABLE_SQL)
            conn.commit()
            rows = conn.execute(
                "SELECT version, name, applied_at, checksum FROM schema_version ORDER BY version"
            ).fetchall()
            return [
                {"version": r[0], "name": r[1], "applied_at": r[2], "checksum": r[3]}
                for r in rows
            ]
        except Exception as exc:
            raise _bounded_migration_error("migration history lookup", exc) from exc

    def summary(self) -> dict[str, Any]:
        return {
            "registered_migrations": self.migration_count,
            "migrations": [
                {"version": m.version, "name": m.name}
                for m in self._migrations
            ],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Built-in migrations for the Mullu Platform schema
# ═══════════════════════════════════════════════════════════════════════════

PLATFORM_MIGRATIONS = [
    Migration(
        version=1,
        name="initial_schema",
        description="Create core tables: ledger, sessions, requests",
        sql="""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY,
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
        sql_pg="""
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
    ),
    Migration(
        version=2,
        name="add_ledger_actor_index",
        description="Add index on ledger.actor_id for actor-scoped queries",
        sql="""
            CREATE INDEX IF NOT EXISTS idx_ledger_actor ON ledger(actor_id);
        """,
    ),
    Migration(
        version=3,
        name="add_audit_trail_table",
        description="Dedicated audit trail table with hash-chain columns",
        sql="""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY,
                entry_id TEXT NOT NULL UNIQUE,
                sequence INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                target TEXT NOT NULL,
                outcome TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '{}',
                entry_hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_trail(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_trail(action);
            CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_trail(outcome);
        """,
        sql_pg="""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id SERIAL PRIMARY KEY,
                entry_id TEXT NOT NULL UNIQUE,
                sequence INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                target TEXT NOT NULL,
                outcome TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '{}',
                entry_hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_trail(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_trail(action);
            CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_trail(outcome);
        """,
    ),
    Migration(
        version=4,
        name="add_cost_events_table",
        description="Cost events for analytics",
        sql="""
            CREATE TABLE IF NOT EXISTS cost_events (
                id INTEGER PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                model TEXT NOT NULL,
                cost REAL NOT NULL,
                tokens INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cost_tenant ON cost_events(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_events(model);
        """,
        sql_pg="""
            CREATE TABLE IF NOT EXISTS cost_events (
                id SERIAL PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                model TEXT NOT NULL,
                cost REAL NOT NULL,
                tokens INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cost_tenant ON cost_events(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_events(model);
        """,
    ),
]


def create_platform_migration_engine(clock: Callable[[], str], dialect: str = "sqlite") -> MigrationEngine:
    """Create a MigrationEngine pre-loaded with platform migrations."""
    engine = MigrationEngine(clock=clock, dialect=dialect)
    for m in PLATFORM_MIGRATIONS:
        engine.register(m)
    return engine
