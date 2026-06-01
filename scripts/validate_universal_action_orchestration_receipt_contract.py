#!/usr/bin/env python3
"""Validate the Universal Action Orchestration validation receipt contract.

Purpose: verify that UAO validation emits pass and fail receipts matching the
repository-local receipt schema.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library and scripts/validate_universal_action_orchestration.py.
Invariants:
  - Validation is read-only.
  - The receipt is not terminal closure evidence.
  - Receipt paths are workspace-relative labels or external basenames only.
  - Receipt status, counts, and check outcomes remain causally consistent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from validate_universal_action_orchestration import build_validation_report
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.validate_universal_action_orchestration import build_validation_report


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "universal_action_orchestration_validation_receipt.schema.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:universal-action-orchestration-validation-receipt:1"
EXPECTED_SCHEMA_TITLE = "Universal Action Orchestration Validation Receipt"
EXPECTED_RECEIPT_ID = "universal_action_orchestration_validation_receipt"
REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "terminal_closure_required",
    "receipt_is_not_terminal_closure",
    "valid",
    "status",
    "schema_path",
    "document_path",
    "example_paths",
    "example_count",
    "checks",
    "check_count",
    "error_count",
    "errors",
)
REQUIRED_CHECK_FIELDS = ("name", "passed")
EXPECTED_CHECK_NAMES = (
    "universal_action_orchestration_schema",
    "universal_action_orchestration_examples",
    "universal_action_orchestration_document",
    "universal_action_orchestration_no_bypass",
    "universal_action_orchestration_receipts",
)
ALLOWED_STATUSES = ("passed", "failed")
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"[A-Za-z]:[/\\]")


class UaoValidationReceiptContractError(ValueError):
    """Raised when the UAO validation receipt contract is invalid."""


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load the UAO validation receipt schema artifact."""

    if not schema_path.exists():
        raise FileNotFoundError(f"missing UAO validation receipt schema: {schema_path}")
    if not schema_path.is_file():
        raise IsADirectoryError(f"UAO validation receipt schema path is not a file: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise UaoValidationReceiptContractError("UAO validation receipt schema must be a JSON object")
    return schema


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title does not identify UAO validation receipt")
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")

    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in REQUIRED_RECEIPT_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required receipt field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing receipt property: {field_name}")

    check_result = schema.get("$defs", {}).get("check_result")
    if not isinstance(check_result, dict):
        errors.append("schema missing check_result definition")
        return errors
    if check_result.get("additionalProperties") is not False:
        errors.append("schema check_result must close additional properties")
    check_required = check_result.get("required")
    check_properties = check_result.get("properties")
    if not isinstance(check_required, list):
        errors.append("schema check_result.required must be a list")
    if not isinstance(check_properties, dict):
        errors.append("schema check_result.properties must be an object")
    if isinstance(check_required, list) and isinstance(check_properties, dict):
        for field_name in REQUIRED_CHECK_FIELDS:
            if field_name not in check_required:
                errors.append(f"schema missing required check field: {field_name}")
            if field_name not in check_properties:
                errors.append(f"schema missing check property: {field_name}")
    return errors


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one UAO validation receipt."""

    errors: list[str] = []
    for field_name in REQUIRED_RECEIPT_FIELDS:
        if field_name not in receipt:
            errors.append(f"receipt missing field: {field_name}")
    extra_fields = sorted(set(receipt) - set(REQUIRED_RECEIPT_FIELDS))
    for field_name in extra_fields:
        errors.append(f"receipt has unexpected field: {field_name}")
    if errors:
        return errors

    if receipt["receipt_id"] != EXPECTED_RECEIPT_ID:
        errors.append("receipt_id is invalid")
    if receipt["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    if receipt["receipt_is_not_terminal_closure"] is not True:
        errors.append("receipt_is_not_terminal_closure must be true")
    if not isinstance(receipt["valid"], bool):
        errors.append("valid must be boolean")
    if receipt["status"] not in ALLOWED_STATUSES:
        errors.append(f"receipt status is invalid: {receipt['status']}")
    elif isinstance(receipt["valid"], bool):
        expected_status = "passed" if receipt["valid"] else "failed"
        if receipt["status"] != expected_status:
            errors.append(f"receipt status must be {expected_status} for valid={receipt['valid']}")

    errors.extend(_validate_safe_path_label("schema_path", receipt["schema_path"]))
    errors.extend(_validate_safe_path_label("document_path", receipt["document_path"]))
    errors.extend(_validate_path_label_array("example_paths", receipt["example_paths"]))
    errors.extend(_validate_checks(receipt["checks"]))
    errors.extend(_validate_errors(receipt["errors"]))

    if not isinstance(receipt["example_count"], int) or isinstance(receipt["example_count"], bool):
        errors.append("example_count must be integer")
    elif isinstance(receipt["example_paths"], list) and receipt["example_count"] != len(receipt["example_paths"]):
        errors.append("example_count does not match example_paths length")
    if not isinstance(receipt["check_count"], int) or isinstance(receipt["check_count"], bool):
        errors.append("check_count must be integer")
    elif isinstance(receipt["checks"], list) and receipt["check_count"] != len(receipt["checks"]):
        errors.append("check_count does not match checks length")
    if not isinstance(receipt["error_count"], int) or isinstance(receipt["error_count"], bool):
        errors.append("error_count must be integer")
    elif isinstance(receipt["errors"], list) and receipt["error_count"] != len(receipt["errors"]):
        errors.append("error_count does not match errors length")

    if isinstance(receipt["checks"], list) and isinstance(receipt["valid"], bool):
        observed_all_passed = all(isinstance(check, dict) and check.get("passed") is True for check in receipt["checks"])
        if observed_all_passed != receipt["valid"]:
            errors.append("valid must match aggregate check outcomes")
    if receipt["status"] == "passed" and receipt["errors"]:
        errors.append("passed receipt must not carry errors")
    if receipt["status"] == "failed" and not receipt["errors"]:
        errors.append("failed receipt must carry at least one error")
    return errors


def build_sample_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build synthetic pass and fail receipts without executing UAO actions."""

    passed_receipt = build_validation_report()
    failed_receipt = build_validation_report(schema_path=WORKSPACE_ROOT / "missing.schema.json")
    return passed_receipt, failed_receipt


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema artifact and synthetic receipt behavior."""

    schema = load_schema(schema_path)
    errors = validate_schema_artifact(schema)
    passed_receipt, failed_receipt = build_sample_receipts()
    errors.extend(f"passed receipt: {error}" for error in validate_receipt(passed_receipt))
    errors.extend(f"failed receipt: {error}" for error in validate_receipt(failed_receipt))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the UAO validation receipt contract."""

    parser = argparse.ArgumentParser(description="Validate Universal Action Orchestration validation receipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-contract: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] universal-action-orchestration-validation-receipt: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_schema\n")
    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_pass_shape\n")
    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_fail_shape\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


def _validate_safe_path_label(label: str, value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{label} must be a non-empty string"]
    errors: list[str] = []
    if "\\" in value or WINDOWS_ABSOLUTE_PATH_PATTERN.search(value) or value.startswith("/"):
        errors.append(f"{label} must not contain a host-local absolute path")
    if any(segment == ".." for segment in value.split("/")):
        errors.append(f"{label} must not contain parent-directory traversal")
    return errors


def _validate_path_label_array(label: str, values: Any) -> list[str]:
    if not isinstance(values, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    if len(set(values)) != len(values):
        errors.append(f"{label} must not contain duplicates")
    for index, value in enumerate(values):
        errors.extend(_validate_safe_path_label(f"{label}[{index}]", value))
    return errors


def _validate_checks(checks: Any) -> list[str]:
    if not isinstance(checks, list):
        return ["checks must be a list"]
    errors: list[str] = []
    observed_names: list[str] = []
    for index, check in enumerate(checks):
        label = f"checks[{index}]"
        if not isinstance(check, dict):
            errors.append(f"{label} must be an object")
            continue
        for field_name in REQUIRED_CHECK_FIELDS:
            if field_name not in check:
                errors.append(f"{label} missing field: {field_name}")
        extra_fields = sorted(set(check) - set(REQUIRED_CHECK_FIELDS))
        for field_name in extra_fields:
            errors.append(f"{label} has unexpected field: {field_name}")
        if "name" in check:
            if check["name"] not in EXPECTED_CHECK_NAMES:
                errors.append(f"{label}.name is invalid")
            else:
                observed_names.append(check["name"])
        if "passed" in check and not isinstance(check["passed"], bool):
            errors.append(f"{label}.passed must be boolean")
    if tuple(observed_names) != EXPECTED_CHECK_NAMES:
        errors.append("checks must preserve the canonical UAO validation check order")
    return errors


def _validate_errors(errors_value: Any) -> list[str]:
    if not isinstance(errors_value, list):
        return ["errors must be a list"]
    errors: list[str] = []
    workspace_root_text = str(WORKSPACE_ROOT.resolve())
    for index, error in enumerate(errors_value):
        label = f"errors[{index}]"
        if not isinstance(error, str):
            errors.append(f"{label} must be string")
            continue
        if workspace_root_text in error or "\\" in error or WINDOWS_ABSOLUTE_PATH_PATTERN.search(error):
            errors.append(f"{label} must not contain a host-local absolute path")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
