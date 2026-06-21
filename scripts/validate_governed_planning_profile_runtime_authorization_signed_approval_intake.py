#!/usr/bin/env python3
"""Validate GovernedPlanningProfile signed approval intake contract.

Purpose: define the no-effect intake contract for a future signed runtime
authorization approval witness without collecting or accepting approval.
Governance scope: OCE signed-field completeness, RAG template and source
witness binding, CDCV hash traceability, CQTE authority denial constraints,
UWMA intake anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: approval witness template validator, schema validator, canonical
hashing, and governed planning profile authority constants.
Invariants:
  - The intake contract is not a signed approval witness.
  - Signature, decision value, and operator approval remain absent.
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
from scripts.validate_governed_planning_profile_runtime_authorization_approval_witness_template import (  # noqa: E402
    APPROVAL_FIELD_IDS,
    APPROVAL_RESPONSE_KIND,
    EXPECTED_APPROVAL_DECISION_VALUE,
    build_approval_witness_template,
    validate_approval_witness_template,
)
from scripts.validate_governed_planning_profile_runtime_authorization_request import (  # noqa: E402
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
)
from scripts.validate_governed_planning_profile_terminal_closure_certificate import (  # noqa: E402
    SATISFIED_PROMOTION_GATE_IDS,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_runtime_authorization_signed_approval_intake.v1"
INTAKE_ID_PREFIX = "governed-planning-profile-runtime-authorization-signed-approval-intake"
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "governed_planning_profile_runtime_authorization_signed_approval_intake.schema.json"
)
DEFAULT_INTAKE = (
    REPO_ROOT
    / "examples"
    / "governed_planning_profile_runtime_authorization_signed_approval_intake.local.json"
)
INTAKE_CONTROL_IDS = (
    "source_approval_template_valid",
    "explicit_decision_value_absent",
    "operator_identity_absent",
    "source_hash_acknowledgements_absent",
    "signature_absent",
    "generic_continuation_rejected",
    "runtime_authorization_gate_blocked",
    "activation_separate_from_approval",
    "authority_denials_preserved",
    "signed_approval_intake_hash_bound",
)
WITNESS_FIELD_IDS = APPROVAL_FIELD_IDS


@dataclass(frozen=True, slots=True)
class SignedApprovalIntakeValidation:
    """Validation result for the signed approval intake contract."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    intake_path: str
    intake_id: str
    source_approval_template_id: str
    intake_control_count: int
    required_witness_field_count: int
    scenario_intake_requirement_count: int
    signed_approval_present: bool
    runtime_authorization_gate_satisfied: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_signed_approval_intake(
    approval_template: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local signed approval intake contract."""

    source_template = dict(approval_template or build_approval_witness_template())
    source_request = _mapping(source_template.get("source_runtime_authorization_request"))
    source_rejection = _mapping(source_template.get("source_generic_continuation_rejection"))
    controls = tuple(_intake_controls(source_template, source_rejection))
    required_fields = tuple(_required_witness_fields())
    scenario_requirements = tuple(_scenario_intake_requirements(source_template))
    payload: dict[str, Any] = {
        "intake_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(source_template.get("profile_id", "")),
        "generated_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "intake_status": "AwaitingSignedApproval",
        "runtime_authorization_response_kind": APPROVAL_RESPONSE_KIND,
        "expected_approval_decision_value": EXPECTED_APPROVAL_DECISION_VALUE,
        "intake_contract_ready": True,
        "intake_accepted_as_approval": False,
        "signed_approval_witness_collected": False,
        "operator_response_recorded": False,
        "operator_approval_collected": False,
        "signed_approval_present": False,
        "decision_value_present": False,
        "decision_value_accepted": False,
        "signature_present": False,
        "signature_verified": False,
        "runtime_authorization_gate_satisfied": False,
        "local_intake_only": True,
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
        "source_approval_witness_template": {
            "template_id": str(source_template.get("template_id", "")),
            "template_hash": str(source_template.get("template_hash", "")),
            "template_status": str(source_template.get("template_status", "")),
            "template_accepted_as_approval": bool(
                source_template.get("template_accepted_as_approval")
            ),
            "approval_witness_collected": bool(
                source_template.get("approval_witness_collected")
            ),
            "signed_approval_present": bool(source_template.get("signed_approval_present")),
            "runtime_authorization_gate_satisfied": bool(
                source_template.get("runtime_authorization_gate_satisfied")
            ),
        },
        "source_runtime_authorization_request": dict(source_request),
        "source_generic_continuation_rejection": dict(source_rejection),
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "intake_controls": list(controls),
        "required_witness_fields": list(required_fields),
        "scenario_intake_requirements": list(scenario_requirements),
        "operator_signature_boundary": {
            "signed_witness_required": True,
            "signed_witness_collected": False,
            "generic_continuation_satisfies_authorization": False,
            "decision_value_required": EXPECTED_APPROVAL_DECISION_VALUE,
            "decision_value_present": False,
            "decision_value_accepted": False,
            "signature_ref_required": True,
            "signature_ref_present": False,
            "signature_verified": False,
            "approval_effect_when_verified": "satisfies_runtime_authorization_response_gate_only",
            "runtime_activation_performed": False,
            "runtime_activation_requires_separate_gate": True,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [
                "explicit_signed_runtime_authorization_approval_witness",
                "separate_runtime_activation_gate",
            ],
            "approval_template_defined": True,
            "signed_approval_intake_contract_ready": True,
            "intake_control_count": len(controls),
            "required_witness_field_count": len(required_fields),
            "scenario_intake_requirement_count": len(scenario_requirements),
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
            "scripts/validate_governed_planning_profile_runtime_authorization_approval_witness_template.py",
            "scripts/validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py",
            "schemas/governed_planning_profile_runtime_authorization_signed_approval_intake.schema.json",
            "examples/governed_planning_profile_runtime_authorization_signed_approval_intake.local.json",
            "tests/test_validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py",
        ],
        "validators": [
            {
                "validator_id": (
                    "governed-planning-profile-runtime-authorization-signed-approval-intake"
                ),
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py"
                ),
            }
        ],
        "next_action": "collect explicit signed runtime authorization approval witness values",
        "intake_hash": "",
    }
    intake_hash = canonical_hash(payload)
    payload["intake_id"] = f"{INTAKE_ID_PREFIX}-{intake_hash[:16]}"
    payload["intake_hash"] = intake_hash
    return payload


def validate_signed_approval_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    intake_path: Path = DEFAULT_INTAKE,
) -> tuple[SignedApprovalIntakeValidation, dict[str, Any]]:
    """Validate the checked-in signed approval intake and projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "signed approval intake schema", errors)
    intake = _load_json_object(intake_path, "signed approval intake", errors)
    template_validation, source_template = validate_approval_witness_template()
    errors.extend(f"source approval witness template: {error}" for error in template_validation.errors)
    produced_intake = build_signed_approval_intake(source_template)

    if schema and intake:
        errors.extend(
            f"{_path_label(intake_path)}: {error}"
            for error in _validate_schema_instance(schema, intake)
        )
        _validate_intake_semantics(intake, errors, _path_label(intake_path))
    if schema:
        errors.extend(
            f"produced signed approval intake: {error}"
            for error in _validate_schema_instance(schema, produced_intake)
        )
        _validate_intake_semantics(produced_intake, errors, "produced signed approval intake")
    if intake and intake != produced_intake:
        errors.append("signed approval intake fixture does not match deterministic produced intake")

    observed = intake or produced_intake
    source_template_ref = _mapping(observed.get("source_approval_witness_template"))
    validation = SignedApprovalIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        intake_path=_path_label(intake_path),
        intake_id=str(observed.get("intake_id", "")),
        source_approval_template_id=str(source_template_ref.get("template_id", "")),
        intake_control_count=len(_sequence(observed.get("intake_controls"))),
        required_witness_field_count=len(_sequence(observed.get("required_witness_fields"))),
        scenario_intake_requirement_count=len(_sequence(observed.get("scenario_intake_requirements"))),
        signed_approval_present=bool(observed.get("signed_approval_present")),
        runtime_authorization_gate_satisfied=bool(
            observed.get("runtime_authorization_gate_satisfied")
        ),
    )
    return validation, produced_intake


