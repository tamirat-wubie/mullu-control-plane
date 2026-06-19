#!/usr/bin/env python3
"""Validate GovernedPlanningProfile generic continuation rejection witness.

Purpose: prove a generic continuation input is not a signed runtime
authorization response for GovernedPlanningProfile runtime promotion.
Governance scope: OCE response classification, RAG authorization-request
binding, CDCV hash traceability, CQTE authority denial constraints, UWMA
rejection anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: runtime authorization request validator, schema validator, and
canonical hashing.
Invariants:
  - A generic continuation is recorded only as a rejection witness.
  - The witness never grants execution, dispatch, replanning, success, runtime
    promotion, or terminal closure authority.
  - A future explicit signed approval witness remains a separate action.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.command_spine import canonical_hash  # noqa: E402
from scripts.validate_governed_planning_profile_operator_shadow_pilot_evidence import (  # noqa: E402
    AUTHORITY_FALSE_FIELDS,
)
from scripts.validate_governed_planning_profile_runtime_authorization_request import (  # noqa: E402
    ALLOWED_RESPONSE_KINDS,
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
    build_runtime_authorization_request,
    validate_runtime_authorization_request,
)
from scripts.validate_governed_planning_profile_terminal_closure_certificate import (  # noqa: E402
    SATISFIED_PROMOTION_GATE_IDS,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_runtime_authorization_generic_continuation_rejection.v1"
WITNESS_ID_PREFIX = "governed-planning-profile-runtime-authorization-generic-continuation-rejection"
REJECTION_RESPONSE_KIND = "record_governed_planning_profile_runtime_authorization_rejection_witness"
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "governed_planning_profile_runtime_authorization_generic_continuation_rejection.schema.json"
)
DEFAULT_WITNESS = (
    REPO_ROOT
    / "examples"
    / "governed_planning_profile_runtime_authorization_generic_continuation_rejection.local.json"
)
REJECTION_CONTROL_IDS = (
    "source_runtime_authorization_request_valid",
    "generic_continuation_not_valid_authorization",
    "signed_approval_absent",
    "rejection_witness_recorded",
    "runtime_authorization_gate_blocked",
    "authority_denials_preserved",
    "foundation_no_effect_boundary_preserved",
    "rejection_witness_hash_bound",
)


@dataclass(frozen=True, slots=True)
class GenericContinuationRejectionValidation:
    """Validation result for the planning-profile continuation rejection witness."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    witness_path: str
    witness_id: str
    source_runtime_authorization_request_id: str
    rejection_control_count: int
    scenario_rejection_count: int
    runtime_authorization_gate_satisfied: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_generic_continuation_rejection_witness(
    runtime_authorization_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local rejection witness for generic continuation."""

    source_request = dict(runtime_authorization_request or build_runtime_authorization_request())
    controls = tuple(_rejection_controls(source_request))
    scenario_rejections = tuple(_scenario_rejections(source_request))
    payload: dict[str, Any] = {
        "witness_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(source_request.get("profile_id", "")),
        "recorded_at": GENERATED_AT,
        "solver_outcome": "GovernanceBlocked",
        "runtime_authorization_response_status": "RejectedNoEffect",
        "runtime_authorization_response_kind": REJECTION_RESPONSE_KIND,
        "generic_continuation_rejected": True,
        "operator_response_recorded": True,
        "operator_approval_collected": False,
        "signed_approval_present": False,
        "runtime_authorization_gate_satisfied": False,
        "local_witness_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_activation_allowed": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_runtime_authorization_request": {
            "request_id": str(source_request.get("request_id", "")),
            "request_hash": str(source_request.get("request_hash", "")),
            "runtime_authorization_request_status": str(
                source_request.get("runtime_authorization_request_status", "")
            ),
            "runtime_authorization_request_submitted": bool(
                source_request.get("runtime_authorization_request_submitted")
            ),
            "operator_response_required": bool(source_request.get("operator_response_required")),
            "operator_response_collected": bool(source_request.get("operator_response_collected")),
            "runtime_authorization_gate_satisfied": bool(
                source_request.get("runtime_authorization_gate_satisfied")
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "rejection_controls": list(controls),
        "scenario_rejections": list(scenario_rejections),
        "operator_response_boundary": {
            "observed_input": "continue",
            "observed_input_kind": "generic_continuation",
            "explicit_signed_authorization_required": True,
            "generic_continuation_satisfies_authorization": False,
            "rejection_witness_records_non_authorization": True,
            "future_signed_approval_still_allowed": True,
            "runtime_activation_performed": False,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [
                "signed_runtime_authorization_approval_witness"
            ],
            "rejection_control_count": len(controls),
            "scenario_rejection_count": len(scenario_rejections),
            "runtime_authorization_request_submitted": True,
            "runtime_authorization_response_recorded": True,
            "runtime_authorization_response_approved": False,
            "runtime_promotion_authorized": False,
        },
        "authority_denials": {
            "runtime_promotion_authorized": False,
            "execution_allowed": False,
            "dispatch_allowed": False,
            "runtime_replanning_enabled": False,
            "success_claim_allowed": False,
            "terminal_closure": False,
        },
        "evidence_refs": [
            "scripts/validate_governed_planning_profile_runtime_authorization_request.py",
            (
                "scripts/"
                "validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py"
            ),
            (
                "schemas/"
                "governed_planning_profile_runtime_authorization_generic_continuation_rejection.schema.json"
            ),
            (
                "examples/"
                "governed_planning_profile_runtime_authorization_generic_continuation_rejection.local.json"
            ),
            (
                "tests/"
                "test_validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py"
            ),
        ],
        "validators": [
            {
                "validator_id": (
                    "governed-planning-profile-runtime-authorization-generic-continuation-rejection"
                ),
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py"
                ),
            }
        ],
        "next_action": "record explicit signed runtime authorization approval witness before activation",
        "witness_hash": "",
    }
    witness_hash = canonical_hash(payload)
    payload["witness_id"] = f"{WITNESS_ID_PREFIX}-{witness_hash[:16]}"
    payload["witness_hash"] = witness_hash
    return payload


def validate_generic_continuation_rejection_witness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    witness_path: Path = DEFAULT_WITNESS,
) -> tuple[GenericContinuationRejectionValidation, dict[str, Any]]:
    """Validate the checked-in rejection witness and deterministic projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "generic continuation rejection schema", errors)
    witness = _load_json_object(witness_path, "generic continuation rejection witness", errors)
    request_validation, source_request = validate_runtime_authorization_request()
    errors.extend(f"source runtime authorization request: {error}" for error in request_validation.errors)
    produced_witness = build_generic_continuation_rejection_witness(source_request)

    if schema and witness:
        errors.extend(
            f"{_path_label(witness_path)}: {error}"
            for error in _validate_schema_instance(schema, witness)
        )
        _validate_witness_semantics(witness, errors, _path_label(witness_path))
    if schema:
        errors.extend(
            f"produced generic continuation rejection witness: {error}"
            for error in _validate_schema_instance(schema, produced_witness)
        )
        _validate_witness_semantics(
            produced_witness,
            errors,
            "produced generic continuation rejection witness",
        )
    if witness and witness != produced_witness:
        errors.append(
            "generic continuation rejection witness fixture does not match deterministic produced witness"
        )

    observed = witness or produced_witness
    source_ref = _mapping(observed.get("source_runtime_authorization_request"))
    validation = GenericContinuationRejectionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        witness_path=_path_label(witness_path),
        witness_id=str(observed.get("witness_id", "")),
        source_runtime_authorization_request_id=str(source_ref.get("request_id", "")),
        rejection_control_count=len(_sequence(observed.get("rejection_controls"))),
        scenario_rejection_count=len(_sequence(observed.get("scenario_rejections"))),
        runtime_authorization_gate_satisfied=bool(
            observed.get("runtime_authorization_gate_satisfied")
        ),
    )
    return validation, produced_witness


