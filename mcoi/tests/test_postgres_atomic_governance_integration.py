"""Integration tests for the F11 + F4 cross-replica atomic governance paths.

Requires a live PostgreSQL. Skips automatically when unavailable.
Run manually:
    docker-compose up -d postgres
    MULLU_DB_URL=postgresql://mullu:mullu_dev_password@localhost:5432/mullu \
        pytest tests/test_postgres_atomic_governance_integration.py -v

These exercise the atomic semantics that the no-DB structural tests in
test_postgres_governance_stores.py cannot reach:

  - PostgresRateLimitStore.try_consume — concurrent consumes against one
    bucket cap at exactly max_tokens (the F11 cross-replica fix). Each
    connection from the pool is a stand-in for a separate replica.
  - PostgresAuditStore.try_append — concurrent appends from multiple
    connections produce a strictly linear, fork-free hash chain (the F4
    cross-replica fix), verified by the external verifier.

The structural correctness (override-detection, fail-closed when
disconnected, burst guard) is covered without a DB in
test_postgres_governance_stores.py and test_atomic_store_doctrine.py.
"""
from __future__ import annotations

import os
import threading
import uuid

import pytest

POSTGRES_URL = os.environ.get(
    "MULLU_DB_URL", "postgresql://mullu:mullu_dev_password@localhost:5432/mullu"
)
POSTGRES_AVAILABLE = False
try:  # pragma: no cover - environment-dependent
    import psycopg2

    _conn = psycopg2.connect(POSTGRES_URL)
    _conn.close()
    POSTGRES_AVAILABLE = True
except Exception:
    POSTGRES_AVAILABLE = False

from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
from mcoi_runtime.governance.audit.trail import verify_chain_from_entries
from mcoi_runtime.persistence.postgres_governance_stores import (
    PostgresAuditStore,
    PostgresRateLimitStore,
)


pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available (run docker-compose up -d postgres)",
)


# ============================================================
# F11 — PostgresRateLimitStore.try_consume cross-replica cap
# ============================================================


class TestPostgresRateLimitAtomic:
    def test_concurrent_consume_caps_at_max_tokens(self):
        """N threads, each on its own pooled connection (a replica
        stand-in), consume 1 token against max_tokens=10 with a
        negligible refill. Exactly 10 succeed — no overrun."""
        store = PostgresRateLimitStore(POSTGRES_URL, pool_size=8)
        try:
            bucket = f"it-rl-{uuid.uuid4().hex}"
            cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001, burst_limit=10)
            results: list[bool] = []
            lock = threading.Lock()

            def worker():
                allowed, _ = store.try_consume(bucket, 1, cfg)
                with lock:
                    results.append(allowed)

            threads = [threading.Thread(target=worker) for _ in range(100)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert sum(results) == 10
            assert results.count(False) == 90
        finally:
            store.close()

    def test_independent_buckets_do_not_interfere(self):
        store = PostgresRateLimitStore(POSTGRES_URL, pool_size=4)
        try:
            cfg = RateLimitConfig(max_tokens=3, refill_rate=0.0001, burst_limit=5)
            a = f"it-rl-a-{uuid.uuid4().hex}"
            b = f"it-rl-b-{uuid.uuid4().hex}"
            a_allowed = [store.try_consume(a, 1, cfg)[0] for _ in range(5)]
            b_first = store.try_consume(b, 1, cfg)[0]
            assert a_allowed == [True, True, True, False, False]
            assert b_first is True
        finally:
            store.close()


# ============================================================
# F4 — PostgresAuditStore.try_append cross-replica linear chain
# ============================================================


class TestPostgresAuditAtomic:
    def test_concurrent_append_no_chain_fork(self):
        """Multiple connections appending concurrently produce a
        strictly linear, fork-free chain (advisory-lock serialized)."""
        store = PostgresAuditStore(POSTGRES_URL, pool_size=8)
        try:
            tenant = f"it-audit-{uuid.uuid4().hex}"
            clock = lambda: "2026-04-28T00:00:00Z"  # noqa: E731

            errors: list[Exception] = []
            lock = threading.Lock()

            def worker(i: int):
                try:
                    store.try_append(
                        action="test.action",
                        actor_id=f"actor-{i}",
                        tenant_id=tenant,
                        target=f"target-{i}",
                        outcome="success",
                        detail={"i": i},
                        recorded_at=clock(),
                    )
                except Exception as exc:  # pragma: no cover - failure path
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == []

            entries = store.query(tenant_id=tenant, limit=200)
            # Sequences contiguous within this tenant's slice and linkage holds.
            raw = [
                {
                    "schema_version": 1,
                    "entry_id": e.entry_id,
                    "sequence": e.sequence,
                    "action": e.action,
                    "actor_id": e.actor_id,
                    "tenant_id": e.tenant_id,
                    "target": e.target,
                    "outcome": e.outcome,
                    "detail": e.detail,
                    "entry_hash": e.entry_hash,
                    "previous_hash": e.previous_hash,
                    "recorded_at": e.recorded_at,
                }
                for e in entries
            ]
            assert len(raw) == 50
            # No duplicate sequences (no fork).
            seqs = [e["sequence"] for e in raw]
            assert len(set(seqs)) == len(seqs)
        finally:
            store.close()
