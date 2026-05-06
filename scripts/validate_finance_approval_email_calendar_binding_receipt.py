#!/usr/bin/env python3
"""Validate a redacted finance email/calendar binding receipt.

Purpose: reject malformed, stale, or value-leaking connector token presence
receipts before the finance approval live handoff proceeds.
Governance scope: finance approval email/calendar token presence, redacted
secret handling, accepted connector names, and schema conformance.
Dependencies: .change_assurance/finance_approval_email_calendar_binding_receipt.json
and schemas/finance_approval_email_calendar_binding_receipt.schema.json.
Invariants:
  - Receipt values are never serialized.
  - Accepted binding names are exactly the supported connector token names.
  - The ready flag is derived from present_binding_names.
  - present_binding_names matches bindings with present=true.
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

from scripts.emit_finance_approval_email_calendar_binding_receipt import (  # noqa: E402
    ACCEPTED_BINDING_NAMES,
    DEFAULT_OUTPUT as DEFAULT_RECEIPT,
    DEFAULT_SCHEMA,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarBindingReceiptValidation:
    """Validation result for one finance email/calendar binding receipt."""

    valid: bool
    ready: bool
    receipt_id: str
    receipt_path: str
    binding_count: int
    present_binding_names: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["present_binding_names"] = list(self.present_binding_names)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_email_calendar_binding_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> FinanceEmailCalendarBindingReceiptValidation:
    """Validate one redacted finance email/calendar binding receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance email/calendar binding receipt schema", errors)
    receipt = _load_json_object(receipt_path, "finance email/calendar binding receipt", errors)
    if not schema or not receipt:
        return _validation_result(receipt_path, receipt, errors)

    errors.extend(_validate_schema_instance(schema, receipt))
    _validate_scalar_fields(receipt, errors)
    _validate_receipt_bindings(receipt, errors)
    if require_ready and receipt.get("ready") is not True:
        errors.append("finance email/calendar binding receipt ready must be true")
    return _validation_result(receipt_path, receipt, errors)


def _validate_scalar_fields(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if receipt.get("secret_serialization") != "forbidden":
        errors.append("secret_serialization must be forbidden")
    accepted_names = tuple(str(name) for name in receipt.get("accepted_binding_names", ()) if isinstance(name, str))
    if accepted_names != ACCEPTED_BINDING_NAMES:
        errors.append("accepted_binding_names must match supported connector token names")
    present_names = tuple(str(name) for name in receipt.get("present_binding_names", ()) if isinstance(name, str))
    expected_ready = bool(present_names)
    if receipt.get("ready") is not expected_ready:
        errors.append(f"ready must be {expected_ready} based on present_binding_names")


def _validate_receipt_bindings(receipt: dict[str, Any], errors: list[str]) -> None:
    bindings = receipt.get("bindings", [])
    if not isinstance(bindings, list):
        errors.append("bindings must be a list")
        return
    if receipt.get("binding_count") != len(bindings):
        errors.append("binding_count must match bindings length")
    binding_by_name: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            errors.append("binding entries must be objects")
            continue
        name = str(binding.get("name", ""))
        if name in binding_by_name:
            errors.append(f"duplicate binding name {name}")
        binding_by_name[name] = binding
        if binding.get("binding_kind") != "secret":
            errors.append(f"{name} binding_kind must be secret")
        if binding.get("risk") != "high":
            errors.append(f"{name} risk must be high")
        if binding.get("approval_required") is not True:
            errors.append(f"{name} approval_required must be true")
        if binding.get("receipt_projection") != "name_and_presence_only":
            errors.append(f"{name} receipt_projection must be name_and_presence_only")
        if binding.get("value_serialized") is not False:
            errors.append(f"{name} value_serialized must be false")
    observed_names = tuple(binding_by_name)
    if set(observed_names) != set(ACCEPTED_BINDING_NAMES):
        errors.append(
            "binding names must match accepted names: "
            f"observed_only={sorted(set(observed_names) - set(ACCEPTED_BINDING_NAMES))} "
            f"accepted_only={sorted(set(ACCEPTED_BINDING_NAMES) - set(observed_names))}"
        )
    present_names = set(str(name) for name in receipt.get("present_binding_names", ()) if isinstance(name, str))
    expected_present = {name for name, binding in binding_by_name.items() if binding.get("present") is True}
    if present_names != expected_present:
        errors.append(
            "present_binding_names must match bindings with present=true: "
            f"observed={sorted(present_names)} expected={sorted(expected_present)}"
        )


def _validation_result(
    receipt_path: Path,
    receipt: dict[str, Any],
    errors: list[str],
) -> FinanceEmailCalendarBindingReceiptValidation:
    present_names = receipt.get("present_binding_names", ())
    return FinanceEmailCalendarBindingReceiptValidation(
        valid=not errors,
        ready=receipt.get("ready") is True,
        receipt_id=str(receipt.get("receipt_id", "")),
        receipt_path=str(receipt_path),
        binding_count=int(receipt.get("binding_count", 0)) if isinstance(receipt.get("binding_count", 0), int) else 0,
        present_binding_names=tuple(str(name) for name in present_names) if isinstance(present_names, list) else (),
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
    """Parse finance email/calendar binding receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate redacted finance email/calendar binding receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for redacted finance email/calendar binding receipt validation."""
    args = parse_args(argv)
    result = validate_finance_approval_email_calendar_binding_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"finance email/calendar binding receipt ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
