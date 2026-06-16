#!/usr/bin/env python3
"""Validate Component Harness route-family promotion approval intake.

Purpose: prove blocked promotion approval candidates expose operator evidence
intake requests without approving promotion, mutating router inventory, or
granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: approval intake schema/example, runtime builder, and promotion
approval candidates validation.
Invariants:
  - Approval intake requests remain open, not submitted, and not approved.
  - Intake requests do not satisfy promotion requirements.
  - Intake requests cannot grant execution, connector, mutation, or terminal
    closure authority.
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

from mcoi_runtime.app.component_route_family_promotion_approval_intake import (  # noqa: E402
    build_component_route_family_promotion_approval_intake,
)
from scripts.validate_component_route_family_promotion_approval_candidates import (  # noqa: E402
    validate_component_route_family_promotion_approval_candidates,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_approval_intake.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT / "examples" / "component_route_family_promotion_approval_intake.governed_connector_framework.json"
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_promotion_approval_intake_validation.json"
TARGET_INTAKE_GATES = {
    "route_binding_gate",
    "lifecycle_gate",
    "authority_upgrade_gate",
    "product_specific_boundary_gate",
}
REQUIRED_APPROVAL_EVIDENCE = {
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "gmail_account_binding_evidence_receipt",
    "operator_approval_if_connector_action_requested",
    "operator_approval_if_external_effect",
    "product_specific_ownership_decision",
    "selected_component_bound_router_inventory_delta",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionApprovalIntakeValidation:
    """Schema and semantic validation report for promotion approval intake."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    intake_request_count: int
    submitted_evidence_count: int
    approval_artifact_requirement_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_approval_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionApprovalIntakeValidation:
    """Validate approval intake schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion approval intake schema", errors)
    example = _load_json_object(example_path, "component route-family promotion approval intake example", errors)

    candidates_validation = validate_component_route_family_promotion_approval_candidates()
    if not candidates_validation.ok:
        errors.extend(
            f"component route-family promotion approval candidates validation failed: {error}"
            for error in candidates_validation.errors
        )

    runtime_report = build_component_route_family_promotion_approval_intake()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_intake_semantics(example, errors, _path_label(example_path))
    _validate_intake_semantics(runtime_report, errors, "runtime component route-family promotion approval intake")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionApprovalIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        intake_request_count=int(summary.get("intake_request_count", 0)) if isinstance(summary, dict) else 0,
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        approval_artifact_requirement_count=(
            int(summary.get("approval_artifact_requirement_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_approval_intake_validation(
    validation: ComponentRouteFamilyPromotionApprovalIntakeValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic promotion approval intake validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_intake_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("intake_decision") != "awaiting_operator_evidence":
        errors.append(f"{label}: intake_decision must be awaiting_operator_evidence")
    if report.get("approval_intake_is_not_execution_authority") is not True:
        errors.append(f"{label}: approval intake must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if report.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    if report.get("target_surface_id") != "governed_connector_framework":
        errors.append(f"{label}: target_surface_id must remain governed_connector_framework")
    if report.get("target_component_id") != "gmail_account_binding_gate":
        errors.append(f"{label}: target_component_id must remain gmail_account_binding_gate")

    approval_requests = report.get("approval_requests")
    summary = report.get("summary")
    if not isinstance(approval_requests, list) or not approval_requests:
        errors.append(f"{label}: approval_requests must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    request_ids = [str(request.get("request_id")) for request in approval_requests if isinstance(request, dict)]
    if len(request_ids) != len(set(request_ids)):
        errors.append(f"{label}: request_ids must be unique")

    observed_gates: set[str] = set()
    open_count = 0
    not_submitted_count = 0
    submitted_count = 0
    required_operator_count = 0
    authority_grant_count = 0
    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")
    collected_required = set(reported_required)
    for request in approval_requests:
        if not isinstance(request, dict):
            errors.append(f"{label}: approval_requests entries must be objects")
            continue
        gate_id = str(request.get("gate_id", ""))
        observed_gates.add(gate_id)
        collected_required.update(_string_list(request.get("required_artifacts")))
        if request.get("intake_state") != "open":
            errors.append(f"{label}: request {gate_id} intake_state must be open")
        if request.get("approval_state") != "not_approved":
            errors.append(f"{label}: request {gate_id} approval_state must be not_approved")
        if request.get("evidence_submission_state") != "not_submitted":
            errors.append(f"{label}: request {gate_id} evidence_submission_state must be not_submitted")
        if request.get("proof_state") != "Unknown":
            errors.append(f"{label}: request {gate_id} proof_state must be Unknown")
        if request.get("operator_required") is not True:
            errors.append(f"{label}: request {gate_id} operator_required must be true")
        if request.get("blocks_promotion") is not True:
            errors.append(f"{label}: request {gate_id} must block promotion")
        if request.get("satisfies_requirement") is not False:
            errors.append(f"{label}: request {gate_id} must not satisfy requirement")
        if request.get("request_is_not_execution_authority") is not True:
            errors.append(f"{label}: request {gate_id} request_is_not_execution_authority must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if request.get(field_name) is not False:
                errors.append(f"{label}: request {gate_id} {field_name} must be false")
        if not request.get("required_artifacts"):
            errors.append(f"{label}: request {gate_id} must carry required_artifacts")
        if not request.get("acceptance_criteria"):
            errors.append(f"{label}: request {gate_id} must carry acceptance_criteria")
        if not request.get("rejection_conditions"):
            errors.append(f"{label}: request {gate_id} must carry rejection_conditions")
        refs = _string_list(request.get("submitted_evidence_refs"))
        if refs:
            errors.append(f"{label}: request {gate_id} submitted_evidence_refs must be empty until verifier exists")
        submitted_count += len(refs)
        if request.get("intake_state") == "open":
            open_count += 1
        if request.get("evidence_submission_state") == "not_submitted":
            not_submitted_count += 1
        if request.get("operator_required") is True:
            required_operator_count += 1
        if (
            request.get("grants_execution_authority") is True
            or request.get("grants_connector_authority") is True
            or request.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_INTAKE_GATES:
        errors.append(f"{label}: approval_requests must cover exactly {sorted(TARGET_INTAKE_GATES)}")
    if reported_required != collected_required:
        errors.append(f"{label}: approval_evidence_required must match request required_artifacts")

    expected_counts = {
        "intake_request_count": len(approval_requests),
        "open_request_count": open_count,
        "not_submitted_request_count": not_submitted_count,
        "submitted_evidence_count": submitted_count,
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "approval_artifact_requirement_count": len(reported_required),
        "required_operator_approval_count": required_operator_count,
        "authority_grant_count": authority_grant_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match approval intake")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_approval_intake_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_approval_candidates_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


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
    """Parse promotion approval intake validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness promotion approval intake.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for promotion approval intake validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_approval_intake(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_approval_intake_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION APPROVAL INTAKE VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
