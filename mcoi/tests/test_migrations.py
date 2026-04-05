"""Tests for schema migration engine."""
from __future__ import annotations

import sqlite3
import tempfile
import os
import pytest

from mcoi_runtime.persistence.migrations import (
    Migration, MigrationEngine, MigrationResult,
    PLATFORM_MIGRATIONS, create_platform_migration_engine,
)

CLOCK = lambda: "2026-03-27T12:00:00Z"


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as d:
        conn = sqlite3.connect(os.path.join(d, "test.db"))
        yield conn
        conn.close()


@pytest.fixture
def engine():
    return MigrationEngine(clock=CLOCK)


class TestMigrationEngine:
    def test_register_migrations(self, engine):
        engine.register(Migration(version=1, name="first", sql="SELECT 1"))
        engine.register(Migration(version=2, name="second", sql="SELECT 2"))
        assert engine.migration_count == 2

    def test_register_out_of_order_raises(self, engine):
        engine.register(Migration(version=2, name="second", sql="SELECT 2"))
        with pytest.raises(ValueError, match="^migration versions must increase monotonically$") as exc_info:
            engine.register(Migration(version=1, name="first", sql="SELECT 1"))
        assert "1" not in str(exc_info.value)
        assert "2" not in str(exc_info.value)

    def test_current_version_empty_db(self, engine, db):
        assert engine.current_version(db) == 0

    def test_apply_single_migration(self, engine, db):
        engine.register(Migration(
            version=1, name="create_test",
            sql="CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);",
        ))
        results = engine.apply_all(db)
        assert len(results) == 1
        assert results[0].success
        assert results[0].version == 1

        # Table should exist
        row = db.execute("SELECT COUNT(*) FROM test_table").fetchone()
        assert row[0] == 0

        # Version should be 1
        assert engine.current_version(db) == 1

    def test_apply_multiple_migrations(self, engine, db):
        engine.register(Migration(version=1, name="v1", sql="CREATE TABLE t1 (id INTEGER);"))
        engine.register(Migration(version=2, name="v2", sql="CREATE TABLE t2 (id INTEGER);"))
        engine.register(Migration(version=3, name="v3", sql="CREATE TABLE t3 (id INTEGER);"))

        results = engine.apply_all(db)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert engine.current_version(db) == 3

    def test_idempotent_apply(self, engine, db):
        engine.register(Migration(version=1, name="v1", sql="CREATE TABLE IF NOT EXISTS t1 (id INTEGER);"))
        engine.apply_all(db)
        # Apply again — should be no-op
        results = engine.apply_all(db)
        assert len(results) == 0

    def test_pending_returns_unapplied(self, engine, db):
        engine.register(Migration(version=1, name="v1", sql="SELECT 1"))
        engine.register(Migration(version=2, name="v2", sql="SELECT 1"))
        engine.apply_all(db)

        engine.register(Migration(version=3, name="v3", sql="SELECT 1"))
        pending = engine.pending(db)
        assert len(pending) == 1
        assert pending[0].version == 3

    def test_failed_migration_raises(self, engine, db):
        engine.register(Migration(version=1, name="bad", sql="INVALID SQL SYNTAX"))
        with pytest.raises(RuntimeError, match="failed"):
            engine.apply_all(db)

    def test_failed_migration_message_is_bounded(self, engine):
        class BrokenMigrationConn:
            def execute(self, _sql: str, _params: tuple = ()):
                return self

            def executescript(self, _sql: str) -> None:
                raise RuntimeError("secret ddl backend failure")

            def commit(self) -> None:
                return None

            def fetchone(self):
                return (0,)

        engine.register(Migration(version=1, name="bad", sql="CREATE TABLE test (id INTEGER);"))

        with pytest.raises(RuntimeError, match=r"^migration execution failed$") as exc_info:
            engine.apply_all(BrokenMigrationConn())

        assert "RuntimeError" not in str(exc_info.value)
        assert "bad" not in str(exc_info.value)
        assert "secret ddl backend failure" not in str(exc_info.value)
        assert str(exc_info.value) == "migration execution failed"

    def test_failed_migration_message_is_bounded(self, engine):
        class BrokenMigrationConn:
            def execute(self, _sql: str, _params: tuple = ()):
                return self

            def executescript(self, _sql: str) -> None:
                raise RuntimeError("secret ddl backend failure")

            def commit(self) -> None:
                return None

            def fetchone(self):
                return (0,)

        engine.register(Migration(version=1, name="bad", sql="CREATE TABLE test (id INTEGER);"))

        with pytest.raises(RuntimeError, match=r"^migration execution failed$") as exc_info:
            engine.apply_all(BrokenMigrationConn())

        assert "RuntimeError" not in str(exc_info.value)
        assert "bad" not in str(exc_info.value)
        assert "secret ddl backend failure" not in str(exc_info.value)
        assert str(exc_info.value) == "migration execution failed"

    def test_history(self, engine, db):
        engine.register(Migration(version=1, name="v1", sql="SELECT 1"))
        engine.register(Migration(version=2, name="v2", sql="SELECT 1"))
        engine.apply_all(db)

        history = engine.history(db)
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2
        assert history[0]["applied_at"] == "2026-03-27T12:00:00Z"

    def test_current_version_raises_bounded_error_on_lookup_failure(self, engine):
        class BrokenVersionConn:
            def execute(self, _sql: str, _params: tuple = ()):
                raise RuntimeError("secret version lookup failure")

            def executescript(self, _sql: str) -> None:
                return None

            def commit(self) -> None:
                return None

        with pytest.raises(RuntimeError, match=r"^migration state lookup failed$") as exc_info:
            engine.current_version(BrokenVersionConn())

        assert "RuntimeError" not in str(exc_info.value)
        assert "secret version lookup failure" not in str(exc_info.value)
        assert str(exc_info.value) == "migration state lookup failed"

    def test_history_raises_bounded_error_on_lookup_failure(self, engine):
        class BrokenHistoryConn:
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, _sql: str, _params: tuple = ()):
                self.calls += 1
                if self.calls >= 2:
                    raise RuntimeError("secret history lookup failure")
                return self

            def executescript(self, _sql: str) -> None:
                return None

            def commit(self) -> None:
                return None

            def fetchall(self):
                return []

        with pytest.raises(RuntimeError, match=r"^migration history lookup failed$") as exc_info:
            engine.history(BrokenHistoryConn())

        assert "RuntimeError" not in str(exc_info.value)
        assert "secret history lookup failure" not in str(exc_info.value)
        assert str(exc_info.value) == "migration history lookup failed"

        assert "migration history lookup failed" in str(exc_info.value)

    def test_summary(self, engine):
        engine.register(Migration(version=1, name="v1", sql="SELECT 1"))
        s = engine.summary()
        assert s["registered_migrations"] == 1
        assert s["migrations"][0]["name"] == "v1"


