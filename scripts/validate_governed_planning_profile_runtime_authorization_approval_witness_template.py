#!/usr/bin/env python3
"""Validate GovernedPlanningProfile runtime authorization approval template.

Purpose: define the no-effect evidence template required for a future explicit
signed runtime authorization approval witness.
Governance scope: OCE approval-field completeness, RAG authorization-request
and rejection-witness binding, CDCV hash traceability, CQTE authority denial
constraints, UWMA template anchoring, SRCA bounded scenario enumeration, and
PRS validation.
Dependencies: runtime authorization request validator, generic continuation
rejection validator, schema validator, and canonical hashing.
Invariants:
  - The template is not an approval witness and is never accepted as approval.
  - Signed approval remains absent and runtime authorization remains blocked.
  - Runtime activation remains a separate governed action after approval.
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
from scripts.validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection import (  # noqa: E402
    REJECTION_RESPONSE_KIND,
    build_generic_continuation_rejection_witness,
    validate_generic_continuation_rejection_witness,
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


SCHEMA_VERSION = "governed_planning_profile_runtime_authorization_approval_witness_template.v1"
TEMPLATE_ID_PREFIX = "governed-planning-profile-runtime-authorization-approval-witness-template"
APPROVAL_RESPONSE_KIND = ALLOWED_RESPONSE_KINDS[0]
EXPECTED_APPROVAL_DECISION_VALUE = "approve_governed_planning_profile_runtime_authorization"
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "governed_planning_profile_runtime_authorization_approval_witness_template.schema.json"
)
DEFAULT_TEMPLATE = (
    REPO_ROOT
    / "examples"
    / "governed_planning_profile_runtime_authorization_approval_witness_template.local.json"
)
APPROVAL_TEMPLATE_CONTROL_IDS = (
    "source_runtime_authorization_request_valid",
    "source_generic_continuation_rejection_valid",
    "approval_template_not_collected_approval",
    "explicit_signed_approval_required",
    "activation_separate_from_approval",
    "runtime_authorization_gate_blocked",
    "authority_denials_preserved",
    "approval_template_hash_bound",
)
APPROVAL_FIELD_IDS = (
    "operator_identity_ref",
    "explicit_decision_value",
    "runtime_authorization_request_hash_acknowledgement",
    "generic_continuation_rejection_hash_acknowledgement",
    "authority_scope_acknowledgement",
    "activation_separation_acknowledgement",
    "rollback_hysteresis_acknowledgement",
    "signed_at",
    "signature_ref",
)


@dataclass(frozen=True, slots=True)
class ApprovalWitnessTemplateValidation:
    """Validation result for the planning-profile approval witness template."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    template_path: str
    template_id: str
    source_runtime_authorization_request_id: str
    source_generic_continuation_rejection_id: str
    approval_template_control_count: int
    required_approval_field_count: int
    scenario_approval_requirement_count: int
    runtime_authorization_gate_satisfied: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_approval_witness_template(
    runtime_authorization_request: Mapping[str, Any] | None = None,
    generic_continuation_rejection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local approval witness template."""

    source_request = dict(runtime_authorization_request or build_runtime_authorization_request())
    source_rejection = dict(
        generic_continuation_rejection
        or build_generic_continuation_rejection_witness(source_request)
    )
    controls = tuple(_approval_template_controls(source_request, source_rejection))
    required_fields = tuple(_required_approval_fields())
    scenario_requirements = tuple(_scenario_approval_requirements(source_request))
    payload: dict[str, Any] = {
        "template_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(source_request.get("profile_id", "")),
        "generated_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "template_status": "TemplateNoEffect",
        "runtime_authorization_response_kind": APPROVAL_RESPONSE_KIND,
        "expected_approval_decision_value": EXPECTED_APPROVAL_DECISION_VALUE,
        "template_accepted_as_approval": False,
        "approval_witness_collected": False,
        "operator_response_recorded": False,
        "operator_approval_collected": False,
        "signed_approval_present": False,
        "runtime_authorization_gate_satisfied": False,
        "local_template_only": True,
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
        "source_generic_continuation_rejection": {
            "witness_id": str(source_rejection.get("witness_id", "")),
            "witness_hash": str(source_rejection.get("witness_hash", "")),
            "runtime_authorization_response_status": str(
                source_rejection.get("runtime_authorization_response_status", "")
            ),
            "runtime_authorization_response_kind": str(
                source_rejection.get("runtime_authorization_response_kind", "")
            ),
            "generic_continuation_rejected": bool(
                source_rejection.get("generic_continuation_rejected")
            ),
            "signed_approval_present": bool(source_rejection.get("signed_approval_present")),
            "runtime_authorization_gate_satisfied": bool(
                source_rejection.get("runtime_authorization_gate_satisfied")
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "approval_template_controls": list(controls),
        "required_approval_fields": list(required_fields),
        "scenario_approval_requirements": list(scenario_requirements),
        "operator_approval_boundary": {
            "template_only": True,
            "generic_continuation_satisfies_authorization": False,
            "explicit_signed_approval_required": True,
            "approval_witness_required": True,
            "approval_witness_collected": False,
            "future_approval_effect": "satisfies_runtime_authorization_response_gate_only",
            "runtime_activation_performed": False,
            "runtime_activation_requires_separate_gate": True,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [
                "explicit_signed_runtime_authorization_approval_witness",
                "separate_runtime_activation_gate",
            ],
            "approval_template_control_count": len(controls),
            "required_approval_field_count": len(required_fields),
            "scenario_approval_requirement_count": len(scenario_requirements),
            "runtime_authorization_request_submitted": True,
            "generic_continuation_rejection_recorded": True,
            "approval_witness_collected": False,
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
            "scripts/validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py",
            "scripts/validate_governed_planning_profile_runtime_authorization_approval_witness_template.py",
            "schemas/governed_planning_profile_runtime_authorization_approval_witness_template.schema.json",
            "examples/governed_planning_profile_runtime_authorization_approval_witness_template.local.json",
            "tests/test_validate_governed_planning_profile_runtime_authorization_approval_witness_template.py",
        ],
        "validators": [
            {
                "validator_id": (
                    "governed-planning-profile-runtime-authorization-approval-witness-template"
                ),
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_runtime_authorization_approval_witness_template.py"
                ),
            }
        ],
        "next_action": "collect explicit signed runtime authorization approval witness matching this template",
        "template_hash": "",
    }
    template_hash = canonical_hash(payload)
    payload["template_id"] = f"{TEMPLATE_ID_PREFIX}-{template_hash[:16]}"
    payload["template_hash"] = template_hash
    return payload


def validate_approval_witness_template(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    template_path: Path = DEFAULT_TEMPLATE,
) -> tuple[ApprovalWitnessTemplateValidation, dict[str, Any]]:
    """Validate the checked-in approval witness template and projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "approval witness template schema", errors)
    template = _load_json_object(template_path, "approval witness template", errors)
    request_validation, source_request = validate_runtime_authorization_request()
    errors.extend(f"source runtime authorization request: {error}" for error in request_validation.errors)
    rejection_validation, source_rejection = validate_generic_continuation_rejection_witness()
    errors.extend(f"source generic continuation rejection: {error}" for error in rejection_validation.errors)
    produced_template = build_approval_witness_template(source_request, source_rejection)

    if schema and template:
        errors.extend(
            f"{_path_label(template_path)}: {error}"
            for error in _validate_schema_instance(schema, template)
        )
        _validate_template_semantics(template, errors, _path_label(template_path))
    if schema:
        errors.extend(
            f"produced approval witness template: {error}"
            for error in _validate_schema_instance(schema, produced_template)
        )
        _validate_template_semantics(produced_template, errors, "produced approval witness template")
    if template and template != produced_template:
        errors.append("approval witness template fixture does not match deterministic produced template")

    observed = template or produced_template
    source_request_ref = _mapping(observed.get("source_runtime_authorization_request"))
    source_rejection_ref = _mapping(observed.get("source_generic_continuation_rejection"))
    validation = ApprovalWitnessTemplateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        template_path=_path_label(template_path),
        template_id=str(observed.get("template_id", "")),
        source_runtime_authorization_request_id=str(source_request_ref.get("request_id", "")),
        source_generic_continuation_rejection_id=str(source_rejection_ref.get("witness_id", "")),
        approval_template_control_count=len(_sequence(observed.get("approval_template_controls"))),
        required_approval_field_count=len(_sequence(observed.get("required_approval_fields"))),
        scenario_approval_requirement_count=len(
            _sequence(observed.get("scenario_approval_requirements"))
        ),
        runtime_authorization_gate_satisfied=bool(
            observed.get("runtime_authorization_gate_satisfied")
        ),
    )
    return validation, produced_template


