#!/usr/bin/env python3
"""Validate the ClarificationRequest public contract.

Purpose: verify that missing-slot interpretation produces one redacted,
non-executing clarification request before planning, search, approval, or
execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - Clarification requests ask one focused question only.
  - Raw user text and secrets remain out of the public payload.
  - Clarification requests do not grant execution authority.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "clarification_request.schema.json"
DEFAULT_REQUEST_PATH = WORKSPACE_ROOT / "examples" / "clarification_request.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:clarification-request:1"
EXPECTED_SCHEMA_TITLE = "Clarification Request"
EXPECTED_REASON = "missing_required_interpretation_slots"
EXPECTED_SAFE_DEFAULT = "no_execution"
EXPECTED_MAX_QUESTIONS = 1
REQUIRED_MISSING_FIELDS = ("target", "allowed_action")
FORBIDDEN_PAYLOAD_KEYS = {
    "raw_body",
    "raw_message",
    "message_body",
    "secret",
    "execution_allowed",
    "approval_granted",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/clarification_request.schema.json",
    "examples/clarification_request.foundation.json",
    "scripts/validate_clarification_request.py",
    "tests/test_validate_clarification_request.py",
    "examples/sdlc/requirement_clarification_request_contract_20260614.json",
    "examples/sdlc/design_clarification_request_contract_20260614.json",
)


class ClarificationRequestValidationError(ValueError):
    """Raised when a clarification request artifact is malformed."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ClarificationRequestValidationError(f"{label} must be a JSON object")
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
            "clarification_id",
            "request_id",
            "tenant_id",
            "actor_id",
            "raw_message_hash",
            "missing_fields",
            "reason",
            "max_questions",
            "safe_default",
            "question",
            "created_at",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        max_questions = properties.get("max_questions", {})
        if not isinstance(max_questions, dict) or max_questions.get("const") != EXPECTED_MAX_QUESTIONS:
            errors.append("schema max_questions must const 1")
        safe_default = properties.get("safe_default", {})
        if not isinstance(safe_default, dict) or EXPECTED_SAFE_DEFAULT not in safe_default.get("enum", []):
            errors.append("schema safe_default must permit only no_execution")
        reason = properties.get("reason", {})
        if not isinstance(reason, dict) or EXPECTED_REASON not in reason.get("enum", []):
            errors.append("schema reason must include missing_required_interpretation_slots")
        raw_message_hash = properties.get("raw_message_hash", {})
        if not isinstance(raw_message_hash, dict) or raw_message_hash.get("pattern") != "^hash://.+$":
            errors.append("schema raw_message_hash must require hash:// reference")
    return errors


def validate_request_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one clarification payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("clarification request must be a JSON object")
        return errors

    _validate_identifier_prefixes(record, errors)
    _validate_missing_fields(record, errors)
    _validate_one_question(record, errors)
    _validate_no_raw_or_authority_payload(record, errors)
    return errors


def validate_request(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    request_path: Path = DEFAULT_REQUEST_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode request."""

    schema = _load_schema(schema_path)
    request = load_json_object(request_path, "ClarificationRequest")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_request_record(request, schema))
    return errors


def build_mutated_request(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default request for tests."""

    request = load_json_object(DEFAULT_REQUEST_PATH, "ClarificationRequest")
    mutated = deepcopy(request)
    for key, value in updates.items():
        mutated[key] = value
    return mutated


def _validate_identifier_prefixes(record: dict[str, Any], errors: list[str]) -> None:
    prefixes = {
        "clarification_id": "clarification-request-",
        "request_id": "interpreted-request-",
        "raw_message_hash": "hash://",
    }
    for field_name, prefix in prefixes.items():
        value = record.get(field_name)
        if not isinstance(value, str) or not value.startswith(prefix):
            errors.append(f"{field_name} must start with {prefix}")


def _validate_missing_fields(record: dict[str, Any], errors: list[str]) -> None:
    missing_fields = record.get("missing_fields")
    if not isinstance(missing_fields, list) or not missing_fields:
        errors.append("missing_fields must be a non-empty list")
        return
    for required_field in REQUIRED_MISSING_FIELDS:
        if required_field not in missing_fields:
            errors.append(f"missing_fields must include {required_field}")


def _validate_one_question(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("reason") != EXPECTED_REASON:
        errors.append(f"reason must be {EXPECTED_REASON}")
    if record.get("safe_default") != EXPECTED_SAFE_DEFAULT:
        errors.append(f"safe_default must be {EXPECTED_SAFE_DEFAULT}")
    if record.get("max_questions") != EXPECTED_MAX_QUESTIONS:
        errors.append("max_questions must be 1")
    question = record.get("question")
    if not isinstance(question, str) or not question.strip():
        errors.append("question must be a non-empty string")
        return
    if question.count("?") != 1:
        errors.append("question must contain exactly one question mark")


def _validate_no_raw_or_authority_payload(record: dict[str, Any], errors: list[str]) -> None:
    forbidden_keys = sorted(FORBIDDEN_PAYLOAD_KEYS.intersection(record))
    for key in forbidden_keys:
        errors.append(f"forbidden payload key present: {key}")
    serialized = json.dumps(record, sort_keys=True)
    for forbidden_fragment in ("secret-token", "private key", "raw user text"):
        if forbidden_fragment in serialized:
            errors.append(f"forbidden raw or secret fragment present: {forbidden_fragment}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def main(argv: list[str] | None = None) -> int:
    """Validate the ClarificationRequest from the command line."""

    parser = argparse.ArgumentParser(description="Validate ClarificationRequest contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_request(args.schema, args.request)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "clarification_request_validation",
                    "schema_path": str(args.schema.relative_to(WORKSPACE_ROOT)),
                    "request_path": str(args.request.relative_to(WORKSPACE_ROOT)),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                    "evidence_refs": list(REQUIRED_EVIDENCE_REFS),
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] clarification_request")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
