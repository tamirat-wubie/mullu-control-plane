#!/usr/bin/env python3
"""Validate GovernedPlanningProfile runtime authorization request.

Purpose: emit and validate a local-only operator authorization request after
the GovernedPlanningProfile terminal closure certificate is collected.
Governance scope: OCE request completeness, RAG terminal certificate binding,
CDCV hash traceability, CQTE authority denial constraints, UWMA request
anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: terminal closure certificate validator, schema validator, and
canonical hashing.
Invariants:
  - The request asks for an operator response only; it does not authorize
    runtime promotion.
  - The request never grants execution, dispatch, replanning, success, or
    terminal closure authority.
  - Runtime promotion still requires a separate signed response witness.
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
from scripts.validate_governed_planning_profile_runtime_promotion_approval_packet import (  # noqa: E402
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
)
from scripts.validate_governed_planning_profile_terminal_closure_certificate import (  # noqa: E402
    SATISFIED_PROMOTION_GATE_IDS,
    build_terminal_closure_certificate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_runtime_authorization_request.v1"
REQUEST_ID_PREFIX = "governed-planning-profile-runtime-authorization-request"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "governed_planning_profile_runtime_authorization_request.schema.json"
DEFAULT_REQUEST = REPO_ROOT / "examples" / "governed_planning_profile_runtime_authorization_request.local.json"
AUTHORIZATION_CONTROL_IDS = (
    "source_terminal_closure_certificate_valid",
    "all_promotion_evidence_satisfied",
    "runtime_authorization_response_required",
    "signed_response_absent",
    "activation_separate_from_request",
    "authority_denials_preserved",
    "foundation_no_effect_boundary_preserved",
    "authorization_request_hash_bound",
)
ALLOWED_RESPONSE_KINDS = (
    "record_governed_planning_profile_runtime_authorization_approval_witness",
    "record_governed_planning_profile_runtime_authorization_rejection_witness",
)


@dataclass(frozen=True, slots=True)
class RuntimeAuthorizationRequestValidation:
    """Validation result for the planning-profile runtime authorization request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    request_path: str
    request_id: str
    source_terminal_closure_certificate_id: str
    authorization_control_count: int
    scenario_authorization_request_count: int
    remaining_promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_authorization_request(
    terminal_closure_certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local runtime authorization request."""

    current_certificate = dict(terminal_closure_certificate or build_terminal_closure_certificate())
    controls = tuple(_authorization_controls(current_certificate))
    scenario_requests = tuple(_scenario_authorization_requests(current_certificate))
    payload: dict[str, Any] = {
        "request_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_certificate.get("profile_id", "")),
        "requested_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "runtime_authorization_request_status": "SubmittedNoEffect",
        "runtime_authorization_request_submitted": True,
        "operator_response_required": True,
        "operator_response_collected": False,
        "runtime_authorization_response_ref": "unknown://governed-planning-profile/runtime-authorization-response",
        "runtime_authorization_gate_satisfied": False,
        "local_request_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_terminal_closure_certificate": {
            "certificate_id": str(current_certificate.get("certificate_id", "")),
            "certificate_hash": str(current_certificate.get("certificate_hash", "")),
            "terminal_closure_certificate_status": str(
                current_certificate.get("terminal_closure_certificate_status", "")
            ),
            "terminal_closure_gate_satisfied": bool(
                current_certificate.get("terminal_closure_gate_satisfied")
            ),
            "all_promotion_evidence_satisfied": bool(
                current_certificate.get("all_promotion_evidence_satisfied")
            ),
            "remaining_promotion_gate_count": len(
                _sequence(current_certificate.get("remaining_promotion_gates"))
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "authorization_controls": list(controls),
        "scenario_authorization_requests": list(scenario_requests),
        "operator_authorization_request": {
            "approver_role": "operator",
            "decision_required": "operator_response_required",
            "allowed_response_kinds": list(ALLOWED_RESPONSE_KINDS),
            "default_response_kind": (
                "record_governed_planning_profile_runtime_authorization_rejection_witness"
            ),
            "response_record_required": True,
            "response_record_collected": False,
            "approval_effect": "satisfies_runtime_authorization_response_gate_only",
            "runtime_promotion_authorized_after_response": False,
        },
        "request_boundary": {
            "source_terminal_closure_certificate_bound": True,
            "all_promotion_evidence_satisfied": True,
            "authorization_request_submitted": True,
            "authorization_response_required": True,
            "authorization_response_collected": False,
            "runtime_activation_performed": False,
            "terminal_closure_authority_granted": False,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [],
            "authorization_control_count": len(controls),
            "scenario_authorization_request_count": len(scenario_requests),
            "all_promotion_evidence_satisfied": True,
            "runtime_authorization_request_submitted": True,
            "runtime_promotion_authorized": False,
        },
        "remaining_promotion_gates": [],
        "authority_denials": {
            "runtime_promotion_authorized": False,
            "execution_allowed": False,
            "dispatch_allowed": False,
            "runtime_replanning_enabled": False,
            "success_claim_allowed": False,
            "terminal_closure": False,
        },
        "evidence_refs": [
            "scripts/validate_governed_planning_profile_terminal_closure_certificate.py",
            "scripts/validate_governed_planning_profile_runtime_authorization_request.py",
            "schemas/governed_planning_profile_runtime_authorization_request.schema.json",
            "examples/governed_planning_profile_runtime_authorization_request.local.json",
            "tests/test_validate_governed_planning_profile_runtime_authorization_request.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-runtime-authorization-request",
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_runtime_authorization_request.py"
                ),
            }
        ],
        "next_action": "record separate signed runtime authorization response witness before activation",
        "request_hash": "",
    }
    request_hash = canonical_hash(payload)
    payload["request_id"] = f"{REQUEST_ID_PREFIX}-{request_hash[:16]}"
    payload["request_hash"] = request_hash
    return payload


def validate_runtime_authorization_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    request_path: Path = DEFAULT_REQUEST,
) -> tuple[RuntimeAuthorizationRequestValidation, dict[str, Any]]:
    """Validate the checked-in authorization request and produced request."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "runtime authorization request schema", errors)
    request = _load_json_object(request_path, "runtime authorization request", errors)
    produced_request = build_runtime_authorization_request()
    if schema and request:
        errors.extend(
            f"{_path_label(request_path)}: {error}"
            for error in _validate_schema_instance(schema, request)
        )
        _validate_request_semantics(request, errors, _path_label(request_path))
    if schema:
        errors.extend(
            f"produced runtime authorization request: {error}"
            for error in _validate_schema_instance(schema, produced_request)
        )
        _validate_request_semantics(
            produced_request,
            errors,
            "produced runtime authorization request",
        )
    if request and request != produced_request:
        errors.append("runtime authorization request fixture does not match deterministic produced request")

    observed = request or produced_request
    validation = RuntimeAuthorizationRequestValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        request_path=_path_label(request_path),
        request_id=str(observed.get("request_id", "")),
        source_terminal_closure_certificate_id=str(
            _mapping(observed.get("source_terminal_closure_certificate")).get("certificate_id", "")
        ),
        authorization_control_count=len(_sequence(observed.get("authorization_controls"))),
        scenario_authorization_request_count=len(
            _sequence(observed.get("scenario_authorization_requests"))
        ),
        remaining_promotion_gate_count=len(_sequence(observed.get("remaining_promotion_gates"))),
    )
    return validation, produced_request


