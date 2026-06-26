#!/usr/bin/env python3
"""Validate Component Harness promotion route-binding decision reports.

Purpose: prove denied promotion authority decisions can produce a denial-only
route-binding decision without route-family promotion or router inventory
mutation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: route-binding decision schema/example, runtime builder, and
promotion authority decision validation.
Invariants:
  - A route-binding decision report is not a router inventory delta.
  - Denied route binding cannot promote a route family.
  - No route-binding decision can grant authority, execute, call connectors,
    or claim terminal closure.
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

from mcoi_runtime.app.component_route_family_promotion_route_binding_decision_report import (  # noqa: E402
    build_component_route_family_promotion_route_binding_decision_report,
)
from scripts.validate_component_route_family_promotion_authority_decision_report import (  # noqa: E402
    validate_component_route_family_promotion_authority_decision_report,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_route_binding_decision_report.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_route_binding_decision_report.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_route_binding_decision_report_validation.json"
)
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
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_decision",
    "authority_upgrade_witness_decision",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
}
MISSING_ROUTE_BINDING_WITNESSES = {
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouteBindingDecisionReportValidation:
    """Schema and semantic validation report for route-binding decision reports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    route_binding_decision_count: int
    route_binding_denial_count: int
    route_binding_authorization_count: int
    router_inventory_mutation_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_route_binding_decision_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouteBindingDecisionReportValidation:
    """Validate route-binding decision schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion route-binding decision schema", errors)
    example = _load_json_object(example_path, "component route-family promotion route-binding decision example", errors)

    authority_decision_validation = validate_component_route_family_promotion_authority_decision_report()
    if not authority_decision_validation.ok:
        errors.extend(
            f"component route-family promotion authority decision validation failed: {error}"
            for error in authority_decision_validation.errors
        )

    runtime_report = build_component_route_family_promotion_route_binding_decision_report()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_route_binding_decision_semantics(example, errors, _path_label(example_path))
    _validate_route_binding_decision_semantics(runtime_report, errors, "runtime component route-family promotion route-binding decision")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouteBindingDecisionReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        route_binding_decision_count=(
            int(summary.get("route_binding_decision_count", 0)) if isinstance(summary, dict) else 0
        ),
        route_binding_denial_count=(
            int(summary.get("route_binding_denial_count", 0)) if isinstance(summary, dict) else 0
        ),
        route_binding_authorization_count=(
            int(summary.get("route_binding_authorization_count", 0)) if isinstance(summary, dict) else 0
        ),
        router_inventory_mutation_count=(
            int(summary.get("router_inventory_mutation_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_route_binding_decision_report_validation(
    validation: ComponentRouteFamilyPromotionRouteBindingDecisionReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic route-binding decision validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_route_binding_decision_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("route_binding_decision_state") != "denied_pending_router_inventory_witness":
        errors.append(f"{label}: route_binding_decision_state must be denied_pending_router_inventory_witness")
    if report.get("promotion_decision") != "blocked_route_binding_not_authorized":
        errors.append(f"{label}: promotion_decision must be blocked_route_binding_not_authorized")
    if report.get("authority_decision_state") != "denied_pending_governed_witnesses":
        errors.append(f"{label}: authority_decision_state must be denied_pending_governed_witnesses")
    for field_name in (
        "record_evidence_satisfied",
        "route_binding_decision_is_not_router_mutation",
        "route_binding_decision_is_not_promotion_approval",
        "route_binding_decision_is_not_authority_grant",
        "foundation_fixture_decision_is_not_live_operator_evidence",
        "separate_router_inventory_delta_required",
        "separate_route_binding_receipt_required",
        "separate_lifecycle_transition_required",
        "separate_authority_upgrade_witness_required",
        "separate_product_ownership_decision_required",
        "terminal_closure_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "action_requirement_satisfied",
        "authority_granted",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "route_family_ownership_authorized",
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
        "route_binding_receipt_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "lifecycle_transition_refs",
        "terminal_closure_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate route-binding evidence exists")

    decisions = report.get("route_binding_decisions")
    summary = report.get("summary")
    if not isinstance(decisions, list) or len(decisions) != 1:
        errors.append(f"{label}: route_binding_decisions must contain exactly one decision")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    decision = decisions[0]
    if not isinstance(decision, dict):
        errors.append(f"{label}: route_binding_decisions entries must be objects")
        return
    _validate_route_binding_decision(decision, errors, label)

    decision_id = str(decision.get("route_binding_decision_id", ""))
    source_authority_id = str(decision.get("source_authority_decision_id", ""))
    source_gate_id = str(decision.get("source_gate_evaluation_id", ""))
    accepted_record_id = str(decision.get("source_operator_submitted_record_id", ""))
    if _string_list(report.get("route_binding_decision_refs")) != [decision_id]:
        errors.append(f"{label}: route_binding_decision_refs must match route_binding_decision_id")
    if _string_list(report.get("source_authority_decision_refs")) != [source_authority_id]:
        errors.append(f"{label}: source_authority_decision_refs must match source authority decision id")
    authority_fuse_refs = _string_list(report.get("authority_fuse_refs"))
    authority_fuse_blocking_refs = _string_list(report.get("authority_fuse_blocking_refs"))
    if len(authority_fuse_refs) != 1:
        errors.append(f"{label}: authority_fuse_refs must contain exactly one target component fuse")
    if authority_fuse_blocking_refs != authority_fuse_refs:
        errors.append(f"{label}: authority_fuse_blocking_refs must match authority_fuse_refs")
    if _string_list(decision.get("authority_fuse_refs")) != authority_fuse_refs:
        errors.append(f"{label}: route-binding decision authority_fuse_refs must match report authority_fuse_refs")
    if _string_list(report.get("satisfied_gate_evaluation_refs")) != [source_gate_id]:
        errors.append(f"{label}: satisfied_gate_evaluation_refs must match source gate evaluation id")
    if _string_list(report.get("accepted_record_refs")) != [accepted_record_id]:
        errors.append(f"{label}: accepted_record_refs must match source operator record id")

    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    required_followups = set(_string_list(report.get("required_followup_decisions")))
    missing_witnesses = set(_string_list(report.get("missing_route_binding_witnesses")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")
    if required_followups != REQUIRED_FOLLOWUP_DECISIONS:
        errors.append(f"{label}: required_followup_decisions must match route-binding follow-up set")
    if missing_witnesses != MISSING_ROUTE_BINDING_WITNESSES:
        errors.append(f"{label}: missing_route_binding_witnesses must match route-binding witness set")

    expected_counts = {
        "route_binding_decision_count": 1,
        "route_binding_denial_count": 1 if decision.get("decision_state") == "denied" else 0,
        "route_binding_authorization_count": 1 if decision.get("route_binding_authorized") is True else 0,
        "router_inventory_delta_authorization_count": (
            1 if decision.get("router_inventory_delta_authorized") is True else 0
        ),
        "router_inventory_mutation_count": 1 if decision.get("mutates_router_inventory") is True else 0,
        "selected_component_binding_count": (
            1 if decision.get("selected_component_binding_authorized") is True else 0
        ),
        "authority_grant_count": 1 if decision.get("authority_granted") is True else 0,
        "promotion_approval_count": 1 if decision.get("promotion_approved") is True else 0,
        "accepted_evidence_count": len(_string_list(decision.get("accepted_evidence_refs"))),
        "rejected_evidence_count": len(_string_list(decision.get("rejected_evidence_refs"))),
        "accepted_record_count": len(_string_list(decision.get("accepted_record_refs"))),
        "route_binding_receipt_count": len(_string_list(decision.get("route_binding_receipt_refs"))),
        "authority_fuse_blocking_count": len(set(_string_list(decision.get("authority_fuse_blocking_refs")))),
        "router_inventory_delta_ref_count": len(_string_list(decision.get("router_inventory_delta_refs"))),
        "approval_artifact_requirement_count": len(reported_required),
        "required_followup_decision_count": len(required_followups),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match route-binding decision")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_route_binding_decision_report_receipt",
        "component_route_family_promotion_authority_decision_report_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_binding_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
        "terminal_closure_denial_receipt",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


def _validate_route_binding_decision(decision: dict[str, Any], errors: list[str], label: str) -> None:
    if decision.get("gate_id") != "route_binding_gate":
        errors.append(f"{label}: route-binding decision gate_id must be route_binding_gate")
    if decision.get("record_kind") != "route_binding":
        errors.append(f"{label}: route-binding decision record_kind must be route_binding")
    for field_name, expected_value in (
        ("decision_state", "denied"),
        ("decision_basis", "authority_decision_denial"),
        ("proof_state", "Pass"),
    ):
        if decision.get(field_name) != expected_value:
            errors.append(f"{label}: route-binding decision {field_name} must be {expected_value}")
    for field_name in (
        "record_evidence_satisfied",
        "source_authority_decision_denied",
        "authority_fuse_blocks_promotion",
        "requires_external_authority_upgrade_evidence",
        "requires_router_inventory_delta",
        "requires_component_route_binding_receipt",
        "requires_lifecycle_transition",
        "requires_authority_upgrade_witness",
        "requires_product_ownership_decision",
        "requires_terminal_closure",
        "decision_is_not_router_mutation",
        "decision_is_not_promotion_approval",
        "decision_is_not_authority_grant",
        "foundation_fixture_decision_is_not_live_operator_evidence",
    ):
        if decision.get(field_name) is not True:
            errors.append(f"{label}: route-binding decision {field_name} must be true")
    for field_name in (
        "action_requirement_satisfied",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "route_family_ownership_authorized",
        "authority_granted",
        "promotion_approved",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if decision.get(field_name) is not False:
            errors.append(f"{label}: route-binding decision {field_name} must be false")
    if _string_list(decision.get("source_authority_decision_refs")) != [
        str(decision.get("source_authority_decision_id"))
    ]:
        errors.append(f"{label}: source_authority_decision_refs must contain only the source authority decision id")
    if len(_string_list(decision.get("authority_fuse_refs"))) != 1:
        errors.append(f"{label}: route-binding decision authority_fuse_refs must contain exactly one target component fuse")
    if _string_list(decision.get("authority_fuse_blocking_refs")) != _string_list(decision.get("authority_fuse_refs")):
        errors.append(f"{label}: route-binding decision authority_fuse_blocking_refs must match authority_fuse_refs")
    if _string_list(decision.get("satisfied_gate_evaluation_refs")) != [
        str(decision.get("source_gate_evaluation_id"))
    ]:
        errors.append(f"{label}: satisfied_gate_evaluation_refs must contain only the source gate id")
    if _string_list(decision.get("accepted_record_refs")) != [
        str(decision.get("source_operator_submitted_record_id"))
    ]:
        errors.append(f"{label}: accepted_record_refs must contain only the source record id")
    for field_name in (
        "route_binding_receipt_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(decision.get(field_name)):
            errors.append(f"{label}: route-binding decision {field_name} must remain empty")
    if set(_string_list(decision.get("missing_route_binding_witnesses"))) != MISSING_ROUTE_BINDING_WITNESSES:
        errors.append(f"{label}: missing_route_binding_witnesses must match route-binding witness set")
    if not decision.get("decision_reason"):
        errors.append(f"{label}: route-binding decision must carry decision_reason")


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
    """Parse route-binding decision report validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness route-binding decision report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for route-binding decision report validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_route_binding_decision_report(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_route_binding_decision_report_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTE BINDING DECISION REPORT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
