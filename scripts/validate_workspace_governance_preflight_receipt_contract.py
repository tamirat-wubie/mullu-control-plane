#!/usr/bin/env python3
"""Validate workspace governance preflight receipt contract.

Purpose: verify that the preflight runner can build pass and fail receipts
that match the repository-local receipt schema.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library and scripts/run_workspace_governance_checks.py.
Invariants:
  - Validation is read-only.
  - Synthetic receipts do not invoke subprocess checks.
  - Receipt replay rejects fields outside the schema surface.
  - Receipt status must match check return-code outcomes.
  - Full preflight receipts carry the canonical required check order and command tails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from run_workspace_governance_checks import CheckResult, build_check_commands, build_receipt
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.run_workspace_governance_checks import CheckResult, build_check_commands, build_receipt


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "workspace_governance_preflight_receipt.schema.json"
REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "terminal_closure_required",
    "receipt_is_not_terminal_closure",
    "status",
    "generated_at_epoch",
    "check_count",
    "checks",
)
REQUIRED_CHECK_FIELDS = ("name", "args", "return_code", "passed", "stdout", "stderr")
OPTIONAL_CHECK_FIELDS = ("termination_reason", "termination_signal")
ALLOWED_TERMINATION_REASONS = ("completed", "exception", "timeout", "terminated")
ALLOWED_STATUSES = ("passed", "failed")
REQUIRED_PREFLIGHT_CHECK_NAMES = tuple(command.name for command in build_check_commands("python"))
REQUIRED_PREFLIGHT_COMMAND_TAILS_BY_NAME = {
    command.name: tuple(command.args[1:]) for command in build_check_commands("python")
}


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

    check_definition = schema.get("$defs", {}).get("check_result", {})
    if not isinstance(check_definition, dict):
        errors.append("schema check_result definition must be an object")
        return errors

    check_required = check_definition.get("required", [])
    if not isinstance(check_required, list):
        errors.append("schema check_result.required must be a list")
    else:
        for field_name in REQUIRED_CHECK_FIELDS:
            if field_name not in check_required:
                errors.append(f"schema missing required check field: {field_name}")

    check_properties = check_definition.get("properties")
    if not isinstance(check_properties, dict):
        errors.append("schema check_result.properties must be an object")
        return errors
    for field_name in OPTIONAL_CHECK_FIELDS:
        if field_name not in check_properties:
            errors.append(f"schema missing optional check property: {field_name}")
    check_name = check_properties.get("name")
    if not isinstance(check_name, dict):
        errors.append("schema check_result.name must be an object")
        return errors
    check_name_enum = check_name.get("enum")
    if not isinstance(check_name_enum, list):
        errors.append("schema check_result.name.enum must be a list")
    elif tuple(check_name_enum) != REQUIRED_PREFLIGHT_CHECK_NAMES:
        errors.append("schema check_result.name.enum must match canonical preflight check order")
    return errors


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one preflight receipt."""

    errors: list[str] = []
    missing_fields: list[str] = []
    for field_name in REQUIRED_RECEIPT_FIELDS:
        if field_name not in receipt:
            missing_fields.append(f"receipt missing field: {field_name}")
    errors.extend(missing_fields)
    extra_fields = sorted(set(receipt) - set(REQUIRED_RECEIPT_FIELDS))
    for field_name in extra_fields:
        errors.append(f"receipt has unexpected field: {field_name}")
    if missing_fields:
        return errors

    if receipt["receipt_id"] != "workspace_governance_preflight_receipt":
        errors.append("receipt_id is invalid")
    if receipt["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    if receipt["receipt_is_not_terminal_closure"] is not True:
        errors.append("receipt_is_not_terminal_closure must be true")
    if receipt["status"] not in ALLOWED_STATUSES:
        errors.append(f"receipt status is invalid: {receipt['status']}")
    if (
        isinstance(receipt["generated_at_epoch"], bool)
        or not isinstance(receipt["generated_at_epoch"], (int, float))
        or receipt["generated_at_epoch"] <= 0
    ):
        errors.append("generated_at_epoch must be a positive epoch timestamp")

    checks = receipt["checks"]
    if not isinstance(checks, list):
        errors.append("checks must be a list")
        return errors
    if isinstance(receipt["check_count"], bool) or not isinstance(receipt["check_count"], int):
        errors.append("check_count must be integer")
    elif receipt["check_count"] != len(checks):
        errors.append("check_count does not match checks length")

    observed_all_passed = True
    observed_names: list[str] = []
    for index, check in enumerate(checks):
        errors.extend(_validate_check_result(check, index))
        if isinstance(check, dict) and isinstance(check.get("name"), str):
            observed_names.append(check["name"])
        if isinstance(check, dict) and check.get("passed") is not True:
            observed_all_passed = False
    if len(set(observed_names)) != len(observed_names):
        errors.append("checks must not contain duplicate names")
    if tuple(observed_names) != REQUIRED_PREFLIGHT_CHECK_NAMES:
        errors.append("checks must preserve the canonical workspace governance check order")
    missing_names = [name for name in REQUIRED_PREFLIGHT_CHECK_NAMES if name not in set(observed_names)]
    if missing_names:
        errors.append(f"receipt missing required preflight check(s): {', '.join(missing_names)}")
    expected_status = "passed" if observed_all_passed else "failed"
    if receipt["status"] != expected_status:
        errors.append(f"receipt status must be {expected_status} for observed check outcomes")
    return errors


def build_sample_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build synthetic pass and fail receipts without running subprocess checks."""

    passed_receipt = build_receipt(_build_synthetic_check_results())
    failed_receipt = build_receipt(
        _build_synthetic_check_results(failing_check_name="universal_action_orchestration_validation_receipt_example")
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
    allowed_fields = set(REQUIRED_CHECK_FIELDS) | set(OPTIONAL_CHECK_FIELDS)
    extra_fields = sorted(set(check) - allowed_fields)
    for field_name in extra_fields:
        errors.append(f"check {index} has unexpected field: {field_name}")
    if errors:
        return errors
    if not isinstance(check["name"], str) or not check["name"]:
        errors.append(f"check {index} name must be a non-empty string")
    elif check["name"] not in REQUIRED_PREFLIGHT_CHECK_NAMES:
        errors.append(f"check {index} name is not a canonical preflight check")
    if not isinstance(check["args"], list) or not all(isinstance(arg, str) and arg for arg in check["args"]):
        errors.append(f"check {index} args must be a list of non-empty strings")
    elif isinstance(check["name"], str) and check["name"] in REQUIRED_PREFLIGHT_COMMAND_TAILS_BY_NAME:
        observed_command_tail = tuple(check["args"][1:])
        expected_command_tail = REQUIRED_PREFLIGHT_COMMAND_TAILS_BY_NAME[check["name"]]
        if observed_command_tail != expected_command_tail:
            errors.append(f"check {index} args do not match canonical preflight command")
    if isinstance(check["return_code"], bool) or not isinstance(check["return_code"], int):
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
    errors.extend(_validate_optional_termination_diagnosis(check, index))
    return errors


def _validate_optional_termination_diagnosis(check: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    termination_reason = check.get("termination_reason")
    termination_signal = check.get("termination_signal")
    if "termination_reason" in check:
        if termination_reason not in ALLOWED_TERMINATION_REASONS:
            errors.append(f"check {index} termination_reason is invalid")
        elif termination_reason == "terminated":
            if (
                isinstance(termination_signal, bool)
                or not isinstance(termination_signal, int)
                or termination_signal <= 0
            ):
                errors.append(f"check {index} terminated checks require positive termination_signal")
        elif termination_signal is not None:
            errors.append(f"check {index} non-terminated checks must not set termination_signal")
    elif "termination_signal" in check:
        errors.append(f"check {index} termination_signal requires termination_reason")
    return errors


def _build_synthetic_check_results(failing_check_name: str | None = None) -> tuple[CheckResult, ...]:
    results: list[CheckResult] = []
    for command in build_check_commands("python"):
        if command.name == failing_check_name:
            results.append(CheckResult(command.name, command.args, 2, "", "STATUS: failed\n"))
        else:
            results.append(CheckResult(command.name, command.args, 0, "STATUS: passed\n", ""))
    return tuple(results)


if __name__ == "__main__":
    raise SystemExit(main())
