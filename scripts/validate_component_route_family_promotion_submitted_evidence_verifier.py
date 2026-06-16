#!/usr/bin/env python3
"""Validate Component Harness promotion submitted-evidence verifier.

Purpose: prove blocked promotion intake requests remain awaiting submitted
evidence without approving promotion, mutating router inventory, or granting
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: submitted-evidence verifier schema/example, runtime builder, and
promotion approval intake validation.
Invariants:
  - Submitted-evidence verifier requests remain awaiting submitted evidence.
  - Missing submitted evidence keeps promotion requirements unsatisfied.
  - Verifier requests cannot grant execution, connector, mutation, or terminal
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

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_verifier import (  # noqa: E402
    build_component_route_family_promotion_submitted_evidence_verifier,
)
from scripts.validate_component_route_family_promotion_approval_intake import (  # noqa: E402
    validate_component_route_family_promotion_approval_intake,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_submitted_evidence_verifier.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_submitted_evidence_verifier.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "component_route_family_promotion_submitted_evidence_verifier_validation.json"
)
TARGET_VERIFIER_GATES = {
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
class ComponentRouteFamilyPromotionSubmittedEvidenceVerifierValidation:
    """Schema and semantic validation report for submitted-evidence verifier."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    verification_request_count: int
    submitted_evidence_count: int
    accepted_evidence_count: int
    rejected_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_submitted_evidence_verifier(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionSubmittedEvidenceVerifierValidation:
    """Validate submitted-evidence verifier schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion submitted-evidence verifier schema", errors)
    example = _load_json_object(
        example_path,
        "component route-family promotion submitted-evidence verifier example",
        errors,
    )

    intake_validation = validate_component_route_family_promotion_approval_intake()
    if not intake_validation.ok:
        errors.extend(
            f"component route-family promotion approval intake validation failed: {error}"
            for error in intake_validation.errors
        )

    runtime_report = build_component_route_family_promotion_submitted_evidence_verifier()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_verifier_semantics(example, errors, _path_label(example_path))
    _validate_verifier_semantics(runtime_report, errors, "runtime component route-family promotion verifier")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionSubmittedEvidenceVerifierValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        verification_request_count=int(summary.get("verification_request_count", 0)) if isinstance(summary, dict) else 0,
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        rejected_evidence_count=int(summary.get("rejected_evidence_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_submitted_evidence_verifier_validation(
    validation: ComponentRouteFamilyPromotionSubmittedEvidenceVerifierValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic submitted-evidence verifier validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_verifier_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("verifier_decision") != "awaiting_submitted_evidence":
        errors.append(f"{label}: verifier_decision must be awaiting_submitted_evidence")
    if report.get("submitted_evidence_verifier_is_not_execution_authority") is not True:
        errors.append(f"{label}: submitted-evidence verifier must not be execution authority")
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
    for field_name in ("submitted_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must be empty until submitted evidence records exist")

    verification_requests = report.get("verification_requests")
    summary = report.get("summary")
    if not isinstance(verification_requests, list) or not verification_requests:
        errors.append(f"{label}: verification_requests must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    request_ids = [
        str(request.get("verifier_request_id"))
        for request in verification_requests
        if isinstance(request, dict)
    ]
    if len(request_ids) != len(set(request_ids)):
        errors.append(f"{label}: verifier_request_ids must be unique")

    observed_gates: set[str] = set()
    awaiting_count = 0
    not_verified_count = 0
    submitted_count = 0
    accepted_count = 0
    rejected_count = 0
    satisfied_count = 0
    blocking_count = 0
    authority_grant_count = 0
    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")
    collected_required = set(reported_required)
    for request in verification_requests:
        if not isinstance(request, dict):
            errors.append(f"{label}: verification_requests entries must be objects")
            continue
        gate_id = str(request.get("gate_id", ""))
        observed_gates.add(gate_id)
        collected_required.update(_string_list(request.get("required_artifacts")))
        if request.get("intake_state") != "open":
            errors.append(f"{label}: request {gate_id} intake_state must be open")
        if request.get("evidence_submission_state") != "not_submitted":
            errors.append(f"{label}: request {gate_id} evidence_submission_state must be not_submitted")
        if request.get("verifier_state") != "awaiting_submitted_evidence":
            errors.append(f"{label}: request {gate_id} verifier_state must be awaiting_submitted_evidence")
        if request.get("verification_state") != "not_verified":
            errors.append(f"{label}: request {gate_id} verification_state must be not_verified")
        if request.get("proof_state") != "Unknown":
            errors.append(f"{label}: request {gate_id} proof_state must be Unknown")
        if request.get("blocks_promotion") is not True:
            errors.append(f"{label}: request {gate_id} must block promotion")
        if request.get("satisfies_requirement") is not False:
            errors.append(f"{label}: request {gate_id} must not satisfy requirement")
        if request.get("verifier_is_not_execution_authority") is not True:
            errors.append(f"{label}: request {gate_id} verifier_is_not_execution_authority must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if request.get(field_name) is not False:
                errors.append(f"{label}: request {gate_id} {field_name} must be false")
        for field_name in ("required_artifacts", "verification_criteria", "rejection_conditions"):
            if not request.get(field_name):
                errors.append(f"{label}: request {gate_id} must carry {field_name}")
        refs_by_field = {
            "submitted_evidence_refs": _string_list(request.get("submitted_evidence_refs")),
            "accepted_evidence_refs": _string_list(request.get("accepted_evidence_refs")),
            "rejected_evidence_refs": _string_list(request.get("rejected_evidence_refs")),
        }
        for field_name, refs in refs_by_field.items():
            if refs:
                errors.append(f"{label}: request {gate_id} {field_name} must be empty until records exist")
        if not request.get("missing_submission_reason"):
            errors.append(f"{label}: request {gate_id} must carry missing_submission_reason")
        submitted_count += len(refs_by_field["submitted_evidence_refs"])
        accepted_count += len(refs_by_field["accepted_evidence_refs"])
        rejected_count += len(refs_by_field["rejected_evidence_refs"])
        if request.get("verifier_state") == "awaiting_submitted_evidence":
            awaiting_count += 1
        if request.get("verification_state") == "not_verified":
            not_verified_count += 1
        if request.get("satisfies_requirement") is True:
            satisfied_count += 1
        if request.get("blocks_promotion") is True:
            blocking_count += 1
        if (
            request.get("grants_execution_authority") is True
            or request.get("grants_connector_authority") is True
            or request.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_VERIFIER_GATES:
        errors.append(f"{label}: verification_requests must cover exactly {sorted(TARGET_VERIFIER_GATES)}")
    if reported_required != collected_required:
        errors.append(f"{label}: approval_evidence_required must match request required_artifacts")

    expected_counts = {
        "verification_request_count": len(verification_requests),
        "awaiting_submitted_evidence_count": awaiting_count,
        "not_verified_request_count": not_verified_count,
        "submitted_evidence_count": submitted_count,
        "accepted_evidence_count": accepted_count,
        "rejected_evidence_count": rejected_count,
        "satisfied_requirement_count": satisfied_count,
        "blocking_request_count": blocking_count,
        "approval_artifact_requirement_count": len(reported_required),
        "authority_grant_count": authority_grant_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match submitted-evidence verifier")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_approval_intake_receipt",
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
    """Parse submitted-evidence verifier validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness submitted-evidence verifier.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for submitted-evidence verifier validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_submitted_evidence_verifier(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_submitted_evidence_verifier_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION SUBMITTED EVIDENCE VERIFIER VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