def _authorization_controls(certificate: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "source_terminal_closure_certificate_valid",
            "status": "Pass",
            "evidence_ref": str(certificate.get("certificate_id", "")),
            "blocks_request_submission": False,
        },
        {
            "control_id": "all_promotion_evidence_satisfied",
            "status": "Pass",
            "evidence_ref": "source_terminal_closure_certificate.promotion_gate_summary",
            "blocks_request_submission": False,
        },
        {
            "control_id": "runtime_authorization_response_required",
            "status": "AwaitingEvidence",
            "evidence_ref": "runtime_authorization_response_ref",
            "blocks_request_submission": False,
        },
        {
            "control_id": "signed_response_absent",
            "status": "AwaitingEvidence",
            "evidence_ref": "operator_authorization_request.response_record_collected",
            "blocks_request_submission": False,
        },
        {
            "control_id": "activation_separate_from_request",
            "status": "Pass",
            "evidence_ref": "request_boundary.runtime_activation_performed",
            "blocks_request_submission": False,
        },
        {
            "control_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_request_submission": False,
        },
        {
            "control_id": "foundation_no_effect_boundary_preserved",
            "status": "Pass",
            "evidence_ref": "local_request_only",
            "blocks_request_submission": False,
        },
        {
            "control_id": "authorization_request_hash_bound",
            "status": "Pass",
            "evidence_ref": "request_hash",
            "blocks_request_submission": False,
        },
    ]


