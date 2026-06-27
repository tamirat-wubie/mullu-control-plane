#!/usr/bin/env python3
"""Validate the gate template registry.

Purpose: prove reusable gate templates are schema-valid, deterministic, and
cover every gate referenced by capability passports.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/gate_template_registry.schema.json,
examples/gate_template_registry.foundation.json, capability passports, and
schema validation helpers.
Invariants:
  - Every gate template is reusable policy metadata, not execution authority.
  - Every capability passport required gate resolves to one template.
  - Approval, evidence, rollback, connector, workspace, external-send, and
    receipt gates are canonical registry members.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402
from mcoi_runtime.app.gate_template_registry import build_gate_template_registry  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "gate_template_registry.schema.json"
DEFAULT_REGISTRY = REPO_ROOT / "examples" / "gate_template_registry.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "gate_template_registry_validation.json"

REQUIRED_TEMPLATE_IDS = {
    "gate.approval.required",
    "gate.evidence.intake",
    "gate.evidence.verification",
    "gate.rollback.required",
    "gate.connector.lease",
    "gate.workspace.write",
    "gate.external.send",
    "gate.receipt.append",
}
REQUIRED_VALIDATOR_COMMANDS = {
    "gate_template_registry_validator": "python scripts/validate_gate_template_registry.py",
    "gate_template_registry_tests": "python -m pytest tests/test_validate_gate_template_registry.py -q",
}


@dataclass(frozen=True, slots=True)
class GateTemplateRegistryValidation:
    """Validation report for the gate template registry."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    registry_path: str
    template_count: int
    passport_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_gate_template_registry(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    registry_path: Path = DEFAULT_REGISTRY,
) -> GateTemplateRegistryValidation:
    """Validate the gate template registry and passport gate coverage."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "gate template registry schema", errors)
    registry = _load_json_object(registry_path, "gate template registry example", errors)
    runtime_registry = build_gate_template_registry() if not errors else {}
    passport_gate_ids = _capability_passport_gate_ids()

    if schema and registry:
        errors.extend(f"{_path_label(registry_path)}: {error}" for error in _validate_schema_instance(schema, registry))
        if registry != runtime_registry:
            errors.append(f"{_path_label(registry_path)}: example does not match runtime projection")
    if registry:
        _validate_registry(registry, passport_gate_ids, errors, _path_label(registry_path))

    templates = registry.get("templates", ()) if isinstance(registry, dict) else ()
    return GateTemplateRegistryValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        registry_path=_path_label(registry_path),
        template_count=len(templates) if isinstance(templates, list) else 0,
        passport_gate_count=len(passport_gate_ids),
    )


def write_gate_template_registry_validation(
    validation: GateTemplateRegistryValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic gate template registry validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_registry(
    registry: dict[str, Any],
    passport_gate_ids: set[str],
    errors: list[str],
    label: str,
) -> None:
    if registry.get("registry_is_not_execution_authority") is not True:
        errors.append(f"{label}: registry_is_not_execution_authority must be true")
    _validate_validators(registry, errors, label)

    templates = registry.get("templates")
    if not isinstance(templates, list):
        errors.append(f"{label}: templates must be a list")
        return

    template_by_id: dict[str, dict[str, Any]] = {}
    for template in templates:
        if not isinstance(template, dict):
            errors.append(f"{label}: template entries must be objects")
            continue
        gate_id = str(template.get("gate_id", ""))
        if gate_id in template_by_id:
            errors.append(f"{label}: duplicate gate template {gate_id}")
        template_by_id[gate_id] = template
        _validate_template(template, errors, label)

    missing_required = sorted(REQUIRED_TEMPLATE_IDS - set(template_by_id))
    if missing_required:
        errors.append(f"{label}: missing required template ids {missing_required}")
    missing_passport_gates = sorted(passport_gate_ids - set(template_by_id))
    if missing_passport_gates:
        errors.append(f"{label}: capability passport gates missing templates {missing_passport_gates}")
    extra_without_passport = sorted(set(template_by_id) - passport_gate_ids)
    if extra_without_passport:
        errors.append(f"{label}: templates not referenced by capability passports {extra_without_passport}")

    if registry.get("template_count") != len(templates):
        errors.append(f"{label}: template_count must match templates")
    categories = registry.get("categories")
    if isinstance(categories, dict):
        projected_categories: dict[str, int] = {}
        for template in templates:
            if isinstance(template, dict):
                category = str(template.get("category", ""))
                projected_categories[category] = projected_categories.get(category, 0) + 1
        if categories != dict(sorted(projected_categories.items())):
            errors.append(f"{label}: categories must match templates")
    else:
        errors.append(f"{label}: categories must be an object")


def _validate_template(template: dict[str, Any], errors: list[str], label: str) -> None:
    gate_id = str(template.get("gate_id", "<missing>"))
    required_receipts = _string_list(template.get("required_receipts"))
    blocks_when_missing = _string_list(template.get("blocks_when_missing"))
    validator_refs = _string_list(template.get("validator_refs"))

    if not required_receipts:
        errors.append(f"{label}: {gate_id} must declare required_receipts")
    if not blocks_when_missing:
        errors.append(f"{label}: {gate_id} must declare blocks_when_missing")
    if "capability_passports_validator" not in validator_refs and gate_id != "gate.uao.admission":
        errors.append(f"{label}: {gate_id} must reference capability_passports_validator")
    if gate_id == "gate.approval.required":
        if template.get("operator_status_when_missing") != "Needs approval":
            errors.append(f"{label}: {gate_id} must map missing state to Needs approval")
        if "execute_without_approval" not in blocks_when_missing:
            errors.append(f"{label}: {gate_id} must block execute_without_approval")
    if gate_id == "gate.receipt.append" and "terminal_closure_certificate" not in required_receipts:
        errors.append(f"{label}: {gate_id} must require terminal_closure_certificate")
    if gate_id == "gate.rollback.required" and "execute_without_recovery" not in blocks_when_missing:
        errors.append(f"{label}: {gate_id} must block execute_without_recovery")


def _validate_validators(registry: dict[str, Any], errors: list[str], label: str) -> None:
    validators = registry.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _capability_passport_gate_ids() -> set[str]:
    passports = build_capability_passports()["passports"]
    gate_ids: set[str] = set()
    for passport in passports:
        gate_ids.update(str(gate_id) for gate_id in passport.get("required_gates", ()))
    return gate_ids


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse gate template registry validation arguments."""

    parser = argparse.ArgumentParser(description="Validate gate template registry.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for gate template registry validation."""

    args = parse_args(argv)
    validation = validate_gate_template_registry(
        schema_path=Path(args.schema),
        registry_path=Path(args.registry),
    )
    write_gate_template_registry_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("GATE TEMPLATE REGISTRY VALID")
    else:
        print(f"GATE TEMPLATE REGISTRY INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
