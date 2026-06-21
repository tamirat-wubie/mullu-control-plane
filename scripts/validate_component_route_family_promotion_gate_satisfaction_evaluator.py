#!/usr/bin/env python3
"""Validate Component Harness promotion gate-satisfaction evaluator reports.

Purpose: prove accepted record-only evidence can satisfy evidence gates without
approving route-family promotion, mutating router inventory, or granting
execution, connector, mutation, or terminal-closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gate-satisfaction evaluator schema/example, runtime builder, and
operator-submitted evidence records validation.
Invariants:
  - Record-evidence gate satisfaction is not promotion authority.
  - Action gates remain unsatisfied until separate authority decisions exist.
  - Gate satisfaction cannot mutate router inventory or claim terminal closure.
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

from mcoi_runtime.app.component_route_family_promotion_gate_satisfaction_evaluator import (  # noqa: E402
    build_component_route_family_promotion_gate_satisfaction_evaluator,
)
from scripts.validate_component_route_family_promotion_operator_submitted_evidence_records import (  # noqa: E402
    validate_component_route_family_promotion_operator_submitted_evidence_records,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_gate_satisfaction_evaluator.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_gate_satisfaction_evaluator.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_gate_satisfaction_evaluator_validation.json"
)
TARGET_GATES = {
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
class ComponentRouteFamilyPromotionGateSatisfactionEvaluatorValidation:
    """Schema and semantic validation report for gate-satisfaction evaluator reports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    gate_evaluation_count: int
    record_evidence_satisfied_gate_count: int
    action_satisfied_gate_count: int
    authority_decision_count: int
    authority_grant_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_gate_satisfaction_evaluator(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
    validate_dependencies: bool = False,
) -> ComponentRouteFamilyPromotionGateSatisfactionEvaluatorValidation:
    """Validate gate-satisfaction evaluator schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion gate-satisfaction schema", errors)
    example = _load_json_object(example_path, "component route-family promotion gate-satisfaction example", errors)

    if validate_dependencies:
        operator_records_validation = validate_component_route_family_promotion_operator_submitted_evidence_records()
        if not operator_records_validation.ok:
            errors.extend(
                f"component route-family promotion operator-submitted evidence records validation failed: {error}"
                for error in operator_records_validation.errors
            )

    runtime_report = build_component_route_family_promotion_gate_satisfaction_evaluator()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_gate_satisfaction_semantics(example, errors, _path_label(example_path))
    _validate_gate_satisfaction_semantics(runtime_report, errors, "runtime component route-family promotion gate satisfaction")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionGateSatisfactionEvaluatorValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        gate_evaluation_count=int(summary.get("gate_evaluation_count", 0)) if isinstance(summary, dict) else 0,
        record_evidence_satisfied_gate_count=(
            int(summary.get("record_evidence_satisfied_gate_count", 0)) if isinstance(summary, dict) else 0
        ),
        action_satisfied_gate_count=int(summary.get("action_satisfied_gate_count", 0)) if isinstance(summary, dict) else 0,
        authority_decision_count=int(summary.get("authority_decision_count", 0)) if isinstance(summary, dict) else 0,
        authority_grant_count=int(summary.get("authority_grant_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_gate_satisfaction_evaluator_validation(
    validation: ComponentRouteFamilyPromotionGateSatisfactionEvaluatorValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic gate-satisfaction evaluator validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_gate_satisfaction_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("gate_satisfaction_decision") != "record_evidence_satisfied_authority_pending":
        errors.append(f"{label}: gate_satisfaction_decision must be record_evidence_satisfied_authority_pending")
    if report.get("promotion_decision") != "blocked_pending_authority_decision":
        errors.append(f"{label}: promotion_decision must be blocked_pending_authority_decision")
    if report.get("all_record_evidence_gates_satisfied") is not True:
        errors.append(f"{label}: all_record_evidence_gates_satisfied must be true")
    if report.get("all_action_gates_satisfied") is not False:
        errors.append(f"{label}: all_action_gates_satisfied must be false")
    if report.get("authority_fuse_enforced") is not True:
        errors.append(f"{label}: authority_fuse_enforced must be true")
    for field_name in (
        "gate_satisfaction_is_not_execution_authority",
        "gate_satisfaction_is_not_promotion_authority",
        "foundation_fixture_gate_satisfaction_is_not_live_operator_evidence",
        "separate_authority_decision_required",
        "separate_route_binding_decision_required",
        "separate_lifecycle_transition_required",
        "terminal_closure_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
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
    if report.get("target_surface_id") != "governed_connector_framework":
        errors.append(f"{label}: target_surface_id must remain governed_connector_framework")
    if report.get("target_component_id") != "gmail_account_binding_gate":
        errors.append(f"{label}: target_component_id must remain gmail_account_binding_gate")
    for field_name in (
        "rejected_record_refs",
        "authority_decision_refs",
        "promotion_approval_refs",
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until authority decision exists")

    evaluations = report.get("gate_evaluations")
    summary = report.get("summary")
    if not isinstance(evaluations, list) or not evaluations:
        errors.append(f"{label}: gate_evaluations must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    evaluation_ids = [
        str(evaluation.get("gate_evaluation_id"))
        for evaluation in evaluations
        if isinstance(evaluation, dict)
    ]
    accepted_record_ids = [
        str(evaluation.get("source_operator_submitted_record_id"))
        for evaluation in evaluations
        if isinstance(evaluation, dict)
    ]
    if len(evaluation_ids) != len(set(evaluation_ids)):
        errors.append(f"{label}: gate_evaluation_ids must be unique")
    if set(_string_list(report.get("satisfied_gate_evaluation_refs"))) != set(evaluation_ids):
        errors.append(f"{label}: satisfied_gate_evaluation_refs must match gate_evaluation_ids")
    if set(_string_list(report.get("accepted_record_refs"))) != set(accepted_record_ids):
        errors.append(f"{label}: accepted_record_refs must match source operator record ids")
    authority_fuse_refs = _string_list(report.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        errors.append(f"{label}: authority_fuse_refs must contain exactly one target component fuse")
    if _string_list(report.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: authority_fuse_blocking_refs must match authority_fuse_refs")

    observed_gates: set[str] = set()
    evaluated_count = 0
    record_satisfied_count = 0
    action_satisfied_count = 0
    blocking_count = 0
    accepted_record_count = 0
    rejected_record_count = 0
    evidence_requirement_count = 0
    action_requirement_count = 0
    authority_decision_count = 0
    promotion_approval_count = 0
    accepted_evidence_count = 0
    rejected_evidence_count = 0
    authority_grant_count = 0
    gate_authority_fuse_refs: set[str] = set()
    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")

    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            errors.append(f"{label}: gate_evaluations entries must be objects")
            continue
        gate_id = str(evaluation.get("gate_id", ""))
        observed_gates.add(gate_id)
        _validate_gate_evaluation(evaluation, errors, label, gate_id)
        if evaluation.get("evaluation_state") == "evaluated":
            evaluated_count += 1
        if evaluation.get("record_evidence_satisfies_gate") is True:
            record_satisfied_count += 1
        if evaluation.get("satisfies_action_requirement") is True:
            action_satisfied_count += 1
        if evaluation.get("blocks_promotion") is True:
            blocking_count += 1
        accepted_record_count += len(_string_list(evaluation.get("accepted_record_refs")))
        rejected_record_count += 0
        if evaluation.get("satisfies_evidence_requirement") is True:
            evidence_requirement_count += 1
        if evaluation.get("satisfies_action_requirement") is True:
            action_requirement_count += 1
        authority_decision_count += len(_string_list(evaluation.get("authority_decision_refs")))
        gate_authority_fuse_refs.update(_string_list(evaluation.get("authority_fuse_refs")))
        promotion_approval_count += len(_string_list(evaluation.get("promotion_approval_refs")))
        accepted_evidence_count += len(_string_list(evaluation.get("accepted_evidence_refs")))
        rejected_evidence_count += len(_string_list(evaluation.get("rejected_evidence_refs")))
        if (
            evaluation.get("grants_execution_authority") is True
            or evaluation.get("grants_connector_authority") is True
            or evaluation.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_GATES:
        errors.append(f"{label}: gate_evaluations must cover exactly {sorted(TARGET_GATES)}")
    if gate_authority_fuse_refs != set(authority_fuse_refs):
        errors.append(f"{label}: every gate evaluation must reference the target authority fuse")

    expected_counts = {
        "gate_evaluation_count": len(evaluations),
        "evaluated_gate_count": evaluated_count,
        "record_evidence_satisfied_gate_count": record_satisfied_count,
        "action_satisfied_gate_count": action_satisfied_count,
        "blocking_gate_count": blocking_count,
        "accepted_record_count": accepted_record_count,
        "rejected_record_count": rejected_record_count,
        "satisfied_evidence_requirement_count": evidence_requirement_count,
        "satisfied_action_requirement_count": action_requirement_count,
        "authority_decision_count": authority_decision_count,
        "promotion_approval_count": promotion_approval_count,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": rejected_evidence_count,
        "approval_artifact_requirement_count": len(reported_required),
        "authority_grant_count": authority_grant_count,
        "authority_fuse_blocking_count": len(authority_fuse_refs),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match gate satisfaction evaluations")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_approval_intake_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


def _validate_gate_evaluation(evaluation: dict[str, Any], errors: list[str], label: str, gate_id: str) -> None:
    expected_values = {
        "evaluation_state": "evaluated",
        "satisfaction_state": "satisfied_record_only",
        "proof_state": "Pass",
        "record_acceptance_state": "accepted_record_only",
        "record_proof_state": "Pass",
    }
    for field_name, expected_value in expected_values.items():
        if evaluation.get(field_name) != expected_value:
            errors.append(f"{label}: gate {gate_id} {field_name} must be {expected_value}")
    for field_name in (
        "record_evidence_satisfies_gate",
        "satisfies_evidence_requirement",
        "blocks_promotion",
        "requires_separate_authority_decision",
        "requires_external_authority_upgrade_evidence",
        "authority_fuse_blocks_promotion",
        "requires_route_binding_decision",
        "requires_lifecycle_transition",
        "requires_terminal_closure",
        "gate_satisfaction_is_not_execution_authority",
        "gate_satisfaction_is_not_promotion_authority",
        "foundation_fixture_gate_satisfaction_is_not_live_operator_evidence",
    ):
        if evaluation.get(field_name) is not True:
            errors.append(f"{label}: gate {gate_id} {field_name} must be true")
    for field_name in (
        "satisfies_action_requirement",
        "mutates_router_inventory",
        "grants_execution_authority",
        "grants_connector_authority",
        "grants_terminal_closure",
    ):
        if evaluation.get(field_name) is not False:
            errors.append(f"{label}: gate {gate_id} {field_name} must be false")
    accepted_record_refs = _string_list(evaluation.get("accepted_record_refs"))
    if accepted_record_refs != [str(evaluation.get("source_operator_submitted_record_id"))]:
        errors.append(f"{label}: gate {gate_id} accepted_record_refs must contain only the source record id")
    if len(_string_list(evaluation.get("authority_fuse_refs"))) != 1:
        errors.append(f"{label}: gate {gate_id} authority_fuse_refs must contain exactly one authority fuse")
    for field_name in (
        "authority_decision_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(evaluation.get(field_name)):
            errors.append(f"{label}: gate {gate_id} {field_name} must remain empty until authority decision exists")
    if not evaluation.get("blocking_reason"):
        errors.append(f"{label}: gate {gate_id} must carry blocking_reason")


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
    """Parse gate-satisfaction evaluator validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness gate-satisfaction evaluator.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for gate-satisfaction evaluator validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
        validate_dependencies=args.strict,
    )
    write_component_route_family_promotion_gate_satisfaction_evaluator_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION GATE SATISFACTION EVALUATOR VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