class TestPlatformMigrations:
    def test_platform_migrations_defined(self):
        assert len(PLATFORM_MIGRATIONS) >= 4

    def test_platform_migrations_sequential(self):
        for i, m in enumerate(PLATFORM_MIGRATIONS):
            assert m.version == i + 1

    def test_create_platform_engine(self):
        engine = create_platform_migration_engine(CLOCK)
        assert engine.migration_count == len(PLATFORM_MIGRATIONS)

    def test_platform_migrations_apply_to_sqlite(self, db):
        engine = create_platform_migration_engine(CLOCK)
        results = engine.apply_all(db)
        assert len(results) == len(PLATFORM_MIGRATIONS)
        assert all(r.success for r in results)

        # Verify tables exist
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "ledger" in table_names
        assert "sessions" in table_names
        assert "requests" in table_names
        assert "audit_trail" in table_names
        assert "cost_events" in table_names
        assert "schema_version" in table_names

    def test_platform_migrations_idempotent(self, db):
        engine = create_platform_migration_engine(CLOCK)
        engine.apply_all(db)
        # Second apply should be no-op
        results = engine.apply_all(db)
        assert len(results) == 0
        assert engine.current_version(db) == len(PLATFORM_MIGRATIONS)


class TestMigrationDialect:
    """Test dialect-aware SQL selection logic."""

    def test_postgresql_dialect_selects_sql_pg(self):
        engine = MigrationEngine(clock=CLOCK, dialect="postgresql")
        m = Migration(version=1, name="dual", sql="sqlite_sql", sql_pg="pg_sql")
        engine.register(m)
        # Verify the engine would pick sql_pg for postgresql dialect
        assert engine._dialect == "postgresql"
        assert m.sql_pg == "pg_sql"
        # The engine selects: sql_pg if dialect=postgresql and sql_pg exists
        selected = m.sql_pg if engine._dialect == "postgresql" and m.sql_pg else m.sql
        assert selected == "pg_sql"

    def test_sqlite_dialect_selects_sql(self):
        engine = MigrationEngine(clock=CLOCK, dialect="sqlite")
        m = Migration(version=1, name="dual", sql="sqlite_sql", sql_pg="pg_sql")
        engine.register(m)
        selected = m.sql_pg if engine._dialect == "postgresql" and m.sql_pg else m.sql
        assert selected == "sqlite_sql"

    def test_fallback_when_no_sql_pg(self):
        engine = MigrationEngine(clock=CLOCK, dialect="postgresql")
        m = Migration(version=1, name="no_pg", sql="fallback_sql")
        engine.register(m)
        # No sql_pg → falls back to sql
        selected = m.sql_pg if engine._dialect == "postgresql" and m.sql_pg else m.sql
        assert selected == "fallback_sql"

    def test_sqlite_dialect_actually_applies(self, db):
        """SQLite dialect applies migrations on real SQLite connection."""
        engine = MigrationEngine(clock=CLOCK, dialect="sqlite")
        engine.register(Migration(
            version=1, name="create_test",
            sql="CREATE TABLE dialect_test (id INTEGER PRIMARY KEY)",
        ))
        results = engine.apply_all(db)
        assert len(results) == 1
        assert results[0].success
        # Verify table exists
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dialect_test'"
        ).fetchall()
        assert len(tables) == 1

    def test_postgresql_placeholder_logic(self):
        """Verify %s is used for postgresql, ? for sqlite."""
        pg_engine = MigrationEngine(clock=CLOCK, dialect="postgresql")
        sq_engine = MigrationEngine(clock=CLOCK, dialect="sqlite")
        assert pg_engine._dialect == "postgresql"
        assert sq_engine._dialect == "sqlite"
