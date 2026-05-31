"""Purpose: normalize product inputs into app-builder ProductSpec contracts.
Governance scope: declarative product-intent admission before architecture
    planning, task graph generation, or software-change request emission.
Dependencies: mapping types and app-builder contract records.
Invariants:
  - Required product fields are explicit and non-empty.
  - Source payload keys map deterministically to ProductSpec fields.
  - No code generation, patching, commit, or deployment occurs in this module.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.app_builder import ProductSpec


_REQUIRED_PRODUCT_FIELDS = frozenset({"app_name", "users", "jobs_to_be_done", "core_flows", "non_goals", "security_requirements"})


def product_spec_from_mapping(payload: Mapping[str, Any]) -> ProductSpec:
    """Build a ProductSpec from a mapping-shaped operator or API payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    missing = tuple(sorted(field for field in _REQUIRED_PRODUCT_FIELDS if field not in payload))
    if missing:
        raise ValueError(f"product_spec_fields_missing:{','.join(missing)}")
    return ProductSpec(
        app_name=_required_text(payload["app_name"], "app_name"),
        users=_tuple_from_payload(payload["users"], "users"),
        jobs_to_be_done=_tuple_from_payload(payload["jobs_to_be_done"], "jobs_to_be_done"),
        core_flows=_tuple_from_payload(payload["core_flows"], "core_flows"),
        non_goals=_tuple_from_payload(payload["non_goals"], "non_goals"),
        security_requirements=_tuple_from_payload(payload["security_requirements"], "security_requirements"),
        metadata=_metadata_from_payload(payload.get("metadata")),
    )


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _tuple_from_payload(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise ValueError(f"{field_name} must be a sequence of strings")
    try:
        items = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a sequence of strings") from exc
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
    return items


def _metadata_from_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a mapping")
    return dict(value)
