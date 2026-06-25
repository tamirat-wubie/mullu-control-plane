#!/usr/bin/env python3
"""Validate Component Harness passports.

Purpose: prove each registered component has one registry-derived passport
that fuses identity, lifecycle, authority, proofs, receipts, health,
dependencies, blocked actions, and validation refs.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_passports.schema.json,
examples/component_passports.foundation.json, component registry, and authority
envelope witnesses.
Invariants:
  - Every registered component has exactly one passport.
  - Passports mirror registry and authority witness state.
  - Passports cannot grant execution authority or terminal closure.
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

from mcoi_runtime.app.component_passports import (  # noqa: E402
    LIVE_AUTHORITY_FLAGS,
    build_component_passports,
)
from scripts.validate_component_authority_envelope_witnesses import (  # noqa: E402
    validate_component_authority_envelope_witnesses,
)
from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_passports.schema.json"
DEFAULT_PASSPORTS = REPO_ROOT / "examples" / "component_passports.foundation.json"
DEFAULT_REGISTRY = REPO_ROOT / "examples" / "component_registry.foundation.json"
DEFAULT_AUTHORITY_WITNESSES = REPO_ROOT / "examples" / "component_authority_envelope_witnesses.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_passports_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_passports_validator": "python scripts/validate_component_passports.py",
    "component_passports_tests": "python -m pytest tests/test_validate_component_passports.py -q",
}


@dataclass(frozen=True, slots=True)
class ComponentPassportValidation:
    """Validation report for component passports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    passport_path: str
    registry_path: str
    authority_witnesses_path: str
    passport_count: int
    component_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_passports(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    passport_path: Path = DEFAULT_PASSPORTS,
    registry_path: Path = DEFAULT_REGISTRY,
    authority_witnesses_path: Path = DEFAULT_AUTHORITY_WITNESSES,
) -> ComponentPassportValidation:
    """Validate component passports against governed source artifacts."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component passports schema", errors)
    passports = _load_json_object(passport_path, "component passports example", errors)
    registry = _load_json_object(registry_path, "component registry example", errors)
    authority_witnesses = _load_json_object(
        authority_witnesses_path,
        "component authority envelope witnesses example",
        errors,
    )

    registry_validation = validate_component_registry(example_paths=(registry_path,))
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)
    authority_validation = validate_component_authority_envelope_witnesses(
        witness_path=authority_witnesses_path,
        registry_path=registry_path,
    )
    if not authority_validation.ok:
        errors.extend(
            f"component authority envelope witness validation failed: {error}"
            for error in authority_validation.errors
        )

    runtime_passports = (
        build_component_passports(
            registry_path=registry_path,
            authority_witnesses_path=authority_witnesses_path,
        )
        if registry and authority_witnesses
        else {}
    )
    if schema and passports:
        errors.extend(f"{_path_label(passport_path)}: {error}" for error in _validate_schema_instance(schema, passports))
        if passports != runtime_passports:
            errors.append(f"{_path_label(passport_path)}: example does not match runtime projection")
    if passports and registry:
        _validate_passport_set(passports, registry, errors, _path_label(passport_path))

    passport_entries = passports.get("passports", ()) if isinstance(passports, dict) else ()
    component_entries = registry.get("components", ()) if isinstance(registry, dict) else ()
    return ComponentPassportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        passport_path=_path_label(passport_path),
        registry_path=_path_label(registry_path),
        authority_witnesses_path=_path_label(authority_witnesses_path),
        passport_count=len(passport_entries) if isinstance(passport_entries, list) else 0,
        component_count=len(component_entries) if isinstance(component_entries, list) else 0,
    )


def write_component_passport_validation(
    validation: ComponentPassportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic component passport validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_passport_set(
    passports: dict[str, Any],
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if passports.get("passport_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: passport_set_is_not_execution_authority must be true")
    for flag_name in ("live_execution_enabled", "live_connector_send_enabled"):
        if passports.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if passports.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    _validate_validators(passports, errors, label)

    component_by_id = _component_by_id(registry, errors, label)
    passport_entries = passports.get("passports")
    if not isinstance(passport_entries, list):
        errors.append(f"{label}: passports must be a list")
        return

    passport_ids: set[str] = set()
    passport_components: set[str] = set()
    for passport in passport_entries:
        if not isinstance(passport, dict):
            errors.append(f"{label}: passport entries must be objects")
            continue
        passport_id = str(passport.get("passport_id", ""))
        component_id = str(passport.get("component_id", ""))
        if passport_id in passport_ids:
            errors.append(f"{label}: duplicate passport_id {passport_id}")
        passport_ids.add(passport_id)
        if component_id in passport_components:
            errors.append(f"{label}: duplicate passport for {component_id}")
        passport_components.add(component_id)
        component = component_by_id.get(component_id)
        if component is None:
            errors.append(f"{label}: passport component {component_id} is not registered")
            continue
        _validate_passport(passport, component, errors, label)

    missing_passports = sorted(set(component_by_id) - passport_components)
    extra_passports = sorted(passport_components - set(component_by_id))
    if missing_passports:
        errors.append(f"{label}: registered components missing passports {missing_passports}")
    if extra_passports:
        errors.append(f"{label}: passports for unknown components {extra_passports}")

    summary = passports.get("summary")
    if isinstance(summary, dict):
        if summary.get("component_count") != len(component_by_id):
            errors.append(f"{label}: summary.component_count must match registry")
        if summary.get("passport_count") != len(passport_entries):
            errors.append(f"{label}: summary.passport_count must match passport entries")


def _validate_validators(passports: dict[str, Any], errors: list[str], label: str) -> None:
    validators = passports.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id: dict[str, dict[str, Any]] = {}
    for validator in validators:
        if not isinstance(validator, dict):
            errors.append(f"{label}: validator entries must be objects")
            continue
        validator_by_id[str(validator.get("validator_id", ""))] = validator
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _validate_passport(
    passport: dict[str, Any],
    component: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(component.get("id", "<missing>"))
    lifecycle = passport.get("lifecycle")
    if not isinstance(lifecycle, dict):
        errors.append(f"{label}: component {component_id} lifecycle must be an object")
    else:
        for field_name in ("mode", "lifecycle_state", "wiring_state", "authority_level"):
            if lifecycle.get(field_name) != component.get(field_name):
                errors.append(f"{label}: component {component_id} lifecycle.{field_name} must match registry")

    identity = passport.get("identity")
    if isinstance(identity, dict):
        for field_name in ("name", "type", "owner_surface"):
            if identity.get(field_name) != component.get(field_name):
                errors.append(f"{label}: component {component_id} identity.{field_name} must match registry")
    else:
        errors.append(f"{label}: component {component_id} identity must be an object")

    if passport.get("authority") != component.get("authority"):
        errors.append(f"{label}: component {component_id} authority must match registry")
    authority = passport.get("authority")
    if isinstance(authority, dict):
        for flag_name in LIVE_AUTHORITY_FLAGS:
            if authority.get(flag_name) is not False:
                errors.append(f"{label}: component {component_id} authority.{flag_name} must be false")
    else:
        errors.append(f"{label}: component {component_id} authority must be an object")

    blocked_actions = set(_string_list(passport.get("blocked_actions")))
    if blocked_actions != set(_string_list(component.get("blocked_actions"))):
        errors.append(f"{label}: component {component_id} blocked_actions must match registry")
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} blocked_actions must include terminal_closure")
    if passport.get("passport_is_not_execution_authority") is not True:
        errors.append(f"{label}: component {component_id} passport_is_not_execution_authority must be true")
    if passport.get("passport_is_not_terminal_closure") is not True:
        errors.append(f"{label}: component {component_id} passport_is_not_terminal_closure must be true")

    receipts = passport.get("receipts")
    if isinstance(receipts, dict):
        if receipts.get("can_claim_terminal_closure") is not False:
            errors.append(f"{label}: component {component_id} receipts.can_claim_terminal_closure must be false")
        if receipts.get("terminal_closure_required") is not True:
            errors.append(f"{label}: component {component_id} receipts.terminal_closure_required must be true")
    else:
        errors.append(f"{label}: component {component_id} receipts must be an object")

    validation = passport.get("last_validation")
    if isinstance(validation, dict):
        validator_refs = set(_string_list(validation.get("validator_refs")))
        for validator_ref in (
            "component_registry_validator",
            "component_authority_envelope_witnesses_validator",
            "component_passports_validator",
        ):
            if validator_ref not in validator_refs:
                errors.append(f"{label}: component {component_id} must require {validator_ref}")
    else:
        errors.append(f"{label}: component {component_id} last_validation must be an object")

    evidence_refs = _string_list(passport.get("evidence_refs"))
    if set(evidence_refs) != set(_string_list(component.get("evidence_refs"))):
        errors.append(f"{label}: component {component_id} evidence_refs must match registry")
    for evidence_ref in evidence_refs:
        evidence_path = evidence_ref.split("#", 1)[0]
        if not (REPO_ROOT / evidence_path).exists():
            errors.append(f"{label}: component {component_id} evidence_ref missing on disk: {evidence_ref}")


def _component_by_id(
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    components = registry.get("components")
    if not isinstance(components, list):
        errors.append(f"{label}: registry components must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            errors.append(f"{label}: registry component entries must be objects")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(f"{label}: registry component entries must carry id")
            continue
        result[component_id] = component
    return result


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
    """Parse component passport validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness passports.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--passports", default=str(DEFAULT_PASSPORTS))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--authority-witnesses", default=str(DEFAULT_AUTHORITY_WITNESSES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component passport validation."""

    args = parse_args(argv)
    validation = validate_component_passports(
        schema_path=Path(args.schema),
        passport_path=Path(args.passports),
        registry_path=Path(args.registry),
        authority_witnesses_path=Path(args.authority_witnesses),
    )
    write_component_passport_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT PASSPORTS VALID")
    else:
        print(f"COMPONENT PASSPORTS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