def _approval_template_controls(
    source_request: Mapping[str, Any],
    source_rejection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "source_runtime_authorization_request_valid",
            "status": "Pass",
            "evidence_ref": str(source_request.get("request_id", "")),
            "blocks_template_emission": False,
        },
        {
            "control_id": "source_generic_continuation_rejection_valid",
            "status": "Pass",
            "evidence_ref": str(source_rejection.get("witness_id", "")),
            "blocks_template_emission": False,
        },
        {
            "control_id": "approval_template_not_collected_approval",
            "status": "Pass",
            "evidence_ref": "template_accepted_as_approval",
            "blocks_template_emission": False,
        },
        {
            "control_id": "explicit_signed_approval_required",
            "status": "AwaitingEvidence",
            "evidence_ref": "required_approval_fields.signature_ref",
            "blocks_template_emission": False,
        },
        {
            "control_id": "activation_separate_from_approval",
            "status": "Pass",
            "evidence_ref": "operator_approval_boundary.runtime_activation_performed",
            "blocks_template_emission": False,
        },
        {
            "control_id": "runtime_authorization_gate_blocked",
            "status": "Pass",
            "evidence_ref": "runtime_authorization_gate_satisfied",
            "blocks_template_emission": False,
        },
        {
            "control_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_template_emission": False,
        },
        {
            "control_id": "approval_template_hash_bound",
            "status": "Pass",
            "evidence_ref": "template_hash",
            "blocks_template_emission": False,
        },
    ]


