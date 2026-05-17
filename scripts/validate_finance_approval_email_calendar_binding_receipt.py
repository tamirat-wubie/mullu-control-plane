#!/usr/bin/env python3
"""Validate a redacted finance email/calendar binding receipt.

Purpose: reject malformed, stale, incomplete, or value-leaking worker and
connector binding receipts before the finance approval live handoff proceeds.
Governance scope: finance approval email/calendar worker binding, connector
token presence, read-only scope witness classification, redacted secret
handling, accepted connector names, and schema conformance.
Dependencies: .change_assurance/finance_approval_email_calendar_binding_receipt.json
and schemas/finance_approval_email_calendar_binding_receipt.schema.json.
Invariants:
  - Receipt values are never serialized.
  - Accepted binding names are exactly the supported worker, token, and scope names.
  - The ready flag is derived from required binding groups and scope classification.
  - present_binding_names matches bindings with present=true.
  - Present scope witnesses are classified exactly once as read-only or invalid.
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
    BINDING_GROUP_BY_NAME,
    BINDING_KIND_BY_NAME,
    CONNECTOR_TOKEN_BINDING_NAMES,
    DEFAULT_OUTPUT as DEFAULT_RECEIPT,
    DEFAULT_SCHEMA,
    REQUIRED_BINDING_GROUPS,
    SCOPE_WITNESS_BINDING_NAMES,
    WORKER_ENDPOINT_BINDING_NAMES,
    WORKER_SECRET_BINDING_NAMES,
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
    required_binding_groups: tuple[str, ...]
    satisfied_binding_groups: tuple[str, ...]
    read_only_scope_witness_names: tuple[str, ...]
    invalid_scope_witness_names: tuple[str, ...]
    readiness_blockers: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["present_binding_names"] = list(self.present_binding_names)
        payload["required_binding_groups"] = list(self.required_binding_groups)
        payload["satisfied_binding_groups"] = list(self.satisfied_binding_groups)
        payload["read_only_scope_witness_names"] = list(self.read_only_scope_witness_names)
        payload["invalid_scope_witness_names"] = list(self.invalid_scope_witness_names)
        payload["readiness_blockers"] = list(self.readiness_blockers)
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
        errors.append("accepted_binding_names must match supported finance email/calendar binding names")
    present_names = _string_tuple(receipt, "present_binding_names")
    required_groups = _string_tuple(receipt, "required_binding_groups")
    satisfied_groups = _string_tuple(receipt, "satisfied_binding_groups")
    read_only_scope_names = _string_tuple(receipt, "read_only_scope_witness_names")
    invalid_scope_names = _string_tuple(receipt, "invalid_scope_witness_names")
    readiness_blockers = _string_tuple(receipt, "readiness_blockers")
    if required_groups != REQUIRED_BINDING_GROUPS:
        errors.append("required_binding_groups must match finance email/calendar readiness groups")
    _validate_scope_classification(
        present_names=present_names,
        read_only_scope_names=read_only_scope_names,
        invalid_scope_names=invalid_scope_names,
        errors=errors,
    )
    expected_satisfied_groups = _expected_satisfied_groups(
        present_names=present_names,
        read_only_scope_names=read_only_scope_names,
    )
    if satisfied_groups != expected_satisfied_groups:
        errors.append(
            "satisfied_binding_groups must match present worker/token/read-only-scope groups: "
            f"observed={list(satisfied_groups)} expected={list(expected_satisfied_groups)}"
        )
    expected_blockers = _expected_readiness_blockers(
        satisfied_groups=expected_satisfied_groups,
        invalid_scope_names=invalid_scope_names,
    )
    if readiness_blockers != expected_blockers:
        errors.append(
            "readiness_blockers must match missing groups and invalid scope witnesses: "
            f"observed={list(readiness_blockers)} expected={list(expected_blockers)}"
        )
    expected_ready = not expected_blockers
    if receipt.get("ready") is not expected_ready:
        errors.append(f"ready must be {expected_ready} based on required binding groups")


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
        expected_kind = BINDING_KIND_BY_NAME.get(name)
        if binding.get("binding_kind") != expected_kind:
            errors.append(f"{name} binding_kind must be {BINDING_KIND_BY_NAME.get(name, '<unknown>')}")
        if binding.get("binding_group") != BINDING_GROUP_BY_NAME.get(name):
            errors.append(f"{name} binding_group must be {BINDING_GROUP_BY_NAME.get(name, '<unknown>')}")
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
        present_binding_names=_string_tuple(receipt, "present_binding_names"),
        required_binding_groups=_string_tuple(receipt, "required_binding_groups"),
        satisfied_binding_groups=_string_tuple(receipt, "satisfied_binding_groups"),
        read_only_scope_witness_names=_string_tuple(receipt, "read_only_scope_witness_names"),
        invalid_scope_witness_names=_string_tuple(receipt, "invalid_scope_witness_names"),
        readiness_blockers=_string_tuple(receipt, "readiness_blockers"),
        errors=tuple(errors),
    )


def _string_tuple(receipt: dict[str, Any], field_name: str) -> tuple[str, ...]:
    values = receipt.get(field_name, ())
    return tuple(str(name) for name in values) if isinstance(values, list) else ()


def _validate_scope_classification(
    *,
    present_names: tuple[str, ...],
    read_only_scope_names: tuple[str, ...],
    invalid_scope_names: tuple[str, ...],
    errors: list[str],
) -> None:
    present_scope_names = set(present_names).intersection(SCOPE_WITNESS_BINDING_NAMES)
    read_only_scope_set = set(read_only_scope_names)
    invalid_scope_set = set(invalid_scope_names)
    if not read_only_scope_set <= set(SCOPE_WITNESS_BINDING_NAMES):
        errors.append(
            "read_only_scope_witness_names must use accepted scope witness names: "
            f"observed_only={sorted(read_only_scope_set - set(SCOPE_WITNESS_BINDING_NAMES))}"
        )
    if not invalid_scope_set <= set(SCOPE_WITNESS_BINDING_NAMES):
        errors.append(
            "invalid_scope_witness_names must use accepted scope witness names: "
            f"observed_only={sorted(invalid_scope_set - set(SCOPE_WITNESS_BINDING_NAMES))}"
        )
    if read_only_scope_set.intersection(invalid_scope_set):
        errors.append("scope witness names cannot be both read-only and invalid")
    if present_scope_names != read_only_scope_set.union(invalid_scope_set):
        errors.append(
            "present scope witnesses must be classified exactly once: "
            f"observed={sorted(read_only_scope_set.union(invalid_scope_set))} "
            f"expected={sorted(present_scope_names)}"
        )


def _expected_satisfied_groups(
    *,
    present_names: tuple[str, ...],
    read_only_scope_names: tuple[str, ...],
) -> tuple[str, ...]:
    present = set(present_names)
    groups = set()
    if present.intersection(WORKER_ENDPOINT_BINDING_NAMES):
        groups.add("worker_endpoint")
    if present.intersection(WORKER_SECRET_BINDING_NAMES):
        groups.add("worker_secret")
    if present.intersection(CONNECTOR_TOKEN_BINDING_NAMES):
        groups.add("connector_token")
    if read_only_scope_names:
        groups.add("read_only_scope_witness")
    return tuple(group for group in REQUIRED_BINDING_GROUPS if group in groups)


def _expected_readiness_blockers(
    *,
    satisfied_groups: tuple[str, ...],
    invalid_scope_names: tuple[str, ...],
) -> tuple[str, ...]:
    satisfied = set(satisfied_groups)
    blockers = [f"missing_{group}" for group in REQUIRED_BINDING_GROUPS if group not in satisfied]
    blockers.extend(f"invalid_scope_witness:{name}" for name in invalid_scope_names)
    return tuple(blockers)


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
