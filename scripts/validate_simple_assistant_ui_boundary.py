#!/usr/bin/env python3
"""Validate the simple assistant UI boundary contract.

Purpose: keep normal-user assistant surfaces simple while preserving hidden
governance depth for operators, auditors, and developers.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: simple assistant UI boundary schema, foundation example, and
shared JSON Schema validation helper.
Invariants:
  - Normal-user statuses are allowlisted.
  - Internal proof and operator terms are hidden from normal-user copy.
  - Audit details are hidden by default but available by explicit detail link.
  - The projection grants no execution, connector mutation, external send, or
    system-of-record write authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_BOUNDARY = REPO_ROOT / "examples" / "simple_assistant_ui_boundary.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "simple_assistant_ui_boundary.schema.json"

REQUIRED_ALLOWED_STATUSES = frozenset(
    {
        "Ready",
        "Needs approval",
        "Blocked for safety",
        "Draft created",
        "Sent after approval",
        "Evidence saved",
    }
)
REQUIRED_ALLOWED_ACTIONS = frozenset({"Approve", "Reject", "Edit draft", "Cancel", "View audit details"})
REQUIRED_PROJECTION_FIELDS = frozenset(
    {
        "title",
        "status_label",
        "risk_label",
        "approval_required",
        "result_label",
        "evidence_label",
        "audit_details_available",
    }
)
REQUIRED_FORBIDDEN_TERMS = frozenset(
    {
        "proof matrix",
        "WHQR",
        "component lifecycle state",
        "receipt schema",
        "protocol manifest count",
        "operator evidence boundary",
        "temporal retention certificate hash",
    }
)


@dataclass(frozen=True, slots=True)
class SimpleAssistantUiBoundaryValidation:
    """Validation result for a simple assistant UI boundary document."""

    valid: bool
    boundary_path: str
    example_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_simple_assistant_ui_boundary(
    *,
    boundary_path: Path = DEFAULT_BOUNDARY,
    schema_path: Path = DEFAULT_SCHEMA,
) -> SimpleAssistantUiBoundaryValidation:
    """Validate the boundary schema conformance and semantic leak controls."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "simple assistant UI boundary schema", errors)
    boundary = _load_json_object(boundary_path, "simple assistant UI boundary", errors)
    assurance_outcome = ""

    if schema and boundary:
        errors.extend(_validate_schema_instance(schema, boundary))
    if boundary:
        assurance = _mapping(boundary.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_boundary_semantics(boundary))

    return SimpleAssistantUiBoundaryValidation(
        valid=not errors,
        boundary_path=_path_label(boundary_path),
        example_count=len(boundary.get("normal_user_examples", ())) if isinstance(boundary, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def _validate_boundary_semantics(boundary: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed_statuses = set(_string_sequence(boundary.get("normal_user_allowed_statuses")))
    allowed_actions = set(_string_sequence(boundary.get("normal_user_allowed_actions")))
    projection_fields = set(_string_sequence(boundary.get("normal_user_projection_fields")))
    forbidden_terms = set(_string_sequence(boundary.get("normal_user_forbidden_terms")))

    if allowed_statuses != REQUIRED_ALLOWED_STATUSES:
        errors.append(
            "normal_user_allowed_statuses must exactly match the approved simple status allowlist"
        )
    if allowed_actions != REQUIRED_ALLOWED_ACTIONS:
        errors.append("normal_user_allowed_actions must exactly match the approved action allowlist")
    if projection_fields != REQUIRED_PROJECTION_FIELDS:
        errors.append("normal_user_projection_fields must exactly match the simple projection fields")
    missing_forbidden_terms = REQUIRED_FORBIDDEN_TERMS - forbidden_terms
    if missing_forbidden_terms:
        errors.append(f"normal_user_forbidden_terms missing required terms: {sorted(missing_forbidden_terms)}")

    visibility_levels = _mapping_sequence(boundary.get("visibility_levels"))
    levels_by_audience = {str(level.get("audience")): level for level in visibility_levels}
    if set(levels_by_audience) != {"normal_user", "power_user_operator", "auditor_developer"}:
        errors.append("visibility_levels must define normal_user, power_user_operator, and auditor_developer")
    normal_user_level = _mapping(levels_by_audience.get("normal_user"))
    if normal_user_level.get("level") != 1:
        errors.append("normal_user visibility level must be level 1")

    audit_details = _mapping(boundary.get("audit_details"))
    if audit_details.get("default_visibility") != "hidden":
        errors.append("audit_details.default_visibility must be hidden")
    if audit_details.get("normal_user_default_hidden") is not True:
        errors.append("audit_details.normal_user_default_hidden must be true")
    if audit_details.get("detail_link_label") != "View audit details":
        errors.append("audit_details.detail_link_label must be View audit details")

    effect_boundary = _mapping(boundary.get("effect_boundary"))
    for field_name in (
        "execution_authority_granted",
        "connector_mutation_allowed",
        "external_send_allowed",
        "system_of_record_write_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            errors.append(f"effect_boundary.{field_name} must be false")
    if effect_boundary.get("projection_only") is not True:
        errors.append("effect_boundary.projection_only must be true")
    if effect_boundary.get("proof_details_hidden_by_default") is not True:
        errors.append("effect_boundary.proof_details_hidden_by_default must be true")
    if effect_boundary.get("operator_details_hidden_by_default") is not True:
        errors.append("effect_boundary.operator_details_hidden_by_default must be true")

    examples = _mapping_sequence(boundary.get("normal_user_examples"))
    for index, example in enumerate(examples):
        status_label = str(example.get("status_label", ""))
        if status_label not in REQUIRED_ALLOWED_STATUSES:
            errors.append(f"normal_user_examples[{index}].status_label is not allowlisted: {status_label}")
        buttons = set(_string_sequence(example.get("buttons")))
        if not buttons <= REQUIRED_ALLOWED_ACTIONS:
            errors.append(f"normal_user_examples[{index}].buttons contains unsupported actions")
        _scan_normal_user_copy(
            example,
            forbidden_terms=forbidden_terms,
            errors=errors,
            path=f"normal_user_examples[{index}]",
        )

    assurance = _mapping(boundary.get("assurance"))
    if assurance.get("normal_user_complexity_leak_detected") is not False:
        errors.append("assurance.normal_user_complexity_leak_detected must be false")
    if assurance.get("authority_drift_detected") is not False:
        errors.append("assurance.authority_drift_detected must be false")

    return errors


def _scan_normal_user_copy(
    value: Any,
    *,
    forbidden_terms: set[str],
    errors: list[str],
    path: str,
) -> None:
    if isinstance(value, str):
        lower_value = value.lower()
        for term in forbidden_terms:
            if term.lower() in lower_value:
                errors.append(f"{path}: normal-user copy leaks forbidden term {term!r}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            _scan_normal_user_copy(child, forbidden_terms=forbidden_terms, errors=errors, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_normal_user_copy(child, forbidden_terms=forbidden_terms, errors=errors, path=f"{path}[{index}]")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_sequence(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--json", action="store_true", help="Print validation result as JSON.")
    args = parser.parse_args()

    result = validate_simple_assistant_ui_boundary(boundary_path=args.boundary, schema_path=args.schema)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"simple assistant UI boundary ok: {result.example_count} normal-user examples")
    else:
        for error in result.errors:
            print(error)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
