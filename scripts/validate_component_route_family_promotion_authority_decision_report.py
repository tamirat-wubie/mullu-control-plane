#!/usr/bin/env python3
"""Validate Component Harness promotion authority decision reports.

Purpose: prove gate-satisfaction evidence can be consumed by authority
decision records while every authority decision remains denial-only and no
route binding, lifecycle transition, connector action, mutation, or terminal
closure is granted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: authority-decision report schema/example, runtime builder, and
gate-satisfaction evaluator validation.
Invariants:
  - Denial-only authority decisions are not authority grants.
  - Record-evidence gate satisfaction is not action-gate satisfaction.
  - Authority decision reports cannot approve promotion or mutate router
    inventory.
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

from mcoi_runtime.app.component_route_family_promotion_authority_decision_report import (  # noqa: E402
    build_component_route_family_promotion_authority_decision_report,
)
from scripts.validate_component_route_family_promotion_gate_satisfaction_evaluator import (  # noqa: E402
    validate_component_route_family_promotion_gate_satisfaction_evaluator,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_authority_decision_report.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_authority_decision_report.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_authority_decision_report_validation.json"
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
REQUIRED_FOLLOWUP_DECISIONS = {
    "component_route_binding_decision",
    "component_lifecycle_transition_decision",
    "authority_upgrade_witness_decision",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
}
MISSING_AUTHORITY_WITNESSES = {
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "terminal_closure_certificate",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionAuthorityDecisionReportValidation:
    """Schema and semantic validation report for authority decision reports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    authority_decision_count: int
    authority_denial_count: int
    authority_grant_count: int
    promotion_approval_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_authority_decision_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionAuthorityDecisionReportValidation:
    """Validate authority decision report schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion authority decision schema", errors)
    example = _load_json_object(example_path, "component route-family promotion authority decision example", errors)

    gate_satisfaction_validation = validate_component_route_family_promotion_gate_satisfaction_evaluator()
    if not gate_satisfaction_validation.ok:
        errors.extend(
            f"component route-family promotion gate-satisfaction evaluator validation failed: {error}"
            for error in gate_satisfaction_validation.errors
        )

    runtime_report = build_component_route_family_promotion_authority_decision_report()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_authority_decision_semantics(example, errors, _path_label(example_path))
    _validate_authority_decision_semantics(runtime_report, errors, "runtime component route-family promotion authority decision")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionAuthorityDecisionReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        authority_decision_count=int(summary.get("authority_decision_count", 0)) if isinstance(summary, dict) else 0,
        authority_denial_count=int(summary.get("authority_denial_count", 0)) if isinstance(summary, dict) else 0,
        authority_grant_count=int(summary.get("authority_grant_count", 0)) if isinstance(summary, dict) else 0,
        promotion_approval_count=int(summary.get("promotion_approval_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_authority_decision_report_validation(
    validation: ComponentRouteFamilyPromotionAuthorityDecisionReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic authority decision report validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_authority_decision_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("authority_decision_state") != "denied_pending_governed_witnesses":
        errors.append(f"{label}: authority_decision_state must be denied_pending_governed_witnesses")
    if report.get("promotion_decision") != "blocked_authority_not_granted":
        errors.append(f"{label}: promotion_decision must be blocked_authority_not_granted")
    if report.get("all_record_evidence_gates_satisfied") is not True:
        errors.append(f"{label}: all_record_evidence_gates_satisfied must be true")
    if report.get("all_action_gates_satisfied") is not False:
        errors.append(f"{label}: all_action_gates_satisfied must be false")
    for field_name in (
        "all_authority_decisions_issued",
        "all_authority_decisions_denied",
        "all_authority_grants_blocked",
        "all_required_followup_decisions_pending",
        "authority_decision_is_not_authority_grant",
        "authority_decision_is_not_promotion_approval",
        "authority_decision_is_not_route_binding",
        "authority_decision_is_not_lifecycle_transition",
        "foundation_fixture_decision_is_not_live_operator_evidence",
        "separate_route_binding_decision_required",
        "separate_lifecycle_transition_required",
        "separate_authority_upgrade_witness_required",
        "separate_product_ownership_decision_required",
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
        "authority_grant_refs",
        "promotion_approval_refs",
        "route_binding_decision_refs",
        "lifecycle_transition_refs",
        "terminal_closure_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate authority evidence exists")

    authority_decisions = report.get("authority_decisions")
    summary = report.get("summary")
    if not isinstance(authority_decisions, list) or not authority_decisions:
        errors.append(f"{label}: authority_decisions must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    decision_ids = [
        str(authority_decision.get("authority_decision_id"))
        for authority_decision in authority_decisions
        if isinstance(authority_decision, dict)
    ]
    source_gate_ids = [
        str(authority_decision.get("source_gate_evaluation_id"))
        for authority_decision in authority_decisions
        if isinstance(authority_decision, dict)
    ]
    accepted_record_ids = [
        str(authority_decision.get("source_operator_submitted_record_id"))
        for authority_decision in authority_decisions
        if isinstance(authority_decision, dict)
    ]
    if len(decision_ids) != len(set(decision_ids)):
        errors.append(f"{label}: authority_decision_ids must be unique")
    if set(_string_list(report.get("authority_decision_refs"))) != set(decision_ids):
        errors.append(f"{label}: authority_decision_refs must match authority_decision_ids")
    if set(_string_list(report.get("satisfied_gate_evaluation_refs"))) != set(source_gate_ids):
        errors.append(f"{label}: satisfied_gate_evaluation_refs must match source gate evaluation ids")
    if set(_string_list(report.get("accepted_record_refs"))) != set(accepted_record_ids):
        errors.append(f"{label}: accepted_record_refs must match source operator record ids")

    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    required_followups = set(_string_list(report.get("required_followup_decisions")))
    missing_witnesses = set(_string_list(report.get("missing_authority_witnesses")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")
    if required_followups != REQUIRED_FOLLOWUP_DECISIONS:
        errors.append(f"{label}: required_followup_decisions must match denied authority follow-up set")
    if missing_witnesses != MISSING_AUTHORITY_WITNESSES:
        errors.append(f"{label}: missing_authority_witnesses must match denied authority witness set")

    observed_gates: set[str] = set()
    authority_denial_count = 0
    authority_grant_count = 0
    record_evidence_satisfied_gate_count = 0
    action_satisfied_gate_count = 0
    blocking_decision_count = 0
    route_binding_authorization_count = 0
    lifecycle_transition_authorization_count = 0
    connector_authorization_count = 0
    terminal_closure_authorization_count = 0
    promotion_approval_count = 0
    accepted_evidence_count = 0
    rejected_evidence_count = 0
    accepted_record_count = 0
    for authority_decision in authority_decisions:
        if not isinstance(authority_decision, dict):
            errors.append(f"{label}: authority_decisions entries must be objects")
            continue
        gate_id = str(authority_decision.get("gate_id", ""))
        observed_gates.add(gate_id)
        _validate_authority_decision(authority_decision, errors, label, gate_id)
        if authority_decision.get("decision_state") == "denied":
            authority_denial_count += 1
        if authority_decision.get("authority_granted") is True:
            authority_grant_count += 1
        if authority_decision.get("record_evidence_satisfied") is True:
            record_evidence_satisfied_gate_count += 1
        if authority_decision.get("action_requirement_satisfied") is True:
            action_satisfied_gate_count += 1
        if authority_decision.get("blocks_promotion") is True:
            blocking_decision_count += 1
        if authority_decision.get("route_binding_authorized") is True:
            route_binding_authorization_count += 1
        if authority_decision.get("lifecycle_transition_authorized") is True:
            lifecycle_transition_authorization_count += 1
        if authority_decision.get("connector_authority_authorized") is True:
            connector_authorization_count += 1
        if authority_decision.get("terminal_closure_authorized") is True:
            terminal_closure_authorization_count += 1
        promotion_approval_count += len(_string_list(authority_decision.get("promotion_approval_refs")))
        accepted_evidence_count += len(_string_list(authority_decision.get("accepted_evidence_refs")))
        rejected_evidence_count += len(_string_list(authority_decision.get("rejected_evidence_refs")))
        accepted_record_count += len(_string_list(authority_decision.get("accepted_record_refs")))

    if observed_gates != TARGET_GATES:
        errors.append(f"{label}: authority_decisions must cover exactly {sorted(TARGET_GATES)}")

    expected_counts = {
        "authority_decision_count": len(authority_decisions),
        "authority_denial_count": authority_denial_count,
        "authority_grant_count": authority_grant_count,
        "record_evidence_satisfied_gate_count": record_evidence_satisfied_gate_count,
        "action_satisfied_gate_count": action_satisfied_gate_count,
        "blocking_decision_count": blocking_decision_count,
        "route_binding_authorization_count": route_binding_authorization_count,
        "lifecycle_transition_authorization_count": lifecycle_transition_authorization_count,
        "connector_authorization_count": connector_authorization_count,
        "terminal_closure_authorization_count": terminal_closure_authorization_count,
        "promotion_approval_count": promotion_approval_count,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": rejected_evidence_count,
        "accepted_record_count": accepted_record_count,
        "approval_artifact_requirement_count": len(reported_required),
        "required_followup_decision_count": len(required_followups),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match authority decisions")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_authority_decision_report_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_preflight_receipt",
        "component_route_binding_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
        "terminal_closure_denial_receipt",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


def _validate_authority_decision(
    authority_decision: dict[str, Any],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    expected_values = {
        "decision_state": "denied",
        "decision_basis": "record_evidence_only",
        "proof_state": "Pass",
    }
    for field_name, expected_value in expected_values.items():
        if authority_decision.get(field_name) != expected_value:
            errors.append(f"{label}: gate {gate_id} {field_name} must be {expected_value}")
    for field_name in (
        "record_evidence_satisfied",
        "blocks_promotion",
        "requires_route_binding_decision",
        "requires_lifecycle_transition",
        "requires_authority_upgrade_witness",
        "requires_product_ownership_decision",
        "requires_terminal_closure",
        "decision_is_not_authority_grant",
        "decision_is_not_promotion_approval",
        "decision_is_not_route_binding",
        "decision_is_not_lifecycle_transition",
        "foundation_fixture_decision_is_not_live_operator_evidence",
    ):
        if authority_decision.get(field_name) is not True:
            errors.append(f"{label}: gate {gate_id} {field_name} must be true")
    for field_name in (
        "action_requirement_satisfied",
        "authority_granted",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "connector_authority_authorized",
        "terminal_closure_authorized",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if authority_decision.get(field_name) is not False:
            errors.append(f"{label}: gate {gate_id} {field_name} must be false")
    if _string_list(authority_decision.get("satisfied_gate_evaluation_refs")) != [
        str(authority_decision.get("source_gate_evaluation_id"))
    ]:
        errors.append(f"{label}: gate {gate_id} satisfied_gate_evaluation_refs must contain only the source gate id")
    if _string_list(authority_decision.get("accepted_record_refs")) != [
        str(authority_decision.get("source_operator_submitted_record_id"))
    ]:
        errors.append(f"{label}: gate {gate_id} accepted_record_refs must contain only the source record id")
    for field_name in (
        "authority_grant_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(authority_decision.get(field_name)):
            errors.append(f"{label}: gate {gate_id} {field_name} must remain empty until separate evidence exists")
    if set(_string_list(authority_decision.get("missing_authority_witnesses"))) != MISSING_AUTHORITY_WITNESSES:
        errors.append(f"{label}: gate {gate_id} missing_authority_witnesses must match denied authority witness set")
    if not authority_decision.get("decision_reason"):
        errors.append(f"{label}: gate {gate_id} must carry decision_reason")


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
    """Parse authority decision report validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness authority decision report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for authority decision report validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_authority_decision_report(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_authority_decision_report_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION AUTHORITY DECISION REPORT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
