"""Purpose: verify deterministic serialization round-trip invariant.
Governance scope: persistence layer tests only.
Dependencies: serialization helpers, TraceEntry contract.
Invariants: serialize(deserialize(serialize(x))) == serialize(x).
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.persistence import (
    CorruptedDataError,
    deserialize_record,
    serialize_record,
)


def _make_trace() -> TraceEntry:
    return TraceEntry(
        trace_id="trace-1",
        parent_trace_id=None,
        event_type="test_event",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash="state-hash-1",
        registry_hash="registry-hash-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )


def test_round_trip_invariant() -> None:
    entry = _make_trace()
    json_str = serialize_record(entry)
    restored = deserialize_record(json_str, TraceEntry)
    json_str2 = serialize_record(restored)
    assert json_str == json_str2


def test_serialize_produces_deterministic_output() -> None:
    entry = _make_trace()
    assert serialize_record(entry) == serialize_record(entry)


def test_deserialize_malformed_json_raises() -> None:
    with pytest.raises(CorruptedDataError):
        deserialize_record("not json", TraceEntry)


def test_deserialize_empty_string_raises() -> None:
    with pytest.raises(CorruptedDataError):
        deserialize_record("", TraceEntry)


def test_deserialize_wrong_type_raises() -> None:
    with pytest.raises(CorruptedDataError):
        deserialize_record("[1, 2, 3]", TraceEntry)


def test_serialize_non_dataclass_raises() -> None:
    with pytest.raises(CorruptedDataError):
        serialize_record({"not": "a dataclass"})
