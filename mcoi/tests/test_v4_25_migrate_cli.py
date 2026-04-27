"""v4.25.0 — `mcoi migrate` CLI subcommand for DB schema migrations.

The migration engine + 4 platform migrations have existed since
earlier releases (mcoi_runtime/persistence/migrations.py). What was
missing was operator-facing CLI access:

- SQLite auto-migrates at server startup (server_platform.py:92)
- Postgres deployments are operator-applied — but pre-v4.25 there was
  no CLI command to inspect or apply them out-of-band

v4.25 adds ``mcoi migrate {status,history,up}`` subcommands that wrap
the existing engine. SQLite-only for this release; postgres operators
continue using SQL files until/unless a customer asks for psycopg2
plumbing here.

Tests use ephemeral SQLite files via tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.cli import main


def _db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "test.sqlite"
    return f"sqlite:///{db_path}"


# ============================================================
# `migrate status` — fresh database
# ============================================================


def test_status_on_fresh_database(tmp_path, capsys):
    """Brand-new DB: current_version=0, all 4 platform migrations pending."""
    rc = main(["migrate", "status", "--db", _db_url(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "current_version: 0" in out
    # 4 platform migrations registered (initial_schema, ledger_actor_index,
    # audit_trail, cost_events)
    assert "registered: 4" in out
    assert "pending: 4" in out
    # All 4 names appear
    assert "initial_schema" in out
    assert "audit_trail" in out


# ============================================================
# `migrate up` — apply pending migrations
# ============================================================


def test_up_applies_all_pending(tmp_path, capsys):
    rc = main(["migrate", "up", "--db", _db_url(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "applied 4 migration(s)" in out
    assert "initial_schema" in out


def test_up_idempotent_when_no_pending(tmp_path, capsys):
    """Running `migrate up` twice in a row: second run is a no-op."""
    db = _db_url(tmp_path)
    main(["migrate", "up", "--db", db])
    capsys.readouterr()  # drain

    rc = main(["migrate", "up", "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    assert "up to date" in out
    assert "no pending migrations" in out


def test_up_dry_run_does_not_mutate(tmp_path, capsys):
    """--dry-run lists pending without applying them."""
    db = _db_url(tmp_path)
    rc = main(["migrate", "up", "--db", db, "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "would apply 4 migration(s)" in out

    # Verify NOT applied — current_version still 0
    rc2 = main(["migrate", "status", "--db", db])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert "current_version: 0" in out2


# ============================================================
# `migrate status` — partial/fully applied database
# ============================================================


def test_status_after_up_shows_zero_pending(tmp_path, capsys):
    db = _db_url(tmp_path)
    main(["migrate", "up", "--db", db])
    capsys.readouterr()

    rc = main(["migrate", "status", "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    assert "current_version: 4" in out
    assert "pending: 0" in out


# ============================================================
# `migrate history`
# ============================================================


def test_history_empty_on_fresh_db(tmp_path, capsys):
    rc = main(["migrate", "history", "--db", _db_url(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no migrations applied" in out


def test_history_shows_applied_entries(tmp_path, capsys):
    db = _db_url(tmp_path)
    main(["migrate", "up", "--db", db])
    capsys.readouterr()

    rc = main(["migrate", "history", "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    # Each of the 4 platform migrations appears
    assert "v  1" in out
    assert "v  4" in out
    assert "initial_schema" in out
    assert "checksum=" in out


# ============================================================
# Error paths
# ============================================================


def test_postgres_url_is_rejected(tmp_path, capsys):
    """v4.25 supports sqlite only; postgres is operator-applied."""
    rc = main([
        "migrate", "status", "--db",
        "postgresql://localhost/mullu",
    ])
    assert rc == 1
    out = capsys.readouterr().out
    assert "sqlite:///" in out


def test_unknown_url_scheme_rejected(tmp_path, capsys):
    rc = main([
        "migrate", "status", "--db", "mysql://localhost/mullu",
    ])
    assert rc == 1
    out = capsys.readouterr().out
    assert "sqlite:///" in out


def test_no_subcommand_shows_usage(capsys):
    """`mcoi migrate` (no subcommand) returns 1 with usage hint."""
    rc = main(["migrate"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Usage: mcoi migrate" in out


# ============================================================
# Schema actually got created (functional check)
# ============================================================


def test_up_creates_expected_tables(tmp_path):
    """After `migrate up`, the platform tables should exist with the
    expected column shape."""
    import sqlite3
    db_path = tmp_path / "test.sqlite"
    db_url = f"sqlite:///{db_path}"
    main(["migrate", "up", "--db", db_url])

    # Inspect the resulting schema
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        # Migrations 1, 3, 4 add tables — version table is 'schema_version'
        assert "schema_version" in tables
        assert "ledger" in tables
        assert "sessions" in tables
        assert "requests" in tables
        assert "audit_trail" in tables
        assert "cost_events" in tables
    finally:
        conn.close()


def test_schema_version_table_records_each_migration(tmp_path):
    """The schema_version table tracks every applied migration."""
    import sqlite3
    db_path = tmp_path / "test.sqlite"
    db_url = f"sqlite:///{db_path}"
    main(["migrate", "up", "--db", db_url])

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT version, name FROM schema_version ORDER BY version"
        ).fetchall()
        assert len(rows) == 4
        assert rows[0] == (1, "initial_schema")
        assert rows[1] == (2, "add_ledger_actor_index")
    finally:
        conn.close()


# ============================================================
# Sequential workflow (status → up → status → history)
# ============================================================


def test_full_workflow(tmp_path, capsys):
    """Smoke test the typical operator workflow."""
    db = _db_url(tmp_path)

    # 1. Status: 4 pending
    main(["migrate", "status", "--db", db])
    out = capsys.readouterr().out
    assert "pending: 4" in out

    # 2. Up: applies all 4
    main(["migrate", "up", "--db", db])
    out = capsys.readouterr().out
    assert "applied 4 migration(s)" in out

    # 3. Status: 0 pending
    main(["migrate", "status", "--db", db])
    out = capsys.readouterr().out
    assert "pending: 0" in out

    # 4. History: 4 entries
    main(["migrate", "history", "--db", db])
    out = capsys.readouterr().out
    history_lines = [l for l in out.split("\n") if l.startswith("v")]
    assert len(history_lines) == 4
