#!/usr/bin/env python3
"""Emit a redacted finance email/calendar connector binding receipt.

Purpose: prove whether the worker endpoint, signing secret, one accepted
email/calendar connector token, and one read-only scope witness are present
before running the finance approval live handoff receipt.
Governance scope: finance approval email/calendar worker binding, token
presence, scope witness classification, redacted secret handling, schema
validation, and operator approval boundary.
Dependencies: schemas/finance_approval_email_calendar_binding_receipt.schema.json.
Invariants:
  - Binding values are never serialized.
  - Readiness requires worker URL, worker secret, one connector token, and one
    read-only scope witness.
  - Scope values are classified only as read-only or invalid by binding name.
  - Every binding entry records name and presence without values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_email_calendar_binding_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_email_calendar_binding_receipt.json"
WORKER_ENDPOINT_BINDING_NAMES = ("MULLU_EMAIL_CALENDAR_WORKER_URL",)
WORKER_SECRET_BINDING_NAMES = ("MULLU_EMAIL_CALENDAR_WORKER_SECRET",)
CONNECTOR_TOKEN_BINDING_NAMES = (
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "GMAIL_ACCESS_TOKEN",
    "GOOGLE_CALENDAR_ACCESS_TOKEN",
    "MICROSOFT_GRAPH_ACCESS_TOKEN",
)
SCOPE_WITNESS_BINDING_NAMES = (
    "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID",
    "GMAIL_SCOPE_ID",
    "GOOGLE_CALENDAR_SCOPE_ID",
    "MICROSOFT_GRAPH_SCOPE_ID",
)
ACCEPTED_BINDING_NAMES = (
    *WORKER_ENDPOINT_BINDING_NAMES,
    *WORKER_SECRET_BINDING_NAMES,
    *CONNECTOR_TOKEN_BINDING_NAMES,
    *SCOPE_WITNESS_BINDING_NAMES,
)
REQUIRED_BINDING_GROUPS = (
    "worker_endpoint",
    "worker_secret",
    "connector_token",
    "read_only_scope_witness",
)
BINDING_GROUP_BY_NAME = {
    **{name: "worker_endpoint" for name in WORKER_ENDPOINT_BINDING_NAMES},
    **{name: "worker_secret" for name in WORKER_SECRET_BINDING_NAMES},
    **{name: "connector_token" for name in CONNECTOR_TOKEN_BINDING_NAMES},
    **{name: "read_only_scope_witness" for name in SCOPE_WITNESS_BINDING_NAMES},
}
BINDING_KIND_BY_NAME = {
    **{name: "endpoint" for name in WORKER_ENDPOINT_BINDING_NAMES},
    **{name: "secret" for name in WORKER_SECRET_BINDING_NAMES},
    **{name: "secret" for name in CONNECTOR_TOKEN_BINDING_NAMES},
    **{name: "scope_witness" for name in SCOPE_WITNESS_BINDING_NAMES},
}
READ_ONLY_SCOPE_HINTS = ("read", "readonly", "metadata", "calendar.events.readonly", "gmail.readonly")
WRITE_SCOPE_HINTS = ("write", "send", "modify", "compose", "insert", "delete")
EnvReader = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarBindingEntry:
    """One redacted finance email/calendar binding entry."""

    name: str
    present: bool
    binding_kind: str
    binding_group: str
    risk: str = "high"
    approval_required: bool = True
    receipt_projection: str = "name_and_presence_only"
    value_serialized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarBindingReceipt:
    """Redacted connector token presence receipt for finance live handoff."""

    schema_version: int
    receipt_id: str
    checked_at: str
    secret_serialization: str
    ready: bool
    accepted_binding_names: tuple[str, ...]
    present_binding_names: tuple[str, ...]
    required_binding_groups: tuple[str, ...]
    satisfied_binding_groups: tuple[str, ...]
    read_only_scope_witness_names: tuple[str, ...]
    invalid_scope_witness_names: tuple[str, ...]
    readiness_blockers: tuple[str, ...]
    binding_count: int
    bindings: tuple[FinanceEmailCalendarBindingEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "checked_at": self.checked_at,
            "secret_serialization": self.secret_serialization,
            "ready": self.ready,
            "accepted_binding_names": list(self.accepted_binding_names),
            "present_binding_names": list(self.present_binding_names),
            "required_binding_groups": list(self.required_binding_groups),
            "satisfied_binding_groups": list(self.satisfied_binding_groups),
            "read_only_scope_witness_names": list(self.read_only_scope_witness_names),
            "invalid_scope_witness_names": list(self.invalid_scope_witness_names),
            "readiness_blockers": list(self.readiness_blockers),
            "binding_count": self.binding_count,
            "bindings": [binding.as_dict() for binding in self.bindings],
        }


def emit_finance_approval_email_calendar_binding_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    env_reader: EnvReader | None = None,
) -> tuple[FinanceEmailCalendarBindingReceipt, tuple[str, ...]]:
    """Build and validate a redacted finance email/calendar binding receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance email/calendar binding receipt schema", errors)
    resolved_env_reader = env_reader or os.environ.get
    env_values = {name: (resolved_env_reader(name) or "").strip() for name in ACCEPTED_BINDING_NAMES}
    bindings = tuple(
        FinanceEmailCalendarBindingEntry(
            name=name,
            present=bool(env_values[name]),
            binding_kind=BINDING_KIND_BY_NAME[name],
            binding_group=BINDING_GROUP_BY_NAME[name],
        )
        for name in ACCEPTED_BINDING_NAMES
    )
    present_names = tuple(binding.name for binding in bindings if binding.present)
    read_only_scope_names, invalid_scope_names = _classify_scope_witnesses(env_values)
    satisfied_groups = _satisfied_binding_groups(
        present_names=present_names,
        read_only_scope_names=read_only_scope_names,
    )
    readiness_blockers = _readiness_blockers(
        satisfied_groups=satisfied_groups,
        invalid_scope_names=invalid_scope_names,
    )
    receipt = FinanceEmailCalendarBindingReceipt(
        schema_version=1,
        receipt_id=_receipt_id(
            present_names=present_names,
            read_only_scope_names=read_only_scope_names,
            invalid_scope_names=invalid_scope_names,
            readiness_blockers=readiness_blockers,
        ),
        checked_at=_validation_clock(),
        secret_serialization="forbidden",
        ready=not readiness_blockers,
        accepted_binding_names=ACCEPTED_BINDING_NAMES,
        present_binding_names=present_names,
        required_binding_groups=REQUIRED_BINDING_GROUPS,
        satisfied_binding_groups=satisfied_groups,
        read_only_scope_witness_names=read_only_scope_names,
        invalid_scope_witness_names=invalid_scope_names,
        readiness_blockers=readiness_blockers,
        binding_count=len(bindings),
        bindings=bindings,
    )
    if schema:
        errors.extend(_validate_schema_instance(schema, receipt.as_dict()))
    _validate_no_values_serialized(receipt, errors)
    return receipt, tuple(errors)


