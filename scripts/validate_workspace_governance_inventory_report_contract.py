#!/usr/bin/env python3
"""Validate workspace governance inventory report contract.

Purpose: verify that inventory reports expose a stable machine-readable shape
and that count fields match artifact records.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library, inventory report schema/example, and
scripts/report_workspace_governance_inventory.py.
Invariants:
  - Validation is read-only and deterministic.
  - Schema, saved example, and current reporter output are checked.
  - Report status derives from artifact missing and issue counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from report_workspace_governance_inventory import build_inventory, build_inventory_report, load_witness
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as a package.
    from scripts.report_workspace_governance_inventory import build_inventory, build_inventory_report, load_witness


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "workspace_governance_inventory_report.schema.json"
DEFAULT_EXAMPLE_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-inventory-report-example.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-witness.json"
REQUIRED_REPORT_FIELDS = (
    "report_id",
    "status",
    "artifact_count",
    "missing_count",
    "issue_count",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "artifacts",
)
REQUIRED_ARTIFACT_FIELDS = (
    "name",
    "path",
    "purpose",
    "exists",
    "size_bytes",
    "issue",
)
ALLOWED_STATUSES = ("passed", "failed")


class InventoryReportContractError(ValueError):
    """Raised when the inventory report contract is invalid."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact identity."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InventoryReportContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("title") != "Workspace Governance Inventory Report":
        errors.append("schema title does not identify workspace governance inventory report")
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
    artifact_required = schema.get("$defs", {}).get("inventory_artifact", {}).get("required", [])
    if not isinstance(artifact_required, list):
        errors.append("schema inventory_artifact.required must be a list")
    else:
        for field_name in REQUIRED_ARTIFACT_FIELDS:
            if field_name not in artifact_required:
                errors.append(f"schema missing required artifact field: {field_name}")
    return errors


def validate_report(report: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one inventory report."""

    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_REPORT_FIELDS if field_name not in report]
    errors.extend(f"report missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(report) - set(REQUIRED_REPORT_FIELDS))
    errors.extend(f"report has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors

    if report["report_id"] != "workspace_governance_inventory":
        errors.append("report_id is invalid")
    if report["status"] not in ALLOWED_STATUSES:
        errors.append(f"report status is invalid: {report['status']}")
    if report["report_is_not_terminal_closure"] is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if report["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")

    artifacts = report["artifacts"]
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        return errors
    for field_name in ("artifact_count", "missing_count", "issue_count"):
        if isinstance(report[field_name], bool) or not isinstance(report[field_name], int) or report[field_name] < 0:
            errors.append(f"{field_name} must be a non-negative integer")
    errors.extend(_validate_report_counts(report, artifacts))
    for index, artifact in enumerate(artifacts):
        errors.extend(_validate_artifact_record(artifact, index))
    return errors


def build_current_report(witness_path: Path = DEFAULT_WITNESS_PATH) -> dict[str, object]:
    """Build the current workspace inventory report without writing files."""

    witness = load_witness(witness_path)
    inventory_records = build_inventory(witness)
    return build_inventory_report(inventory_records)


def validate_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    example_path: Path = DEFAULT_EXAMPLE_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate schema, saved example, and current reporter output."""

    schema = load_json_object(schema_path, "inventory report schema")
    example = load_json_object(example_path, "inventory report example")
    current_report = build_current_report(witness_path)
    errors = validate_schema_artifact(schema)
    errors.extend(f"example report: {error}" for error in validate_report(example))
    errors.extend(f"current report: {error}" for error in validate_report(current_report))
    return errors


def _validate_report_counts(report: dict[str, Any], artifacts: list[Any]) -> list[str]:
    errors: list[str] = []
    artifact_count = len(artifacts)
    missing_count = sum(1 for artifact in artifacts if isinstance(artifact, dict) and artifact.get("exists") is False)
    issue_count = sum(1 for artifact in artifacts if isinstance(artifact, dict) and artifact.get("issue") is not None)
    expected_status = "passed" if missing_count == 0 and issue_count == 0 else "failed"
    if report.get("artifact_count") != artifact_count:
        errors.append("artifact_count does not match artifacts length")
    if report.get("missing_count") != missing_count:
        errors.append("missing_count does not match missing artifacts")
    if report.get("issue_count") != issue_count:
        errors.append("issue_count does not match artifact issues")
    if report.get("status") != expected_status:
        errors.append(f"report status must be {expected_status} for observed artifact records")
    return errors


def _validate_artifact_record(artifact: Any, index: int) -> list[str]:
    if not isinstance(artifact, dict):
        return [f"artifact {index} must be an object"]
    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_ARTIFACT_FIELDS if field_name not in artifact]
    errors.extend(f"artifact {index} missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(artifact) - set(REQUIRED_ARTIFACT_FIELDS))
    errors.extend(f"artifact {index} has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors
    for field_name in ("name", "path", "purpose"):
        if not isinstance(artifact[field_name], str) or not artifact[field_name]:
            errors.append(f"artifact {index} {field_name} must be a non-empty string")
    if not isinstance(artifact["exists"], bool):
        errors.append(f"artifact {index} exists must be boolean")
    if artifact["size_bytes"] is not None and (
        isinstance(artifact["size_bytes"], bool)
        or not isinstance(artifact["size_bytes"], int)
        or artifact["size_bytes"] < 0
    ):
        errors.append(f"artifact {index} size_bytes must be null or a non-negative integer")
    if artifact["issue"] is not None and (not isinstance(artifact["issue"], str) or not artifact["issue"]):
        errors.append(f"artifact {index} issue must be null or a non-empty string")
    if artifact["exists"] is True and artifact["size_bytes"] is None:
        errors.append(f"artifact {index} existing artifact must include size_bytes")
    if artifact["exists"] is False and artifact["issue"] is None:
        errors.append(f"artifact {index} missing artifact must include issue")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the workspace governance inventory report contract."""

    parser = argparse.ArgumentParser(description="Validate workspace governance inventory report contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="path to inventory report schema JSON")
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE_PATH, help="path to inventory report example JSON")
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH, help="path to governance witness JSON")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.schema, args.example, args.witness)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-inventory-contract: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] inventory-report-contract: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] workspace_governance_inventory_report_schema\n")
    sys.stdout.write("[PASS] workspace_governance_inventory_report_example\n")
    sys.stdout.write("[PASS] workspace_governance_inventory_report_current_output\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
