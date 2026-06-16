#!/usr/bin/env python3
"""Validate router-inventory delta witness requirement reports."""

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
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_requirements import (  # noqa: E402
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_requirements,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_candidate import (  # noqa: E402
    validate_component_route_family_promotion_router_inventory_delta_candidate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_router_inventory_delta_witness_requirements.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_witness_requirements.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_witness_requirements_validation.json"
)
REQUIREMENT_SET = set(WITNESS_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsValidation:
    """Schema and semantic validation report for witness requirements."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    requirement_count: int
    unmet_requirement_count: int
    witness_mint_count: int
    router_inventory_mutation_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsValidation:
    """Validate witness requirement schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta witness requirements schema", errors)
    example = _load_json_object(example_path, "router-inventory delta witness requirements example", errors)

    candidate_validation = validate_component_route_family_promotion_router_inventory_delta_candidate()
    if not candidate_validation.ok:
        errors.extend(
            f"router-inventory delta candidate validation failed: {error}"
            for error in candidate_validation.errors
        )

    runtime_report = build_component_route_family_promotion_router_inventory_delta_witness_requirements()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_requirement_semantics(example, errors, _path_label(example_path))
    _validate_requirement_semantics(runtime_report, errors, "runtime router-inventory delta witness requirements")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        requirement_count=int(summary.get("requirement_count", 0)) if isinstance(summary, dict) else 0,
        unmet_requirement_count=int(summary.get("unmet_requirement_count", 0)) if isinstance(summary, dict) else 0,
        witness_mint_count=int(summary.get("witness_mint_count", 0)) if isinstance(summary, dict) else 0,
        router_inventory_mutation_count=(
            int(summary.get("router_inventory_mutation_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_router_inventory_delta_witness_requirements_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic witness requirements validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_requirement_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "witness_status": "requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_not_authorized",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "governed",
        "requirements_report_issued",
        "requirements_report_is_not_delta",
        "requirements_report_is_not_evidence",
        "requirements_report_is_not_witness",
        "requirements_report_is_not_route_binding",
        "requirements_report_is_not_authority_grant",
        "requirements_report_is_not_promotion_approval",
        "requirements_report_is_not_terminal_closure",
        "separate_router_inventory_delta_witness_required",
        "separate_operator_approval_required",
        "separate_route_binding_authorization_required",
        "separate_lifecycle_transition_authorization_required",
        "separate_authority_upgrade_witness_required",
        "separate_product_ownership_witness_required",
        "separate_terminal_closure_certificate_required",
        "dry_run_candidate_required",
        "dry_run_candidate_present",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "selected_component_binding_created",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "authority_upgrade_authorized",
        "authority_granted",
        "promotion_approved",
        "terminal_certificate_minted",
        "terminal_closure_authorized",
        "terminal_closure_claimed",
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
    for field_name in (
        "router_inventory_delta_witness_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "route_binding_authorization_refs",
        "lifecycle_transition_authorization_refs",
        "authority_upgrade_witness_refs",
        "authority_grant_refs",
        "product_ownership_witness_refs",
        "terminal_closure_certificate_refs",
        "terminal_closure_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate witness evidence exists")

    requirements = report.get("witness_requirements")
    summary = report.get("summary")
    if not isinstance(requirements, list) or len(requirements) != len(REQUIREMENT_SET):
        errors.append(f"{label}: witness_requirements must contain six requirements")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if set(_string_list([r.get("requirement_artifact") for r in requirements if isinstance(r, dict)])) != REQUIREMENT_SET:
        errors.append(f"{label}: witness requirement artifacts must match required set")
    if _string_list(report.get("witness_requirement_refs")) != [
        str(record.get("requirement_id")) for record in requirements if isinstance(record, dict)
    ]:
        errors.append(f"{label}: witness_requirement_refs must match requirement ids")
    source_refs = _string_list(report.get("source_router_inventory_delta_candidate_refs"))
    if len(source_refs) != 1:
        errors.append(f"{label}: source_router_inventory_delta_candidate_refs must contain one candidate")

    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append(f"{label}: witness_requirements entries must be objects")
            continue
        _validate_requirement_record(requirement, source_refs, errors, label)

    expected_counts = {
        "requirement_count": len(requirements),
        "unmet_requirement_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("requirement_state") == "unmet"),
        "satisfied_requirement_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("satisfied") is True),
        "unknown_proof_state_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("proof_state") == "Unknown"),
        "present_evidence_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("evidence_present") is True),
        "authorization_present_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("authorization_present") is True),
        "witness_mint_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("witness_minted") is True),
        "applied_delta_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("delta_applied") is True),
        "router_inventory_mutation_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("router_inventory_mutated") is True),
        "selected_component_binding_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("selected_component_binding_created") is True),
        "authority_grant_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("authority_granted") is True),
        "promotion_approval_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("promotion_approved") is True),
        "terminal_closure_claim_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("terminal_closure_claimed") is True),
        "blocking_requirement_count": sum(1 for r in requirements if isinstance(r, dict) and r.get("blocks_witness_minting") is True),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match witness requirements")
    if "witness_minting" not in set(_string_list(report.get("blocked_actions"))):
        errors.append(f"{label}: blocked_actions must include witness_minting")


def _validate_requirement_record(
    requirement: dict[str, Any],
    source_refs: list[str],
    errors: list[str],
    label: str,
) -> None:
    expected_strings = {
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "requirement_state": "unmet",
        "proof_state": "Unknown",
    }
    for field_name, expected_value in expected_strings.items():
        if requirement.get(field_name) != expected_value:
            errors.append(f"{label}: requirement {field_name} must be {expected_value}")
    if requirement.get("requirement_artifact") not in REQUIREMENT_SET:
        errors.append(f"{label}: requirement_artifact must be in required set")
    for field_name in (
        "hard_constraint_unknown_blocks_witness",
        "required",
        "blocks_witness_minting",
        "blocks_promotion",
        "record_is_not_evidence",
        "record_is_not_authorization",
        "record_is_not_witness",
        "record_is_not_delta",
        "record_is_not_authority_grant",
        "record_is_not_promotion_approval",
        "record_is_not_terminal_closure",
    ):
        if requirement.get(field_name) is not True:
            errors.append(f"{label}: requirement {field_name} must be true")
    for field_name in (
        "satisfied",
        "evidence_present",
        "authorization_present",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "selected_component_binding_created",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
    ):
        if requirement.get(field_name) is not False:
            errors.append(f"{label}: requirement {field_name} must be false")
    if _string_list(requirement.get("source_candidate_refs")) != source_refs:
        errors.append(f"{label}: source_candidate_refs must match source candidate")
    for field_name in (
        "evidence_refs",
        "authorization_refs",
        "witness_refs",
        "router_inventory_delta_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(requirement.get(field_name)):
            errors.append(f"{label}: requirement {field_name} must remain empty")


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
    """Parse router-inventory delta witness requirements validation arguments."""

    parser = argparse.ArgumentParser(description="Validate router-inventory delta witness requirements.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router-inventory delta witness requirements validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_router_inventory_delta_witness_requirements_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA WITNESS REQUIREMENTS VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
