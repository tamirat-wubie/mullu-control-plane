#!/usr/bin/env python3
"""Validate signed approval generic continuation rejection witness.

Purpose: prove a generic continuation input does not satisfy the
GovernedPlanningProfile signed approval intake contract.
Governance scope: OCE response classification, RAG signed-intake and PR
evidence binding, CDCV hash traceability, CQTE authority denial constraints,
UWMA rejection anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: signed approval intake validator, schema validator, canonical
hashing, and governed planning profile authority constants.
Invariants:
  - A generic continuation is recorded only as a rejection witness.
  - The witness never records signed approval values or signature verification.
  - Runtime authorization and activation remain blocked.
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
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
)
from scripts.validate_governed_planning_profile_runtime_authorization_signed_approval_intake import (  # noqa: E402
    EXPECTED_APPROVAL_DECISION_VALUE,
    INTAKE_CONTROL_IDS,
    WITNESS_FIELD_IDS,
    build_signed_approval_intake,
    validate_signed_approval_intake,
)
from scripts.validate_governed_planning_profile_terminal_closure_certificate import (  # noqa: E402
    SATISFIED_PROMOTION_GATE_IDS,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = (
    "governed_planning_profile_runtime_authorization_signed_approval_"
    "generic_continuation_rejection.v1"
)
WITNESS_ID_PREFIX = (
    "governed-planning-profile-runtime-authorization-signed-approval-"
    "generic-continuation-rejection"
)
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / (
        "governed_planning_profile_runtime_authorization_signed_approval_"
        "generic_continuation_rejection.schema.json"
    )
)
DEFAULT_WITNESS = (
    REPO_ROOT
    / "examples"
    / (
        "governed_planning_profile_runtime_authorization_signed_approval_"
        "generic_continuation_rejection.local.json"
    )
)
PR_EVIDENCE = {
    "pr_number": 2047,
    "pr_url": "https://github.com/tamirat-wubie/mullu-control-plane/pull/2047",
    "head_ref": "codex/planning-runtime-authorization-signed-approval-intake-20260620",
    "head_oid": "a9495425958b1755a3c5ce1866b3b8e45541565b",
    "state": "CLOSED",
    "merged": False,
    "closed_by": "tamirat-wubie",
    "closed_at": "2026-06-20T09:44:17Z",
    "checks_observed_green": True,
    "operator_close_respected": True,
}
REJECTION_CONTROL_IDS = (
    "source_signed_approval_intake_valid",
    "closed_pr_2047_evidence_bound",
    "generic_continuation_not_signed_witness",
    "decision_value_absent",
    "operator_identity_absent",
    "signature_absent",
    "signature_not_verified",
    "runtime_authorization_gate_blocked",
    "activation_separate_from_approval",
    "authority_denials_preserved",
    "rejection_witness_hash_bound",
)


@dataclass(frozen=True, slots=True)
class SignedApprovalGenericContinuationRejectionValidation:
    """Validation result for signed approval generic continuation rejection."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    witness_path: str
    witness_id: str
    source_signed_approval_intake_id: str
    rejection_control_count: int
    required_witness_field_rejection_count: int
    scenario_rejection_count: int
    signed_approval_present: bool
    runtime_authorization_gate_satisfied: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_signed_approval_generic_continuation_rejection(
    signed_approval_intake: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local generic-continuation rejection witness."""

    source_intake = dict(signed_approval_intake or build_signed_approval_intake())
    controls = tuple(_rejection_controls(source_intake))
    field_rejections = tuple(_required_witness_field_rejections(source_intake))
    scenario_rejections = tuple(_scenario_rejections(source_intake))
    payload: dict[str, Any] = {
        "witness_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(source_intake.get("profile_id", "")),
        "recorded_at": GENERATED_AT,
        "solver_outcome": "GovernanceBlocked",
        "rejection_status": "RejectedNoEffect",
        "observed_input": "continue",
        "observed_input_kind": "generic_continuation",
        "generic_continuation_rejected": True,
        "operator_response_recorded": True,
        "operator_approval_collected": False,
        "signed_approval_witness_collected": False,
        "signed_approval_present": False,
        "decision_value_present": False,
        "decision_value_accepted": False,
        "signature_present": False,
        "signature_verified": False,
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
        "source_signed_approval_intake": {
            "intake_id": str(source_intake.get("intake_id", "")),
            "intake_hash": str(source_intake.get("intake_hash", "")),
            "intake_status": str(source_intake.get("intake_status", "")),
            "signed_approval_witness_collected": bool(
                source_intake.get("signed_approval_witness_collected")
            ),
            "signed_approval_present": bool(source_intake.get("signed_approval_present")),
            "decision_value_accepted": bool(source_intake.get("decision_value_accepted")),
            "signature_verified": bool(source_intake.get("signature_verified")),
            "runtime_authorization_gate_satisfied": bool(
                source_intake.get("runtime_authorization_gate_satisfied")
            ),
        },
        "source_pull_request_evidence": dict(PR_EVIDENCE),
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "rejection_controls": list(controls),
        "required_witness_field_rejections": list(field_rejections),
        "scenario_rejections": list(scenario_rejections),
        "operator_response_boundary": {
            "observed_input": "continue",
            "observed_input_kind": "generic_continuation",
            "generic_continuation_satisfies_authorization": False,
            "expected_approval_decision_value": EXPECTED_APPROVAL_DECISION_VALUE,
            "signed_witness_required": True,
            "signed_witness_collected": False,
            "signature_ref_required": True,
            "signature_ref_present": False,
            "signature_verified": False,
            "future_signed_approval_still_allowed": True,
            "runtime_activation_performed": False,
            "runtime_activation_requires_separate_gate": True,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [
                "explicit_signed_runtime_authorization_approval_witness",
                "separate_runtime_activation_gate",
            ],
            "signed_approval_intake_contract_ready": True,
            "generic_continuation_rejection_recorded": True,
            "rejection_control_count": len(controls),
            "required_witness_field_rejection_count": len(field_rejections),
            "scenario_rejection_count": len(scenario_rejections),
            "signed_approval_witness_collected": False,
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
            "scripts/validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py",
            (
                "scripts/validate_governed_planning_profile_runtime_authorization_"
                "signed_approval_generic_continuation_rejection.py"
            ),
            (
                "schemas/governed_planning_profile_runtime_authorization_"
                "signed_approval_generic_continuation_rejection.schema.json"
            ),
            (
                "examples/governed_planning_profile_runtime_authorization_"
                "signed_approval_generic_continuation_rejection.local.json"
            ),
            (
                "tests/test_validate_governed_planning_profile_runtime_authorization_"
                "signed_approval_generic_continuation_rejection.py"
            ),
        ],
        "validators": [
            {
                "validator_id": (
                    "governed-planning-profile-runtime-authorization-signed-approval-"
                    "generic-continuation-rejection"
                ),
                "command": (
                    "python scripts/validate_governed_planning_profile_runtime_authorization_"
                    "signed_approval_generic_continuation_rejection.py"
                ),
            }
        ],
        "next_action": "collect explicit signed runtime authorization approval witness values",
        "witness_hash": "",
    }
    witness_hash = canonical_hash(payload)
    payload["witness_id"] = f"{WITNESS_ID_PREFIX}-{witness_hash[:16]}"
    payload["witness_hash"] = witness_hash
    return payload


def validate_signed_approval_generic_continuation_rejection(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    witness_path: Path = DEFAULT_WITNESS,
) -> tuple[SignedApprovalGenericContinuationRejectionValidation, dict[str, Any]]:
    """Validate the checked-in signed-approval continuation rejection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "signed approval rejection schema", errors)
    witness = _load_json_object(witness_path, "signed approval rejection witness", errors)
    intake_validation, source_intake = validate_signed_approval_intake()
    errors.extend(f"source signed approval intake: {error}" for error in intake_validation.errors)
    produced_witness = build_signed_approval_generic_continuation_rejection(source_intake)

    if schema and witness:
        errors.extend(
            f"{_path_label(witness_path)}: {error}"
            for error in _validate_schema_instance(schema, witness)
        )
        _validate_witness_semantics(witness, errors, _path_label(witness_path))
    if schema:
        errors.extend(
            f"produced signed approval generic continuation rejection: {error}"
            for error in _validate_schema_instance(schema, produced_witness)
        )
        _validate_witness_semantics(
            produced_witness,
            errors,
            "produced signed approval generic continuation rejection",
        )
    if witness and witness != produced_witness:
        errors.append("signed approval generic continuation rejection fixture does not match deterministic produced witness")

    observed = witness or produced_witness
    source_intake_ref = _mapping(observed.get("source_signed_approval_intake"))
    validation = SignedApprovalGenericContinuationRejectionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        witness_path=_path_label(witness_path),
        witness_id=str(observed.get("witness_id", "")),
        source_signed_approval_intake_id=str(source_intake_ref.get("intake_id", "")),
        rejection_control_count=len(_sequence(observed.get("rejection_controls"))),
        required_witness_field_rejection_count=len(
            _sequence(observed.get("required_witness_field_rejections"))
        ),
        scenario_rejection_count=len(_sequence(observed.get("scenario_rejections"))),
        signed_approval_present=bool(observed.get("signed_approval_present")),
        runtime_authorization_gate_satisfied=bool(
            observed.get("runtime_authorization_gate_satisfied")
        ),
    )
    return validation, produced_witness


