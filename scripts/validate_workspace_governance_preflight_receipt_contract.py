#!/usr/bin/env python3
"""Validate workspace governance preflight receipt contract.

Purpose: verify that the preflight runner can build pass and fail receipts
that match the repository-local receipt schema.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library and scripts/run_workspace_governance_checks.py.
Invariants:
  - Validation is read-only.
  - Synthetic receipts do not invoke subprocess checks.
  - Receipt status must match check return-code outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from run_workspace_governance_checks import CheckResult, build_receipt
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.run_workspace_governance_checks import CheckResult, build_receipt


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "workspace_governance_preflight_receipt.schema.json"
REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "terminal_closure_required",
    "receipt_is_not_terminal_closure",
    "status",
    "check_count",
    "checks",
)
REQUIRED_CHECK_FIELDS = ("name", "args", "return_code", "passed", "stdout", "stderr")
ALLOWED_STATUSES = ("passed", "failed")


class PreflightReceiptContractError(ValueError):
    """Raised when the preflight receipt contract is invalid."""


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load the preflight receipt schema artifact."""

    if not schema_path.exists():
        raise FileNotFoundError(f"missing preflight receipt schema: {schema_path}")
    if not schema_path.is_file():
        raise IsADirectoryError(f"preflight receipt schema path is not a file: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise PreflightReceiptContractError("preflight receipt schema must be a JSON object")
    return schema


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("title") != "Workspace Governance Preflight Receipt":
        errors.append("schema title does not identify workspace governance preflight receipt")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")

    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    else:
        for field_name in REQUIRED_RECEIPT_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required receipt field: {field_name}")

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    else:
        for field_name in REQUIRED_RECEIPT_FIELDS:
            if field_name not in properties:
                errors.append(f"schema missing receipt property: {field_name}")

    check_required = schema.get("$defs", {}).get("check_result", {}).get("required", [])
    if not isinstance(check_required, list):
        errors.append("schema check_result.required must be a list")
    else:
        for field_name in REQUIRED_CHECK_FIELDS:
            if field_name not in check_required:
                errors.append(f"schema missing required check field: {field_name}")
    return errors


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one preflight receipt."""

    errors: list[str] = []
    for field_name in REQUIRED_RECEIPT_FIELDS:
        if field_name not in receipt:
            errors.append(f"receipt missing field: {field_name}")
    if errors:
        return errors

    if receipt["receipt_id"] != "workspace_governance_preflight_receipt":
        errors.append("receipt_id is invalid")
    if receipt["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    if receipt["receipt_is_not_terminal_closure"] is not True:
        errors.append("receipt_is_not_terminal_closure must be true")
    if receipt["status"] not in ALLOWED_STATUSES:
        errors.append(f"receipt status is invalid: {receipt['status']}")

    checks = receipt["checks"]
    if not isinstance(checks, list):
        errors.append("checks must be a list")
        return errors
    if receipt["check_count"] != len(checks):
        errors.append("check_count does not match checks length")

    observed_all_passed = True
    for index, check in enumerate(checks):
        errors.extend(_validate_check_result(check, index))
        if isinstance(check, dict) and check.get("passed") is not True:
            observed_all_passed = False
    expected_status = "passed" if observed_all_passed else "failed"
    if receipt["status"] != expected_status:
        errors.append(f"receipt status must be {expected_status} for observed check outcomes")
    return errors


def build_sample_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build synthetic pass and fail receipts without running subprocess checks."""

    passed_receipt = build_receipt(
        (
            CheckResult("synthetic_pass", ("python", "synthetic.py"), 0, "STATUS: passed\n", ""),
        )
    )
    failed_receipt = build_receipt(
        (
            CheckResult("synthetic_pass", ("python", "synthetic.py"), 0, "STATUS: passed\n", ""),
            CheckResult("synthetic_fail", ("python", "missing.py"), 2, "", "STATUS: failed\n"),
        )
    )
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
    """Validate the workspace governance preflight receipt contract."""

    parser = argparse.ArgumentParser(description="Validate workspace governance preflight receipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-contract: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] preflight-receipt-contract: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_schema\n")
    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_pass_shape\n")
    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_fail_shape\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


def _validate_check_result(check: Any, index: int) -> list[str]:
    if not isinstance(check, dict):
        return [f"check {index} must be an object"]
    errors: list[str] = []
    for field_name in REQUIRED_CHECK_FIELDS:
        if field_name not in check:
            errors.append(f"check {index} missing field: {field_name}")
    if errors:
        return errors
    if not isinstance(check["name"], str) or not check["name"]:
        errors.append(f"check {index} name must be a non-empty string")
    if not isinstance(check["args"], list) or not all(isinstance(arg, str) and arg for arg in check["args"]):
        errors.append(f"check {index} args must be a list of non-empty strings")
    if not isinstance(check["return_code"], int):
        errors.append(f"check {index} return_code must be integer")
    if not isinstance(check["passed"], bool):
        errors.append(f"check {index} passed must be boolean")
    if not isinstance(check["stdout"], str):
        errors.append(f"check {index} stdout must be string")
    if not isinstance(check["stderr"], str):
        errors.append(f"check {index} stderr must be string")
    if isinstance(check["return_code"], int) and isinstance(check["passed"], bool):
        expected_passed = check["return_code"] == 0
        if check["passed"] != expected_passed:
            errors.append(f"check {index} passed does not match return_code")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