def write_finance_email_calendar_binding_receipt(
    receipt: FinanceEmailCalendarBindingReceipt,
    output_path: Path,
) -> Path:
    """Write one redacted finance email/calendar binding receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_no_values_serialized(
    receipt: FinanceEmailCalendarBindingReceipt,
    errors: list[str],
) -> None:
    if receipt.secret_serialization != "forbidden":
        errors.append("secret_serialization must be forbidden")
    for binding in receipt.bindings:
        if binding.value_serialized is not False:
            errors.append(f"{binding.name} value_serialized must be false")
        if binding.receipt_projection != "name_and_presence_only":
            errors.append(f"{binding.name} receipt_projection must be name_and_presence_only")


def _classify_scope_witnesses(env_values: dict[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    read_only_names: list[str] = []
    invalid_names: list[str] = []
    for name in SCOPE_WITNESS_BINDING_NAMES:
        value = env_values[name]
        if not value:
            continue
        if _scope_is_read_only(value):
            read_only_names.append(name)
        else:
            invalid_names.append(name)
    return tuple(read_only_names), tuple(invalid_names)


def _scope_is_read_only(scope_value: str) -> bool:
    scope = scope_value.lower()
    if "calendar.events" in scope and "calendar.events.readonly" not in scope:
        return False
    if any(hint in scope for hint in WRITE_SCOPE_HINTS):
        return False
    return any(hint in scope for hint in READ_ONLY_SCOPE_HINTS)


def _satisfied_binding_groups(
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


def _readiness_blockers(
    *,
    satisfied_groups: tuple[str, ...],
    invalid_scope_names: tuple[str, ...],
) -> tuple[str, ...]:
    satisfied = set(satisfied_groups)
    blockers = [f"missing_{group}" for group in REQUIRED_BINDING_GROUPS if group not in satisfied]
    blockers.extend(f"invalid_scope_witness:{name}" for name in invalid_scope_names)
    return tuple(blockers)


def _receipt_id(
    *,
    present_names: tuple[str, ...],
    read_only_scope_names: tuple[str, ...],
    invalid_scope_names: tuple[str, ...],
    readiness_blockers: tuple[str, ...],
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "accepted_binding_names": ACCEPTED_BINDING_NAMES,
                "present_binding_names": present_names,
                "required_binding_groups": REQUIRED_BINDING_GROUPS,
                "read_only_scope_witness_names": read_only_scope_names,
                "invalid_scope_witness_names": invalid_scope_names,
                "readiness_blockers": readiness_blockers,
                "checked_at": _validation_clock(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"finance-email-calendar-binding-receipt-{digest[:16]}"


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


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance email/calendar binding receipt arguments."""
    parser = argparse.ArgumentParser(description="Emit redacted finance email/calendar binding receipt.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance email/calendar binding receipt emission."""
    args = parse_args(argv)
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(schema_path=Path(args.schema))
    write_finance_email_calendar_binding_receipt(receipt, Path(args.output))
    payload = receipt.as_dict() | {"errors": list(errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif receipt.ready and not errors:
        print("finance email/calendar binding receipt ready")
    else:
        print("finance email/calendar binding receipt blocked")
    return 0 if (not errors and (receipt.ready or not args.strict)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