def _rejection_controls(source_intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence_refs = {
        "source_signed_approval_intake_valid": str(source_intake.get("intake_id", "")),
        "closed_pr_2047_evidence_bound": PR_EVIDENCE["pr_url"],
        "generic_continuation_not_signed_witness": "observed_input",
        "decision_value_absent": "decision_value_present",
        "operator_identity_absent": "required_witness_fields.operator_identity_ref",
        "signature_absent": "signature_present",
        "signature_not_verified": "signature_verified",
        "runtime_authorization_gate_blocked": "runtime_authorization_gate_satisfied",
        "activation_separate_from_approval": "operator_response_boundary.runtime_activation_performed",
        "authority_denials_preserved": "authority_denials",
        "rejection_witness_hash_bound": "witness_hash",
    }
    return [
        {
            "control_id": control_id,
            "status": "Pass",
            "evidence_ref": evidence_refs[control_id],
            "blocks_authorization": True,
        }
        for control_id in REJECTION_CONTROL_IDS
    ]


def _required_witness_field_rejections(source_intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    rejections: list[dict[str, Any]] = []
    for field in _sequence(source_intake.get("required_witness_fields")):
        if not isinstance(field, Mapping):
            continue
        rejections.append({
            "field_id": str(field.get("field_id", "")),
            "required": True,
            "value_present": False,
            "verified": False,
            "accepted_from_generic_continuation": False,
            "rejection_reason": "generic_continuation_is_not_signed_approval_evidence",
        })
    return rejections


def _scenario_rejections(source_intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    rejections: list[dict[str, Any]] = []
    for scenario in _sequence(source_intake.get("scenario_intake_requirements")):
        if not isinstance(scenario, Mapping):
            continue
        rejections.append({
            "scenario_id": str(scenario.get("scenario_id", "")),
            "plan_class": str(scenario.get("plan_class", "")),
            "generic_continuation_rejected": True,
            "signed_approval_witness_collected": False,
            "runtime_authorization_response_approved": False,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return rejections


def _validate_witness_semantics(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("solver_outcome", "GovernanceBlocked"),
        ("rejection_status", "RejectedNoEffect"),
        ("observed_input", "continue"),
        ("observed_input_kind", "generic_continuation"),
        ("generic_continuation_rejected", True),
        ("operator_response_recorded", True),
        ("operator_approval_collected", False),
        ("signed_approval_witness_collected", False),
        ("signed_approval_present", False),
        ("decision_value_present", False),
        ("decision_value_accepted", False),
        ("signature_present", False),
        ("signature_verified", False),
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
    _validate_source_intake(witness, errors, label)
    _validate_pr_evidence(witness, errors, label)
    _validate_controls(witness, errors, label)
    _validate_field_rejections(witness, errors, label)
    _validate_scenario_rejections(witness, errors, label)
    _validate_operator_boundary(witness, errors, label)
    _validate_promotion_summary(witness, errors, label)
    _validate_authority_denials(witness, errors, label)


def _validate_source_intake(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    source = _mapping(witness.get("source_signed_approval_intake"))
    for field_name, expected in (
        ("intake_status", "AwaitingSignedApproval"),
        ("signed_approval_witness_collected", False),
        ("signed_approval_present", False),
        ("decision_value_accepted", False),
        ("signature_verified", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source.get(field_name) != expected:
            errors.append(f"{label}: source_signed_approval_intake.{field_name} must be {expected!r}")
    if not str(source.get("intake_id", "")).startswith(
        "governed-planning-profile-runtime-authorization-signed-approval-intake-"
    ):
        errors.append(f"{label}: source signed approval intake id mismatch")
    if len(str(source.get("intake_hash", ""))) != 64:
        errors.append(f"{label}: source signed approval intake hash must be 64 characters")


def _validate_pr_evidence(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence = _mapping(witness.get("source_pull_request_evidence"))
    for field_name, expected in PR_EVIDENCE.items():
        if evidence.get(field_name) != expected:
            errors.append(f"{label}: source_pull_request_evidence.{field_name} must be {expected!r}")


def _validate_controls(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
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
        if control.get("blocks_authorization") is not True:
            errors.append(f"{label}: rejection control {control_id} must block authorization")


def _validate_field_rejections(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    fields = _sequence(witness.get("required_witness_field_rejections"))
    observed_ids = tuple(str(field.get("field_id", "")) for field in fields if isinstance(field, Mapping))
    if observed_ids != WITNESS_FIELD_IDS:
        errors.append(f"{label}: required witness field rejection ids mismatch")
    for field in fields:
        if not isinstance(field, Mapping):
            errors.append(f"{label}: required witness field rejection must be an object")
            continue
        field_id = str(field.get("field_id", ""))
        for field_name, expected in (
            ("required", True),
            ("value_present", False),
            ("verified", False),
            ("accepted_from_generic_continuation", False),
            ("rejection_reason", "generic_continuation_is_not_signed_approval_evidence"),
        ):
            if field.get(field_name) != expected:
                errors.append(f"{label}: field rejection {field_id}.{field_name} must be {expected!r}")


def _validate_scenario_rejections(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenarios = _sequence(witness.get("scenario_rejections"))
    if len(scenarios) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_rejections must cover all expected plan classes")
        return
    observed_classes = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            errors.append(f"{label}: scenario rejection must be an object")
            continue
        observed_classes.append(str(scenario.get("plan_class", "")))
        for field_name, expected in (
            ("generic_continuation_rejected", True),
            ("signed_approval_witness_collected", False),
            ("runtime_authorization_response_approved", False),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if scenario.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario rejection classes must match required order")


def _validate_operator_boundary(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(witness.get("operator_response_boundary"))
    for field_name, expected in (
        ("observed_input", "continue"),
        ("observed_input_kind", "generic_continuation"),
        ("generic_continuation_satisfies_authorization", False),
        ("expected_approval_decision_value", EXPECTED_APPROVAL_DECISION_VALUE),
        ("signed_witness_required", True),
        ("signed_witness_collected", False),
        ("signature_ref_required", True),
        ("signature_ref_present", False),
        ("signature_verified", False),
        ("future_signed_approval_still_allowed", True),
        ("runtime_activation_performed", False),
        ("runtime_activation_requires_separate_gate", True),
    ):
        if boundary.get(field_name) != expected:
            errors.append(f"{label}: operator_response_boundary.{field_name} must be {expected!r}")


def _validate_promotion_summary(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(witness.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != (
        "explicit_signed_runtime_authorization_approval_witness",
        "separate_runtime_activation_gate",
    ):
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    for field_name, expected in (
        ("signed_approval_intake_contract_ready", True),
        ("generic_continuation_rejection_recorded", True),
        ("rejection_control_count", len(REJECTION_CONTROL_IDS)),
        ("required_witness_field_rejection_count", len(WITNESS_FIELD_IDS)),
        ("scenario_rejection_count", len(EXPECTED_PLAN_CLASSES)),
        ("signed_approval_witness_collected", False),
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


def _render_text(
    validation: SignedApprovalGenericContinuationRejectionValidation,
    stream: TextIO,
) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.rejection_control_count}; "
            f"fields={validation.required_witness_field_rejection_count}; "
            f"scenarios={validation.scenario_rejection_count}; "
            f"signed_approval_present={validation.signed_approval_present}; "
            f"runtime_authorization_gate={validation.runtime_authorization_gate_satisfied}",
            file=stream,
        )
        print("NEXT: collect explicit signed approval witness values", file=stream)
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
        help="Signed approval generic continuation rejection witness to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_witness = validate_signed_approval_generic_continuation_rejection(
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
