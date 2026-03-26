"""Phase 198B — SQLite Persistence Backend.

Purpose: Durable storage for requests, ledger entries, and session state.
"""
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from typing import Any

class SQLiteStore:
    def __init__(self, db_path: str = "mullu.db"):
        self._path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._setup_tables()

    def _setup_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        """)
        self._conn.commit()

    def append_ledger(self, entry_type: str, actor_id: str, tenant_id: str, content: dict[str, Any], content_hash: str) -> int:
        from datetime import datetime, timezone
        cur = self._conn.execute(
            "INSERT INTO ledger (entry_type, actor_id, tenant_id, content, content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_type, actor_id, tenant_id, json.dumps(content, sort_keys=True), content_hash, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def query_ledger(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, entry_type, actor_id, content, content_hash, created_at FROM ledger WHERE tenant_id = ? ORDER BY id DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [{"id": r[0], "type": r[1], "actor": r[2], "content": json.loads(r[3]), "hash": r[4], "at": r[5]} for r in rows]

    def ledger_count(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            return self._conn.execute("SELECT COUNT(*) FROM ledger WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    def save_request(self, request_id: str, tenant_id: str, method: str, path: str, status_code: int, governed: bool) -> None:
        from datetime import datetime, timezone
        self._conn.execute(
            "INSERT OR REPLACE INTO requests (request_id, tenant_id, method, path, status_code, governed, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_id, tenant_id, method, path, status_code, 1 if governed else 0, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
