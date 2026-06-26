#!/usr/bin/env python3
"""Validate Component Harness evidence submission intake previews.

Purpose: prove submitted-evidence intake remains non-accepting, runtime-aligned,
queue-bound, and authority-denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_evidence_submission_intake.schema.json,
examples/component_evidence_submission_intake.foundation.json, component
evidence request queue validation, and scripts.validate_schemas.
Invariants:
  - The example payload equals the runtime projection.
  - Submitted refs are observations only.
  - Evidence acceptance, rejection, authority, promotion, and closure stay false.
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

from mcoi_runtime.app.component_evidence_submission_intake import (  # noqa: E402
    REQUIRED_VALIDATOR_REFS,
    build_component_evidence_submission_intake,
)
from scripts.validate_component_evidence_request_queue import validate_component_evidence_request_queue  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_evidence_submission_intake.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_evidence_submission_intake.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_evidence_submission_intake_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_evidence_submission_intake_validator": "python scripts/validate_component_evidence_submission_intake.py",
    "component_evidence_submission_intake_tests": (
        "python -m pytest tests/test_validate_component_evidence_submission_intake.py -q"
    ),
}


@dataclass(frozen=True, slots=True)
class ComponentEvidenceSubmissionIntakeValidation:
    """Validation result for component evidence submission intake previews."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    request_slot_count: int
    submitted_slot_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_evidence_submission_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentEvidenceSubmissionIntakeValidation:
    """Validate intake schema, example, runtime projection, and invariants."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component evidence submission intake schema", errors)
    example = _load_json_object(example_path, "component evidence submission intake example", errors)

    queue_validation = validate_component_evidence_request_queue()
    if not queue_validation.ok:
        errors.extend(f"component evidence request queue validation failed: {error}" for error in queue_validation.errors)

    runtime_projection = build_component_evidence_submission_intake()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_projection:
            errors.append(f"{_path_label(example_path)}: example does not match runtime projection")
        _validate_intake_semantics(example, errors, _path_label(example_path))

    summary = example.get("summary", {}) if isinstance(example, dict) else {}
    return ComponentEvidenceSubmissionIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        request_slot_count=int(summary.get("request_slot_count", 0)) if isinstance(summary, dict) else 0,
        submitted_slot_count=int(summary.get("submitted_slot_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_evidence_submission_intake_validation(
    validation: ComponentEvidenceSubmissionIntakeValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic intake validation result."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_intake_semantics(intake: dict[str, Any], errors: list[str], label: str) -> None:
    for flag_name in (
        "intake_is_not_execution_authority",
        "intake_is_not_evidence_submission",
        "intake_is_not_evidence_acceptance",
        "intake_is_not_evidence_rejection",
        "intake_is_not_authority_grant",
        "intake_is_not_promotion_approval",
        "intake_is_not_terminal_closure",
        "submitted_evidence_refs_are_observations_only",
    ):
        if intake.get(flag_name) is not True:
            errors.append(f"{label}: {flag_name} must be true")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_accepted",
        "evidence_rejected",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if intake.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")

    slots = intake.get("intake_slots")
    if not isinstance(slots, list) or not slots:
        errors.append(f"{label}: intake_slots must be a non-empty list")
        return
    _validate_summary(intake, slots, errors, label)
    _validate_validators(intake, errors, label)
    for slot in slots:
        if not isinstance(slot, dict):
            errors.append(f"{label}: intake slot entries must be objects")
            continue
        _validate_intake_slot(slot, errors, label)


def _validate_summary(intake: dict[str, Any], slots: list[Any], errors: list[str], label: str) -> None:
    summary = intake.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    typed_slots = [slot for slot in slots if isinstance(slot, dict)]
    expected_counts = {
        "request_slot_count": len(typed_slots),
        "submitted_slot_count": sum(1 for slot in typed_slots if slot.get("submitted_evidence_observed") is True),
        "submitted_evidence_ref_count": sum(len(_string_list(slot.get("submitted_evidence_refs"))) for slot in typed_slots),
        "accepted_evidence_count": sum(len(_string_list(slot.get("accepted_evidence_refs"))) for slot in typed_slots),
        "rejected_evidence_count": sum(len(_string_list(slot.get("rejected_evidence_refs"))) for slot in typed_slots),
        "authority_grant_count": sum(1 for slot in typed_slots if slot.get("authority_granted") is True),
        "terminal_closure_allowed_count": sum(1 for slot in typed_slots if slot.get("terminal_closure_allowed") is True),
    }
    for field_name, expected_value in expected_counts.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"{label}: summary.{field_name} must be {expected_value}")


def _validate_intake_slot(slot: dict[str, Any], errors: list[str], label: str) -> None:
    slot_id = str(slot.get("intake_slot_id", ""))
    for flag_name in ("request_bound", "intake_only"):
        if slot.get(flag_name) is not True:
            errors.append(f"{label}: slot {slot_id} {flag_name} must be true")
    for flag_name in (
        "evidence_accepted",
        "evidence_rejected",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if slot.get(flag_name) is not False:
            errors.append(f"{label}: slot {slot_id} {flag_name} must be false")
    if slot.get("proof_state") != "Unknown":
        errors.append(f"{label}: slot {slot_id} proof_state must be Unknown")
    if slot.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: slot {slot_id} outcome must be AwaitingEvidence")
    submitted_refs = _string_list(slot.get("submitted_evidence_refs"))
    if slot.get("submitted_evidence_observed") != bool(submitted_refs):
        errors.append(f"{label}: slot {slot_id} submitted_evidence_observed must match submitted refs")
    if submitted_refs and slot.get("submission_state") != "submitted_not_verified":
        errors.append(f"{label}: slot {slot_id} submitted refs must remain submitted_not_verified")
    if not submitted_refs and slot.get("submission_state") != "awaiting_submission":
        errors.append(f"{label}: slot {slot_id} empty refs must remain awaiting_submission")
    if "terminal_closure" not in _string_list(slot.get("blocked_actions")):
        errors.append(f"{label}: slot {slot_id} blocked_actions must include terminal_closure")
    if not _string_list(slot.get("claim_firewall_blocking_claim_ids")):
        errors.append(f"{label}: slot {slot_id} must carry claim firewall blocking claim ids")
    validator_refs = set(_string_list(slot.get("required_validator_refs")))
    for validator_ref in REQUIRED_VALIDATOR_REFS:
        if validator_ref not in validator_refs:
            errors.append(f"{label}: slot {slot_id} must require {validator_ref}")


def _validate_validators(intake: dict[str, Any], errors: list[str], label: str) -> None:
    validators = intake.get("validators")
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
    if not all(isinstance(item, str) and item for item in value):
        return []
    return value


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component evidence submission intake validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness evidence submission intake.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component evidence submission intake validation."""

    args = parse_args(argv)
    validation = validate_component_evidence_submission_intake(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_evidence_submission_intake_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT EVIDENCE SUBMISSION INTAKE VALID")
    else:
        print(f"COMPONENT EVIDENCE SUBMISSION INTAKE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
