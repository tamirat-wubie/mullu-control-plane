#!/usr/bin/env python3
"""Validate a personal-assistant approval queue read-model fixture.

Purpose: ensure approval queue projections remain evidence-only, schema-backed,
and unable to imply send, connector mutation, or system-of-record execution.
Governance scope: approval packet schema conformance, receipt conformance,
no secret serialization, no raw private payload projection, and no approval-as-
execution overclaim.
Dependencies: personal-assistant approval queue schema, approval schema,
receipt schema, and example read-model fixture.
Invariants:
  - Approval queue read models never grant execution authority.
  - Every queued packet validates against the approval packet schema.
  - Every queue receipt validates against the receipt schema and semantic checks.
  - Secret-like values and raw private connector payloads are rejected.
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

from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_QUEUE = REPO_ROOT / "examples" / "personal_assistant_approval_queue_read_model.json"
DEFAULT_QUEUE_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval_queue.schema.json"
DEFAULT_APPROVAL_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantApprovalQueueValidation:
    """Validation result for one approval queue projection."""

    valid: bool
    queue_path: str
    approval_count: int
    receipt_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_approval_queue(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    queue_schema_path: Path = DEFAULT_QUEUE_SCHEMA,
    approval_schema_path: Path = DEFAULT_APPROVAL_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantApprovalQueueValidation:
    """Validate one personal-assistant approval queue read model."""
    errors: list[str] = []
    queue_schema = _load_json_object(queue_schema_path, "approval queue schema", errors)
    approval_schema = _load_json_object(approval_schema_path, "approval schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    queue = _load_json_object(queue_path, "approval queue read model", errors)
    if queue_schema and queue:
        errors.extend(_validate_schema_instance(queue_schema, queue))
    if queue:
        errors.extend(_validate_queue_semantics(queue, approval_schema, receipt_schema))
        _scan_private_or_secret_payload(queue, errors, path="$")
    return PersonalAssistantApprovalQueueValidation(
        valid=not errors,
        queue_path=_path_label(queue_path),
        approval_count=int(queue.get("approval_count", 0)) if isinstance(queue, dict) else 0,
        receipt_count=len(queue.get("receipt_ids", ())) if isinstance(queue, dict) else 0,
        errors=tuple(errors),
    )


def _validate_queue_semantics(
    queue: dict[str, Any],
    approval_schema: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in (
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "approval_is_execution",
    ):
        if queue.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    metadata = queue.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        if metadata.get("foundation_only") is not True:
            errors.append("metadata.foundation_only must be true")
        if metadata.get("approval_decision_executes_action") is not False:
            errors.append("metadata.approval_decision_executes_action must be false")

    records = queue.get("records", ())
    if not isinstance(records, list):
        errors.append("records must be a list")
        return tuple(errors)
    if queue.get("approval_count") != len(records):
        errors.append("approval_count must equal records length")

    receipt_ids: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        packet = record.get("packet")
        receipts = record.get("receipts")
        if isinstance(packet, dict) and approval_schema:
            errors.extend(f"records[{index}].packet {message}" for message in _validate_schema_instance(approval_schema, packet))
            if packet.get("approval_id") != record.get("approval_id"):
                errors.append(f"records[{index}].approval_id must match packet.approval_id")
        else:
            errors.append(f"records[{index}].packet must be an object")
        if not isinstance(receipts, list) or not receipts:
            errors.append(f"records[{index}].receipts must be a non-empty list")
            continue
        for receipt_index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict):
                errors.append(f"records[{index}].receipts[{receipt_index}] must be an object")
                continue
            if receipt_schema:
                errors.extend(
                    f"records[{index}].receipts[{receipt_index}] {message}"
                    for message in _validate_schema_instance(receipt_schema, receipt)
                )
            errors.extend(
                f"records[{index}].receipts[{receipt_index}] {message}"
                for message in validate_personal_assistant_receipt_payload(receipt)
            )
            receipt_id = receipt.get("receipt_id")
            if isinstance(receipt_id, str):
                receipt_ids.append(receipt_id)
    if sorted(queue.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match receipts embedded in records")
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


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant approval queue validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant approval queue read model.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--schema", default=str(DEFAULT_QUEUE_SCHEMA))
    parser.add_argument("--approval-schema", default=str(DEFAULT_APPROVAL_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant approval queue validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_approval_queue(
        queue_path=Path(args.queue),
        queue_schema_path=Path(args.schema),
        approval_schema_path=Path(args.approval_schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant approval queue ok "
            f"approvals={result.approval_count} receipts={result.receipt_count}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
