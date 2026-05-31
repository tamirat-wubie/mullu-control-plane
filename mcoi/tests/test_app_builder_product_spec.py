"""Tests for app-builder product specification admission.

Purpose: verify mapping-shaped product payloads become strict ProductSpec
contracts before architecture planning or task graph generation.
Governance scope: product-intent ingress, explicit field typing, metadata
shape validation, and no silent scalar coercion.
Dependencies: pytest and mcoi_runtime.core.app_builder.product_spec.
Invariants: required product fields are present, app names are text, list
fields contain strings, and metadata remains mapping-shaped.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.app_builder.product_spec import product_spec_from_mapping


def _valid_payload() -> dict[str, object]:
    return {
        "app_name": "Operator Console",
        "users": ["operator", "reviewer"],
        "jobs_to_be_done": ["inspect runtime posture"],
        "core_flows": ["open dashboard", "review health"],
        "non_goals": ["direct deployment"],
        "security_requirements": ["read-only by default"],
        "metadata": {"source": "test"},
    }


def test_product_spec_from_mapping_accepts_valid_payload() -> None:
    product_spec = product_spec_from_mapping(_valid_payload())

    assert product_spec.app_name == "Operator Console"
    assert product_spec.users == ("operator", "reviewer")
    assert product_spec.metadata["source"] == "test"


def test_product_spec_from_mapping_rejects_non_string_app_name() -> None:
    payload = _valid_payload()
    payload["app_name"] = 1001

    with pytest.raises(ValueError, match="app_name must be a string"):
        product_spec_from_mapping(payload)

    assert payload["app_name"] == 1001
    assert payload["users"] == ["operator", "reviewer"]


def test_product_spec_from_mapping_rejects_blank_app_name() -> None:
    payload = _valid_payload()
    payload["app_name"] = "   "

    with pytest.raises(ValueError, match="app_name must be non-empty"):
        product_spec_from_mapping(payload)

    assert payload["app_name"] == "   "
    assert payload["metadata"] == {"source": "test"}


def test_product_spec_from_mapping_rejects_non_mapping_metadata() -> None:
    payload = _valid_payload()
    payload["metadata"] = ["source", "test"]

    with pytest.raises(ValueError, match="metadata must be a mapping"):
        product_spec_from_mapping(payload)

    assert payload["metadata"] == ["source", "test"]
    assert payload["app_name"] == "Operator Console"


def test_product_spec_from_mapping_rejects_non_string_sequence_items() -> None:
    payload = _valid_payload()
    payload["core_flows"] = ["open dashboard", 42]

    with pytest.raises(ValueError, match=r"core_flows\[1\] must be a string"):
        product_spec_from_mapping(payload)

    assert payload["core_flows"] == ["open dashboard", 42]
    assert payload["security_requirements"] == ["read-only by default"]
