"""Purpose: verify bounded shared contract-helper messages.
Governance scope: shared contract helper validation only.
Dependencies: contracts _base helper module.
Invariants:
  - Known schema field labels preserve stable helper messages.
  - Unknown caller-supplied field labels collapse to bounded generic labels.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.contracts._base import (
    ContractRecord,
    require_datetime_text,
    require_non_empty_tuple,
    require_non_empty_text,
    require_non_negative_int,
)


@dataclass(frozen=True)
class ContractProbe(ContractRecord):
    z_field: str
    a_field: dict[str, float]


def test_known_field_label_preserves_schema_stable_message() -> None:
    with pytest.raises(ValueError, match=r"^request_id must be a non-empty string$"):
        require_non_empty_text("", "request_id")


def test_unknown_text_field_label_is_bounded() -> None:
    with pytest.raises(ValueError, match=r"^value must be a non-empty string$") as excinfo:
        require_non_empty_text("", "secret_field_name")
    assert "secret_field_name" not in str(excinfo.value)


def test_unknown_datetime_field_label_is_bounded() -> None:
    with pytest.raises(ValueError, match=r"^value must be an ISO 8601 date-time string$") as excinfo:
        require_datetime_text("not-a-timestamp", "private_timestamp")
    assert "private_timestamp" not in str(excinfo.value)


def test_unknown_numeric_field_label_is_bounded() -> None:
    with pytest.raises(ValueError, match=r"^value must be non-negative$") as excinfo:
        require_non_negative_int(-1, "sensitive_counter")
    assert "sensitive_counter" not in str(excinfo.value)


def test_non_empty_tuple_accepts_json_array_shapes() -> None:
    frozen = require_non_empty_tuple(["alpha", {"nested": ["beta"]}], "items")

    assert frozen[0] == "alpha"
    assert frozen[1]["nested"] == ("beta",)
    assert isinstance(frozen, tuple)


def test_non_empty_tuple_rejects_scalar_text() -> None:
    with pytest.raises(ValueError, match=r"^items must be an array$"):
        require_non_empty_tuple("abc", "items")  # type: ignore[arg-type]


def test_unknown_tuple_field_label_is_bounded() -> None:
    with pytest.raises(ValueError, match=r"^value must be an array$") as excinfo:
        require_non_empty_tuple(123, "private_items")  # type: ignore[arg-type]
    assert "private_items" not in str(excinfo.value)


def test_contract_record_to_json_is_sorted_and_deterministic() -> None:
    record = ContractProbe(z_field="last", a_field={"b": 2.0, "a": 1.0})
    serialized = record.to_json()

    assert serialized == '{"a_field":{"a":1.0,"b":2.0},"z_field":"last"}'
    assert serialized.index("a_field") < serialized.index("z_field")
    assert serialized == record.to_json()


def test_contract_record_to_json_rejects_non_finite_float() -> None:
    record = ContractProbe(z_field="last", a_field={"secret_metric": float("inf")})

    with pytest.raises(ValueError, match=r"^contract record must be deterministic JSON$") as excinfo:
        record.to_json()

    message = str(excinfo.value)
    assert message == "contract record must be deterministic JSON"
    assert "secret_metric" not in message
    assert "Infinity" not in message
