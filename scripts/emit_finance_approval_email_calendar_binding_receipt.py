#!/usr/bin/env python3
"""Emit a redacted finance email/calendar connector binding receipt.

Purpose: prove whether one accepted email/calendar connector token is present
before running the finance approval live handoff receipt.
Governance scope: finance approval email/calendar token presence, redacted
secret handling, schema validation, and operator approval boundary.
Dependencies: schemas/finance_approval_email_calendar_binding_receipt.schema.json.
Invariants:
  - Token values are never serialized.
  - Any one accepted connector token is enough for readiness.
  - Every binding entry records name and presence only.
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
ACCEPTED_BINDING_NAMES = (
    "GMAIL_ACCESS_TOKEN",
    "GOOGLE_CALENDAR_ACCESS_TOKEN",
    "MICROSOFT_GRAPH_ACCESS_TOKEN",
)
EnvReader = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarBindingEntry:
    """One redacted finance email/calendar binding entry."""

    name: str
    present: bool
    binding_kind: str = "secret"
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
    bindings = tuple(
        FinanceEmailCalendarBindingEntry(
            name=name,
            present=bool((resolved_env_reader(name) or "").strip()),
        )
        for name in ACCEPTED_BINDING_NAMES
    )
    present_names = tuple(binding.name for binding in bindings if binding.present)
    receipt = FinanceEmailCalendarBindingReceipt(
        schema_version=1,
        receipt_id=_receipt_id(present_names),
        checked_at=_validation_clock(),
        secret_serialization="forbidden",
        ready=bool(present_names),
        accepted_binding_names=ACCEPTED_BINDING_NAMES,
        present_binding_names=present_names,
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


def _receipt_id(present_names: tuple[str, ...]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "accepted_binding_names": ACCEPTED_BINDING_NAMES,
                "present_binding_names": present_names,
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
