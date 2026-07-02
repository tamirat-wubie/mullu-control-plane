#!/usr/bin/env python3
"""Validate capability passports.

Purpose: prove every governed capability has one registry-derived passport
with unlock level, allowed and blocked actions, gates, receipts, rollback
status, and next unlock evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/capability_passports.schema.json,
examples/capability_passports.foundation.json, and capability pack sources.
Invariants:
  - Every capability pack entry has exactly one passport.
  - Passports are read models and never grant execution authority.
  - Effect-bearing passports expose approval, receipt, evidence, and recovery gates.
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
from capability_levels.ladder import (  # noqa: E402
    CAPABILITY_PROMOTION_LADDER_ID,
    default_capability_promotion_ladder,
    validate_capability_promotion_ladder,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_passports.schema.json"
DEFAULT_PASSPORTS = REPO_ROOT / "examples" / "capability_passports.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_passports_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "capability_passports_validator": "python scripts/validate_capability_passports.py",
    "capability_passports_tests": "python -m pytest tests/test_validate_capability_passports.py -q",
}
REQUIRED_BASE_GATES = {
    "gate.uao.admission",
    "gate.capability.registry",
    "gate.evidence.intake",
    "gate.evidence.verification",
    "gate.receipt.append",
}


@dataclass(frozen=True, slots=True)
class CapabilityPassportValidation:
    """Validation report for capability passports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    passport_path: str
    passport_count: int
    capability_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_passports(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    passport_path: Path = DEFAULT_PASSPORTS,
) -> CapabilityPassportValidation:
    """Validate capability passports against governed source artifacts."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "capability passports schema", errors)
    passports = _load_json_object(passport_path, "capability passports example", errors)
    runtime_passports = build_capability_passports() if not errors else {}

    if schema and passports:
        errors.extend(f"{_path_label(passport_path)}: {error}" for error in _validate_schema_instance(schema, passports))
        if passports != runtime_passports:
            errors.append(f"{_path_label(passport_path)}: example does not match runtime projection")
    if passports:
        _validate_passport_set(passports, runtime_passports, errors, _path_label(passport_path))

    passport_entries = passports.get("passports", ()) if isinstance(passports, dict) else ()
    runtime_entries = runtime_passports.get("passports", ()) if isinstance(runtime_passports, dict) else ()
    return CapabilityPassportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        passport_path=_path_label(passport_path),
        passport_count=len(passport_entries) if isinstance(passport_entries, list) else 0,
        capability_count=len(runtime_entries) if isinstance(runtime_entries, list) else 0,
    )


def write_capability_passport_validation(
    validation: CapabilityPassportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic capability passport validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_capability_passports_example(output_path: Path = DEFAULT_PASSPORTS) -> Path:
    """Write the current runtime projection as the checked passport example."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_capability_passports(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_passport_set(
    passports: dict[str, Any],
    runtime_passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if passports.get("passport_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: passport_set_is_not_execution_authority must be true")
    if passports.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    ladder_errors = validate_capability_promotion_ladder()
    errors.extend(f"{label}: {error}" for error in ladder_errors)
    _validate_validators(passports, errors, label)

    passport_entries = passports.get("passports")
    runtime_entries = runtime_passports.get("passports") if isinstance(runtime_passports, dict) else []
    if not isinstance(passport_entries, list):
        errors.append(f"{label}: passports must be a list")
        return
    if not isinstance(runtime_entries, list):
        errors.append(f"{label}: runtime passports must be a list")
        return

    passport_by_capability: dict[str, dict[str, Any]] = {}
    for passport in passport_entries:
        if not isinstance(passport, dict):
            errors.append(f"{label}: passport entries must be objects")
            continue
        capability_id = str(passport.get("capability_id", ""))
        if capability_id in passport_by_capability:
            errors.append(f"{label}: duplicate passport for {capability_id}")
        passport_by_capability[capability_id] = passport
        _validate_passport(passport, errors, label)

    runtime_capability_ids = {str(passport.get("capability_id", "")) for passport in runtime_entries}
    passport_capability_ids = set(passport_by_capability)
    missing = sorted(runtime_capability_ids - passport_capability_ids)
    extra = sorted(passport_capability_ids - runtime_capability_ids)
    if missing:
        errors.append(f"{label}: registered capabilities missing passports {missing}")
    if extra:
        errors.append(f"{label}: passports for unknown capabilities {extra}")

    summary = passports.get("summary")
    if isinstance(summary, dict):
        if summary.get("capability_count") != len(runtime_entries):
            errors.append(f"{label}: summary.capability_count must match runtime capabilities")
        if summary.get("passport_count") != len(passport_entries):
            errors.append(f"{label}: summary.passport_count must match passport entries")
        if summary.get("approval_required_count") != _gate_count(passport_entries, "gate.approval.required"):
            errors.append(f"{label}: summary.approval_required_count must match gate count")
        if summary.get("receipt_required_count") != sum(1 for passport in passport_entries if passport.get("required_receipts")):
            errors.append(f"{label}: summary.receipt_required_count must match passports")
        expected_promotion_counts = _promotion_counts(passport_entries)
        if summary.get("promotion_level_counts") != expected_promotion_counts:
            errors.append(f"{label}: summary.promotion_level_counts must match passports")
    else:
        errors.append(f"{label}: summary must be an object")


