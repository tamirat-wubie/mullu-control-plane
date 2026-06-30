#!/usr/bin/env python3
"""Validate the master capability control-system read model.

Purpose: prove the capability control system is a read-only projection over
capability packs, passports, unlock levels, friction modes, and dashboard
tasks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/capability_control_system.schema.json,
examples/capability_control_system.foundation.json, capability packs, and
capability passport dashboard projection.
Invariants:
  - Control-system state is not execution authority.
  - Every capability pack entry has exactly one registry row.
  - L0-L9 unlock levels and friction modes are present.
  - Fast Mode is limited to lab-safe local boundaries.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.capability_control_system import (  # noqa: E402
    FRICTION_MODES,
    OPERATING_BOUNDARIES,
    build_capability_control_system,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_control_system.schema.json"
DEFAULT_CONTROL_SYSTEM = REPO_ROOT / "examples" / "capability_control_system.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_control_system_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "capability_control_system_validator": "python scripts/validate_capability_control_system.py",
    "capability_control_system_tests": "python -m pytest tests/test_validate_capability_control_system.py -q",
}
REQUIRED_SAFE_ZONES = {"docs", "tests", "examples", "readme", "schemas", "validators", "local_demo_files"}
REQUIRED_DANGEROUS_ZONES = {
    "delete_files",
    "touch_secrets",
    "send_email",
    "move_money",
    "deploy",
    "merge_to_main",
    "write_production_data",
}


@dataclass(frozen=True, slots=True)
class CapabilityControlSystemValidation:
    """Validation report for the capability control-system read model."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    control_system_path: str
    capability_count: int
    unlock_level_count: int
    friction_mode_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_control_system(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    control_system_path: Path = DEFAULT_CONTROL_SYSTEM,
) -> CapabilityControlSystemValidation:
    """Validate the control-system example against runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "capability control system schema", errors)
    control_system = _load_json_object(control_system_path, "capability control system example", errors)
    runtime_control_system = build_capability_control_system() if not errors else {}

    if schema and control_system:
        errors.extend(
            f"{_path_label(control_system_path)}: {error}"
            for error in _validate_schema_instance(schema, control_system)
        )
        if control_system != runtime_control_system:
            errors.append(f"{_path_label(control_system_path)}: example does not match runtime projection")
    if control_system:
        _validate_control_system(control_system, runtime_control_system, errors, _path_label(control_system_path))

    registry = control_system.get("registry", ()) if isinstance(control_system, dict) else ()
    levels = control_system.get("unlock_levels", ()) if isinstance(control_system, dict) else ()
    modes = control_system.get("friction_modes", ()) if isinstance(control_system, dict) else ()
    return CapabilityControlSystemValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        control_system_path=_path_label(control_system_path),
        capability_count=len(registry) if isinstance(registry, list) else 0,
        unlock_level_count=len(levels) if isinstance(levels, list) else 0,
        friction_mode_count=len(modes) if isinstance(modes, list) else 0,
    )


def write_capability_control_system_validation(
    validation: CapabilityControlSystemValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic control-system validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_capability_control_system_example(output_path: Path = DEFAULT_CONTROL_SYSTEM) -> Path:
    """Write the current runtime projection as the checked example."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_capability_control_system(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_control_system(
    control_system: Mapping[str, Any],
    runtime_control_system: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if control_system.get("control_system_is_not_execution_authority") is not True:
        errors.append(f"{label}: control_system_is_not_execution_authority must be true")
    if control_system.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    _validate_validators(control_system, errors, label)
    _validate_unlock_levels(control_system, errors, label)
    _validate_friction_modes(control_system, errors, label)
    _validate_boundaries(control_system, errors, label)
    _validate_registry(control_system, runtime_control_system, errors, label)
    _validate_dashboard_tasks(control_system, errors, label)


def _validate_unlock_levels(control_system: Mapping[str, Any], errors: list[str], label: str) -> None:
    levels = control_system.get("unlock_levels")
    if not isinstance(levels, list):
        errors.append(f"{label}: unlock_levels must be a list")
        return
    observed = tuple(level.get("level_id") for level in levels if isinstance(level, dict))
    if observed != tuple(f"L{index}" for index in range(10)):
        errors.append(f"{label}: unlock_levels must be consecutive L0-L9")
    for level in levels:
        if not isinstance(level, dict):
            errors.append(f"{label}: unlock level entries must be objects")
            continue
        level_id = str(level.get("level_id", ""))
        if level.get("level", -1) >= 7 and level.get("requires_live_witness") is not True:
            errors.append(f"{label}: {level_id} must require live witness")
        if level.get("level", -1) in {3, 4, 5, 8, 9} and level.get("requires_rollback") is not True:
            errors.append(f"{label}: {level_id} must require rollback")


