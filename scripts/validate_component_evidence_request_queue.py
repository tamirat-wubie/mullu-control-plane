#!/usr/bin/env python3
"""Validate Component Harness evidence request queues.

Purpose: prove component evidence request queues are schema-valid,
runtime-aligned, request-only, and bound to bundle compiler plus claim firewall
evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_evidence_request_queue.schema.json,
examples/component_evidence_request_queue.foundation.json, bundle compiler,
claim firewall validation, and scripts.validate_schemas.
Invariants:
  - The example payload equals the runtime projection.
  - Request slots cannot submit, accept, approve, grant, execute, or close.
  - Every slot is blocked by terminal closure and claim firewall refs.
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

from mcoi_runtime.app.component_evidence_request_queue import (  # noqa: E402
    REQUIRED_VALIDATOR_REFS,
    build_component_evidence_request_queue,
)
from scripts.validate_component_bundle_compiler import validate_component_bundle_compiler  # noqa: E402
from scripts.validate_component_claim_firewall import validate_component_claim_firewall  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_evidence_request_queue.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_evidence_request_queue.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_evidence_request_queue_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_evidence_request_queue_validator": "python scripts/validate_component_evidence_request_queue.py",
    "component_evidence_request_queue_tests": "python -m pytest tests/test_validate_component_evidence_request_queue.py -q",
}


@dataclass(frozen=True, slots=True)
class ComponentEvidenceRequestQueueValidation:
    """Validation result for component evidence request queues."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    request_slot_count: int
    bundle_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_evidence_request_queue(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentEvidenceRequestQueueValidation:
    """Validate queue schema, example, runtime projection, and invariants."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component evidence request queue schema", errors)
    example = _load_json_object(example_path, "component evidence request queue example", errors)

    for label, validation in (
        ("component bundle compiler", validate_component_bundle_compiler()),
        ("component claim firewall", validate_component_claim_firewall()),
    ):
        if not validation.ok:
            errors.extend(f"{label} validation failed: {error}" for error in validation.errors)

    runtime_projection = build_component_evidence_request_queue()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_projection:
            errors.append(f"{_path_label(example_path)}: example does not match runtime projection")
        _validate_queue_semantics(example, errors, _path_label(example_path))

    summary = example.get("summary", {}) if isinstance(example, dict) else {}
    return ComponentEvidenceRequestQueueValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        request_slot_count=int(summary.get("request_slot_count", 0)) if isinstance(summary, dict) else 0,
        bundle_count=int(summary.get("bundle_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_evidence_request_queue_validation(
    validation: ComponentEvidenceRequestQueueValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic queue validation result."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_queue_semantics(queue: dict[str, Any], errors: list[str], label: str) -> None:
    for flag_name in (
        "queue_is_not_execution_authority",
        "queue_is_not_evidence_submission",
        "queue_is_not_evidence_acceptance",
        "queue_is_not_authority_grant",
        "queue_is_not_promotion_approval",
        "queue_is_not_terminal_closure",
    ):
        if queue.get(flag_name) is not True:
            errors.append(f"{label}: {flag_name} must be true")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_submitted",
        "evidence_accepted",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if queue.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")

    request_slots = queue.get("request_slots")
    if not isinstance(request_slots, list) or not request_slots:
        errors.append(f"{label}: request_slots must be a non-empty list")
        return
    _validate_summary(queue, request_slots, errors, label)
    _validate_validators(queue, errors, label)
    for slot in request_slots:
        if not isinstance(slot, dict):
            errors.append(f"{label}: request slot entries must be objects")
            continue
        _validate_request_slot(slot, errors, label)


def _validate_summary(
    queue: dict[str, Any],
    request_slots: list[Any],
    errors: list[str],
    label: str,
) -> None:
    summary = queue.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    typed_slots = [slot for slot in request_slots if isinstance(slot, dict)]
    expected_counts = {
        "request_slot_count": len(typed_slots),
        "operator_input_required_count": sum(1 for slot in typed_slots if slot.get("operator_input_required") is True),
        "unknown_proof_state_count": sum(1 for slot in typed_slots if slot.get("proof_state") == "Unknown"),
        "submitted_evidence_count": sum(1 for slot in typed_slots if slot.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for slot in typed_slots if slot.get("evidence_accepted") is True),
        "authority_grant_count": sum(1 for slot in typed_slots if slot.get("authority_granted") is True),
        "terminal_closure_allowed_count": sum(
            1 for slot in typed_slots if slot.get("terminal_closure_allowed") is True
        ),
    }
    for field_name, expected_value in expected_counts.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"{label}: summary.{field_name} must be {expected_value}")


def _validate_request_slot(slot: dict[str, Any], errors: list[str], label: str) -> None:
    request_id = str(slot.get("request_id", ""))
    for flag_name in ("operator_input_required", "request_only"):
        if slot.get(flag_name) is not True:
            errors.append(f"{label}: slot {request_id} {flag_name} must be true")
    for flag_name in (
        "requirement_satisfied",
        "evidence_submitted",
        "evidence_accepted",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if slot.get(flag_name) is not False:
            errors.append(f"{label}: slot {request_id} {flag_name} must be false")
    if slot.get("proof_state") != "Unknown":
        errors.append(f"{label}: slot {request_id} proof_state must be Unknown")
    if slot.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: slot {request_id} outcome must be AwaitingEvidence")
    if "terminal_closure" not in _string_list(slot.get("blocked_actions")):
        errors.append(f"{label}: slot {request_id} blocked_actions must include terminal_closure")
    if not _string_list(slot.get("claim_firewall_blocking_claim_ids")):
        errors.append(f"{label}: slot {request_id} must carry claim firewall blocking claim ids")
    validator_refs = set(_string_list(slot.get("required_validator_refs")))
    for validator_ref in REQUIRED_VALIDATOR_REFS:
        if validator_ref not in validator_refs:
            errors.append(f"{label}: slot {request_id} must require {validator_ref}")


def _validate_validators(queue: dict[str, Any], errors: list[str], label: str) -> None:
    validators = queue.get("validators")
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
    """Parse component evidence request queue validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness evidence request queue.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component evidence request queue validation."""

    args = parse_args(argv)
    validation = validate_component_evidence_request_queue(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_evidence_request_queue_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT EVIDENCE REQUEST QUEUE VALID")
    else:
        print(f"COMPONENT EVIDENCE REQUEST QUEUE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