def _validate_passport(passport: dict[str, Any], errors: list[str], label: str) -> None:
    capability_id = str(passport.get("capability_id", "<missing>"))
    if passport.get("passport_is_not_execution_authority") is not True:
        errors.append(f"{label}: {capability_id} passport_is_not_execution_authority must be true")
    _validate_promotion_profile(passport, errors, label, capability_id)

    required_gates = set(_string_list(passport.get("required_gates")))
    missing_base_gates = sorted(REQUIRED_BASE_GATES - required_gates)
    if missing_base_gates:
        errors.append(f"{label}: {capability_id} missing base gates {missing_base_gates}")

    required_receipts = _string_list(passport.get("required_receipts"))
    if "terminal_closure_certificate" not in required_receipts:
        errors.append(f"{label}: {capability_id} must require terminal_closure_certificate")
    if "effect_reconciliation_receipt" not in required_receipts:
        errors.append(f"{label}: {capability_id} must require effect_reconciliation_receipt")

    blocked_actions = set(_string_list(passport.get("blocked_actions")))
    if "claim_success_without_terminal_certificate" not in blocked_actions:
        errors.append(f"{label}: {capability_id} must block terminal success overclaim")

    rollback_status = passport.get("rollback_status")
    if isinstance(rollback_status, dict):
        status = rollback_status.get("status")
        if "gate.rollback.required" in required_gates and status == "missing":
            errors.append(f"{label}: {capability_id} rollback gate cannot have missing rollback status")
    else:
        errors.append(f"{label}: {capability_id} rollback_status must be an object")

    if passport.get("production_ready") is not True and "gate.production.evidence" not in required_gates:
        errors.append(f"{label}: {capability_id} non-production passport must require gate.production.evidence")
    if passport.get("production_ready") is True and passport.get("operator_status") == "Live action disabled":
        errors.append(f"{label}: {capability_id} production-ready passport cannot be Live action disabled")


def _validate_promotion_profile(
    passport: dict[str, Any],
    errors: list[str],
    label: str,
    capability_id: str,
) -> None:
    if passport.get("promotion_ladder_id") != CAPABILITY_PROMOTION_LADDER_ID:
        errors.append(f"{label}: {capability_id} promotion_ladder_id mismatch")
    if passport.get("promotion_level_is_not_execution_authority") is not True:
        errors.append(f"{label}: {capability_id} promotion_level_is_not_execution_authority must be true")
    level_number = passport.get("promotion_level_number")
    level_id = passport.get("current_promotion_level")
    levels = {level.level: level for level in default_capability_promotion_ladder()}
    if not isinstance(level_number, int) or isinstance(level_number, bool) or level_number not in levels:
        errors.append(f"{label}: {capability_id} promotion_level_number invalid")
        return
    expected_level = levels[level_number]
    if level_id != expected_level.level_id:
        errors.append(f"{label}: {capability_id} current_promotion_level must match promotion_level_number")
    if passport.get("promotion_level_name") != expected_level.name:
        errors.append(f"{label}: {capability_id} promotion_level_name must match ladder")
    if passport.get("promotion_required_gates") != list(expected_level.required_gates):
        errors.append(f"{label}: {capability_id} promotion_required_gates must match ladder")
    if passport.get("promotion_required_evidence") != list(expected_level.required_evidence):
        errors.append(f"{label}: {capability_id} promotion_required_evidence must match ladder")
    if passport.get("promotion_requires_operator_approval") is not expected_level.requires_operator_approval:
        errors.append(f"{label}: {capability_id} promotion approval flag must match ladder")
    if passport.get("promotion_requires_receipt") is not expected_level.requires_receipt:
        errors.append(f"{label}: {capability_id} promotion receipt flag must match ladder")
    if passport.get("promotion_requires_rollback") is not expected_level.requires_rollback:
        errors.append(f"{label}: {capability_id} promotion rollback flag must match ladder")
    if passport.get("promotion_requires_live_witness") is not expected_level.requires_live_witness:
        errors.append(f"{label}: {capability_id} promotion live witness flag must match ladder")


def _validate_validators(passports: dict[str, Any], errors: list[str], label: str) -> None:
    validators = passports.get("validators")
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


def _gate_count(passports: list[Any], gate: str) -> int:
    return sum(
        1
        for passport in passports
        if isinstance(passport, dict) and gate in _string_list(passport.get("required_gates"))
    )


def _promotion_counts(passports: list[Any]) -> dict[str, int]:
    counts = {f"L{level}": 0 for level in range(10)}
    for passport in passports:
        if isinstance(passport, dict):
            level_id = str(passport.get("current_promotion_level", ""))
            if level_id in counts:
                counts[level_id] += 1
    return counts


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
    """Parse capability passport validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability passports.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--passports", default=str(DEFAULT_PASSPORTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write-example", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for capability passport validation."""

    args = parse_args(argv)
    if args.write_example:
        write_capability_passports_example(Path(args.passports))
    validation = validate_capability_passports(
        schema_path=Path(args.schema),
        passport_path=Path(args.passports),
    )
    write_capability_passport_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY PASSPORTS VALID")
    else:
        print(f"CAPABILITY PASSPORTS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
