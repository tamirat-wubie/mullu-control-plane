#!/usr/bin/env python3
"""Validate Component Harness authority fuses.

Purpose: prove component authority transitions are fuse-gated and cannot be
self-upgraded by any registered component.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_authority_fuse.schema.json,
examples/component_authority_fuse.foundation.json, and component passports.
Invariants:
  - Every component passport has exactly one authority fuse.
  - Every fuse remains blocked and denial-only.
  - Authority upgrades require external evidence; no component may upgrade
    itself.
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

from mcoi_runtime.app.component_authority_fuse import (  # noqa: E402
    REQUIRED_FUSE_EVIDENCE,
    build_component_authority_fuse,
)
from scripts.validate_component_passports import validate_component_passports  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_authority_fuse.schema.json"
DEFAULT_FUSE = REPO_ROOT / "examples" / "component_authority_fuse.foundation.json"
DEFAULT_PASSPORTS = REPO_ROOT / "examples" / "component_passports.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_authority_fuse_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_authority_fuse_validator": "python scripts/validate_component_authority_fuse.py",
    "component_authority_fuse_tests": "python -m pytest tests/test_validate_component_authority_fuse.py -q",
}


@dataclass(frozen=True, slots=True)
class ComponentAuthorityFuseValidation:
    """Validation report for component authority fuses."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fuse_path: str
    passports_path: str
    fuse_count: int
    passport_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_authority_fuse(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fuse_path: Path = DEFAULT_FUSE,
    passports_path: Path = DEFAULT_PASSPORTS,
) -> ComponentAuthorityFuseValidation:
    """Validate component authority fuses against component passports."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component authority fuse schema", errors)
    fuse_set = _load_json_object(fuse_path, "component authority fuse example", errors)
    passports = _load_json_object(passports_path, "component passports example", errors)

    passport_validation = validate_component_passports(passport_path=passports_path)
    if not passport_validation.ok:
        errors.extend(f"component passport validation failed: {error}" for error in passport_validation.errors)

    runtime_fuse = build_component_authority_fuse(passports_path=passports_path) if passports else {}
    if schema and fuse_set:
        errors.extend(f"{_path_label(fuse_path)}: {error}" for error in _validate_schema_instance(schema, fuse_set))
        if fuse_set != runtime_fuse:
            errors.append(f"{_path_label(fuse_path)}: example does not match runtime projection")
    if fuse_set and passports:
        _validate_fuse_set(fuse_set, passports, errors, _path_label(fuse_path))

    fuse_entries = fuse_set.get("fuses", ()) if isinstance(fuse_set, dict) else ()
    passport_entries = passports.get("passports", ()) if isinstance(passports, dict) else ()
    return ComponentAuthorityFuseValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fuse_path=_path_label(fuse_path),
        passports_path=_path_label(passports_path),
        fuse_count=len(fuse_entries) if isinstance(fuse_entries, list) else 0,
        passport_count=len(passport_entries) if isinstance(passport_entries, list) else 0,
    )


def write_component_authority_fuse_validation(
    validation: ComponentAuthorityFuseValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic component authority fuse validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_fuse_set(
    fuse_set: dict[str, Any],
    passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if fuse_set.get("fuse_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: fuse_set_is_not_execution_authority must be true")
    for flag_name in ("live_execution_enabled", "live_connector_send_enabled"):
        if fuse_set.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if fuse_set.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    if set(_string_list(fuse_set.get("required_fuse_evidence"))) != set(REQUIRED_FUSE_EVIDENCE):
        errors.append(f"{label}: required_fuse_evidence must match authority fuse evidence requirements")
    _validate_validators(fuse_set, errors, label)

    passport_by_component = _passport_by_component(passports, errors, label)
    fuses = fuse_set.get("fuses")
    if not isinstance(fuses, list):
        errors.append(f"{label}: fuses must be a list")
        return
    fuse_components: set[str] = set()
    for fuse in fuses:
        if not isinstance(fuse, dict):
            errors.append(f"{label}: fuse entries must be objects")
            continue
        component_id = str(fuse.get("component_id", ""))
        if component_id in fuse_components:
            errors.append(f"{label}: duplicate fuse for {component_id}")
        fuse_components.add(component_id)
        passport = passport_by_component.get(component_id)
        if passport is None:
            errors.append(f"{label}: fuse component {component_id} is not in passports")
            continue
        _validate_fuse(fuse, passport, errors, label)

    missing_fuses = sorted(set(passport_by_component) - fuse_components)
    extra_fuses = sorted(fuse_components - set(passport_by_component))
    if missing_fuses:
        errors.append(f"{label}: passports missing authority fuses {missing_fuses}")
    if extra_fuses:
        errors.append(f"{label}: authority fuses for unknown components {extra_fuses}")


def _validate_validators(fuse_set: dict[str, Any], errors: list[str], label: str) -> None:
    validators = fuse_set.get("validators")
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


def _validate_fuse(
    fuse: dict[str, Any],
    passport: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(passport.get("component_id", "<missing>"))
    lifecycle = passport.get("lifecycle")
    if isinstance(lifecycle, dict):
        if fuse.get("current_authority_level") != lifecycle.get("authority_level"):
            errors.append(f"{label}: component {component_id} current_authority_level must match passport")
    else:
        errors.append(f"{label}: component {component_id} passport lifecycle must be an object")

    for field_name in (
        "self_upgrade_allowed",
        "can_upgrade_authority",
        "can_mutate_authority_envelope",
        "can_enable_live_action",
        "terminal_closure_allowed",
    ):
        if fuse.get(field_name) is not False:
            errors.append(f"{label}: component {component_id} {field_name} must be false")
    for field_name in ("fuse_is_not_execution_authority", "fuse_is_not_terminal_closure"):
        if fuse.get(field_name) is not True:
            errors.append(f"{label}: component {component_id} {field_name} must be true")
    if fuse.get("decision") != "blocked":
        errors.append(f"{label}: component {component_id} decision must be blocked")
    if fuse.get("outcome") != "GovernanceBlocked":
        errors.append(f"{label}: component {component_id} outcome must be GovernanceBlocked")
    if set(_string_list(fuse.get("required_evidence"))) != set(REQUIRED_FUSE_EVIDENCE):
        errors.append(f"{label}: component {component_id} required_evidence must match fuse requirements")
    if set(_string_list(fuse.get("missing_evidence"))) != set(REQUIRED_FUSE_EVIDENCE):
        errors.append(f"{label}: component {component_id} missing_evidence must match fuse requirements")
    validator_refs = set(_string_list(fuse.get("required_validator_refs")))
    for validator_ref in ("component_passports_validator", "component_authority_fuse_validator"):
        if validator_ref not in validator_refs:
            errors.append(f"{label}: component {component_id} must require {validator_ref}")


def _passport_by_component(
    passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    entries = passports.get("passports")
    if not isinstance(entries, list):
        errors.append(f"{label}: passports must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for passport in entries:
        if not isinstance(passport, dict):
            errors.append(f"{label}: passport entries must be objects")
            continue
        component_id = passport.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(f"{label}: passport entries must carry component_id")
            continue
        result[component_id] = passport
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
    """Parse component authority fuse validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness authority fuses.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--fuse", default=str(DEFAULT_FUSE))
    parser.add_argument("--passports", default=str(DEFAULT_PASSPORTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component authority fuse validation."""

    args = parse_args(argv)
    validation = validate_component_authority_fuse(
        schema_path=Path(args.schema),
        fuse_path=Path(args.fuse),
        passports_path=Path(args.passports),
    )
    write_component_authority_fuse_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT AUTHORITY FUSE VALID")
    else:
        print(f"COMPONENT AUTHORITY FUSE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
