#!/usr/bin/env python3
"""Validate operator plan receipt bundle read models.

Purpose: prove cross-plan receipt bundles are schema-backed, count-consistent,
and read-only.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: operator plan receipt bundle schema and checked-in foundation example.
Invariants:
  - Bundle rows do not expose raw messages.
  - Bundle rows do not grant execution or write authority.
  - Summary and aggregate counts replay from embedded plan exports.
  - Missing command identifiers replay from embedded plan exports.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_plan_receipt_bundle_read_model.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "operator_plan_receipt_bundle_read_model.foundation.json"


@dataclass(frozen=True, slots=True)
class OperatorPlanReceiptBundleValidation:
    """Validation result for one operator plan receipt bundle read model."""

    valid: bool
    errors: tuple[str, ...]
    plan_export_count: int
    receipt_count: int


def validate_operator_plan_receipt_bundle_read_model(
    *,
    path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> OperatorPlanReceiptBundleValidation:
    """Validate one operator plan receipt bundle read model."""
    errors: list[str] = []
    payload = _load_json_object(path, "operator plan receipt bundle", errors)
    schema = _load_schema(schema_path)
    if payload:
        errors.extend(_validate_schema_instance(schema, payload))
        errors.extend(_semantic_errors(payload))
    return OperatorPlanReceiptBundleValidation(
        valid=not errors,
        errors=tuple(errors),
        plan_export_count=_bounded_int(payload.get("plan_export_count")) if payload else 0,
        receipt_count=_bounded_int(payload.get("receipt_count")) if payload else 0,
    )


def _semantic_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("raw_message_exposed") is not False:
        errors.append("raw_message_exposed must be false")
    if payload.get("execution_allowed") is not False:
        errors.append("execution_allowed must be false")
    if payload.get("write_allowed") is not False:
        errors.append("write_allowed must be false")
    plan_exports = _list_of_objects(payload.get("plan_exports"))
    summaries = _list_of_objects(payload.get("plan_export_summaries"))
    if payload.get("plan_export_count") != len(plan_exports):
        errors.append("plan_export_count must match plan_exports length")
    if payload.get("count") != len(plan_exports):
        errors.append("count must match plan_exports length")
    if len(summaries) != len(plan_exports):
        errors.append("plan_export_summaries length must match plan_exports length")
    expected_missing_ids: list[str] = []
    expected_receipt_count = 0
    expected_receipt_group_count = 0
    expected_step_command_count = 0
    expected_evidence_ref_count = 0
    expected_certified_count = 0
    expected_bundle_count = 0
    for index, export in enumerate(plan_exports):
        if export.get("raw_message_exposed") is not False:
            errors.append(f"plan_exports[{index}].raw_message_exposed must be false")
        if export.get("execution_allowed") is not False:
            errors.append(f"plan_exports[{index}].execution_allowed must be false")
        if export.get("write_allowed") is not False:
            errors.append(f"plan_exports[{index}].write_allowed must be false")
        expected_step_command_count += _bounded_int(export.get("step_command_count"))
        expected_receipt_group_count += _bounded_int(export.get("receipt_group_count"))
        expected_receipt_count += _bounded_int(export.get("receipt_count"))
        if export.get("status") == "certified":
            expected_certified_count += 1
        if export.get("evidence_bundle_available") is True:
            expected_bundle_count += 1
        expected_missing_ids.extend(_text_list(export.get("missing_step_command_ids")))
        evidence_bundle = export.get("plan_evidence_bundle")
        if isinstance(evidence_bundle, Mapping):
            expected_evidence_ref_count += len(_text_list(evidence_bundle.get("evidence_refs")))
    aggregate_expectations = {
        "certified_export_count": expected_certified_count,
        "evidence_bundle_count": expected_bundle_count,
        "step_command_count": expected_step_command_count,
        "receipt_group_count": expected_receipt_group_count,
        "receipt_count": expected_receipt_count,
        "evidence_ref_count": expected_evidence_ref_count,
    }
    for key, expected in aggregate_expectations.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must replay from plan_exports")
    if _text_list(payload.get("missing_step_command_ids")) != expected_missing_ids:
        errors.append("missing_step_command_ids must replay from plan_exports")
    for index, summary in enumerate(summaries):
        export = plan_exports[index] if index < len(plan_exports) else {}
        evidence_bundle = export.get("plan_evidence_bundle") if isinstance(export, Mapping) else None
        evidence_ref_count = (
            len(_text_list(evidence_bundle.get("evidence_refs")))
            if isinstance(evidence_bundle, Mapping)
            else 0
        )
        summary_expectations = {
            "plan_id": export.get("plan_id"),
            "status": export.get("status"),
            "evidence_bundle_available": export.get("evidence_bundle_available") is True,
            "step_command_count": _bounded_int(export.get("step_command_count")),
            "receipt_group_count": _bounded_int(export.get("receipt_group_count")),
            "receipt_count": _bounded_int(export.get("receipt_count")),
            "evidence_ref_count": evidence_ref_count,
            "missing_step_command_count": len(_text_list(export.get("missing_step_command_ids"))),
        }
        for key, expected in summary_expectations.items():
            if summary.get(key) != expected:
                errors.append(f"plan_export_summaries[{index}].{key} must replay from plan_exports")
    return errors


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} failed to load: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return parsed


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bounded_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def main(argv: list[str] | None = None) -> int:
    """Run operator plan receipt bundle read-model validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args(argv)
    result = validate_operator_plan_receipt_bundle_read_model(
        path=args.path,
        schema_path=args.schema,
    )
    if result.valid:
        print(
            "[PASS] operator_plan_receipt_bundle_read_model "
            f"plans={result.plan_export_count} receipts={result.receipt_count}"
        )
        print("STATUS: passed")
        return 0
    for error in result.errors:
        print(f"[FAIL] {error}")
    print("STATUS: failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
