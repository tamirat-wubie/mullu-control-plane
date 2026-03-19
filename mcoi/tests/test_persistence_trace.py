"""Purpose: verify trace store append-only persistence and fail-closed loading.
Governance scope: persistence layer tests only.
Dependencies: trace store module, TraceEntry contract, tmp_path fixture.
Invariants: one file per trace entry, append-only, fail closed on malformed data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.persistence import (
    CorruptedDataError,
    PersistenceError,
    TraceNotFoundError,
    TraceStore,
)


def _make_trace(trace_id: str, parent: str | None = None) -> TraceEntry:
    return TraceEntry(
        trace_id=trace_id,
        parent_trace_id=parent,
        event_type="test_event",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash="state-hash-1",
        registry_hash="registry-hash-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )


def test_append_and_load_trace(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    entry = _make_trace("trace-1")
    store.append(entry)

    loaded = store.load_trace("trace-1")
    assert loaded.trace_id == "trace-1"
    assert loaded.event_type == "test_event"
    assert loaded.subject_id == "subject-1"


def test_list_traces(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    assert store.list_traces() == ()

    store.append(_make_trace("trace-a"))
    store.append(_make_trace("trace-b", parent="trace-a"))

    listed = store.list_traces()
    assert "trace-a" in listed
    assert "trace-b" in listed


def test_load_all_preserves_order(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    store.append(_make_trace("trace-a"))
    store.append(_make_trace("trace-b"))
    store.append(_make_trace("trace-c"))

    all_entries = store.load_all()
    ids = tuple(e.trace_id for e in all_entries)
    assert ids == ("trace-a", "trace-b", "trace-c")


def test_load_nonexistent_trace_raises(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    with pytest.raises(TraceNotFoundError):
        store.load_trace("no-such-trace")


def test_malformed_trace_file_raises(tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir(parents=True)
    (trace_dir / "bad-trace.json").write_text("not json", encoding="utf-8")

    store = TraceStore(trace_dir)
    with pytest.raises(CorruptedDataError):
        store.load_trace("bad-trace")


def test_empty_trace_id_raises(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    with pytest.raises(PersistenceError):
        store.load_trace("")


def test_load_all_empty_dir(tmp_path: Path) -> None:
    store = TraceStore(tmp_path / "traces")
    assert store.load_all() == ()
