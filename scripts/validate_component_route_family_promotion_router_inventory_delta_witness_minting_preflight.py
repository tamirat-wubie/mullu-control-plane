#!/usr/bin/env python3
"""Validate router-inventory delta witness minting preflight reports."""

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
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_preflight import (  # noqa: E402
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_requirements import (  # noqa: E402
    validate_component_route_family_promotion_router_inventory_delta_witness_requirements,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_preflight.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_preflight.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation.json"
)
REQUIREMENT_SET = set(WITNESS_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightValidation:
    """Schema and semantic validation report for witness minting preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    preflight_check_count: int
    blocked_check_count: int
    witness_mint_count: int
    router_inventory_mutation_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightValidation:
    """Validate minting preflight schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta witness minting preflight schema", errors)
    example = _load_json_object(example_path, "router-inventory delta witness minting preflight example", errors)

    requirements_validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements()
    if not requirements_validation.ok:
        errors.extend(
            f"router-inventory delta witness requirements validation failed: {error}"
            for error in requirements_validation.errors
        )

    runtime_report = build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_minting_preflight_semantics(example, errors, _path_label(example_path))
    _validate_minting_preflight_semantics(
        runtime_report,
        errors,
        "runtime router-inventory delta witness minting preflight",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        preflight_check_count=int(summary.get("preflight_check_count", 0)) if isinstance(summary, dict) else 0,
        blocked_check_count=int(summary.get("blocked_check_count", 0)) if isinstance(summary, dict) else 0,
        witness_mint_count=int(summary.get("witness_mint_count", 0)) if isinstance(summary, dict) else 0,
        router_inventory_mutation_count=(
            int(summary.get("router_inventory_mutation_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic minting preflight validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_minting_preflight_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "minting_preflight_state": "blocked_requirements_unmet",
        "source_witness_requirements_status": "requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_preflight",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "governed",
        "minting_preflight_issued",
        "minting_preflight_is_not_delta",
        "minting_preflight_is_not_evidence",
        "minting_preflight_is_not_witness",
        "minting_preflight_is_not_route_binding",
        "minting_preflight_is_not_authority_grant",
        "minting_preflight_is_not_promotion_approval",
        "minting_preflight_is_not_terminal_closure",
        "requirements_report_required",
        "requirements_report_present",
        "requirements_unmet",
        "hard_constraint_unknown_blocks_minting",
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
            errors.append(f"{label}: {field_name} must remain empty until separate minting evidence exists")

    checks = report.get("minting_preflight_checks")
    summary = report.get("summary")
    if not isinstance(checks, list) or len(checks) != len(REQUIREMENT_SET):
        errors.append(f"{label}: minting_preflight_checks must contain six checks")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if set(_string_list([check.get("requirement_artifact") for check in checks if isinstance(check, dict)])) != REQUIREMENT_SET:
        errors.append(f"{label}: minting preflight artifacts must match required set")
    if _string_list(report.get("minting_preflight_check_refs")) != [
        str(check.get("check_id")) for check in checks if isinstance(check, dict)
    ]:
        errors.append(f"{label}: minting_preflight_check_refs must match check ids")
    source_requirement_refs = _string_list(report.get("source_witness_requirement_refs"))
    if len(source_requirement_refs) != len(REQUIREMENT_SET):
        errors.append(f"{label}: source_witness_requirement_refs must contain six source requirements")
    if len(_string_list(report.get("source_witness_requirements_report_refs"))) != 1:
        errors.append(f"{label}: source_witness_requirements_report_refs must contain one report")

    for check in checks:
        if not isinstance(check, dict):
            errors.append(f"{label}: minting_preflight_checks entries must be objects")
            continue
        _validate_preflight_check(check, source_requirement_refs, errors, label)

    expected_counts = {
        "source_requirements_report_count": 1,
        "minting_preflight_count": 1,
        "preflight_check_count": len(checks),
        "blocked_check_count": sum(1 for check in checks if isinstance(check, dict) and check.get("check_state") == "blocked"),
        "satisfied_check_count": sum(1 for check in checks if isinstance(check, dict) and check.get("satisfied") is True),
        "unknown_proof_state_count": sum(1 for check in checks if isinstance(check, dict) and check.get("proof_state") == "Unknown"),
        "present_evidence_count": sum(1 for check in checks if isinstance(check, dict) and check.get("evidence_present") is True),
        "authorization_present_count": sum(1 for check in checks if isinstance(check, dict) and check.get("authorization_present") is True),
        "witness_minting_authorization_count": sum(1 for check in checks if isinstance(check, dict) and check.get("witness_minting_authorized") is True),
        "witness_mint_count": sum(1 for check in checks if isinstance(check, dict) and check.get("witness_minted") is True),
        "applied_delta_count": sum(1 for check in checks if isinstance(check, dict) and check.get("delta_applied") is True),
        "router_inventory_mutation_count": sum(1 for check in checks if isinstance(check, dict) and check.get("router_inventory_mutated") is True),
        "selected_component_binding_count": sum(1 for check in checks if isinstance(check, dict) and check.get("selected_component_binding_created") is True),
        "authority_grant_count": sum(1 for check in checks if isinstance(check, dict) and check.get("authority_granted") is True),
        "promotion_approval_count": sum(1 for check in checks if isinstance(check, dict) and check.get("promotion_approved") is True),
        "terminal_closure_claim_count": sum(1 for check in checks if isinstance(check, dict) and check.get("terminal_closure_claimed") is True),
        "blocking_minting_check_count": sum(1 for check in checks if isinstance(check, dict) and check.get("blocks_witness_minting") is True),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match minting preflight checks")
    if "witness_minting" not in set(_string_list(report.get("blocked_actions"))):
        errors.append(f"{label}: blocked_actions must include witness_minting")


def _validate_preflight_check(
    check: dict[str, Any],
    source_requirement_refs: list[str],
    errors: list[str],
    label: str,
) -> None:
    expected_strings = {
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "check_state": "blocked",
        "proof_state": "Unknown",
    }
    for field_name, expected_value in expected_strings.items():
        if check.get(field_name) != expected_value:
            errors.append(f"{label}: check {field_name} must be {expected_value}")
    if check.get("requirement_artifact") not in REQUIREMENT_SET:
        errors.append(f"{label}: check requirement_artifact must be in required set")
    for field_name in (
        "required",
        "hard_constraint_unknown_blocks_minting",
        "blocks_witness_minting",
        "blocks_promotion",
        "check_is_not_evidence",
        "check_is_not_authorization",
        "check_is_not_witness",
        "check_is_not_delta",
        "check_is_not_authority_grant",
        "check_is_not_promotion_approval",
        "check_is_not_terminal_closure",
    ):
        if check.get(field_name) is not True:
            errors.append(f"{label}: check {field_name} must be true")
    for field_name in (
        "satisfied",
        "evidence_present",
        "authorization_present",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "selected_component_binding_created",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
    ):
        if check.get(field_name) is not False:
            errors.append(f"{label}: check {field_name} must be false")
    if _string_list(check.get("source_requirement_refs")) != [str(check.get("source_requirement_id"))]:
        errors.append(f"{label}: check source_requirement_refs must match source requirement")
    if str(check.get("source_requirement_id")) not in source_requirement_refs:
        errors.append(f"{label}: check source_requirement_id must be listed by report")
    for field_name in (
        "evidence_refs",
        "authorization_refs",
        "witness_refs",
        "router_inventory_delta_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(check.get(field_name)):
            errors.append(f"{label}: check {field_name} must remain empty")


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
    """Parse router-inventory delta witness minting preflight validation arguments."""

    parser = argparse.ArgumentParser(description="Validate router-inventory delta witness minting preflight.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router-inventory delta witness minting preflight validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA WITNESS MINTING PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
