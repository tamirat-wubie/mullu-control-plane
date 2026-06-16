#!/usr/bin/env python3
"""Validate router-inventory delta witness minting denial reports."""

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
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_denial_report import (  # noqa: E402
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight import (  # noqa: E402
    validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation.json"
)
REQUIREMENT_SET = set(WITNESS_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportValidation:
    """Schema and semantic validation report for witness minting denial."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    denial_decision_count: int
    witness_minting_denial_count: int
    witness_mint_count: int
    router_inventory_mutation_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportValidation:
    """Validate minting denial schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta witness minting denial schema", errors)
    example = _load_json_object(example_path, "router-inventory delta witness minting denial example", errors)

    preflight_validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight()
    if not preflight_validation.ok:
        errors.extend(
            f"router-inventory delta witness minting preflight validation failed: {error}"
            for error in preflight_validation.errors
        )

    runtime_report = build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_denial_report_semantics(example, errors, _path_label(example_path))
    _validate_denial_report_semantics(
        runtime_report,
        errors,
        "runtime router-inventory delta witness minting denial report",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        denial_decision_count=int(summary.get("denial_decision_count", 0)) if isinstance(summary, dict) else 0,
        witness_minting_denial_count=(
            int(summary.get("witness_minting_denial_count", 0)) if isinstance(summary, dict) else 0
        ),
        witness_mint_count=int(summary.get("witness_mint_count", 0)) if isinstance(summary, dict) else 0,
        router_inventory_mutation_count=(
            int(summary.get("router_inventory_mutation_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic minting denial validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_denial_report_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "denial_report_state": "denied_requirements_unmet",
        "source_minting_preflight_state": "blocked_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_denied",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "governed",
        "denial_report_issued",
        "denial_report_is_not_delta",
        "denial_report_is_not_evidence",
        "denial_report_is_not_witness",
        "denial_report_is_not_route_binding",
        "denial_report_is_not_authority_grant",
        "denial_report_is_not_promotion_approval",
        "denial_report_is_not_terminal_closure",
        "minting_preflight_required",
        "minting_preflight_present",
        "requirements_unmet",
        "hard_constraint_unknown_blocks_minting",
        "witness_minting_denied",
        "separate_router_inventory_delta_witness_required",
        "separate_operator_approval_required",
        "separate_route_binding_authorization_required",
        "separate_lifecycle_transition_authorization_required",
        "separate_authority_upgrade_witness_required",
        "separate_product_ownership_witness_required",
        "separate_terminal_closure_certificate_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "witness_minting_authorized",
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

    decisions = report.get("minting_denial_decisions")
    summary = report.get("summary")
    if not isinstance(decisions, list) or len(decisions) != 1:
        errors.append(f"{label}: minting_denial_decisions must contain exactly one decision")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    decision = decisions[0]
    if not isinstance(decision, dict):
        errors.append(f"{label}: minting_denial_decisions entries must be objects")
        return
    _validate_denial_decision(decision, errors, label)

    if _string_list(report.get("minting_denial_decision_refs")) != [str(decision.get("denial_decision_id"))]:
        errors.append(f"{label}: minting_denial_decision_refs must match denial decision id")
    if _string_list(report.get("router_inventory_delta_witness_denial_refs")) != [
        str(decision.get("denial_decision_id"))
    ]:
        errors.append(f"{label}: router_inventory_delta_witness_denial_refs must match denial decision id")
    if _string_list(report.get("source_minting_preflight_refs")) != [
        str(decision.get("source_minting_preflight_id"))
    ]:
        errors.append(f"{label}: source_minting_preflight_refs must match source preflight id")
    if _string_list(report.get("source_minting_preflight_check_refs")) != _string_list(
        decision.get("source_minting_preflight_check_refs")
    ):
        errors.append(f"{label}: source_minting_preflight_check_refs must match denial decision checks")
    if set(_string_list(report.get("missing_witness_requirements"))) != REQUIREMENT_SET:
        errors.append(f"{label}: missing_witness_requirements must match required witness set")

    expected_counts = {
        "source_minting_preflight_count": len(_string_list(report.get("source_minting_preflight_refs"))),
        "source_preflight_check_count": len(_string_list(report.get("source_minting_preflight_check_refs"))),
        "source_blocked_check_count": len(_string_list(report.get("source_minting_preflight_check_refs"))),
        "source_unknown_proof_state_count": len(_string_list(report.get("source_minting_preflight_check_refs"))),
        "denial_decision_count": 1,
        "denied_decision_count": 1 if decision.get("decision_state") == "denied" else 0,
        "witness_minting_denial_count": 1 if decision.get("witness_minting_denied") is True else 0,
        "witness_minting_authorization_count": 1 if decision.get("witness_minting_authorized") is True else 0,
        "witness_mint_count": 1 if decision.get("witness_minted") is True else 0,
        "applied_delta_count": 1 if decision.get("delta_applied") is True else 0,
        "router_inventory_mutation_count": 1 if decision.get("router_inventory_mutated") is True else 0,
        "selected_component_binding_count": 1 if decision.get("selected_component_binding_created") is True else 0,
        "authority_grant_count": 1 if decision.get("authority_granted") is True else 0,
        "promotion_approval_count": 1 if decision.get("promotion_approved") is True else 0,
        "terminal_closure_claim_count": 1 if decision.get("terminal_closure_claimed") is True else 0,
        "accepted_evidence_count": len(_string_list(decision.get("accepted_evidence_refs"))),
        "rejected_evidence_count": len(_string_list(decision.get("rejected_evidence_refs"))),
        "missing_witness_requirement_count": len(_string_list(decision.get("missing_witness_requirements"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match minting denial decision")
    if "witness_minting" not in set(_string_list(report.get("blocked_actions"))):
        errors.append(f"{label}: blocked_actions must include witness_minting")


def _validate_denial_decision(decision: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "decision_state": "denied",
        "decision_basis": "minting_preflight_blocked_requirements_unmet",
        "proof_state": "Pass",
    }
    for field_name, expected_value in expected_strings.items():
        if decision.get(field_name) != expected_value:
            errors.append(f"{label}: denial decision {field_name} must be {expected_value}")
    for field_name in (
        "source_preflight_blocked",
        "requirements_unmet",
        "hard_constraint_unknown_blocks_minting",
        "witness_minting_denied",
        "decision_is_not_witness",
        "decision_is_not_delta",
        "decision_is_not_evidence",
        "decision_is_not_authority_grant",
        "decision_is_not_promotion_approval",
        "decision_is_not_terminal_closure",
    ):
        if decision.get(field_name) is not True:
            errors.append(f"{label}: denial decision {field_name} must be true")
    for field_name in (
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "selected_component_binding_created",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if decision.get(field_name) is not False:
            errors.append(f"{label}: denial decision {field_name} must be false")
    if _string_list(decision.get("source_minting_preflight_refs")) != [
        str(decision.get("source_minting_preflight_id"))
    ]:
        errors.append(f"{label}: denial decision source_minting_preflight_refs must match source preflight")
    if len(_string_list(decision.get("source_minting_preflight_check_refs"))) != len(REQUIREMENT_SET):
        errors.append(f"{label}: denial decision source_minting_preflight_check_refs must contain six refs")
    if set(_string_list(decision.get("missing_witness_requirements"))) != REQUIREMENT_SET:
        errors.append(f"{label}: denial decision missing_witness_requirements must match required witness set")
    for field_name in (
        "router_inventory_delta_witness_refs",
        "router_inventory_delta_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(decision.get(field_name)):
            errors.append(f"{label}: denial decision {field_name} must remain empty")
    if not decision.get("decision_reason"):
        errors.append(f"{label}: denial decision must carry decision_reason")


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
    """Parse router-inventory delta witness minting denial validation arguments."""

    parser = argparse.ArgumentParser(description="Validate router-inventory delta witness minting denial report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router-inventory delta witness minting denial validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA WITNESS MINTING DENIAL REPORT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
