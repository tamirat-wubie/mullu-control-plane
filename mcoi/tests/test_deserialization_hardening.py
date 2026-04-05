"""Purpose: verify recursive typed deserialization — nested dataclasses, enums, tuples, optionals.
Governance scope: persistence deserialization hardening tests only.
Dependencies: _serialization module, contracts.
Invariants:
  - Nested dataclasses reconstruct recursively.
  - Enums reconstruct from string values.
  - Tuples reconstruct from JSON arrays.
  - Optional fields handle None correctly.
  - Unsupported shapes fail closed.
  - No raw dict leakage into typed fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

import pytest

from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.contracts.execution import ExecutionResult, ExecutionOutcome, EffectRecord
from mcoi_runtime.contracts.verification import VerificationResult, VerificationCheck, VerificationStatus
from mcoi_runtime.contracts.communication import CommunicationMessage, CommunicationChannel, DeliveryStatus
from mcoi_runtime.contracts.integration import ConnectorDescriptor, EffectClass, TrustClass
from mcoi_runtime.contracts.temporal import TemporalTask, TemporalState, TemporalTrigger, TriggerType
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.persistence._serialization import serialize_record, deserialize_record
from mcoi_runtime.persistence.errors import CorruptedDataError


_CLOCK = "2026-03-19T00:00:00+00:00"


# --- Flat round-trip (regression) ---


def test_flat_trace_entry_round_trips() -> None:
    entry = TraceEntry(
        trace_id="t-1", parent_trace_id=None, event_type="test",
        subject_id="s-1", goal_id="g-1",
        state_hash="h-1", registry_hash="r-1",
        timestamp=_CLOCK,
    )
    json_str = serialize_record(entry)
    restored = deserialize_record(json_str, TraceEntry)
    assert serialize_record(restored) == json_str
    assert restored.trace_id == "t-1"


# --- Enum reconstruction ---


def test_enum_field_round_trips() -> None:
    desc = ConnectorDescriptor(
        connector_id="c-1", name="Test", provider="test",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-1", enabled=True,
    )
    json_str = serialize_record(desc)
    restored = deserialize_record(json_str, ConnectorDescriptor)
    assert restored.effect_class is EffectClass.EXTERNAL_READ
    assert restored.trust_class is TrustClass.BOUNDED_EXTERNAL
    assert isinstance(restored.effect_class, EffectClass)


def test_capability_confidence_round_trips() -> None:
    conf = CapabilityConfidence(
        capability_id="cap-1",
        success_rate=0.95, verification_pass_rate=0.9,
        timeout_rate=0.02, error_rate=0.03,
        sample_count=100, assessed_at=_CLOCK,
    )
    json_str = serialize_record(conf)
    restored = deserialize_record(json_str, CapabilityConfidence)
    assert restored.capability_id == "cap-1"
    assert restored.success_rate == 0.95


# --- Nested dataclass reconstruction ---


@dataclass(frozen=True, slots=True)
class Inner:
    value: str
    count: int


@dataclass(frozen=True, slots=True)
class Outer:
    outer_id: str
    inner: Inner
    label: str = "default"


def test_nested_dataclass_round_trips() -> None:
    obj = Outer(outer_id="o-1", inner=Inner(value="hello", count=42))
    json_str = serialize_record(obj)
    restored = deserialize_record(json_str, Outer)
    assert isinstance(restored.inner, Inner)
    assert restored.inner.value == "hello"
    assert restored.inner.count == 42
    assert restored.outer_id == "o-1"


# --- Tuple of dataclasses ---


class ItemStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class Item:
    item_id: str
    status: ItemStatus


@dataclass(frozen=True, slots=True)
class Container:
    container_id: str
    items: tuple[Item, ...]


def test_tuple_of_dataclasses_round_trips() -> None:
    obj = Container(
        container_id="c-1",
        items=(
            Item(item_id="i-1", status=ItemStatus.ACTIVE),
            Item(item_id="i-2", status=ItemStatus.INACTIVE),
        ),
    )
    json_str = serialize_record(obj)
    restored = deserialize_record(json_str, Container)
    assert len(restored.items) == 2
    assert isinstance(restored.items, tuple)
    assert isinstance(restored.items[0], Item)
    assert restored.items[0].item_id == "i-1"
    assert restored.items[0].status is ItemStatus.ACTIVE
    assert restored.items[1].status is ItemStatus.INACTIVE


# --- Optional nested dataclass ---


@dataclass(frozen=True, slots=True)
class WithOptional:
    required_id: str
    optional_inner: Inner | None = None


def test_optional_nested_present() -> None:
    obj = WithOptional(required_id="r-1", optional_inner=Inner(value="hi", count=1))
    json_str = serialize_record(obj)
    restored = deserialize_record(json_str, WithOptional)
    assert restored.optional_inner is not None
    assert isinstance(restored.optional_inner, Inner)
    assert restored.optional_inner.value == "hi"


def test_optional_nested_absent() -> None:
    obj = WithOptional(required_id="r-1", optional_inner=None)
    json_str = serialize_record(obj)
    restored = deserialize_record(json_str, WithOptional)
    assert restored.optional_inner is None


# --- Temporal task with nested trigger ---


def test_temporal_task_with_trigger_round_trips() -> None:
    task = TemporalTask(
        task_id="task-1", goal_id="g-1", description="test",
        trigger=TemporalTrigger(
            trigger_id="trig-1",
            trigger_type=TriggerType.AT_TIME,
            value="2027-01-01T00:00:00+00:00",
        ),
        state=TemporalState.PENDING,
        created_at=_CLOCK,
    )
    json_str = serialize_record(task)
    restored = deserialize_record(json_str, TemporalTask)
    assert isinstance(restored.trigger, TemporalTrigger)
    assert restored.trigger.trigger_type is TriggerType.AT_TIME
    assert restored.state is TemporalState.PENDING


# --- Malformed nested content fails closed ---


def test_malformed_nested_dataclass_fails() -> None:
    """Inner field is a string instead of a dict — should fail."""
    import json
    raw = json.dumps({"outer_id": "o-1", "inner": "not-a-dict", "label": "x"})
    with pytest.raises(CorruptedDataError, match=r"^expected object for dataclass field$") as excinfo:
        deserialize_record(raw, Outer)
    assert "inner" not in str(excinfo.value)


def test_invalid_enum_value_fails() -> None:
    import json
    raw = json.dumps({
        "connector_id": "c-1", "name": "Test", "provider": "test",
        "effect_class": "nonexistent_class",
        "trust_class": "bounded_external",
        "credential_scope_id": "s-1", "enabled": True,
    })
    with pytest.raises(CorruptedDataError, match=r"^invalid enum value$") as excinfo:
        deserialize_record(raw, ConnectorDescriptor)
    assert "nonexistent_class" not in str(excinfo.value)


def test_wrong_type_in_tuple_fails() -> None:
    import json
    raw = json.dumps({
        "container_id": "c-1",
        "items": ["not-a-dict", "also-not-a-dict"],
    })
    with pytest.raises(CorruptedDataError, match=r"^expected object for dataclass field$") as excinfo:
        deserialize_record(raw, Container)
    assert "not-a-dict" not in str(excinfo.value)


# --- Verify no raw dict leakage ---


def test_no_raw_dict_in_nested_fields() -> None:
    """After deserialization, nested fields must be actual dataclass instances, not dicts."""
    obj = Container(
        container_id="c-1",
        items=(Item(item_id="i-1", status=ItemStatus.ACTIVE),),
    )
    json_str = serialize_record(obj)
    restored = deserialize_record(json_str, Container)

    # This would fail if items contained raw dicts
    assert not isinstance(restored.items[0], dict)
    assert hasattr(restored.items[0], "item_id")
    assert hasattr(restored.items[0], "status")


def test_roundtrip_determinism_with_nested() -> None:
    obj = Outer(outer_id="o-1", inner=Inner(value="test", count=99))
    s1 = serialize_record(obj)
    r1 = deserialize_record(s1, Outer)
    s2 = serialize_record(r1)
    assert s1 == s2