def _scenario_authorization_requests(certificate: Mapping[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for scenario_closure in _sequence(certificate.get("scenario_terminal_closures")):
        if not isinstance(scenario_closure, Mapping):
            continue
        requests.append({
            "scenario_id": str(scenario_closure.get("scenario_id", "")),
            "plan_class": str(scenario_closure.get("plan_class", "")),
            "source_terminal_closure_status": str(
                scenario_closure.get("terminal_closure_status", "")
            ),
            "authorization_request_status": "SubmittedNoEffect",
            "runtime_authorization_response_required": True,
            "runtime_authorization_response_collected": False,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return requests


def _validate_request_semantics(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    if request.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if request.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    for field_name, expected in (
        ("runtime_authorization_request_status", "SubmittedNoEffect"),
        ("runtime_authorization_request_submitted", True),
        ("operator_response_required", True),
        ("operator_response_collected", False),
        ("runtime_authorization_gate_satisfied", False),
        ("local_request_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = request.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    if not str(request.get("runtime_authorization_response_ref", "")).startswith("unknown://"):
        errors.append(f"{label}: runtime_authorization_response_ref must remain unknown")
    source_certificate = _mapping(request.get("source_terminal_closure_certificate"))
    if source_certificate.get("terminal_closure_certificate_status") != "CollectedNoEffect":
        errors.append(f"{label}: source terminal closure certificate status must be CollectedNoEffect")
    if source_certificate.get("terminal_closure_gate_satisfied") is not True:
        errors.append(f"{label}: source terminal closure gate must be satisfied")
    if source_certificate.get("all_promotion_evidence_satisfied") is not True:
        errors.append(f"{label}: source promotion evidence must be satisfied")
    if source_certificate.get("remaining_promotion_gate_count") != 0:
        errors.append(f"{label}: source remaining promotion gate count must be 0")
    observed_classes = tuple(request.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_authorization_controls(request, errors, label)
    _validate_scenario_authorization_requests(request, errors, label)
    _validate_operator_authorization_request(request, errors, label)
    _validate_request_boundary(request, errors, label)
    _validate_promotion_gate_summary(request, errors, label)
    _validate_authority_denials(request, errors, label)


def _validate_authorization_controls(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(request.get("authorization_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != AUTHORIZATION_CONTROL_IDS:
        errors.append(f"{label}: authorization control ids mismatch")
    awaiting_ids = {"runtime_authorization_response_required", "signed_response_absent"}
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: authorization control must be an object")
            continue
        control_id = str(control.get("control_id", ""))
        expected_status = "AwaitingEvidence" if control_id in awaiting_ids else "Pass"
        if control.get("status") != expected_status:
            errors.append(f"{label}: authorization control {control_id} status must be {expected_status}")
        if control.get("blocks_request_submission") is not False:
            errors.append(f"{label}: authorization control must not block request submission")


def _validate_scenario_authorization_requests(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenario_requests = _sequence(request.get("scenario_authorization_requests"))
    if len(scenario_requests) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_authorization_requests must cover all expected plan classes")
        return
    observed_classes = []
    for scenario_request in scenario_requests:
        if not isinstance(scenario_request, Mapping):
            errors.append(f"{label}: scenario authorization request must be an object")
            continue
        observed_classes.append(str(scenario_request.get("plan_class", "")))
        for field_name, expected in (
            ("source_terminal_closure_status", "ClosedNoEffect"),
            ("authorization_request_status", "SubmittedNoEffect"),
            ("runtime_authorization_response_required", True),
            ("runtime_authorization_response_collected", False),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if scenario_request.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario authorization request classes must match required order")


def _validate_operator_authorization_request(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    operator_request = _mapping(request.get("operator_authorization_request"))
    if operator_request.get("approver_role") != "operator":
        errors.append(f"{label}: operator_authorization_request.approver_role must be operator")
    if operator_request.get("decision_required") != "operator_response_required":
        errors.append(f"{label}: operator_authorization_request.decision_required mismatch")
    if tuple(operator_request.get("allowed_response_kinds", ())) != ALLOWED_RESPONSE_KINDS:
        errors.append(f"{label}: operator_authorization_request.allowed_response_kinds mismatch")
    if operator_request.get("default_response_kind") != ALLOWED_RESPONSE_KINDS[1]:
        errors.append(f"{label}: operator_authorization_request.default_response_kind must reject by default")
    if operator_request.get("response_record_required") is not True:
        errors.append(f"{label}: operator_authorization_request.response_record_required must be true")
    if operator_request.get("response_record_collected") is not False:
        errors.append(f"{label}: operator_authorization_request.response_record_collected must be false")
    if operator_request.get("approval_effect") != "satisfies_runtime_authorization_response_gate_only":
        errors.append(f"{label}: operator_authorization_request.approval_effect must be gate-only")
    if operator_request.get("runtime_promotion_authorized_after_response") is not False:
        errors.append(
            f"{label}: operator_authorization_request.runtime_promotion_authorized_after_response must be false"
        )


def _validate_request_boundary(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(request.get("request_boundary"))
    for field_name in (
        "source_terminal_closure_certificate_bound",
        "all_promotion_evidence_satisfied",
        "authorization_request_submitted",
        "authorization_response_required",
    ):
        if boundary.get(field_name) is not True:
            errors.append(f"{label}: request_boundary.{field_name} must be true")
    for field_name in (
        "authorization_response_collected",
        "runtime_activation_performed",
        "terminal_closure_authority_granted",
    ):
        if boundary.get(field_name) is not False:
            errors.append(f"{label}: request_boundary.{field_name} must be false")


def _validate_promotion_gate_summary(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(request.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != ():
        errors.append(f"{label}: remaining promotion gate ids must be empty")
    if summary.get("authorization_control_count") != len(AUTHORIZATION_CONTROL_IDS):
        errors.append(f"{label}: promotion_gate_summary.authorization_control_count mismatch")
    if summary.get("scenario_authorization_request_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: promotion_gate_summary.scenario_authorization_request_count mismatch")
    if summary.get("all_promotion_evidence_satisfied") is not True:
        errors.append(f"{label}: promotion_gate_summary.all_promotion_evidence_satisfied must be true")
    if summary.get("runtime_authorization_request_submitted") is not True:
        errors.append(f"{label}: promotion_gate_summary.runtime_authorization_request_submitted must be true")
    if summary.get("runtime_promotion_authorized") is not False:
        errors.append(f"{label}: promotion_gate_summary.runtime_promotion_authorized must be false")
    if _sequence(request.get("remaining_promotion_gates")):
        errors.append(f"{label}: remaining_promotion_gates must be empty")


def _validate_authority_denials(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(request.get("authority_denials"))
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


def _render_text(validation: RuntimeAuthorizationRequestValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.authorization_control_count}; "
            f"scenarios={validation.scenario_authorization_request_count}; "
            f"remaining_promotion_gates={validation.remaining_promotion_gate_count}",
            file=stream,
        )
        print("NEXT: record separate signed runtime authorization response witness", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument(
        "--request",
        type=Path,
        default=DEFAULT_REQUEST,
        help="Runtime authorization request to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_request = validate_runtime_authorization_request(request_path=args.request)
    if args.json:
        payload = validation.as_dict()
        payload["produced_request"] = produced_request
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