def _rejection_controls(source_request: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "source_runtime_authorization_request_valid",
            "status": "Pass",
            "evidence_ref": str(source_request.get("request_id", "")),
            "blocks_runtime_authorization": False,
        },
        {
            "control_id": "generic_continuation_not_valid_authorization",
            "status": "Pass",
            "evidence_ref": "operator_response_boundary.observed_input",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "signed_approval_absent",
            "status": "Pass",
            "evidence_ref": "signed_approval_present",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "rejection_witness_recorded",
            "status": "Pass",
            "evidence_ref": "runtime_authorization_response_kind",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "runtime_authorization_gate_blocked",
            "status": "Pass",
            "evidence_ref": "runtime_authorization_gate_satisfied",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "foundation_no_effect_boundary_preserved",
            "status": "Pass",
            "evidence_ref": "local_witness_only",
            "blocks_runtime_authorization": True,
        },
        {
            "control_id": "rejection_witness_hash_bound",
            "status": "Pass",
            "evidence_ref": "witness_hash",
            "blocks_runtime_authorization": True,
        },
    ]


def _scenario_rejections(source_request: Mapping[str, Any]) -> list[dict[str, Any]]:
    rejections: list[dict[str, Any]] = []
    for scenario_request in _sequence(source_request.get("scenario_authorization_requests")):
        if not isinstance(scenario_request, Mapping):
            continue
        rejections.append({
            "scenario_id": str(scenario_request.get("scenario_id", "")),
            "plan_class": str(scenario_request.get("plan_class", "")),
            "source_authorization_request_status": str(
                scenario_request.get("authorization_request_status", "")
            ),
            "observed_input_kind": "generic_continuation",
            "rejection_status": "RejectedNoEffect",
            "runtime_authorization_response_approved": False,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return rejections


def _validate_witness_semantics(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    if witness.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if witness.get("solver_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: solver_outcome must remain GovernanceBlocked")
    for field_name, expected in (
        ("runtime_authorization_response_status", "RejectedNoEffect"),
        ("runtime_authorization_response_kind", REJECTION_RESPONSE_KIND),
        ("generic_continuation_rejected", True),
        ("operator_response_recorded", True),
        ("operator_approval_collected", False),
        ("signed_approval_present", False),
        ("runtime_authorization_gate_satisfied", False),
        ("local_witness_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("runtime_activation_allowed", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = witness.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_source_request(witness, errors, label)
    _validate_rejection_controls(witness, errors, label)
    _validate_scenario_rejections(witness, errors, label)
    _validate_operator_response_boundary(witness, errors, label)
    _validate_promotion_gate_summary(witness, errors, label)
    _validate_authority_denials(witness, errors, label)


def _validate_source_request(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_request = _mapping(witness.get("source_runtime_authorization_request"))
    for field_name, expected in (
        ("runtime_authorization_request_status", "SubmittedNoEffect"),
        ("runtime_authorization_request_submitted", True),
        ("operator_response_required", True),
        ("operator_response_collected", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source_request.get(field_name) != expected:
            errors.append(f"{label}: source_runtime_authorization_request.{field_name} must be {expected!r}")
    if not str(source_request.get("request_id", "")).startswith(
        "governed-planning-profile-runtime-authorization-request-"
    ):
        errors.append(f"{label}: source runtime authorization request id mismatch")
    if len(str(source_request.get("request_hash", ""))) != 64:
        errors.append(f"{label}: source runtime authorization request hash must be 64 hex characters")


def _validate_rejection_controls(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(witness.get("rejection_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != REJECTION_CONTROL_IDS:
        errors.append(f"{label}: rejection control ids mismatch")
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: rejection control must be an object")
            continue
        control_id = str(control.get("control_id", ""))
        if control.get("status") != "Pass":
            errors.append(f"{label}: rejection control {control_id} status must be Pass")
        expected_block = control_id != "source_runtime_authorization_request_valid"
        if control.get("blocks_runtime_authorization") is not expected_block:
            errors.append(
                f"{label}: rejection control {control_id} blocks_runtime_authorization mismatch"
            )


def _validate_scenario_rejections(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenario_rejections = _sequence(witness.get("scenario_rejections"))
    if len(scenario_rejections) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_rejections must cover all expected plan classes")
        return
    observed_classes = []
    for scenario_rejection in scenario_rejections:
        if not isinstance(scenario_rejection, Mapping):
            errors.append(f"{label}: scenario rejection must be an object")
            continue
        observed_classes.append(str(scenario_rejection.get("plan_class", "")))
        for field_name, expected in (
            ("source_authorization_request_status", "SubmittedNoEffect"),
            ("observed_input_kind", "generic_continuation"),
            ("rejection_status", "RejectedNoEffect"),
            ("runtime_authorization_response_approved", False),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if scenario_rejection.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario rejection classes must match required order")


def _validate_operator_response_boundary(
    witness: Mapping[str, Any], errors: list[str], label: str
) -> None:
    boundary = _mapping(witness.get("operator_response_boundary"))
    for field_name, expected in (
        ("observed_input", "continue"),
        ("observed_input_kind", "generic_continuation"),
        ("explicit_signed_authorization_required", True),
        ("generic_continuation_satisfies_authorization", False),
        ("rejection_witness_records_non_authorization", True),
        ("future_signed_approval_still_allowed", True),
        ("runtime_activation_performed", False),
    ):
        if boundary.get(field_name) != expected:
            errors.append(f"{label}: operator_response_boundary.{field_name} must be {expected!r}")


def _validate_promotion_gate_summary(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(witness.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != (
        "signed_runtime_authorization_approval_witness",
    ):
        errors.append(f"{label}: remaining promotion gate ids must require signed authorization approval")
    if summary.get("rejection_control_count") != len(REJECTION_CONTROL_IDS):
        errors.append(f"{label}: promotion_gate_summary.rejection_control_count mismatch")
    if summary.get("scenario_rejection_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: promotion_gate_summary.scenario_rejection_count mismatch")
    for field_name, expected in (
        ("runtime_authorization_request_submitted", True),
        ("runtime_authorization_response_recorded", True),
        ("runtime_authorization_response_approved", False),
        ("runtime_promotion_authorized", False),
    ):
        if summary.get(field_name) != expected:
            errors.append(f"{label}: promotion_gate_summary.{field_name} must be {expected!r}")


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_FALSE_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"{label}: authority_denials.{field_name} must be false")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{_path_label(path)}: missing {label}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{_path_label(path)}: invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{_path_label(path)}: {label} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, list) else ()


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _render_text(validation: GenericContinuationRejectionValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.rejection_control_count}; "
            f"scenarios={validation.scenario_rejection_count}; "
            f"runtime_authorization_gate={validation.runtime_authorization_gate_satisfied}",
            file=stream,
        )
        print("NEXT: record explicit signed runtime authorization approval witness", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument(
        "--witness",
        type=Path,
        default=DEFAULT_WITNESS,
        help="Generic continuation rejection witness to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_witness = validate_generic_continuation_rejection_witness(
        witness_path=args.witness
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_witness"] = produced_witness
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
