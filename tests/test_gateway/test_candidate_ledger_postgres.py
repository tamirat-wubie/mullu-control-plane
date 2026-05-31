"""Tests for the Postgres-backed candidate ledger store.

Uses an injected fake connection so the full store logic is exercised in CI
without a live database. A skip-gated smoke test runs against a real Postgres
when MULLU_TEST_CANDIDATE_LEDGER_DSN is set.
"""

from __future__ import annotations

import os

import pytest

from gateway.candidate_ledger import CandidateLedger, CandidateRun, CandidateScore
from gateway.candidate_ledger_postgres import (
    PostgresCandidateLedgerStore,
    connect,
)


class FakeConnection:
    """In-memory stand-in for a DB-API connection covering the store's queries."""

    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}  # record_hash -> row
        self._result: list[tuple] = []
        self.commits = 0
        self.closed = False

    def execute(self, query: str, params: tuple = ()) -> None:
        q = " ".join(query.lower().split())
        self._result = []
        if q.startswith("create table"):
            return
        if q.startswith("insert into candidate_runs"):
            record_hash, signature_hash, problem_id, recorded_at, payload = params
            self._rows[record_hash] = {
                "signature_hash": signature_hash,
                "problem_id": problem_id,
                "recorded_at": recorded_at,
                "payload": payload,
            }
            return
        if q.startswith("select 1 from candidate_runs where record_hash"):
            self._result = [(1,)] if params[0] in self._rows else []
            return
        if q.startswith("select payload from candidate_runs where signature_hash"):
            ordered = sorted(self._rows.values(), key=lambda r: r["recorded_at"])
            self._result = [(r["payload"],) for r in ordered if r["signature_hash"] == params[0]]
            return
        if q.startswith("select payload from candidate_runs"):
            ordered = sorted(self._rows.values(), key=lambda r: r["recorded_at"])
            self._result = [(r["payload"],) for r in ordered]
            return
        if q.startswith("select count(*) from candidate_runs"):
            self._result = [(len(self._rows),)]
            return
        raise AssertionError(f"unexpected query: {q}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


def _run(
    *,
    signature_hash: str = "sigA",
    run_seed: str = "s1",
    findings: tuple[str, ...] = (),
    recorded_at: str = "2026-05-31T00:00:00Z",
) -> CandidateRun:
    return CandidateRun(
        record_id="r",
        signature_hash=signature_hash,
        problem_id="p",
        candidate_pipeline_id="pipe",
        method_families=("rule_based",),
        outcome="passed",
        scores=(CandidateScore(metric_id="m", value=1.0, direction="maximize"),),
        baseline_delta={"m": 0.5},
        failure_modes=(),
        evidence_refs=("e1",),
        cost_units=1.0,
        duration_seconds=0.0,
        run_seed=run_seed,
        is_baseline=False,
        recorded_at=recorded_at,
        adversarial_review_findings=findings,
    )


def test_init_creates_schema_unless_disabled():
    fake = FakeConnection()
    PostgresCandidateLedgerStore(fake)
    assert fake.commits >= 1  # schema creation committed
    fake2 = FakeConnection()
    PostgresCandidateLedgerStore(fake2, ensure_schema=False)
    assert fake2.commits == 0


def test_append_has_record_and_roundtrip():
    store = PostgresCandidateLedgerStore(FakeConnection())
    record = _run(run_seed="s1")
    store.append(record)
    assert store.has_record(record.record_hash)
    runs = store.list_all()
    assert len(runs) == 1
    assert runs[0] == record  # byte-faithful reconstruction


def test_duplicate_append_raises():
    store = PostgresCandidateLedgerStore(FakeConnection())
    record = _run(run_seed="s1")
    store.append(record)
    with pytest.raises(ValueError, match="duplicate_record_hash"):
        store.append(record)


def test_record_with_findings_roundtrips():
    store = PostgresCandidateLedgerStore(FakeConnection())
    record = _run(run_seed="s1", findings=("unmitigated_injection_surface:c",))
    store.append(record)
    got = store.list_all()[0]
    assert got == record
    assert got.adversarial_review_findings == ("unmitigated_injection_surface:c",)


def test_list_for_signature_isolates_signatures():
    store = PostgresCandidateLedgerStore(FakeConnection())
    a = _run(signature_hash="A", run_seed="a1", recorded_at="2026-05-31T00:00:01Z")
    b = _run(signature_hash="B", run_seed="b1", recorded_at="2026-05-31T00:00:02Z")
    store.append(a)
    store.append(b)
    assert {r.record_hash for r in store.list_for_signature("A")} == {a.record_hash}
    assert {r.record_hash for r in store.list_all()} == {a.record_hash, b.record_hash}


def test_status_reports_backend_and_count():
    store = PostgresCandidateLedgerStore(FakeConnection())
    assert store.status() == {"backend": "postgres", "available": True, "records": 0}
    store.append(_run(run_seed="s1"))
    assert store.status()["records"] == 1


def test_drop_in_as_candidate_ledger_backend():
    # The store plugs into the high-level CandidateLedger unchanged.
    ledger = CandidateLedger(PostgresCandidateLedgerStore(FakeConnection()))
    recorded = ledger.record(
        signature_hash="sig1",
        problem_id="p",
        candidate_pipeline_id="pipe",
        method_families=("graph_match",),
        outcome="passed",
        scores=(CandidateScore(metric_id="f1", value=0.9, direction="maximize"),),
        baseline_delta={"f1": 0.2},
        run_seed="s1",
    )
    assert ledger.for_signature("sig1")[0].record_hash == recorded.record_hash
    winners = ledger.winners_for("sig1", primary_metric_id="f1")
    assert len(winners) == 1
    assert winners[0].record_hash == recorded.record_hash


def test_connect_without_psycopg2_raises_clearly(monkeypatch):
    # Force the lazy import to fail and confirm a clear error (not ImportError).
    import builtins

    real_import = builtins.__import__

    def _fail(name, *args, **kwargs):
        if name == "psycopg2":
            raise ImportError("no psycopg2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail)
    with pytest.raises(RuntimeError, match="psycopg2 is required"):
        connect("postgresql://localhost/db")


@pytest.mark.skipif(
    not os.environ.get("MULLU_TEST_CANDIDATE_LEDGER_DSN"),
    reason="set MULLU_TEST_CANDIDATE_LEDGER_DSN to run the real-Postgres smoke test",
)
def test_real_postgres_roundtrip():  # pragma: no cover - integration only
    store = connect(os.environ["MULLU_TEST_CANDIDATE_LEDGER_DSN"])
    record = _run(run_seed="real-smoke")
    if not store.has_record(record.record_hash):
        store.append(record)
    assert store.has_record(record.record_hash)
