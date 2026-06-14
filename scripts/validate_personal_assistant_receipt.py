#!/usr/bin/env python3
"""Validate a personal-assistant receipt fixture.

Purpose: ensure personal-assistant receipts record what happened, what did not
happen, redaction policy, approval status, and bounded evidence without
serializing raw connector payloads or secrets.
Governance scope: receipt schema conformance, actions-taken coverage,
actions-not-taken coverage, P4/P5 approval gates, redaction evidence, secret
serialization denial, and raw private connector payload denial.
Dependencies: schemas/personal_assistant_receipt.schema.json,
examples/personal_assistant_receipt_draft_only.json, and
examples/personal_assistant_receipt_math_reasoning.json.
Invariants:
  - Receipts must record actions taken and actions not taken.
  - Raw private connector payloads and secret-like values are rejected.
  - P4/P5 allowed execution requires explicit approval reference.
  - Math receipts cannot imply connector use, payment, publication, or record writes.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / "examples" / "personal_assistant_receipt_draft_only.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"

APPROVAL_REQUIRED_LEVELS = frozenset({"P3", "P4", "P5"})
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "connector_response",
        "private_connector_payload",
        "email_body",
        "message_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)

MATH_FORBIDDEN_TAKEN_FRAGMENTS = (
    "pay",
    "payment",
    "subscription",
    "system_of_record",
    "connector",
    "external_submission",
    "public_post",
    "publish",
    "publication",
)

MATH_REQUIRED_NOT_TAKEN_FRAGMENTS = (
    "payment",
    "subscription",
    "system_of_record",
    "connector",
    "external_submission",
    "public_post",
    "publication",
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantReceiptValidation:
    """Validation result for one personal-assistant receipt."""

    valid: bool
    receipt_id: str
    receipt_path: str
    actions_taken_count: int
    actions_not_taken_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PersonalAssistantReceiptValidation:
    """Validate one personal-assistant receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "personal-assistant receipt schema", errors)
    receipt = _load_json_object(receipt_path, "personal-assistant receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        errors.extend(validate_personal_assistant_receipt_payload(receipt))
    return _result(receipt_path=receipt_path, receipt=receipt, errors=errors)


def validate_personal_assistant_receipt_payload(receipt: dict[str, Any]) -> tuple[str, ...]:
    """Validate semantic receipt invariants that JSON Schema cannot express."""
    errors: list[str] = []
    actions_taken = _string_list(receipt, "actions_taken")
    actions_not_taken = _string_list(receipt, "actions_not_taken")
    risk_level = str(receipt.get("risk_level", ""))
    approval_required = receipt.get("approval_required") is True
    approval_ref = str(receipt.get("approval_ref", ""))
    decision = str(receipt.get("decision", ""))

    if not actions_taken:
        errors.append("actions_taken must be non-empty")
    if not actions_not_taken:
        errors.append("actions_not_taken must be non-empty")

    private_payload_policy = receipt.get("private_payload_policy", {})
    if not isinstance(private_payload_policy, dict):
        errors.append("private_payload_policy must be an object")
    else:
        if private_payload_policy.get("raw_private_payload_serialized") is not False:
            errors.append("raw_private_payload_serialized must be false")
        if private_payload_policy.get("secret_values_serialized") is not False:
            errors.append("secret_values_serialized must be false")
        if private_payload_policy.get("connector_payload_projection") == "raw":
            errors.append("connector_payload_projection must not be raw")

    if risk_level in APPROVAL_REQUIRED_LEVELS and not approval_required:
        errors.append(f"{risk_level} receipt requires explicit approval")
    if decision == "allowed" and approval_required and not approval_ref:
        errors.append("allowed approval-required receipt must include approval_ref")

    connectors_used = _string_list(receipt, "connectors_used")
    redactions = _string_list(receipt, "redactions")
    if connectors_used and not redactions:
        errors.append("connector-backed receipts must record redactions")

    if _is_math_receipt(receipt):
        errors.extend(
            _validate_math_receipt_boundary(
                receipt=receipt,
                actions_taken=actions_taken,
                actions_not_taken=actions_not_taken,
                connectors_used=connectors_used,
                private_payload_policy=private_payload_policy,
            )
        )

    _scan_private_or_secret_payload(receipt, errors, path="$")
    return tuple(errors)


def _is_math_receipt(receipt: dict[str, Any]) -> bool:
    skill_id = str(receipt.get("skill_id", ""))
    metadata = receipt.get("metadata", {})
    return skill_id.startswith("math.") or (
        isinstance(metadata, dict) and metadata.get("math_execution_boundary") == "planning_only"
    )


def _validate_math_receipt_boundary(
    *,
    receipt: dict[str, Any],
    actions_taken: tuple[str, ...],
    actions_not_taken: tuple[str, ...],
    connectors_used: tuple[str, ...],
    private_payload_policy: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    if connectors_used:
        errors.append("math receipt cannot record connectors_used")
    if receipt.get("approval_required") is True:
        errors.append("math receipt cannot require approval for planning-only work")
    if private_payload_policy.get("connector_payload_projection") != "no_connector_payload":
        errors.append("math receipt must use no_connector_payload projection")

    taken_text = " ".join(actions_taken).lower()
    unsafe_taken = sorted(fragment for fragment in MATH_FORBIDDEN_TAKEN_FRAGMENTS if fragment in taken_text)
    if unsafe_taken:
        errors.append(f"math receipt actions_taken imply forbidden effects {unsafe_taken}")

    not_taken_text = " ".join(actions_not_taken).lower()
    missing_not_taken = sorted(
        fragment for fragment in MATH_REQUIRED_NOT_TAKEN_FRAGMENTS if fragment not in not_taken_text
    )
    if missing_not_taken:
        errors.append(f"math receipt actions_not_taken missing forbidden-effect witnesses {missing_not_taken}")
    return tuple(errors)


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private connector payload field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _result(
    *,
    receipt_path: Path,
    receipt: dict[str, Any],
    errors: list[str],
) -> PersonalAssistantReceiptValidation:
    return PersonalAssistantReceiptValidation(
        valid=not errors,
        receipt_id=str(receipt.get("receipt_id", "")) if isinstance(receipt, dict) else "",
        receipt_path=_path_label(receipt_path),
        actions_taken_count=len(_string_list(receipt, "actions_taken")) if isinstance(receipt, dict) else 0,
        actions_not_taken_count=len(_string_list(receipt, "actions_not_taken")) if isinstance(receipt, dict) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _string_list(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
    values = payload.get(field_name, ())
    return tuple(value for value in values if isinstance(value, str)) if isinstance(values, list) else ()


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant receipt validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant receipt ok "
            f"actions_taken={result.actions_taken_count} "
            f"actions_not_taken={result.actions_not_taken_count}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
