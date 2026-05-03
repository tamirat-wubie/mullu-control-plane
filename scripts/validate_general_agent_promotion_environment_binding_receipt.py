#!/usr/bin/env python3
"""Validate a redacted general-agent promotion environment binding receipt.

Purpose: reject stale, malformed, or value-leaking environment binding receipts
before live adapter or deployment execution starts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .change_assurance/general_agent_promotion_environment_binding_receipt.json,
examples/general_agent_promotion_environment_bindings.json, and
schemas/general_agent_promotion_environment_binding_receipt.schema.json.
Invariants:
  - Receipt binding names match the environment binding contract.
  - Receipt values are never serialized.
  - The ready flag is derived from missing_bindings.
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

from scripts.emit_general_agent_promotion_environment_binding_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RECEIPT,
    DEFAULT_RECEIPT_SCHEMA,
)
from scripts.validate_general_agent_promotion_environment_bindings import (  # noqa: E402
    DEFAULT_CONTRACT,
    DEFAULT_SCHEMA as DEFAULT_CONTRACT_SCHEMA,
    validate_general_agent_promotion_environment_bindings,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


@dataclass(frozen=True, slots=True)
class PromotionEnvironmentBindingReceiptValidation:
    """Validation result for one redacted binding receipt."""

    valid: bool
    ready: bool
    receipt_id: str
    receipt_path: str
    binding_count: int
    missing_bindings: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["missing_bindings"] = list(self.missing_bindings)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_environment_binding_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    contract_path: Path = DEFAULT_CONTRACT,
    contract_schema_path: Path = DEFAULT_CONTRACT_SCHEMA,
    require_ready: bool = False,
) -> PromotionEnvironmentBindingReceiptValidation:
    """Validate one redacted environment binding receipt."""
    errors: list[str] = []
    contract_validation = validate_general_agent_promotion_environment_bindings(
        contract_path=contract_path,
        schema_path=contract_schema_path,
    )
    errors.extend(contract_validation.errors)
    receipt_schema = _load_json_object(receipt_schema_path, "environment binding receipt schema", errors)
    receipt = _load_json_object(receipt_path, "environment binding receipt", errors)
    contract = _load_json_object(contract_path, "environment binding contract", errors)
    if not receipt_schema or not receipt or not contract:
        return _validation_result(receipt_path, receipt, errors)

    errors.extend(_validate_schema_instance(receipt_schema, receipt))
    _validate_scalar_fields(receipt, contract, errors)
    _validate_receipt_bindings(receipt, contract, errors)
    if require_ready and receipt.get("ready") is not True:
        errors.append("receipt ready must be true")
    return _validation_result(receipt_path, receipt, errors)


def _validate_scalar_fields(receipt: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    expected_scalars: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": "general-agent-promotion-environment-binding-receipt-v1",
        "contract_id": contract.get("contract_id"),
        "secret_serialization": "forbidden",
    }
    for field_name, expected_value in expected_scalars.items():
        if receipt.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value!r}")
    missing_bindings = receipt.get("missing_bindings", [])
    if isinstance(missing_bindings, list):
        expected_ready = not missing_bindings
        if receipt.get("ready") is not expected_ready:
            errors.append(f"ready must be {expected_ready} based on missing_bindings")


def _validate_receipt_bindings(receipt: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    receipt_bindings = receipt.get("bindings", [])
    contract_bindings = contract.get("bindings", [])
    if not isinstance(receipt_bindings, list):
        errors.append("bindings must be a list")
        return
    if not isinstance(contract_bindings, list):
        errors.append("contract bindings must be a list")
        return
    contract_by_name = {
        str(binding.get("name", "")): binding
        for binding in contract_bindings
        if isinstance(binding, dict)
    }
    receipt_by_name: dict[str, dict[str, Any]] = {}
    for binding in receipt_bindings:
        if not isinstance(binding, dict):
            errors.append("receipt bindings entries must be objects")
            continue
        name = str(binding.get("name", ""))
        if name in receipt_by_name:
            errors.append(f"duplicate receipt binding name {name}")
        receipt_by_name[name] = binding
        contract_binding = contract_by_name.get(name)
        if contract_binding is None:
            errors.append(f"unexpected receipt binding name {name}")
            continue
        for field_name in ("binding_kind", "risk", "approval_required", "receipt_projection"):
            if binding.get(field_name) != contract_binding.get(field_name):
                errors.append(f"{name} {field_name} must match contract")
        if binding.get("value_serialized") is not False:
            errors.append(f"{name} value_serialized must be false")
    _validate_binding_name_sets(receipt, receipt_bindings, contract_by_name, receipt_by_name, errors)


def _validate_binding_name_sets(
    receipt: dict[str, Any],
    receipt_bindings: list[Any],
    contract_by_name: dict[str, dict[str, Any]],
    receipt_by_name: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    contract_names = set(contract_by_name)
    receipt_names = set(receipt_by_name)
    if receipt_names != contract_names:
        errors.append(
            "receipt binding names must match contract: "
            f"receipt_only={sorted(receipt_names - contract_names)} "
            f"contract_only={sorted(contract_names - receipt_names)}"
        )
    missing_bindings = set(str(name) for name in receipt.get("missing_bindings", []) if isinstance(name, str))
    expected_missing = {name for name, binding in receipt_by_name.items() if binding.get("present") is not True}
    if missing_bindings != expected_missing:
        errors.append(
            "missing_bindings must match bindings with present=false: "
            f"observed={sorted(missing_bindings)} expected={sorted(expected_missing)}"
        )
    if receipt.get("binding_count") != len(receipt_bindings):
        errors.append("binding_count must match bindings length")


def _validation_result(
    receipt_path: Path,
    receipt: dict[str, Any],
    errors: list[str],
) -> PromotionEnvironmentBindingReceiptValidation:
    missing_bindings = receipt.get("missing_bindings", ())
    return PromotionEnvironmentBindingReceiptValidation(
        valid=not errors,
        ready=receipt.get("ready") is True,
        receipt_id=str(receipt.get("receipt_id", "")),
        receipt_path=str(receipt_path),
        binding_count=int(receipt.get("binding_count", 0)) if isinstance(receipt.get("binding_count", 0), int) else 0,
        missing_bindings=tuple(str(name) for name in missing_bindings) if isinstance(missing_bindings, list) else (),
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse environment binding receipt validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate redacted promotion environment binding receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--contract-schema", default=str(DEFAULT_CONTRACT_SCHEMA))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for redacted environment binding receipt validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_environment_binding_receipt(
        receipt_path=Path(args.receipt),
        receipt_schema_path=Path(args.receipt_schema),
        contract_path=Path(args.contract),
        contract_schema_path=Path(args.contract_schema),
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion environment binding receipt ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
