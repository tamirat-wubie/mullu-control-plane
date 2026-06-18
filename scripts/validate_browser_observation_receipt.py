#!/usr/bin/env python3
"""Validate the BrowserObservationReceipt contract.

Purpose: verify that browser inspection evidence remains digest-only,
operator-scoped, and separated from navigation, mutation, session, secret, and
publication authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, capture
policy decision ledger schema, evidence classification manifest, UAO, and
LifeMeaningJudgment schema.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example stores no raw URL, raw DOM, raw screenshot, or raw
    secret values.
  - Browser navigation, click, submit, keystroke injection, cookie/session
    reads, external writes, connector calls, publication, terminal closure, and
    success claims remain denied.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "browser_observation_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "browser_observation_receipt.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:browser-observation-receipt:1"
EXPECTED_SCHEMA_TITLE = "Browser Observation Receipt"
EXPECTED_RECEIPT_VERSION = "browser_observation_receipt.v1"
REQUIRED_RECEIPT_REFS = {
    "browser_observation_receipt_schema": "schemas/browser_observation_receipt.schema.json",
    "capture_policy_decision_ledger_schema": "schemas/capture_policy_decision_ledger.schema.json",
    "evidence_classification_manifest_schema": "schemas/evidence_classification_manifest.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/browser_observation_receipt.schema.json",
    "examples/browser_observation_receipt.foundation.json",
    "scripts/validate_browser_observation_receipt.py",
    "tests/test_validate_browser_observation_receipt.py",
    "docs/87_browser_observation_receipt_contract.md",
    "schemas/capture_policy_decision_ledger.schema.json",
    "schemas/evidence_classification_manifest.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "docs/82_cross_repo_opportunity_map.md",
)
DENIED_AUTHORITY_FIELDS = (
    "navigation_performed",
    "click_performed",
    "form_submit_performed",
    "keystroke_injection_performed",
    "cookie_or_session_read",
    "secret_captured",
    "external_write_performed",
    "file_write_performed",
    "connector_call_performed",
    "publication_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
RAW_STORAGE_FIELDS = (
    "raw_url_stored",
    "raw_dom_stored",
    "raw_screenshot_stored",
    "raw_secret_value_stored",
)
DIGEST_FIELDS = (
    ("observation_scope", "source_url_hash"),
    ("observation_artifacts", "dom_digest_ref"),
    ("observation_artifacts", "screenshot_digest_ref"),
    ("observation_artifacts", "title_digest_ref"),
)


class BrowserObservationReceiptError(ValueError):
    """Raised when a BrowserObservationReceipt artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BrowserObservationReceiptError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
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
        for field_name in (
            "receipt_id",
            "receipt_version",
            "observation_scope",
            "observation_artifacts",
            "authority_boundary",
            "privacy_guard",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_browser_observation_receipt_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one browser observation receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("browser observation receipt must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_observation_scope(record.get("observation_scope"), errors)
    _validate_observation_artifacts(record.get("observation_artifacts"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_privacy_guard(record.get("privacy_guard"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_browser_observation_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "BrowserObservationReceipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_browser_observation_receipt_record(receipt, schema))
    return errors


def build_mutated_browser_observation_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "BrowserObservationReceipt")
    mutated = deepcopy(receipt)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match browser_observation_receipt.v1")
    for parent_name, field_name in DIGEST_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_observation_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("observation_scope must be an object")
        return
    if scope.get("url_redaction_policy") != "hash_only_no_raw_url":
        errors.append("observation_scope.url_redaction_policy must be hash_only_no_raw_url")
    if scope.get("observation_mode") != "read_only_operator_supplied":
        errors.append("observation_scope.observation_mode must be read_only_operator_supplied")
    if scope.get("consent_scope") != "operator_local_explicit":
        errors.append("observation_scope.consent_scope must be operator_local_explicit")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("observation_scope.tenant_scope must be foundation-local-only")
    for field_name in ("consent_ref", "uao_ref"):
        if not isinstance(scope.get(field_name), str) or scope.get(field_name) == "":
            errors.append(f"observation_scope.{field_name} must be non-empty")


def _validate_observation_artifacts(artifacts: Any, errors: list[str]) -> None:
    if not isinstance(artifacts, dict):
        errors.append("observation_artifacts must be an object")
        return
    expected_refs = {
        "capture_policy_ref": REQUIRED_RECEIPT_REFS["capture_policy_decision_ledger_schema"],
        "evidence_classification_ref": REQUIRED_RECEIPT_REFS["evidence_classification_manifest_schema"],
    }
    for field_name, expected_ref in expected_refs.items():
        if artifacts.get(field_name) != expected_ref:
            errors.append(f"observation_artifacts.{field_name} must be {expected_ref}")
    if not isinstance(artifacts.get("viewport_ref"), str) or artifacts.get("viewport_ref") == "":
        errors.append("observation_artifacts.viewport_ref must be non-empty")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_privacy_guard(guard: Any, errors: list[str]) -> None:
    if not isinstance(guard, dict):
        errors.append("privacy_guard must be an object")
        return
    for field_name in RAW_STORAGE_FIELDS:
        if guard.get(field_name) is not False:
            errors.append(f"privacy_guard.{field_name} must be false")
    if guard.get("private_payload_redacted") is not True:
        errors.append("privacy_guard.private_payload_redacted must be true")
    if guard.get("operator_review_required") is not True:
        errors.append("privacy_guard.operator_review_required must be true")
    if not isinstance(guard.get("retention_policy_ref"), str) or guard.get("retention_policy_ref") == "":
        errors.append("privacy_guard.retention_policy_ref must be non-empty")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    boundary = record.get("authority_boundary")
    guard = record.get("privacy_guard")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(boundary, dict) or not isinstance(guard, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("authority_boundary, privacy_guard, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("digest_only") is not True:
        errors.append("contract_summary.digest_only must be true")
    if summary.get("authority_denied") is not True:
        errors.append("contract_summary.authority_denied must be true")
    expected_counts = {
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "privacy_guard_count": len(guard),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value:
        errors.append(f"{label} must not store a raw URL")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate BrowserObservationReceipt artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate BrowserObservationReceipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_browser_observation_receipt(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "browser_observation_receipt_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] browser_observation_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