def _required_approval_fields() -> list[dict[str, Any]]:
    field_descriptions = {
        "operator_identity_ref": "stable operator identity reference",
        "explicit_decision_value": EXPECTED_APPROVAL_DECISION_VALUE,
        "runtime_authorization_request_hash_acknowledgement": "source request hash acknowledged",
        "generic_continuation_rejection_hash_acknowledgement": "generic continuation rejection hash acknowledged",
        "authority_scope_acknowledgement": "approval satisfies response gate only",
        "activation_separation_acknowledgement": "activation remains a separate governed action",
        "rollback_hysteresis_acknowledgement": "rollback and replanning guards acknowledged",
        "signed_at": "absolute timestamp for signed approval",
        "signature_ref": "verifiable signature or signed witness reference",
    }
    return [
        {
            "field_id": field_id,
            "required": True,
            "collected": False,
            "accepted_from_generic_continuation": False,
            "description": field_descriptions[field_id],
        }
        for field_id in APPROVAL_FIELD_IDS
    ]


def _scenario_approval_requirements(source_request: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for scenario_request in _sequence(source_request.get("scenario_authorization_requests")):
        if not isinstance(scenario_request, Mapping):
            continue
        requirements.append({
            "scenario_id": str(scenario_request.get("scenario_id", "")),
            "plan_class": str(scenario_request.get("plan_class", "")),
            "source_authorization_request_status": str(
                scenario_request.get("authorization_request_status", "")
            ),
            "approval_witness_required": True,
            "approval_witness_collected": False,
            "runtime_authorization_response_approved": False,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return requirements


def _validate_template_semantics(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    if template.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if template.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    for field_name, expected in (
        ("template_status", "TemplateNoEffect"),
        ("runtime_authorization_response_kind", APPROVAL_RESPONSE_KIND),
        ("expected_approval_decision_value", EXPECTED_APPROVAL_DECISION_VALUE),
        ("template_accepted_as_approval", False),
        ("approval_witness_collected", False),
        ("operator_response_recorded", False),
        ("operator_approval_collected", False),
        ("signed_approval_present", False),
        ("runtime_authorization_gate_satisfied", False),
        ("local_template_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("runtime_activation_allowed", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = template.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_source_request(template, errors, label)
    _validate_source_rejection(template, errors, label)
    _validate_controls(template, errors, label)
    _validate_required_fields(template, errors, label)
    _validate_scenario_requirements(template, errors, label)
    _validate_operator_boundary(template, errors, label)
    _validate_promotion_summary(template, errors, label)
    _validate_authority_denials(template, errors, label)


def _validate_source_request(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_request = _mapping(template.get("source_runtime_authorization_request"))
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
        errors.append(f"{label}: source runtime authorization request hash must be 64 characters")


def _validate_source_rejection(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_rejection = _mapping(template.get("source_generic_continuation_rejection"))
    for field_name, expected in (
        ("runtime_authorization_response_status", "RejectedNoEffect"),
        ("runtime_authorization_response_kind", REJECTION_RESPONSE_KIND),
        ("generic_continuation_rejected", True),
        ("signed_approval_present", False),
        ("runtime_authorization_gate_satisfied", False),
    ):
        if source_rejection.get(field_name) != expected:
            errors.append(f"{label}: source_generic_continuation_rejection.{field_name} must be {expected!r}")
    if not str(source_rejection.get("witness_id", "")).startswith(
        "governed-planning-profile-runtime-authorization-generic-continuation-rejection-"
    ):
        errors.append(f"{label}: source generic continuation rejection witness id mismatch")
    if len(str(source_rejection.get("witness_hash", ""))) != 64:
        errors.append(f"{label}: source generic continuation rejection hash must be 64 characters")


def _validate_controls(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(template.get("approval_template_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != APPROVAL_TEMPLATE_CONTROL_IDS:
        errors.append(f"{label}: approval template control ids mismatch")
    awaiting_ids = {"explicit_signed_approval_required"}
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: approval template control must be an object")
            continue
        control_id = str(control.get("control_id", ""))
        expected_status = "AwaitingEvidence" if control_id in awaiting_ids else "Pass"
        if control.get("status") != expected_status:
            errors.append(f"{label}: approval template control {control_id} status must be {expected_status}")
        if control.get("blocks_template_emission") is not False:
            errors.append(f"{label}: approval template control must not block template emission")


def _validate_required_fields(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    fields = _sequence(template.get("required_approval_fields"))
    observed_ids = tuple(str(field.get("field_id", "")) for field in fields if isinstance(field, Mapping))
    if observed_ids != APPROVAL_FIELD_IDS:
        errors.append(f"{label}: required approval field ids mismatch")
    for field in fields:
        if not isinstance(field, Mapping):
            errors.append(f"{label}: required approval field must be an object")
            continue
        field_id = str(field.get("field_id", ""))
        if field.get("required") is not True:
            errors.append(f"{label}: required approval field {field_id} required must be true")
        if field.get("collected") is not False:
            errors.append(f"{label}: required approval field {field_id} collected must be false")
        if field.get("accepted_from_generic_continuation") is not False:
            errors.append(
                f"{label}: required approval field {field_id} accepted_from_generic_continuation must be false"
            )


def _validate_scenario_requirements(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenario_requirements = _sequence(template.get("scenario_approval_requirements"))
    if len(scenario_requirements) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_approval_requirements must cover all expected plan classes")
        return
    observed_classes = []
    for scenario_requirement in scenario_requirements:
        if not isinstance(scenario_requirement, Mapping):
            errors.append(f"{label}: scenario approval requirement must be an object")
            continue
        observed_classes.append(str(scenario_requirement.get("plan_class", "")))
        for field_name, expected in (
            ("source_authorization_request_status", "SubmittedNoEffect"),
            ("approval_witness_required", True),
            ("approval_witness_collected", False),
            ("runtime_authorization_response_approved", False),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if scenario_requirement.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario approval requirement classes must match required order")


def _validate_operator_boundary(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(template.get("operator_approval_boundary"))
    for field_name, expected in (
        ("template_only", True),
        ("generic_continuation_satisfies_authorization", False),
        ("explicit_signed_approval_required", True),
        ("approval_witness_required", True),
        ("approval_witness_collected", False),
        ("future_approval_effect", "satisfies_runtime_authorization_response_gate_only"),
        ("runtime_activation_performed", False),
        ("runtime_activation_requires_separate_gate", True),
    ):
        if boundary.get(field_name) != expected:
            errors.append(f"{label}: operator_approval_boundary.{field_name} must be {expected!r}")


def _validate_promotion_summary(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(template.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != (
        "explicit_signed_runtime_authorization_approval_witness",
        "separate_runtime_activation_gate",
    ):
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    for field_name, expected in (
        ("approval_template_control_count", len(APPROVAL_TEMPLATE_CONTROL_IDS)),
        ("required_approval_field_count", len(APPROVAL_FIELD_IDS)),
        ("scenario_approval_requirement_count", len(EXPECTED_PLAN_CLASSES)),
        ("runtime_authorization_request_submitted", True),
        ("generic_continuation_rejection_recorded", True),
        ("approval_witness_collected", False),
        ("runtime_authorization_response_approved", False),
        ("runtime_promotion_authorized", False),
    ):
        if summary.get(field_name) != expected:
            errors.append(f"{label}: promotion_gate_summary.{field_name} must be {expected!r}")


def _validate_authority_denials(template: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(template.get("authority_denials"))
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


def _render_text(validation: ApprovalWitnessTemplateValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.approval_template_control_count}; "
            f"required_fields={validation.required_approval_field_count}; "
            f"scenarios={validation.scenario_approval_requirement_count}; "
            f"runtime_authorization_gate={validation.runtime_authorization_gate_satisfied}",
            file=stream,
        )
        print("NEXT: collect explicit signed runtime authorization approval witness", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Approval witness template to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_template = validate_approval_witness_template(template_path=args.template)
    if args.json:
        payload = validation.as_dict()
        payload["produced_template"] = produced_template
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
