#!/usr/bin/env python3
"""Validate finance email/calendar live receipt readiness.

Purpose: reject malformed or write-observing email/calendar live receipts before
finance approval live handoff promotion.
Governance scope: finance approval read-only connector evidence, adapter
identity, blocker derivation, and schema conformance.
Dependencies: .change_assurance/email_calendar_live_receipt.json and
schemas/finance_approval_email_calendar_live_receipt.schema.json.
Invariants:
  - The adapter id is exactly communication.email_calendar_worker.
  - Ready receipts are passed, verification-passed, and read-only.
  - Failed receipts remain valid blocked evidence when require-ready is false.
  - Secret values and exception details are not required or echoed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_capability_adapter_live_receipts import DEFAULT_EMAIL_CALENDAR_RECEIPT  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_email_calendar_live_receipt.schema.json"
READ_ONLY_OPERATIONS = ("email.search", "calendar.conflict_check")


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarLiveReceiptValidation:
    """Validation result for one finance email/calendar live receipt."""

    valid: bool
    ready: bool
    receipt_id: str
    receipt_path: str
    adapter_id: str
    status: str
    verification_status: str
    external_write: bool
    provider_operation: str
    blockers: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_email_calendar_live_receipt(
    *,
    receipt_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> FinanceEmailCalendarLiveReceiptValidation:
    """Validate one finance email/calendar live receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance email/calendar live receipt schema", errors)
    receipt = _load_json_object(receipt_path, "finance email/calendar live receipt", errors)
    if not schema or not receipt:
        return _validation_result(receipt_path, receipt, errors)

    errors.extend(_validate_schema_instance(schema, receipt))
    _validate_semantics(receipt, errors)
    ready = _receipt_ready(receipt)
    if require_ready and not ready:
        errors.append("finance email/calendar live receipt ready must be true")
    return _validation_result(receipt_path, receipt, errors)


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("adapter_id") != "communication.email_calendar_worker":
        errors.append("adapter_id must be communication.email_calendar_worker")
    if receipt.get("status") not in {"passed", "failed"}:
        errors.append("status must be passed or failed")
    if receipt.get("verification_status") not in {"passed", "failed"}:
        errors.append("verification_status must be passed or failed")
    if receipt.get("status") == "passed" and receipt.get("verification_status") != "passed":
        errors.append("passed status requires verification_status=passed")
    if receipt.get("external_write") is not False:
        errors.append("external_write must be false for finance live receipt readiness")
    operation = str(receipt.get("provider_operation", ""))
    if receipt.get("status") == "passed" and operation not in READ_ONLY_OPERATIONS:
        errors.append("passed finance live receipt requires a read-only provider_operation")
    blockers = receipt.get("blockers", [])
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
    elif receipt.get("status") == "passed" and blockers:
        errors.append("passed finance live receipt must not carry blockers")
    _validate_worker_receipt(receipt, errors)


def _validate_worker_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    worker_receipt = receipt.get("worker_receipt")
    if receipt.get("status") == "passed" and not isinstance(worker_receipt, dict):
        errors.append("passed finance live receipt requires worker_receipt object")
        return
    if not isinstance(worker_receipt, dict):
        return
    for field_name in ("connector_id", "provider_operation", "resource_id", "response_digest"):
        expected_value = str(receipt.get(field_name, "")).strip()
        if expected_value and worker_receipt.get(field_name) != receipt.get(field_name):
            errors.append(f"worker_receipt {field_name} must match receipt {field_name}")
    if worker_receipt.get("external_write") is not False:
        errors.append("worker_receipt external_write must be false")
    if receipt.get("status") != "passed":
        return
    if worker_receipt.get("verification_status") != "passed":
        errors.append("passed finance live receipt requires worker_receipt verification_status=passed")
    if worker_receipt.get("capability_id") not in READ_ONLY_OPERATIONS:
        errors.append("passed finance live receipt requires read-only worker_receipt capability_id")
    if worker_receipt.get("action") not in READ_ONLY_OPERATIONS:
        errors.append("passed finance live receipt requires read-only worker_receipt action")
    if worker_receipt.get("forbidden_effects_observed") is not False:
        errors.append("passed finance live receipt requires no forbidden worker effects")
    if not str(worker_receipt.get("query_hash", "")).strip():
        errors.append("passed finance live receipt requires worker_receipt query_hash")
    evidence_refs = worker_receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("passed finance live receipt requires worker_receipt evidence_refs")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("adapter_id") == "communication.email_calendar_worker"
        and receipt.get("status") == "passed"
        and receipt.get("verification_status") == "passed"
        and receipt.get("external_write") is False
        and str(receipt.get("provider_operation", "")) in READ_ONLY_OPERATIONS
        and _worker_receipt_ready(receipt)
        and receipt.get("blockers") == []
    )


def _worker_receipt_ready(receipt: dict[str, Any]) -> bool:
    worker_receipt = receipt.get("worker_receipt")
    return (
        isinstance(worker_receipt, dict)
        and worker_receipt.get("connector_id") == receipt.get("connector_id")
        and worker_receipt.get("provider_operation") == receipt.get("provider_operation")
        and worker_receipt.get("resource_id") == receipt.get("resource_id")
        and worker_receipt.get("response_digest") == receipt.get("response_digest")
        and worker_receipt.get("verification_status") == "passed"
        and worker_receipt.get("capability_id") in READ_ONLY_OPERATIONS
        and worker_receipt.get("action") in READ_ONLY_OPERATIONS
        and worker_receipt.get("external_write") is False
        and worker_receipt.get("forbidden_effects_observed") is False
        and bool(str(worker_receipt.get("query_hash", "")).strip())
        and isinstance(worker_receipt.get("evidence_refs"), list)
        and bool(worker_receipt.get("evidence_refs"))
    )


def _validation_result(
    receipt_path: Path,
    receipt: dict[str, Any],
    errors: list[str],
) -> FinanceEmailCalendarLiveReceiptValidation:
    blockers = receipt.get("blockers", ())
    return FinanceEmailCalendarLiveReceiptValidation(
        valid=not errors,
        ready=not errors and _receipt_ready(receipt),
        receipt_id=str(receipt.get("receipt_id", "")),
        receipt_path=str(receipt_path),
        adapter_id=str(receipt.get("adapter_id", "")),
        status=str(receipt.get("status", "")),
        verification_status=str(receipt.get("verification_status", "")),
        external_write=receipt.get("external_write") is True,
        provider_operation=str(receipt.get("provider_operation", "")),
        blockers=tuple(str(blocker) for blocker in blockers) if isinstance(blockers, list) else (),
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance email/calendar live receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance email/calendar live receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_EMAIL_CALENDAR_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance email/calendar live receipt validation."""
    args = parse_args(argv)
    result = validate_finance_approval_email_calendar_live_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"finance email/calendar live receipt ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
