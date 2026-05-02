#!/usr/bin/env python3
"""Validate general-agent promotion environment binding contracts.

Purpose: keep operator-provided environment bindings explicit, risk-classified,
and safe to reference without serializing secret values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/general_agent_promotion_environment_bindings.json,
schemas/general_agent_promotion_environment_bindings.schema.json, and the
general-agent promotion operator checklist.
Invariants:
  - Required binding names match the operator checklist.
  - Secret-like bindings are critical, approval-required, and never serialized.
  - Receipts may record binding names and presence only.
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

from scripts.validate_general_agent_promotion_operator_checklist import (  # noqa: E402
    DEFAULT_CHECKLIST,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_CONTRACT = REPO_ROOT / "examples" / "general_agent_promotion_environment_bindings.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_environment_bindings.schema.json"
REQUIRED_BINDING_SPECS: dict[str, tuple[str, str, bool]] = {
    "MULLU_BROWSER_SANDBOX_EVIDENCE": ("artifact_path", "medium", False),
    "MULLU_VOICE_PROBE_AUDIO": ("audio_path", "high", True),
    "MULLU_GATEWAY_URL": ("url", "high", False),
    "MULLU_RUNTIME_WITNESS_SECRET": ("secret", "critical", True),
    "MULLU_RUNTIME_CONFORMANCE_SECRET": ("secret", "critical", True),
    "MULLU_AUTHORITY_OPERATOR_SECRET": ("secret", "critical", True),
}


@dataclass(frozen=True, slots=True)
class PromotionEnvironmentBindingValidation:
    """Validation result for the environment binding contract."""

    valid: bool
    contract_id: str
    contract_path: str
    schema_path: str
    binding_count: int
    required_names: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["required_names"] = list(self.required_names)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_environment_bindings(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    schema_path: Path = DEFAULT_SCHEMA,
    checklist_path: Path = DEFAULT_CHECKLIST,
) -> PromotionEnvironmentBindingValidation:
    """Validate the promotion environment binding contract."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "environment binding schema", errors)
    contract = _load_json_object(contract_path, "environment binding contract", errors)
    checklist = _load_json_object(checklist_path, "operator checklist", errors)
    if not schema or not contract or not checklist:
        return _validation_result(contract_path, schema_path, contract, errors)

    errors.extend(_validate_schema_instance(schema, contract))
    _validate_scalar_fields(contract, errors)
    _validate_binding_specs(contract, errors)
    _validate_checklist_alignment(contract, checklist, errors)
    return _validation_result(contract_path, schema_path, contract, errors)


def _validate_scalar_fields(contract: dict[str, Any], errors: list[str]) -> None:
    expected_scalars: dict[str, Any] = {
        "schema_version": 1,
        "contract_id": "general-agent-promotion-environment-bindings-v1",
        "status": "blocked_until_operator_binding",
        "secret_serialization": "forbidden",
    }
    for field_name, expected_value in expected_scalars.items():
        if contract.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value!r}")


def _validate_binding_specs(contract: dict[str, Any], errors: list[str]) -> None:
    bindings = contract.get("bindings", [])
    if not isinstance(bindings, list):
        errors.append("bindings must be a list")
        return
    observed_names: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            errors.append("bindings entries must be objects")
            continue
        name = str(binding.get("name", ""))
        if name in observed_names:
            errors.append(f"duplicate binding name {name}")
        observed_names.add(name)
        expected = REQUIRED_BINDING_SPECS.get(name)
        if expected is None:
            errors.append(f"unexpected binding name {name}")
            continue
        expected_kind, expected_risk, expected_approval = expected
        if binding.get("binding_kind") != expected_kind:
            errors.append(f"{name} binding_kind must be {expected_kind}")
        if binding.get("risk") != expected_risk:
            errors.append(f"{name} risk must be {expected_risk}")
        if binding.get("approval_required") is not expected_approval:
            errors.append(f"{name} approval_required must be {expected_approval}")
        if binding.get("may_serialize_value") is not False:
            errors.append(f"{name} may_serialize_value must be false")
        if binding.get("receipt_projection") != "name_and_presence_only":
            errors.append(f"{name} receipt_projection must be name_and_presence_only")
        if expected_kind == "secret" and expected_approval is not True:
            errors.append(f"{name} secret binding must require approval")
    missing = sorted(set(REQUIRED_BINDING_SPECS) - observed_names)
    if missing:
        errors.append(f"bindings missing {missing}")


def _validate_checklist_alignment(
    contract: dict[str, Any],
    checklist: dict[str, Any],
    errors: list[str],
) -> None:
    contract_names = {
        str(binding.get("name", ""))
        for binding in contract.get("bindings", [])
        if isinstance(binding, dict)
    }
    checklist_names = {
        str(name)
        for name in checklist.get("required_environment_variables", [])
    }
    if contract_names != checklist_names:
        errors.append(
            "binding names must match checklist required_environment_variables: "
            f"contract_only={sorted(contract_names - checklist_names)} "
            f"checklist_only={sorted(checklist_names - contract_names)}"
        )


def _validation_result(
    contract_path: Path,
    schema_path: Path,
    contract: dict[str, Any],
    errors: list[str],
) -> PromotionEnvironmentBindingValidation:
    bindings = contract.get("bindings", ())
    required_names = tuple(
        sorted(str(binding.get("name", "")) for binding in bindings if isinstance(binding, dict))
    )
    return PromotionEnvironmentBindingValidation(
        valid=not errors,
        contract_id=str(contract.get("contract_id", "")),
        contract_path=str(contract_path),
        schema_path=str(schema_path),
        binding_count=len(bindings) if isinstance(bindings, list) else 0,
        required_names=required_names,
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
    """Parse environment binding validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion environment bindings.")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for environment binding validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_environment_bindings(
        contract_path=Path(args.contract),
        schema_path=Path(args.schema),
        checklist_path=Path(args.checklist),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion environment bindings ok bindings={result.binding_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