def _intake_controls(
    source_template: Mapping[str, Any],
    source_rejection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    awaiting_ids = {
        "explicit_decision_value_absent",
        "operator_identity_absent",
        "source_hash_acknowledgements_absent",
        "signature_absent",
    }
    evidence_refs = {
        "source_approval_template_valid": str(source_template.get("template_id", "")),
        "explicit_decision_value_absent": "required_witness_fields.explicit_decision_value",
        "operator_identity_absent": "required_witness_fields.operator_identity_ref",
        "source_hash_acknowledgements_absent": "required_witness_fields.source_hash_acknowledgements",
        "signature_absent": "required_witness_fields.signature_ref",
        "generic_continuation_rejected": str(source_rejection.get("witness_id", "")),
        "runtime_authorization_gate_blocked": "runtime_authorization_gate_satisfied",
        "activation_separate_from_approval": "operator_signature_boundary.runtime_activation_performed",
        "authority_denials_preserved": "authority_denials",
        "signed_approval_intake_hash_bound": "intake_hash",
    }
    return [
        {
            "control_id": control_id,
            "status": "AwaitingEvidence" if control_id in awaiting_ids else "Pass",
            "evidence_ref": evidence_refs[control_id],
            "blocks_authorization": True,
        }
        for control_id in INTAKE_CONTROL_IDS
    ]


def _required_witness_fields() -> list[dict[str, Any]]:
    field_descriptions = {
        "operator_identity_ref": "stable operator identity reference",
        "explicit_decision_value": EXPECTED_APPROVAL_DECISION_VALUE,
        "runtime_authorization_request_hash_acknowledgement": "source request hash acknowledgement",
        "generic_continuation_rejection_hash_acknowledgement": "generic continuation rejection hash acknowledgement",
        "authority_scope_acknowledgement": "approval satisfies response gate only",
        "activation_separation_acknowledgement": "activation remains a separate governed action",
        "rollback_hysteresis_acknowledgement": "rollback and replanning guards acknowledgement",
        "signed_at": "absolute timestamp for signed approval",
        "signature_ref": "verifiable signature or signed witness reference",
    }
    return [
        {
            "field_id": field_id,
            "required": True,
            "value_present": False,
            "verified": False,
            "accepted_from_generic_continuation": False,
            "description": field_descriptions[field_id],
        }
        for field_id in WITNESS_FIELD_IDS
    ]


def _scenario_intake_requirements(source_template: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for scenario_template in _sequence(source_template.get("scenario_approval_requirements")):
        if not isinstance(scenario_template, Mapping):
            continue
        requirements.append({
            "scenario_id": str(scenario_template.get("scenario_id", "")),
            "plan_class": str(scenario_template.get("plan_class", "")),
            "signed_approval_witness_required": True,
            "signed_approval_witness_collected": False,
            "runtime_authorization_response_approved": False,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return requirements


def _validate_intake_semantics(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    if intake.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    for field_name, expected in (
        ("solver_outcome", "AwaitingEvidence"),
        ("intake_status", "AwaitingSignedApproval"),
        ("runtime_authorization_response_kind", APPROVAL_RESPONSE_KIND),
        ("expected_approval_decision_value", EXPECTED_APPROVAL_DECISION_VALUE),
        ("intake_contract_ready", True),
        ("intake_accepted_as_approval", False),
        ("signed_approval_witness_collected", False),
        ("operator_response_recorded", False),
        ("operator_approval_collected", False),
        ("signed_approval_present", False),
        ("decision_value_present", False),
        ("decision_value_accepted", False),
        ("signature_present", False),
        ("signature_verified", False),
        ("runtime_authorization_gate_satisfied", False),
        ("local_intake_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("runtime_activation_allowed", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = intake.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_source_template(intake, errors, label)
    _validate_source_request(intake, errors, label)
    _validate_source_rejection(intake, errors, label)
    _validate_controls(intake, errors, label)
    _validate_required_fields(intake, errors, label)
    _validate_scenario_requirements(intake, errors, label)
    _validate_signature_boundary(intake, errors, label)
    _validate_promotion_summary(intake, errors, label)
    _validate_authority_denials(intake, errors, label)


def _validate_source_template(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_template = _mapping(intake.get("source_approval_witness_template"))
    for field_name, expected in (
        ("template_status", "TemplateNoEffect"),
        ("template_accepted_as_approval", False),
        ("approval_witness_collected", False),
        ("signed_approval_present", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source_template.get(field_name) != expected:
            errors.append(f"{label}: source_approval_witness_template.{field_name} must be {expected!r}")
    if not str(source_template.get("template_id", "")).startswith(
        "governed-planning-profile-runtime-authorization-approval-witness-template-"
    ):
        errors.append(f"{label}: source approval witness template id mismatch")
    if len(str(source_template.get("template_hash", ""))) != 64:
        errors.append(f"{label}: source approval witness template hash must be 64 characters")


def _validate_source_request(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_request = _mapping(intake.get("source_runtime_authorization_request"))
    for field_name, expected in (
        ("runtime_authorization_request_status", "SubmittedNoEffect"),
        ("runtime_authorization_request_submitted", True),
        ("operator_response_required", True),
        ("operator_response_collected", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source_request.get(field_name) != expected:
            errors.append(f"{label}: source_runtime_authorization_request.{field_name} must be {expected!r}")


def _validate_source_rejection(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_rejection = _mapping(intake.get("source_generic_continuation_rejection"))
    for field_name, expected in (
        ("runtime_authorization_response_status", "RejectedNoEffect"),
        ("generic_continuation_rejected", True),
        ("signed_approval_present", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source_rejection.get(field_name) != expected:
            errors.append(f"{label}: source_generic_continuation_rejection.{field_name} must be {expected!r}")


def _validate_controls(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(intake.get("intake_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != INTAKE_CONTROL_IDS:
        errors.append(f"{label}: intake control ids mismatch")
    awaiting_ids = {
        "explicit_decision_value_absent",
        "operator_identity_absent",
        "source_hash_acknowledgements_absent",
        "signature_absent",
    }
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: intake control must be an object")
            continue
        control_id = str(control.get("control_id", ""))
        expected_status = "AwaitingEvidence" if control_id in awaiting_ids else "Pass"
        if control.get("status") != expected_status:
            errors.append(f"{label}: intake control {control_id} status must be {expected_status}")
        if control.get("blocks_authorization") is not True:
            errors.append(f"{label}: intake control {control_id} must block authorization")


def _validate_required_fields(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    fields = _sequence(intake.get("required_witness_fields"))
    observed_ids = tuple(str(field.get("field_id", "")) for field in fields if isinstance(field, Mapping))
    if observed_ids != WITNESS_FIELD_IDS:
        errors.append(f"{label}: required witness field ids mismatch")
    for field in fields:
        if not isinstance(field, Mapping):
            errors.append(f"{label}: required witness field must be an object")
            continue
        field_id = str(field.get("field_id", ""))
        for field_name, expected in (
            ("required", True),
            ("value_present", False),
            ("verified", False),
            ("accepted_from_generic_continuation", False),
        ):
            if field.get(field_name) != expected:
                errors.append(f"{label}: required witness field {field_id} {field_name} must be {expected!r}")


def _validate_scenario_requirements(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    requirements = _sequence(intake.get("scenario_intake_requirements"))
    if len(requirements) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_intake_requirements must cover all expected plan classes")
        return
    observed_classes = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            errors.append(f"{label}: scenario intake requirement must be an object")
            continue
        observed_classes.append(str(requirement.get("plan_class", "")))
        for field_name, expected in (
            ("signed_approval_witness_required", True),
            ("signed_approval_witness_collected", False),
            ("runtime_authorization_response_approved", False),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if requirement.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario intake classes must match required order")


def _validate_signature_boundary(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(intake.get("operator_signature_boundary"))
    for field_name, expected in (
        ("signed_witness_required", True),
        ("signed_witness_collected", False),
        ("generic_continuation_satisfies_authorization", False),
        ("decision_value_required", EXPECTED_APPROVAL_DECISION_VALUE),
        ("decision_value_present", False),
        ("decision_value_accepted", False),
        ("signature_ref_required", True),
        ("signature_ref_present", False),
        ("signature_verified", False),
        ("approval_effect_when_verified", "satisfies_runtime_authorization_response_gate_only"),
        ("runtime_activation_performed", False),
        ("runtime_activation_requires_separate_gate", True),
    ):
        if boundary.get(field_name) != expected:
            errors.append(f"{label}: operator_signature_boundary.{field_name} must be {expected!r}")


def _validate_promotion_summary(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(intake.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != (
        "explicit_signed_runtime_authorization_approval_witness",
        "separate_runtime_activation_gate",
    ):
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    for field_name, expected in (
        ("approval_template_defined", True),
        ("signed_approval_intake_contract_ready", True),
        ("intake_control_count", len(INTAKE_CONTROL_IDS)),
        ("required_witness_field_count", len(WITNESS_FIELD_IDS)),
        ("scenario_intake_requirement_count", len(EXPECTED_PLAN_CLASSES)),
        ("signed_approval_witness_collected", False),
        ("runtime_authorization_response_approved", False),
        ("runtime_promotion_authorized", False),
    ):
        if summary.get(field_name) != expected:
            errors.append(f"{label}: promotion_gate_summary.{field_name} must be {expected!r}")


def _validate_authority_denials(intake: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(intake.get("authority_denials"))
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


def _render_text(validation: SignedApprovalIntakeValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.intake_control_count}; "
            f"required_fields={validation.required_witness_field_count}; "
            f"scenarios={validation.scenario_intake_requirement_count}; "
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
        "--intake",
        type=Path,
        default=DEFAULT_INTAKE,
        help="Signed approval intake contract to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_intake = validate_signed_approval_intake(intake_path=args.intake)
    if args.json:
        payload = validation.as_dict()
        payload["produced_intake"] = produced_intake
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
