#!/usr/bin/env python3
"""Validate router-inventory delta witness remediation plans."""

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

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (  # noqa: E402
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_plan import (  # noqa: E402
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report import (  # noqa: E402
    validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "component_route_family_promotion_router_inventory_delta_witness_remediation_plan.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_witness_remediation_plan.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation.json"
)
REQUIREMENT_SET = set(WITNESS_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanValidation:
    """Schema and semantic validation report for witness remediation plan."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    remediation_step_count: int
    planned_step_count: int
    accepted_evidence_count: int
    witness_mint_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanValidation:
    """Validate remediation plan schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta witness remediation plan schema", errors)
    example = _load_json_object(example_path, "router-inventory delta witness remediation plan example", errors)

    denial_validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report()
    if not denial_validation.ok:
        errors.extend(
            f"router-inventory delta witness minting denial validation failed: {error}"
            for error in denial_validation.errors
        )

    runtime_report = build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_remediation_plan_semantics(example, errors, _path_label(example_path))
    _validate_remediation_plan_semantics(runtime_report, errors, "runtime router-inventory delta witness remediation plan")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        remediation_step_count=int(summary.get("remediation_step_count", 0)) if isinstance(summary, dict) else 0,
        planned_step_count=int(summary.get("planned_step_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        witness_mint_count=int(summary.get("witness_mint_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic remediation plan validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_remediation_plan_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "remediation_plan_state": "planned_not_executed",
        "source_denial_report_state": "denied_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_remediation_pending",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "governed",
        "remediation_plan_issued",
        "remediation_plan_is_not_delta",
        "remediation_plan_is_not_evidence",
        "remediation_plan_is_not_authorization",
        "remediation_plan_is_not_witness",
        "remediation_plan_is_not_authority_grant",
        "remediation_plan_is_not_promotion_approval",
        "remediation_plan_is_not_terminal_closure",
        "source_denial_report_required",
        "source_denial_report_present",
        "requirements_unmet",
        "witness_minting_denied",
        "remediation_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "remediation_executed",
        "evidence_submitted",
        "evidence_accepted",
        "requirements_satisfied",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "router_inventory_delta_authorized",
        "selected_component_binding_created",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "authority_granted",
        "promotion_approved",
        "terminal_certificate_minted",
        "terminal_closure_claimed",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    for field_name in (
        "accepted_evidence_refs",
        "submitted_evidence_refs",
        "authorization_refs",
        "router_inventory_delta_witness_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate evidence exists")

    steps = report.get("remediation_steps")
    summary = report.get("summary")
    if not isinstance(steps, list) or len(steps) != len(REQUIREMENT_SET):
        errors.append(f"{label}: remediation_steps must contain six steps")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if set(_string_list([step.get("requirement_artifact") for step in steps if isinstance(step, dict)])) != REQUIREMENT_SET:
        errors.append(f"{label}: remediation step artifacts must match required set")
    if _string_list(report.get("remediation_step_refs")) != [
        str(step.get("step_id")) for step in steps if isinstance(step, dict)
    ]:
        errors.append(f"{label}: remediation_step_refs must match step ids")
    if len(_string_list(report.get("source_minting_denial_decision_refs"))) != 1:
        errors.append(f"{label}: source_minting_denial_decision_refs must contain one decision")

    for step in steps:
        if not isinstance(step, dict):
            errors.append(f"{label}: remediation_steps entries must be objects")
            continue
        _validate_remediation_step(step, errors, label)

    expected_counts = {
        "source_denial_decision_count": len(_string_list(report.get("source_minting_denial_decision_refs"))),
        "remediation_step_count": len(steps),
        "planned_step_count": sum(1 for step in steps if isinstance(step, dict) and step.get("step_state") == "planned"),
        "executed_step_count": sum(1 for step in steps if isinstance(step, dict) and step.get("remediation_executed") is True),
        "submitted_evidence_count": sum(1 for step in steps if isinstance(step, dict) and step.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for step in steps if isinstance(step, dict) and step.get("evidence_accepted") is True),
        "authorization_present_count": sum(1 for step in steps if isinstance(step, dict) and step.get("authorization_present") is True),
        "satisfied_requirement_count": sum(1 for step in steps if isinstance(step, dict) and step.get("requirement_satisfied") is True),
        "unknown_proof_state_count": sum(1 for step in steps if isinstance(step, dict) and step.get("proof_state") == "Unknown"),
        "witness_minting_authorization_count": sum(1 for step in steps if isinstance(step, dict) and step.get("witness_minting_authorized") is True),
        "witness_mint_count": sum(1 for step in steps if isinstance(step, dict) and step.get("witness_minted") is True),
        "applied_delta_count": sum(1 for step in steps if isinstance(step, dict) and step.get("delta_applied") is True),
        "router_inventory_mutation_count": sum(1 for step in steps if isinstance(step, dict) and step.get("router_inventory_mutated") is True),
        "authority_grant_count": sum(1 for step in steps if isinstance(step, dict) and step.get("authority_granted") is True),
        "promotion_approval_count": sum(1 for step in steps if isinstance(step, dict) and step.get("promotion_approved") is True),
        "terminal_closure_claim_count": sum(1 for step in steps if isinstance(step, dict) and step.get("terminal_closure_claimed") is True),
        "blocking_step_count": sum(1 for step in steps if isinstance(step, dict) and step.get("blocks_witness_minting") is True),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match remediation steps")


def _validate_remediation_step(step: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "step_state": "planned",
        "proof_state": "Unknown",
    }
    for field_name, expected_value in expected_strings.items():
        if step.get(field_name) != expected_value:
            errors.append(f"{label}: step {field_name} must be {expected_value}")
    if step.get("requirement_artifact") not in REQUIREMENT_SET:
        errors.append(f"{label}: step requirement_artifact must be in required set")
    for field_name in (
        "required",
        "plan_only",
        "evidence_required",
        "blocks_witness_minting",
        "blocks_promotion",
        "step_is_not_evidence",
        "step_is_not_authorization",
        "step_is_not_witness",
        "step_is_not_delta",
        "step_is_not_authority_grant",
        "step_is_not_promotion_approval",
        "step_is_not_terminal_closure",
    ):
        if step.get(field_name) is not True:
            errors.append(f"{label}: step {field_name} must be true")
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "authorization_present",
        "requirement_satisfied",
        "remediation_executed",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
    ):
        if step.get(field_name) is not False:
            errors.append(f"{label}: step {field_name} must be false")
    if _string_list(step.get("source_denial_decision_refs")) != [str(step.get("source_denial_decision_id"))]:
        errors.append(f"{label}: step source_denial_decision_refs must match source denial")
    for field_name in (
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "authorization_refs",
        "witness_refs",
        "router_inventory_delta_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(step.get(field_name)):
            errors.append(f"{label}: step {field_name} must remain empty")


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
    """Parse router-inventory delta witness remediation plan validation arguments."""

    parser = argparse.ArgumentParser(description="Validate router-inventory delta witness remediation plan.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router-inventory delta witness remediation plan validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA WITNESS REMEDIATION PLAN VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
