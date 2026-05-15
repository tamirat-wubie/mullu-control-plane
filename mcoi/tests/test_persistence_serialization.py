"""Purpose: verify deterministic serialization round-trip invariant.
Governance scope: persistence layer tests only.
Dependencies: serialization helpers, TraceEntry contract.
Invariants: serialize(deserialize(serialize(x))) == serialize(x).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.contracts._base import ContractRecord
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


@dataclass(frozen=True)
class _NonFiniteContract(ContractRecord):
    value: float


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
    with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(JSONDecodeError\)$"):
        deserialize_record("not json", TraceEntry)


def test_deserialize_rejects_nonfinite_json_constants_with_bounded_error() -> None:
    raw = (
        '{"event_type":"test_event","goal_id":"goal-1","parent_trace_id":null,'
        '"registry_hash":"registry-hash-1","state_hash":"state-hash-1",'
        '"subject_id":"subject-1","timestamp":"2026-03-19T00:00:00+00:00",'
        '"trace_id":"trace-1","score":NaN}'
    )

    with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(ValueError\)$") as excinfo:
        deserialize_record(raw, TraceEntry)

    message = str(excinfo.value)
    assert message == "malformed JSON (ValueError)"
    assert "nan" not in message.lower()
    assert "score" not in message


def test_deserialize_empty_string_raises() -> None:
    with pytest.raises(CorruptedDataError):
        deserialize_record("", TraceEntry)


def test_deserialize_wrong_type_raises() -> None:
    with pytest.raises(CorruptedDataError, match=r"^expected JSON object$"):
        deserialize_record("[1, 2, 3]", TraceEntry)


def test_deserialize_unexpected_fields_raises() -> None:
    raw = (
        '{"event_type":"test_event","goal_id":"goal-1","parent_trace_id":null,'
        '"registry_hash":"registry-hash-1","state_hash":"state-hash-1",'
        '"subject_id":"subject-1","timestamp":"2026-03-19T00:00:00+00:00",'
        '"trace_id":"trace-1","unexpected":"value"}'
    )
    with pytest.raises(CorruptedDataError, match=r"^unexpected fields$") as excinfo:
        deserialize_record(raw, TraceEntry)
    assert "value" not in str(excinfo.value)


def test_serialize_non_dataclass_raises() -> None:
    with pytest.raises(
        CorruptedDataError,
        match=r"^serialize_record requires a contract record or dataclass instance$",
    ) as excinfo:
        serialize_record({"not": "a dataclass"})
    assert "dict" not in str(excinfo.value)


def test_contract_record_to_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="^contract record must be deterministic JSON$") as excinfo:
        _NonFiniteContract(float("nan")).to_json()

    message = str(excinfo.value)
    assert message == "contract record must be deterministic JSON"
    assert "nan" not in message.lower()
    assert "value" not in message


def test_serialize_record_rejects_nonfinite_values_with_bounded_error() -> None:
    with pytest.raises(CorruptedDataError, match=r"^failed to serialize record \(ValueError\)$") as excinfo:
        serialize_record(_NonFiniteContract(float("nan")))

    message = str(excinfo.value)
    assert message == "failed to serialize record (ValueError)"
    assert "nan" not in message.lower()
    assert "value" not in message