def _validate_friction_modes(control_system: Mapping[str, Any], errors: list[str], label: str) -> None:
    modes = control_system.get("friction_modes")
    if not isinstance(modes, list):
        errors.append(f"{label}: friction_modes must be a list")
        return
    observed_modes = tuple(mode.get("mode_id") for mode in modes if isinstance(mode, dict))
    if observed_modes != FRICTION_MODES:
        errors.append(f"{label}: friction_modes must be strict, balanced, fast")
    mode_by_id = {str(mode.get("mode_id", "")): mode for mode in modes if isinstance(mode, dict)}
    fast = mode_by_id.get("fast", {})
    if fast.get("default_boundary") != "lab":
        errors.append(f"{label}: fast mode must default to lab")
    if set(_string_list(fast.get("automatic_zones"))) != REQUIRED_SAFE_ZONES:
        errors.append(f"{label}: fast mode must expose only safe automatic zones")
    for mode in modes:
        if not isinstance(mode, dict):
            continue
        if set(_string_list(mode.get("blocked_zones"))) != REQUIRED_DANGEROUS_ZONES:
            errors.append(f"{label}: {mode.get('mode_id')} blocked_zones must match dangerous zones")


def _validate_boundaries(control_system: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundaries = control_system.get("operating_boundaries")
    if not isinstance(boundaries, list):
        errors.append(f"{label}: operating_boundaries must be a list")
        return
    observed = tuple(boundary.get("boundary_id") for boundary in boundaries if isinstance(boundary, dict))
    if observed != OPERATING_BOUNDARIES:
        errors.append(f"{label}: operating_boundaries must be lab then real_world")
    safe_zones = set(_string_list(control_system.get("safe_automatic_zones")))
    dangerous_zones = set(_string_list(control_system.get("dangerous_zones")))
    if safe_zones != REQUIRED_SAFE_ZONES:
        errors.append(f"{label}: safe automatic zones mismatch")
    if dangerous_zones != REQUIRED_DANGEROUS_ZONES:
        errors.append(f"{label}: dangerous zones mismatch")
    if safe_zones & dangerous_zones:
        errors.append(f"{label}: safe and dangerous zones must be disjoint")


def _validate_registry(
    control_system: Mapping[str, Any],
    runtime_control_system: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    registry = control_system.get("registry")
    runtime_registry = runtime_control_system.get("registry") if isinstance(runtime_control_system, dict) else []
    if not isinstance(registry, list) or not isinstance(runtime_registry, list):
        errors.append(f"{label}: registry must be a list")
        return
    if len(registry) != len(runtime_registry):
        errors.append(f"{label}: registry count must match runtime projection")
    capability_ids = [str(row.get("capability_id", "")) for row in registry if isinstance(row, dict)]
    if len(set(capability_ids)) != len(capability_ids):
        errors.append(f"{label}: registry capability ids must be unique")
    for row in registry:
        if not isinstance(row, dict):
            errors.append(f"{label}: registry rows must be objects")
            continue
        capability_id = str(row.get("capability_id", "<missing>"))
        if not str(row.get("unlock_level", "")).startswith("L"):
            errors.append(f"{label}: {capability_id} unlock_level must use L-level")
        if row.get("fast_mode_lab_ready") is True and row.get("requires_live_witness") is True:
            errors.append(f"{label}: {capability_id} fast mode cannot require live witness")
        if row.get("blocked") is True and not row.get("next_evidence_needed"):
            errors.append(f"{label}: {capability_id} blocked rows need next evidence")


def _validate_dashboard_tasks(control_system: Mapping[str, Any], errors: list[str], label: str) -> None:
    tasks = control_system.get("dashboard_tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append(f"{label}: dashboard_tasks must be a non-empty list")
        return
    for task in tasks:
        if not isinstance(task, dict):
            errors.append(f"{label}: dashboard task entries must be objects")
            continue
        if not task.get("task") or not task.get("reason") or not task.get("action_needed"):
            errors.append(f"{label}: dashboard task must include task, reason, and action_needed")


def _validate_validators(control_system: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = control_system.get("validators")
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
    """Parse capability control-system validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability control system.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--control-system", default=str(DEFAULT_CONTROL_SYSTEM))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write-example", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for capability control-system validation."""

    args = parse_args(argv)
    if args.write_example:
        write_capability_control_system_example(Path(args.control_system))
    validation = validate_capability_control_system(
        schema_path=Path(args.schema),
        control_system_path=Path(args.control_system),
    )
    write_capability_control_system_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY CONTROL SYSTEM VALID")
    else:
        print(f"CAPABILITY CONTROL SYSTEM INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
