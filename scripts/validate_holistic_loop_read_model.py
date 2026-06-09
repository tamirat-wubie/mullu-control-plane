#!/usr/bin/env python3
"""Validate holistic loop read-model report contract.

Purpose: verify that the holistic loop report has a stable machine-readable
shape and blocker/status consistency.
Governance scope: schema artifact, current read-model output, blocker
derivation, non-terminal closure boundary, and bounded count fields.
Dependencies: Python standard library and scripts/report_holistic_loop_read_model.py.
Invariants:
  - Validation is read-only and deterministic.
  - Report status derives from loop blockers.
  - Missing evidence must appear as blockers before closure can be claimed.
  - The report is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from report_holistic_loop_read_model import build_report
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as a package.
    from scripts.report_holistic_loop_read_model import build_report


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "holistic_loop_read_model.schema.json"
REQUIRED_REPORT_FIELDS = (
    "report_id",
    "status",
    "generated_at",
    "loop_count",
    "returned_count",
    "blocked_count",
    "verified_count",
    "truncated",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "loops",
)
REQUIRED_LOOP_FIELDS = (
    "loop_id",
    "name",
    "purpose",
    "owner",
    "risk_class",
    "status",
    "mode",
    "current_step",
    "required_authority",
    "required_evidence",
    "evidence_refs",
    "missing_evidence",
    "closure_conditions",
    "open_blockers",
    "rollback_policy",
    "learning_policy",
    "updated_at",
)
REPORT_STATUSES = ("blocked", "verified")
LOOP_STATUSES = ("open", "blocked", "verified", "closed")
LOOP_MODES = ("real", "dry_run", "shadow", "simulation", "replay")
LOOP_STEPS = (
    "observe",
    "decide",
    "act",
    "verify",
    "record_receipt",
    "update_state",
    "learn",
    "audit",
    "close",
)


class HolisticLoopReadModelContractError(ValueError):
    """Raised when the holistic loop read-model contract is invalid."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact identity."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HolisticLoopReadModelContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema validation errors."""

    errors: list[str] = []
    if schema.get("title") != "Holistic Loop Read Model":
        errors.append("schema title does not identify holistic loop read model")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    else:
        for field_name in REQUIRED_REPORT_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required report field: {field_name}")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    else:
        for field_name in REQUIRED_REPORT_FIELDS:
            if field_name not in properties:
                errors.append(f"schema missing report property: {field_name}")
    loop_required = schema.get("$defs", {}).get("loop_summary", {}).get("required", [])
    if not isinstance(loop_required, list):
        errors.append("schema loop_summary.required must be a list")
    else:
        for field_name in REQUIRED_LOOP_FIELDS:
            if field_name not in loop_required:
                errors.append(f"schema missing required loop field: {field_name}")
    return errors


def validate_report(report: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one loop read-model report."""

    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_REPORT_FIELDS if field_name not in report]
    errors.extend(f"report missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(report) - set(REQUIRED_REPORT_FIELDS))
    errors.extend(f"report has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors

    if report["report_id"] != "holistic_loop_read_model":
        errors.append("report_id is invalid")
    if report["status"] not in REPORT_STATUSES:
        errors.append(f"report status is invalid: {report['status']}")
    if report["report_is_not_terminal_closure"] is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if report["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    for field_name in ("loop_count", "returned_count", "blocked_count", "verified_count"):
        if isinstance(report[field_name], bool) or not isinstance(report[field_name], int):
            errors.append(f"{field_name} must be an integer")
        elif report[field_name] < 0:
            errors.append(f"{field_name} must be non-negative")
    if not isinstance(report["truncated"], bool):
        errors.append("truncated must be boolean")

    loops = report["loops"]
    if not isinstance(loops, list):
        errors.append("loops must be a list")
        return errors
    errors.extend(_validate_report_counts(report, loops))
    for index, loop in enumerate(loops):
        errors.extend(_validate_loop_summary(loop, index))
    return errors


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema and current reporter output."""

    schema = load_json_object(schema_path, "holistic loop read-model schema")
    current_report = build_report()
    errors = validate_schema_artifact(schema)
    errors.extend(f"current report: {error}" for error in validate_report(current_report))
    return errors


def _validate_report_counts(report: dict[str, Any], loops: list[Any]) -> list[str]:
    errors: list[str] = []
    loop_count = len(loops)
    blocked_count = sum(
        1 for loop in loops if isinstance(loop, dict) and bool(loop.get("open_blockers"))
    )
    verified_count = sum(
        1 for loop in loops if isinstance(loop, dict) and loop.get("status") == "verified"
    )
    expected_status = "blocked" if blocked_count else "verified"
    if report.get("returned_count") != loop_count:
        errors.append("returned_count does not match loop summaries length")
    if report.get("loop_count") < report.get("returned_count", 0):
        errors.append("loop_count cannot be lower than returned_count")
    if report.get("blocked_count") != blocked_count:
        errors.append("blocked_count does not match loop blockers")
    if report.get("verified_count") != verified_count:
        errors.append("verified_count does not match verified loops")
    if report.get("status") != expected_status:
        errors.append(f"report status must be {expected_status} for observed blockers")
    return errors


def _validate_loop_summary(loop: Any, index: int) -> list[str]:
    if not isinstance(loop, dict):
        return [f"loop {index} must be an object"]
    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_LOOP_FIELDS if field_name not in loop]
    errors.extend(f"loop {index} missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(loop) - set(REQUIRED_LOOP_FIELDS))
    errors.extend(f"loop {index} has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors
    for field_name in (
        "loop_id",
        "name",
        "purpose",
        "owner",
        "risk_class",
        "rollback_policy",
        "learning_policy",
        "updated_at",
    ):
        if not isinstance(loop[field_name], str) or not loop[field_name]:
            errors.append(f"loop {index} {field_name} must be a non-empty string")
    if loop["status"] not in LOOP_STATUSES:
        errors.append(f"loop {index} status is invalid")
    if loop["mode"] not in LOOP_MODES:
        errors.append(f"loop {index} mode is invalid")
    if loop["current_step"] not in LOOP_STEPS:
        errors.append(f"loop {index} current_step is invalid")
    for field_name in (
        "required_authority",
        "required_evidence",
        "evidence_refs",
        "missing_evidence",
        "closure_conditions",
        "open_blockers",
    ):
        errors.extend(_validate_text_list(loop[field_name], f"loop {index} {field_name}"))
    if loop["open_blockers"] and loop["status"] != "blocked":
        errors.append(f"loop {index} with blockers must be blocked")
    if loop["status"] in {"verified", "closed"} and loop["missing_evidence"]:
        errors.append(f"loop {index} verified or closed loop cannot miss evidence")
    for evidence_name in loop["missing_evidence"]:
        expected_blocker = f"missing_evidence:{evidence_name}"
        if expected_blocker not in loop["open_blockers"]:
            errors.append(f"loop {index} missing evidence lacks blocker: {evidence_name}")
    return errors


def _validate_text_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            errors.append(f"{label} must contain only non-empty strings")
            break
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the holistic loop read-model report contract."""

    parser = argparse.ArgumentParser(description="Validate holistic loop read-model report.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="schema JSON path")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[BLOCKED] load-holistic-loop-contract: {exc}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-contract: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1

    sys.stdout.write("[PASS] holistic_loop_read_model_schema\n")
    sys.stdout.write("[PASS] holistic_loop_read_model_current_output\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
