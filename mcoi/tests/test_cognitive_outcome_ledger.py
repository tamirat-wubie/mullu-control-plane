"""Tests for the D1 cognitive outcome ledger substrate.

Covers the six categories from §6 of docs/design/COGNITIVE_OUTCOME_LEDGER.md:
  1. append + chain integrity (sequence-monotone, chain hash valid)
  2. replay returns identical event sequence in original order
  3. dup-suppress idempotence (same content can be re-applied safely; the
     content-addressed body write does NOT corrupt on re-append)
  4. concurrent-write serialisation (multi-thread + bounded-retry path)
  5. corrupted-file refuses to serve (tampering at any layer surfaces as
     CorruptedDataError -- fail-CLOSED)
  6. per-tenant isolation (one tenant's chain cannot taint another's)

The substrate has NO integration with CognitiveLearner / runtime / routers yet;
those land in follow-up PRs. These tests therefore exercise only the persistence
module's contract.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeEntry,
    CognitiveOutcomeEvent,
    FileBackedCognitiveOutcomeLedger,
)
from mcoi_runtime.persistence.errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
)
from mcoi_runtime.persistence.hash_chain import compute_content_hash


# ---------- helpers ----------


def _event(
    *,
    capability_id: str = "llm.completion",
    source_ref: str = "wf-001",
    succeeded: bool = True,
    verified: bool = True,
    admitted_entry_id: str | None = "ep-1",
    learned_at: str = "2026-06-03T12:00:00Z",
    prior_confidence: float = 0.5,
    next_confidence: float = 0.55,
) -> CognitiveOutcomeEvent:
    return CognitiveOutcomeEvent(
        capability_id=capability_id,
        succeeded=succeeded,
        verified=verified,
        admitted_entry_id=admitted_entry_id,
        source_ref=source_ref,
        learned_at=learned_at,
        prior_confidence=prior_confidence,
        next_confidence=next_confidence,
    )


def _ledger(tmp_path: Path, *, tenant_id: str = "tenant-A") -> FileBackedCognitiveOutcomeLedger:
    return FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id=tenant_id)


# ---------- (0) shape invariants ----------


def test_event_rejects_blank_capability_id():
    with pytest.raises(Exception):
        _event(capability_id="   ")


def test_event_rejects_out_of_range_confidence():
    with pytest.raises(Exception):
        _event(prior_confidence=1.5)


def test_event_is_hashable_and_round_trip_equal():
    a = _event()
    b = _event()
    assert a == b
    assert hash(a) == hash(b)


def test_entry_rejects_negative_sequence(tmp_path):
    with pytest.raises(Exception):
        CognitiveOutcomeEntry(
            sequence=-1,
            event=_event(),
            content_hash="a" * 64,
            chain_hash="b" * 64,
            previous_chain_hash="0" * 64,
            recorded_at="2026-06-03T12:00:00Z",
        )


# ---------- (1) append + chain integrity ----------


def test_append_assigns_monotone_sequence(tmp_path):
    ledger = _ledger(tmp_path)
    e1 = ledger.append(_event(source_ref="wf-001"))
    e2 = ledger.append(_event(source_ref="wf-002"))
    e3 = ledger.append(_event(source_ref="wf-003"))
    assert (e1.sequence, e2.sequence, e3.sequence) == (0, 1, 2)
    assert ledger.latest_sequence() == 2


def test_append_chain_validates_clean(tmp_path):
    ledger = _ledger(tmp_path)
    for i in range(8):
        ledger.append(_event(source_ref=f"wf-{i}"))
    # validate() must return without raising on a clean chain.
    ledger.validate()


def test_first_entry_chains_to_genesis(tmp_path):
    ledger = _ledger(tmp_path)
    e = ledger.append(_event(source_ref="wf-genesis"))
    assert e.previous_chain_hash == "0" * 64
    assert e.sequence == 0


def test_subsequent_entries_chain_to_prior(tmp_path):
    ledger = _ledger(tmp_path)
    e1 = ledger.append(_event(source_ref="wf-001"))
    e2 = ledger.append(_event(source_ref="wf-002"))
    assert e2.previous_chain_hash == e1.chain_hash


def test_empty_ledger_latest_sequence_is_none(tmp_path):
    ledger = _ledger(tmp_path)
    assert ledger.latest_sequence() is None
    # replay() on empty ledger yields nothing.
    assert list(ledger.replay()) == []
    # validate() on empty ledger succeeds (vacuously).
    ledger.validate()


# ---------- (2) replay returns identical event sequence ----------


def test_replay_preserves_event_order_and_content(tmp_path):
    ledger = _ledger(tmp_path)
    events = [
        _event(source_ref=f"wf-{i}", next_confidence=0.5 + 0.01 * i)
        for i in range(10)
    ]
    for e in events:
        ledger.append(e)
    replayed = list(ledger.replay())
    assert len(replayed) == 10
    for index, entry in enumerate(replayed):
        assert entry.sequence == index
        assert entry.event == events[index]


def test_replay_yields_chain_metadata(tmp_path):
    ledger = _ledger(tmp_path)
    appended = [ledger.append(_event(source_ref=f"wf-{i}")) for i in range(3)]
    replayed = list(ledger.replay())
    for written, read in zip(appended, replayed, strict=True):
        assert read.sequence == written.sequence
        assert read.content_hash == written.content_hash
        assert read.chain_hash == written.chain_hash
        assert read.previous_chain_hash == written.previous_chain_hash
        assert read.recorded_at == written.recorded_at


# ---------- (3) dup-suppress idempotence ----------


def test_appending_identical_event_twice_succeeds_with_distinct_sequences(tmp_path):
    """Two appends of the same event content get DISTINCT sequence numbers.

    Per the design doc, idempotency is at the CONTENT layer (body file is
    content-addressed so two writes don't corrupt each other); each append
    is a NEW chain event regardless. Replay therefore yields the event
    twice -- the rehydrate path is responsible for any application-level
    dedup (e.g. via source_ref + admitted_entry_id).
    """
    ledger = _ledger(tmp_path)
    e = _event(source_ref="wf-001")
    a = ledger.append(e)
    b = ledger.append(e)
    assert a.sequence == 0
    assert b.sequence == 1
    # The body file content is the same; the chain entries are different.
    assert a.content_hash == b.content_hash
    assert a.chain_hash != b.chain_hash


def test_existing_body_is_not_rewritten(tmp_path):
    """A repeat content-addressed body write must NOT clobber the existing file."""
    ledger = _ledger(tmp_path)
    e = _event(source_ref="wf-001")
    ledger.append(e)
    body_dir = tmp_path / "tenant-A" / "bodies"
    body_files = list(body_dir.iterdir())
    assert len(body_files) == 1
    original_mtime = body_files[0].stat().st_mtime
    # Re-append the SAME body content.
    ledger.append(e)
    # Body file count unchanged (no second body file for the duplicate body).
    assert len(list(body_dir.iterdir())) == 1
    # File untouched -- our atomic write SKIPS the rewrite when body already exists.
    assert body_files[0].stat().st_mtime == original_mtime


# ---------- (4) concurrent-write serialisation ----------


@pytest.fixture
def _force_thread_switches():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_appends_produce_strictly_monotone_chain(tmp_path, _force_thread_switches):
    """8 threads x 25 appends each; chain must remain strictly monotone."""
    ledger = _ledger(tmp_path)
    errors: list[BaseException] = []
    guard = threading.Lock()

    def worker(worker_id: int) -> None:
        try:
            for i in range(25):
                ledger.append(_event(source_ref=f"wf-{worker_id}-{i}"))
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [], f"concurrent append raised: {errors[:1]}"
    # Chain still validates end-to-end.
    ledger.validate()
    # All 200 events accounted for with monotone sequence 0..199.
    sequences = [entry.sequence for entry in ledger.replay()]
    assert sequences == list(range(200))


# ---------- (5) corrupted-file fail-CLOSED ----------


def test_tampered_body_file_fails_validate(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append(_event(source_ref="wf-1"))
    ledger.append(_event(source_ref="wf-2"))
    # Tamper with one body file -- arbitrary byte change. The body is
    # content-addressed by hash, so any change to the bytes is detected by
    # the SHA-256 mismatch (we don't rely on a specific text replacement
    # being present in the lex-first body).
    body_dir = tmp_path / "tenant-A" / "bodies"
    body_files = sorted(body_dir.iterdir())
    original = body_files[0].read_text(encoding="utf-8")
    body_files[0].write_text(original + " ", encoding="utf-8")
    with pytest.raises(CorruptedDataError):
        ledger.validate()


def test_missing_body_file_fails_validate(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append(_event(source_ref="wf-1"))
    # Delete the body file (chain entry still present).
    body_dir = tmp_path / "tenant-A" / "bodies"
    next(body_dir.iterdir()).unlink()
    with pytest.raises(CorruptedDataError):
        ledger.validate()


def test_tampered_chain_entry_fails_validate(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append(_event(source_ref="wf-1"))
    ledger.append(_event(source_ref="wf-2"))
    # Tamper with a chain entry's stored content_hash.
    tenant_dir = tmp_path / "tenant-A"
    chain_files = sorted(
        f for f in tenant_dir.iterdir() if f.suffix == ".json" and f.name[0].isdigit()
    )
    raw = chain_files[0].read_text(encoding="utf-8")
    # Flip one hex char in the content_hash field; chain hash recompute will fail.
    tampered = raw.replace('"content_hash":"', '"content_hash":"f', 1)
    chain_files[0].write_text(tampered, encoding="utf-8")
    with pytest.raises(CorruptedDataError):
        ledger.validate()


def test_replay_also_detects_body_tamper(tmp_path):
    """A tampered body must surface a fail-CLOSED error even via the replay path.

    The rehydrate workflow is "validate then replay"; this test guards against
    a future refactor that skips validate and only iterates replay.
    """
    ledger = _ledger(tmp_path)
    ledger.append(_event(source_ref="wf-1"))
    body_dir = tmp_path / "tenant-A" / "bodies"
    body_file = next(body_dir.iterdir())
    original = body_file.read_text(encoding="utf-8")
    body_file.write_text(original + " ", encoding="utf-8")
    with pytest.raises(CorruptedDataError):
        list(ledger.replay())


# ---------- (6) per-tenant isolation ----------


def test_per_tenant_chains_are_independent(tmp_path):
    a = _ledger(tmp_path, tenant_id="tenant-A")
    b = _ledger(tmp_path, tenant_id="tenant-B")
    a.append(_event(source_ref="wf-A1"))
    a.append(_event(source_ref="wf-A2"))
    b.append(_event(source_ref="wf-B1"))
    assert a.latest_sequence() == 1
    assert b.latest_sequence() == 0
    a_events = [entry.event.source_ref for entry in a.replay()]
    b_events = [entry.event.source_ref for entry in b.replay()]
    assert a_events == ["wf-A1", "wf-A2"]
    assert b_events == ["wf-B1"]


def test_tenant_id_rejects_path_traversal(tmp_path):
    with pytest.raises((PersistenceError, PathTraversalError)):
        FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="../escape")


def test_tenant_id_rejects_blank(tmp_path):
    with pytest.raises(Exception):
        FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="   ")


def test_tenant_id_rejects_too_long(tmp_path):
    with pytest.raises(PersistenceError):
        FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="t" * 65)


# ---------- (bonus) determinism: same input sequence -> same chain ----------


def test_two_independent_ledgers_with_identical_input_produce_identical_chain(tmp_path):
    """Determinism property: identical event sequence -> identical chain hashes.

    Confirms the chain primitives + canonical serialisation are deterministic
    across instances. This is the property the design doc names as the
    foundation of replay-equivalence.
    """
    ledger_a = _ledger(tmp_path / "a", tenant_id="tenant")
    ledger_b = _ledger(tmp_path / "b", tenant_id="tenant")
    events = [_event(source_ref=f"wf-{i}", next_confidence=0.5 + 0.01 * i) for i in range(5)]
    out_a = [ledger_a.append(e) for e in events]
    out_b = [ledger_b.append(e) for e in events]
    # The recorded_at field comes from wall-clock so it WILL differ; everything
    # else (sequence, content_hash, chain_hash, previous_chain_hash) must match.
    for x, y in zip(out_a, out_b, strict=True):
        assert x.sequence == y.sequence
        assert x.content_hash == y.content_hash
        assert x.chain_hash == y.chain_hash
        assert x.previous_chain_hash == y.previous_chain_hash
        assert x.event == y.event


# ---------- (bonus) body content-hash matches recompute ----------


def test_recorded_content_hash_matches_canonical_recompute(tmp_path):
    ledger = _ledger(tmp_path)
    e = _event(source_ref="wf-1")
    entry = ledger.append(e)
    # The chain's content_hash is over the canonical-serialised body. Read the
    # body off disk and recompute; must match what the chain recorded.
    body_dir = tmp_path / "tenant-A" / "bodies"
    body_file = next(body_dir.iterdir())
    recompute = compute_content_hash(body_file.read_text(encoding="utf-8"))
    assert entry.content_hash == recompute
