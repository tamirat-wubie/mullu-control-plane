#!/usr/bin/env python3
"""Emit a redacted general-agent promotion environment binding receipt.

Purpose: record operator environment binding presence before live adapter or
deployment execution starts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/general_agent_promotion_environment_bindings.json and
schemas/general_agent_promotion_environment_binding_receipt.schema.json.
Invariants:
  - Environment values are never serialized.
  - Each binding receipt records only name, presence, kind, risk, approval, and projection.
  - Strict mode fails until every contract binding is present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_general_agent_promotion_environment_bindings import (  # noqa: E402
    DEFAULT_CONTRACT,
    DEFAULT_SCHEMA as DEFAULT_CONTRACT_SCHEMA,
    validate_general_agent_promotion_environment_bindings,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_environment_binding_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_environment_binding_receipt.json"
EnvReader = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class EnvironmentBindingReceiptEntry:
    """One redacted environment binding receipt entry."""

    name: str
    present: bool
    binding_kind: str
    risk: str
    approval_required: bool
    receipt_projection: str
    value_serialized: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt entry."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EnvironmentBindingReceipt:
    """Redacted receipt for promotion environment binding presence."""

    schema_version: int
    receipt_id: str
    checked_at: str
    contract_id: str
    secret_serialization: str
    ready: bool
    binding_count: int
    missing_bindings: tuple[str, ...]
    bindings: tuple[EnvironmentBindingReceiptEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready receipt output."""
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "checked_at": self.checked_at,
            "contract_id": self.contract_id,
            "secret_serialization": self.secret_serialization,
            "ready": self.ready,
            "binding_count": self.binding_count,
            "missing_bindings": list(self.missing_bindings),
            "bindings": [binding.as_dict() for binding in self.bindings],
        }


def emit_general_agent_promotion_environment_binding_receipt(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    contract_schema_path: Path = DEFAULT_CONTRACT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    env_reader: EnvReader | None = None,
) -> tuple[EnvironmentBindingReceipt, tuple[str, ...]]:
    """Build and validate a redacted environment binding receipt."""
    errors: list[str] = []
    contract_validation = validate_general_agent_promotion_environment_bindings(
        contract_path=contract_path,
        schema_path=contract_schema_path,
    )
    errors.extend(contract_validation.errors)
    contract = _load_json_object(contract_path, "environment binding contract", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "environment binding receipt schema", errors)
    if errors:
        return _empty_receipt(), tuple(errors)

    resolved_env_reader = env_reader or os.environ.get
    entries = tuple(
        _receipt_entry(binding, resolved_env_reader)
        for binding in contract.get("bindings", ())
        if isinstance(binding, dict)
    )
    missing = tuple(entry.name for entry in entries if not entry.present)
    receipt = EnvironmentBindingReceipt(
        schema_version=1,
        receipt_id="general-agent-promotion-environment-binding-receipt-v1",
        checked_at=_validation_clock(),
        contract_id=str(contract.get("contract_id", "")),
        secret_serialization=str(contract.get("secret_serialization", "")),
        ready=not missing,
        binding_count=len(entries),
        missing_bindings=missing,
        bindings=entries,
    )
    errors.extend(_validate_schema_instance(receipt_schema, receipt.as_dict()))
    _validate_no_values_serialized(receipt, errors)
    return receipt, tuple(errors)


def write_environment_binding_receipt(receipt: EnvironmentBindingReceipt, output_path: Path) -> Path:
    """Write one redacted environment binding receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _receipt_entry(binding: dict[str, Any], env_reader: EnvReader) -> EnvironmentBindingReceiptEntry:
    name = str(binding.get("name", ""))
    return EnvironmentBindingReceiptEntry(
        name=name,
        present=bool((env_reader(name) or "").strip()),
        binding_kind=str(binding.get("binding_kind", "")),
        risk=str(binding.get("risk", "")),
        approval_required=binding.get("approval_required") is True,
        receipt_projection="name_and_presence_only",
        value_serialized=False,
    )


def _validate_no_values_serialized(receipt: EnvironmentBindingReceipt, errors: list[str]) -> None:
    for entry in receipt.bindings:
        if entry.value_serialized is not False:
            errors.append(f"{entry.name} value_serialized must be false")
        if entry.receipt_projection != "name_and_presence_only":
            errors.append(f"{entry.name} receipt_projection must be name_and_presence_only")


def _empty_receipt() -> EnvironmentBindingReceipt:
    return EnvironmentBindingReceipt(
        schema_version=1,
        receipt_id="general-agent-promotion-environment-binding-receipt-v1",
        checked_at=_validation_clock(),
        contract_id="",
        secret_serialization="forbidden",
        ready=False,
        binding_count=0,
        missing_bindings=(),
        bindings=(),
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


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse environment binding receipt CLI arguments."""
    parser = argparse.ArgumentParser(description="Emit redacted promotion environment binding receipt.")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--contract-schema", default=str(DEFAULT_CONTRACT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for redacted environment binding receipt emission."""
    args = parse_args(argv)
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        contract_path=Path(args.contract),
        contract_schema_path=Path(args.contract_schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    write_environment_binding_receipt(receipt, Path(args.output))
    payload = receipt.as_dict() | {"errors": list(errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif receipt.ready and not errors:
        print(f"general-agent promotion environment binding receipt ready bindings={receipt.binding_count}")
    else:
        print(f"general-agent promotion environment binding receipt blocked missing={list(receipt.missing_bindings)}")
    return 0 if (not errors and (receipt.ready or not args.strict)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
