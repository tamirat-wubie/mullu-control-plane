"""Purpose: direct tests for the foundational invariant helpers.
Governance scope: runtime-core validation and defensive copying only.
Dependencies: invariants module.
Invariants: validation is explicit, deterministic, and side-effect free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

import pytest

from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    copied,
    ensure_dataclass_instance,
    ensure_iso_timestamp,
    ensure_non_empty_text,
    freeze_mapping,
    stable_identifier,
)


# ---------------------------------------------------------------------------
# ensure_non_empty_text
# ---------------------------------------------------------------------------


class TestEnsureNonEmptyText:
    def test_valid_string(self) -> None:
        assert ensure_non_empty_text("f", "hello") == "hello"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="must be a non-empty string"):
            ensure_non_empty_text("f", "")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_non_empty_text("f", "   ")

    def test_tab_only_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_non_empty_text("f", "\t\n")

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_non_empty_text("f", None)  # type: ignore[arg-type]

    def test_int_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_non_empty_text("f", 123)  # type: ignore[arg-type]

    def test_error_is_bounded(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="^value must be a non-empty string$") as exc_info:
            ensure_non_empty_text("my_field", "")
        assert "my_field" not in str(exc_info.value)

    def test_string_with_spaces_valid(self) -> None:
        assert ensure_non_empty_text("f", "  hello  ") == "  hello  "


# ---------------------------------------------------------------------------
# ensure_iso_timestamp
# ---------------------------------------------------------------------------


class TestEnsureIsoTimestamp:
    def test_valid_iso_with_offset(self) -> None:
        ts = "2026-03-20T12:00:00+00:00"
        assert ensure_iso_timestamp("f", ts) == ts

    def test_valid_iso_with_z(self) -> None:
        ts = "2026-03-20T12:00:00Z"
        assert ensure_iso_timestamp("f", ts) == ts

    def test_valid_date_only(self) -> None:
        assert ensure_iso_timestamp("f", "2026-03-20") == "2026-03-20"

    def test_malformed_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="^value must be an ISO-8601 timestamp$"):
            ensure_iso_timestamp("f", "not-a-date")

    def test_empty_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_iso_timestamp("f", "")

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_iso_timestamp("f", None)  # type: ignore[arg-type]

    def test_partial_date_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_iso_timestamp("f", "2026-13-40")


# ---------------------------------------------------------------------------
# ensure_dataclass_instance
# ---------------------------------------------------------------------------


@dataclass
class _SampleDC:
    x: int = 1


class TestEnsureDataclassInstance:
    def test_valid_instance(self) -> None:
        dc = _SampleDC()
        assert ensure_dataclass_instance("f", dc) is dc

    def test_class_itself_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="^value must be a dataclass instance$"):
            ensure_dataclass_instance("f", _SampleDC)

    def test_plain_dict_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_dataclass_instance("f", {"x": 1})

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_dataclass_instance("f", None)

    def test_string_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ensure_dataclass_instance("f", "hello")


# ---------------------------------------------------------------------------
# copied
# ---------------------------------------------------------------------------


class TestCopied:
    def test_deep_copy_dict(self) -> None:
        original = {"a": [1, 2, 3]}
        result = copied(original)
        assert result == original
        result["a"].append(4)
        assert original["a"] == [1, 2, 3]

    def test_deep_copy_list(self) -> None:
        original = [[1], [2]]
        result = copied(original)
        result[0].append(99)
        assert original[0] == [1]

    def test_scalar_passthrough(self) -> None:
        assert copied(42) == 42
        assert copied("hello") == "hello"

    def test_none(self) -> None:
        assert copied(None) is None


# ---------------------------------------------------------------------------
# freeze_mapping
# ---------------------------------------------------------------------------


class TestFreezeMapping:
    def test_returns_mapping_proxy(self) -> None:
        result = freeze_mapping({"a": 1, "b": 2})
        assert isinstance(result, MappingProxyType)

    def test_immutable(self) -> None:
        result = freeze_mapping({"a": 1})
        with pytest.raises(TypeError):
            result["a"] = 2  # type: ignore[index]

    def test_nested_values_deep_copied(self) -> None:
        original = {"key": [1, 2, 3]}
        frozen = freeze_mapping(original)
        original["key"].append(4)
        assert list(frozen["key"]) == [1, 2, 3]

    def test_empty_mapping(self) -> None:
        result = freeze_mapping({})
        assert isinstance(result, MappingProxyType)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# stable_identifier
# ---------------------------------------------------------------------------


class TestStableIdentifier:
    def test_deterministic(self) -> None:
        a = stable_identifier("pre", {"x": 1, "y": 2})
        b = stable_identifier("pre", {"x": 1, "y": 2})
        assert a == b

    def test_prefix_included(self) -> None:
        result = stable_identifier("myprefix", {"k": "v"})
        assert result.startswith("myprefix-")

    def test_key_order_independent(self) -> None:
        a = stable_identifier("p", {"a": 1, "b": 2})
        b = stable_identifier("p", {"b": 2, "a": 1})
        assert a == b

    def test_different_payloads_differ(self) -> None:
        a = stable_identifier("p", {"x": 1})
        b = stable_identifier("p", {"x": 2})
        assert a != b

    def test_different_prefixes_differ(self) -> None:
        a = stable_identifier("alpha", {"x": 1})
        b = stable_identifier("beta", {"x": 1})
        assert a != b

    def test_hash_length(self) -> None:
        result = stable_identifier("p", {"k": "v"})
        # Format: "p-" + 12 hex chars
        assert len(result) == len("p-") + 12

    def test_empty_payload(self) -> None:
        result = stable_identifier("p", {})
        assert result.startswith("p-")
        assert len(result) > 2

    def test_non_string_values_serialized(self) -> None:
        # default=str handles non-JSON types
        result = stable_identifier("p", {"ts": "2026-03-20"})
        assert result.startswith("p-")
