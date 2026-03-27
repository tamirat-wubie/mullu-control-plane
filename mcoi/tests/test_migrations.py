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
        with pytest.raises(ValueError, match="must be >"):
            engine.register(Migration(version=1, name="first", sql="SELECT 1"))

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

    def test_history(self, engine, db):
        engine.register(Migration(version=1, name="v1", sql="SELECT 1"))
        engine.register(Migration(version=2, name="v2", sql="SELECT 1"))
        engine.apply_all(db)

        history = engine.history(db)
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2
        assert history[0]["applied_at"] == "2026-03-27T12:00:00Z"

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
