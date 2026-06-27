#!/usr/bin/env python3
"""Validate the capability debt report.

Purpose: prove capability governance gaps are projected into one operator
next-action debt row per capability.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/capability_debt_report.schema.json,
examples/capability_debt_report.foundation.json, capability passports,
evidence passports, and sandbox-to-live promotion paths.
Invariants:
  - Every capability passport has exactly one debt row.
  - Debt reports are read models and never execution authority.
  - Summary counters match the projected debt rows.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.capability_debt_report import build_capability_debt_report  # noqa: E402
from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_debt_report.schema.json"
DEFAULT_DEBT_REPORT = REPO_ROOT / "examples" / "capability_debt_report.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_debt_report_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "capability_debt_report_validator": "python scripts/validate_capability_debt_report.py",
    "capability_debt_report_tests": "python -m pytest tests/test_validate_capability_debt_report.py -q",
}
DEBT_CATEGORIES = ("evidence", "approval", "rollback", "replay", "promotion", "live_action")
SEVERITIES = ("critical", "high", "medium", "low")


@dataclass(frozen=True, slots=True)
class CapabilityDebtReportValidation:
    """Validation report for capability debt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    debt_report_path: str
    debt_row_count: int
    capability_count: int
    total_debt_item_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_debt_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    debt_report_path: Path = DEFAULT_DEBT_REPORT,
) -> CapabilityDebtReportValidation:
    """Validate the capability debt report against runtime projections."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "capability debt report schema", errors)
    debt_report = _load_json_object(debt_report_path, "capability debt report example", errors)
    runtime_debt_report = build_capability_debt_report() if not errors else {}
    runtime_passports = build_capability_passports() if not errors else {}

    if schema and debt_report:
        errors.extend(f"{_path_label(debt_report_path)}: {error}" for error in _validate_schema_instance(schema, debt_report))
        if debt_report != runtime_debt_report:
            errors.append(f"{_path_label(debt_report_path)}: example does not match runtime projection")
    if debt_report:
        _validate_debt_report(debt_report, runtime_passports, errors, _path_label(debt_report_path))

    summary = debt_report.get("summary", {}) if isinstance(debt_report, dict) else {}
    rows = debt_report.get("debt_rows", ()) if isinstance(debt_report, dict) else ()
    runtime_entries = runtime_passports.get("passports", ()) if isinstance(runtime_passports, dict) else ()
    return CapabilityDebtReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        debt_report_path=_path_label(debt_report_path),
        debt_row_count=len(rows) if isinstance(rows, list) else 0,
        capability_count=len(runtime_entries) if isinstance(runtime_entries, list) else 0,
        total_debt_item_count=int(summary.get("total_debt_item_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_capability_debt_report_validation(
    validation: CapabilityDebtReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic capability debt validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_debt_report(
    debt_report: dict[str, Any],
    runtime_passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if debt_report.get("debt_report_is_not_execution_authority") is not True:
        errors.append(f"{label}: debt_report_is_not_execution_authority must be true")
    if debt_report.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    _validate_validators(debt_report, errors, label)

    rows = _list_of_objects(debt_report.get("debt_rows"))
    passport_entries = _list_of_objects(runtime_passports.get("passports"))
    row_by_capability: dict[str, dict[str, Any]] = {}
    for row in rows:
        capability_id = str(row.get("capability_id", ""))
        if capability_id in row_by_capability:
            errors.append(f"{label}: duplicate debt row for {capability_id}")
        row_by_capability[capability_id] = row
        _validate_debt_row(row, errors, label)

    passport_ids = {str(passport.get("capability_id", "")) for passport in passport_entries}
    row_ids = set(row_by_capability)
    missing = sorted(passport_ids - row_ids)
    extra = sorted(row_ids - passport_ids)
    if missing:
        errors.append(f"{label}: registered capabilities missing debt rows {missing}")
    if extra:
        errors.append(f"{label}: debt rows for unknown capabilities {extra}")
    _validate_summary(debt_report, rows, passport_entries, errors, label)
    _validate_top_debt_items(debt_report, rows, errors, label)


def _validate_debt_row(row: dict[str, Any], errors: list[str], label: str) -> None:
    capability_id = str(row.get("capability_id", "<missing>"))
    if row.get("debt_row_is_not_execution_authority") is not True:
        errors.append(f"{label}: {capability_id} debt_row_is_not_execution_authority must be true")
    if row.get("live_action_enabled") is not False:
        errors.append(f"{label}: {capability_id} live_action_enabled must be false")
    debt_items = _list_of_objects(row.get("debt_items"))
    if row.get("debt_item_count") != len(debt_items):
        errors.append(f"{label}: {capability_id} debt_item_count must match debt_items")
    if debt_items and row.get("debt_severity") != _highest_severity(debt_items):
        errors.append(f"{label}: {capability_id} debt_severity must match highest item severity")
    if not str(row.get("next_action", "")).strip():
        errors.append(f"{label}: {capability_id} next_action must be non-empty")
    for item in debt_items:
        _validate_debt_item(item, capability_id, errors, label)


def _validate_debt_item(
    item: Mapping[str, Any],
    capability_id: str,
    errors: list[str],
    label: str,
) -> None:
    category = item.get("category")
    severity = item.get("severity")
    if category not in DEBT_CATEGORIES:
        errors.append(f"{label}: {capability_id} debt item category invalid")
    if severity not in SEVERITIES:
        errors.append(f"{label}: {capability_id} debt item severity invalid")
    if not _string_list(item.get("missing_refs")):
        errors.append(f"{label}: {capability_id} debt item missing_refs must be non-empty")
    if not str(item.get("fix", "")).strip():
        errors.append(f"{label}: {capability_id} debt item fix must be non-empty")


def _validate_summary(
    debt_report: Mapping[str, Any],
    rows: list[dict[str, Any]],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    summary = debt_report.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if summary.get("capability_count") != len(passport_entries):
        errors.append(f"{label}: summary.capability_count must match runtime capabilities")
    if summary.get("debt_row_count") != len(rows):
        errors.append(f"{label}: summary.debt_row_count must match debt rows")
    expected_total = sum(int(row.get("debt_item_count", 0)) for row in rows)
    if summary.get("total_debt_item_count") != expected_total:
        errors.append(f"{label}: summary.total_debt_item_count must match debt rows")
    if summary.get("capabilities_with_debt_count") != sum(1 for row in rows if int(row.get("debt_item_count", 0)) > 0):
        errors.append(f"{label}: summary.capabilities_with_debt_count must match debt rows")
    if summary.get("live_action_enabled_count") != 0:
        errors.append(f"{label}: summary.live_action_enabled_count must be zero")
    expected_categories = _category_counts(rows)
    if summary.get("category_counts") != expected_categories:
        errors.append(f"{label}: summary.category_counts must match debt rows")
    expected_severities = {severity: sum(1 for row in rows if row.get("debt_severity") == severity) for severity in SEVERITIES}
    if summary.get("severity_counts") != expected_severities:
        errors.append(f"{label}: summary.severity_counts must match debt rows")


def _validate_top_debt_items(
    debt_report: Mapping[str, Any],
    rows: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    top_items = _list_of_objects(debt_report.get("top_debt_items"))
    expected = _sorted_debt_items(rows)[:25]
    if top_items != expected:
        errors.append(f"{label}: top_debt_items must contain first 25 sorted debt items")


def _validate_validators(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = payload.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _sorted_debt_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        for item in _list_of_objects(row.get("debt_items")):
            items.append({
                "capability_id": row["capability_id"],
                "family": row["family"],
                **item,
            })
    return sorted(
        items,
        key=lambda item: (
            SEVERITIES.index(str(item["severity"])),
            str(item["category"]),
            str(item.get("capability_id", "")),
            str(item["debt_id"]),
        ),
    )


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {category: 0 for category in DEBT_CATEGORIES}
    for row in rows:
        for item in _list_of_objects(row.get("debt_items")):
            counts[str(item.get("category"))] += 1
    return counts


def _highest_severity(debt_items: list[dict[str, Any]]) -> str:
    return sorted((str(item["severity"]) for item in debt_items), key=SEVERITIES.index)[0]


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capability debt report validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability debt report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--debt-report", default=str(DEFAULT_DEBT_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for capability debt report validation."""

    args = parse_args(argv)
    validation = validate_capability_debt_report(
        schema_path=Path(args.schema),
        debt_report_path=Path(args.debt_report),
    )
    write_capability_debt_report_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY DEBT REPORT VALID")
    else:
        print(f"CAPABILITY DEBT REPORT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
