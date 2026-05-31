"""Postgres-backed candidate ledger store.

Purpose: A durable `CandidateLedgerStore` for the Solver Forge comparison
    ledger, alongside the existing in-memory and JSON-file stores. It mirrors
    the platform persistence layer's `DatabaseConnection` protocol
    (`mcoi/mcoi_runtime/persistence/postgres_store.py`) so it works with the
    platform's Postgres connection — or any DB-API-shaped connection — and so
    it is fully testable with an injected fake connection (no live database
    required in CI).
Governance scope: storage only. Like every other store it is append-only and
    rejects duplicate `record_hash` writes; it never promotes, scores, or
    mutates a record. It changes nothing about the composer, the gates, or the
    maturity ladder.
Dependencies: gateway.candidate_ledger (CandidateLedgerStore contract,
    CandidateRun, record_from_mapping). psycopg2 is imported lazily and only
    when opening a real connection, so importing this module never requires it.
Invariants:
  - Append-only: records are inserted, never updated or deleted.
  - Duplicate `record_hash` raises `ValueError`, matching the in-memory and
    JSON stores (so the store is a drop-in `CandidateLedgerStore`).
  - Reconstructed runs are byte-faithful: a CandidateRun stored and read back
    is equal to the original (same `record_hash`).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol

from gateway.candidate_ledger import (
    CandidateLedgerStore,
    CandidateRun,
    record_from_mapping,
)


class LedgerDatabaseConnection(Protocol):
    """The slice of the platform `DatabaseConnection` protocol this store uses."""

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS candidate_runs (
    record_hash TEXT PRIMARY KEY,
    signature_hash TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_candidate_runs_signature ON candidate_runs(signature_hash);
"""


class PostgresCandidateLedgerStore(CandidateLedgerStore):
    """Append-only candidate ledger store over a SQL connection."""

    def __init__(
        self,
        connection: LedgerDatabaseConnection,
        *,
        ensure_schema: bool = True,
    ) -> None:
        self._conn = connection
        if ensure_schema:
            self._conn.execute(_CREATE_TABLE)
            self._conn.commit()

    def append(self, record: CandidateRun) -> None:
        # Reject duplicates to honour the append-only, no-overwrite contract.
        self._conn.execute(
            "SELECT 1 FROM candidate_runs WHERE record_hash = %s",
            (record.record_hash,),
        )
        if self._conn.fetchone() is not None:
            raise ValueError(f"duplicate_record_hash:{record.record_hash}")
        self._conn.execute(
            "INSERT INTO candidate_runs "
            "(record_hash, signature_hash, problem_id, recorded_at, payload) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                record.record_hash,
                record.signature_hash,
                record.problem_id,
                record.recorded_at,
                json.dumps(asdict(record), sort_keys=True, default=str),
            ),
        )
        self._conn.commit()

    def list_for_signature(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        self._conn.execute(
            "SELECT payload FROM candidate_runs WHERE signature_hash = %s "
            "ORDER BY recorded_at",
            (signature_hash,),
        )
        return self._rows_to_runs(self._conn.fetchall())

    def list_all(self) -> tuple[CandidateRun, ...]:
        self._conn.execute("SELECT payload FROM candidate_runs ORDER BY recorded_at")
        return self._rows_to_runs(self._conn.fetchall())

    def has_record(self, record_hash: str) -> bool:
        self._conn.execute(
            "SELECT 1 FROM candidate_runs WHERE record_hash = %s", (record_hash,)
        )
        return self._conn.fetchone() is not None

    def status(self) -> dict[str, Any]:
        self._conn.execute("SELECT COUNT(*) FROM candidate_runs")
        row = self._conn.fetchone()
        count = int(row[0]) if row else 0
        return {"backend": "postgres", "available": True, "records": count}

    @staticmethod
    def _rows_to_runs(rows: list[tuple[Any, ...]]) -> tuple[CandidateRun, ...]:
        runs: list[CandidateRun] = []
        for row in rows:
            payload = row[0]
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode("utf-8")
            data = json.loads(payload) if isinstance(payload, str) else payload
            runs.append(record_from_mapping(data))
        return tuple(runs)


class _Psycopg2Adapter:  # pragma: no cover - exercised only against a live DB
    """Adapt a psycopg2 connection to LedgerDatabaseConnection (execute on the
    connection, fetch from a single reused cursor)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._cursor = conn.cursor()

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        self._cursor.execute(query, params)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._cursor.fetchone()

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._cursor.fetchall())

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._cursor.close()
        self._conn.close()


def connect(
    connection_string: str, *, ensure_schema: bool = True
) -> PostgresCandidateLedgerStore:
    """Open a psycopg2 connection and wrap it as a candidate ledger store.

    psycopg2 is imported lazily so this module loads without it; tests inject a
    fake connection instead of calling this.
    """
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "psycopg2 is required for the Postgres candidate ledger store; "
            "install psycopg2-binary or inject a connection directly"
        ) from exc
    raw = psycopg2.connect(connection_string)  # pragma: no cover - needs a DB
    return PostgresCandidateLedgerStore(
        _Psycopg2Adapter(raw), ensure_schema=ensure_schema
    )
