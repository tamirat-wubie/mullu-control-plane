#!/usr/bin/env python3
"""Validate Component Harness authority envelope witnesses.

Purpose: prove each registered component has a registry-matching authority
envelope witness that denies live effects and terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_authority_envelope_witnesses.schema.json,
examples/component_authority_envelope_witnesses.foundation.json,
examples/component_registry.foundation.json, and component registry validation.
Invariants:
  - Every registered component has exactly one authority envelope witness.
  - Witness authority, state, wiring, and authority level match the registry.
  - Current authority witnesses cannot grant upgrades or live effects.
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

from mcoi_runtime.app.component_authority_envelope_witnesses import (  # noqa: E402
    LIVE_AUTHORITY_FLAGS,
    build_component_authority_envelope_witnesses,
)
from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_authority_envelope_witnesses.schema.json"
DEFAULT_WITNESSES = REPO_ROOT / "examples" / "component_authority_envelope_witnesses.foundation.json"
DEFAULT_REGISTRY = REPO_ROOT / "examples" / "component_registry.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_authority_envelope_witnesses_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_authority_envelope_witnesses_validator": (
        "python scripts/validate_component_authority_envelope_witnesses.py"
    ),
    "component_authority_envelope_witnesses_tests": (
        "python -m pytest tests/test_validate_component_authority_envelope_witnesses.py -q"
    ),
}


@dataclass(frozen=True, slots=True)
class ComponentAuthorityEnvelopeWitnessValidation:
    """Validation report for authority envelope witnesses."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    witness_path: str
    registry_path: str
    witness_count: int
    component_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_authority_envelope_witnesses(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    witness_path: Path = DEFAULT_WITNESSES,
    registry_path: Path = DEFAULT_REGISTRY,
) -> ComponentAuthorityEnvelopeWitnessValidation:
    """Validate authority envelope witnesses against registry state."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component authority envelope witness schema", errors)
    witnesses = _load_json_object(witness_path, "component authority envelope witness example", errors)
    registry = _load_json_object(registry_path, "component registry example", errors)

    registry_validation = validate_component_registry(example_paths=(registry_path,))
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)

    runtime_witnesses = (
        build_component_authority_envelope_witnesses(registry_path=registry_path)
        if not errors or registry
        else {}
    )
    if schema and witnesses:
        errors.extend(
            f"{_path_label(witness_path)}: {error}"
            for error in _validate_schema_instance(schema, witnesses)
        )
        if witnesses != runtime_witnesses:
            errors.append(f"{_path_label(witness_path)}: example does not match runtime projection")
    if witnesses and registry:
        _validate_witness_set(witnesses, registry, errors, _path_label(witness_path))

    witness_entries = witnesses.get("authority_witnesses", ()) if isinstance(witnesses, dict) else ()
    component_entries = registry.get("components", ()) if isinstance(registry, dict) else ()
    return ComponentAuthorityEnvelopeWitnessValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        witness_path=_path_label(witness_path),
        registry_path=_path_label(registry_path),
        witness_count=len(witness_entries) if isinstance(witness_entries, list) else 0,
        component_count=len(component_entries) if isinstance(component_entries, list) else 0,
    )


def write_component_authority_envelope_witness_validation(
    validation: ComponentAuthorityEnvelopeWitnessValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic authority envelope witness validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_witness_set(
    witnesses: dict[str, Any],
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if witnesses.get("source_registry") != "examples/component_registry.foundation.json":
        errors.append(f"{label}: source_registry must be examples/component_registry.foundation.json")
    if witnesses.get("witness_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: witness_set_is_not_execution_authority must be true")
    for flag_name in ("live_execution_enabled", "live_connector_send_enabled"):
        if witnesses.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if witnesses.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    _validate_policy(witnesses, errors, label)
    _validate_validators(witnesses, errors, label)

    component_by_id = _component_by_id(registry, errors, label)
    witness_entries = witnesses.get("authority_witnesses")
    if not isinstance(witness_entries, list):
        errors.append(f"{label}: authority_witnesses must be a list")
        return

    witness_ids: set[str] = set()
    witness_components: set[str] = set()
    for witness in witness_entries:
        if not isinstance(witness, dict):
            errors.append(f"{label}: authority witness entries must be objects")
            continue
        witness_id = str(witness.get("witness_id", ""))
        component_id = str(witness.get("component_id", ""))
        if witness_id in witness_ids:
            errors.append(f"{label}: duplicate witness_id {witness_id}")
        witness_ids.add(witness_id)
        if component_id in witness_components:
            errors.append(f"{label}: duplicate component authority witness for {component_id}")
        witness_components.add(component_id)
        component = component_by_id.get(component_id)
        if component is None:
            errors.append(f"{label}: witness component {component_id} is not registered")
            continue
        _validate_witness(witness, component, errors, label)

    missing_witnesses = sorted(set(component_by_id) - witness_components)
    extra_witnesses = sorted(witness_components - set(component_by_id))
    if missing_witnesses:
        errors.append(f"{label}: registered components missing authority witnesses {missing_witnesses}")
    if extra_witnesses:
        errors.append(f"{label}: authority witnesses for unknown components {extra_witnesses}")


def _validate_policy(witnesses: dict[str, Any], errors: list[str], label: str) -> None:
    policy = witnesses.get("authority_policy")
    if not isinstance(policy, dict):
        errors.append(f"{label}: authority_policy must be an object")
        return
    if policy.get("default_all_live_effect_flags_false") is not True:
        errors.append(f"{label}: default_all_live_effect_flags_false must be true")
    if set(_string_list(policy.get("live_effect_flags"))) != set(LIVE_AUTHORITY_FLAGS):
        errors.append(f"{label}: live_effect_flags must match the authority live-effect flags")
    if policy.get("authority_upgrade_requires_separate_witness") is not True:
        errors.append(f"{label}: authority_upgrade_requires_separate_witness must be true")


def _validate_validators(witnesses: dict[str, Any], errors: list[str], label: str) -> None:
    validators = witnesses.get("validators")
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


def _validate_witness(
    witness: dict[str, Any],
    component: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(component.get("id", "<missing>"))
    for field_name in ("lifecycle_state", "wiring_state", "authority_level"):
        if witness.get(field_name) != component.get(field_name):
            errors.append(
                f"{label}: component {component_id} witness {field_name} must match registry {component.get(field_name)}"
            )
    if witness.get("proof_state") != "Pass":
        errors.append(f"{label}: component {component_id} proof_state must be Pass")
    if witness.get("authority") != component.get("authority"):
        errors.append(f"{label}: component {component_id} authority must match registry authority")
    if witness.get("authority_matches_registry") is not True:
        errors.append(f"{label}: component {component_id} authority_matches_registry must be true")
    for field_name in (
        "witness_is_not_execution_authority",
        "witness_is_not_terminal_closure",
        "authority_upgrade_requires_separate_witness",
    ):
        if witness.get(field_name) is not True:
            errors.append(f"{label}: component {component_id} {field_name} must be true")
    if witness.get("external_effect") is not False:
        errors.append(f"{label}: component {component_id} external_effect must be false")

    blocked_actions = set(_string_list(witness.get("blocked_actions")))
    if blocked_actions != set(_string_list(component.get("blocked_actions"))):
        errors.append(f"{label}: component {component_id} blocked_actions must match registry")
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} blocked_actions must include terminal_closure")
    authority = witness.get("authority")
    if not isinstance(authority, dict):
        errors.append(f"{label}: component {component_id} authority must be an object")
    else:
        for flag_name in LIVE_AUTHORITY_FLAGS:
            if authority.get(flag_name) is not False:
                errors.append(f"{label}: component {component_id} authority.{flag_name} must be false")
    _validate_evidence_refs(witness, component_id, errors, label)


def _validate_evidence_refs(
    witness: dict[str, Any],
    component_id: str,
    errors: list[str],
    label: str,
) -> None:
    evidence_refs = _string_list(witness.get("evidence_refs"))
    if not evidence_refs:
        errors.append(f"{label}: component {component_id} evidence_refs must not be empty")
    for evidence_ref in evidence_refs:
        evidence_path = evidence_ref.split("#", 1)[0]
        if not (REPO_ROOT / evidence_path).exists():
            errors.append(f"{label}: component {component_id} evidence_ref missing on disk: {evidence_ref}")
    validator_refs = _string_list(witness.get("required_validator_refs"))
    for validator_ref in ("component_registry_validator", "component_authority_envelope_witnesses_validator"):
        if validator_ref not in validator_refs:
            errors.append(f"{label}: component {component_id} must require {validator_ref}")


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
    """Parse authority envelope witness validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness authority envelope witnesses.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--witnesses", default=str(DEFAULT_WITNESSES))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for authority envelope witness validation."""

    args = parse_args(argv)
    validation = validate_component_authority_envelope_witnesses(
        schema_path=Path(args.schema),
        witness_path=Path(args.witnesses),
        registry_path=Path(args.registry),
    )
    write_component_authority_envelope_witness_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT AUTHORITY ENVELOPE WITNESSES VALID")
    else:
        print(f"COMPONENT AUTHORITY ENVELOPE WITNESSES INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
