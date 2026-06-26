#!/usr/bin/env python3
"""Validate Component Harness promotion terminal-closure denial reports.

Purpose: prove denied product-ownership decisions can produce a denial-only
terminal-closure decision without minting terminal certificates, approving
promotion, granting authority, mutating router inventory, or claiming closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: terminal-closure denial schema/example, runtime builder, and
promotion product-ownership decision validation.
Invariants:
  - A terminal-closure denial report is not a terminal certificate.
  - Denial reports cannot claim terminal closure.
  - No terminal-closure denial can execute, call connectors, mutate router
    inventory, grant authority, approve promotion, or close the action.
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

from mcoi_runtime.app.component_route_family_promotion_terminal_closure_denial_report import (  # noqa: E402
    DEFAULT_PRODUCT_BUNDLE_ID,
    build_component_route_family_promotion_terminal_closure_denial_report,
)
from scripts.validate_component_route_family_promotion_product_ownership_decision_report import (  # noqa: E402
    validate_component_route_family_promotion_product_ownership_decision_report,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_terminal_closure_denial_report.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_terminal_closure_denial_report.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_terminal_closure_denial_report_validation.json"
)
REQUIRED_FOLLOWUP_DECISIONS = {
    "selected_component_bound_router_inventory_delta",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_certificate",
}
MISSING_TERMINAL_CLOSURE_WITNESSES = {
    "terminal_closure_certificate",
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionTerminalClosureDenialReportValidation:
    """Schema and semantic validation report for terminal-closure denial."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    terminal_closure_decision_count: int
    terminal_closure_denial_count: int
    terminal_closure_authorization_count: int
    terminal_certificate_mint_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_terminal_closure_denial_report(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionTerminalClosureDenialReportValidation:
    """Validate terminal-closure denial schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "terminal-closure denial schema", errors)
    example = _load_json_object(example_path, "terminal-closure denial example", errors)

    product_validation = validate_component_route_family_promotion_product_ownership_decision_report()
    if not product_validation.ok:
        errors.extend(
            f"component route-family promotion product ownership validation failed: {error}"
            for error in product_validation.errors
        )

    runtime_report = build_component_route_family_promotion_terminal_closure_denial_report()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_terminal_denial_semantics(example, errors, _path_label(example_path))
    _validate_terminal_denial_semantics(
        runtime_report,
        errors,
        "runtime component route-family promotion terminal-closure denial",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionTerminalClosureDenialReportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        terminal_closure_decision_count=(
            int(summary.get("terminal_closure_decision_count", 0)) if isinstance(summary, dict) else 0
        ),
        terminal_closure_denial_count=(
            int(summary.get("terminal_closure_denial_count", 0)) if isinstance(summary, dict) else 0
        ),
        terminal_closure_authorization_count=(
            int(summary.get("terminal_closure_authorization_count", 0)) if isinstance(summary, dict) else 0
        ),
        terminal_certificate_mint_count=(
            int(summary.get("terminal_certificate_mint_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_terminal_closure_denial_report_validation(
    validation: ComponentRouteFamilyPromotionTerminalClosureDenialReportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic terminal-closure denial validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_terminal_denial_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "terminal_closure_decision_state": "denied_pending_terminal_closure_certificate",
        "promotion_decision": "blocked_terminal_closure_not_authorized",
        "product_ownership_decision_state": "denied_pending_product_specific_ownership_witness",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "terminal_closure_denial_issued",
        "terminal_closure_denial_is_not_terminal_certificate",
        "terminal_closure_denial_is_not_terminal_closure",
        "terminal_closure_denial_is_not_promotion_approval",
        "terminal_closure_denial_is_not_authority_grant",
        "foundation_fixture_decision_is_not_live_operator_evidence",
        "separate_terminal_closure_certificate_required",
        "separate_product_ownership_witness_required",
        "separate_authority_upgrade_witness_required",
        "separate_lifecycle_transition_receipt_required",
        "separate_route_binding_receipt_required",
        "separate_router_inventory_delta_required",
        "terminal_closure_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "terminal_closure_authorized",
        "terminal_certificate_minted",
        "terminal_closure_witness_emitted",
        "terminal_closure_claimed",
        "promotion_approved",
        "product_ownership_authorized",
        "product_bundle_binding_authorized",
        "product_ownership_witness_emitted",
        "product_route_ownership_bound",
        "route_family_ownership_authorized",
        "authority_upgrade_authorized",
        "authority_level_changed",
        "authority_witness_emitted",
        "authority_envelope_mutated",
        "authority_granted",
        "lifecycle_transition_authorized",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
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
        "terminal_closure_certificate_refs",
        "terminal_closure_witness_refs",
        "terminal_closure_refs",
        "promotion_approval_refs",
        "product_ownership_witness_refs",
        "product_bundle_binding_refs",
        "authority_upgrade_witness_refs",
        "authority_envelope_mutation_refs",
        "authority_grant_refs",
        "lifecycle_transition_receipt_refs",
        "route_binding_receipt_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate terminal evidence exists")

    decisions = report.get("terminal_closure_decisions")
    summary = report.get("summary")
    if not isinstance(decisions, list) or len(decisions) != 1:
        errors.append(f"{label}: terminal_closure_decisions must contain exactly one decision")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    decision = decisions[0]
    if not isinstance(decision, dict):
        errors.append(f"{label}: terminal_closure_decisions entries must be objects")
        return
    _validate_terminal_decision(decision, errors, label)

    if _string_list(report.get("terminal_closure_decision_refs")) != [str(decision.get("terminal_closure_decision_id"))]:
        errors.append(f"{label}: terminal_closure_decision_refs must match terminal_closure_decision_id")
    if _string_list(report.get("source_product_ownership_decision_refs")) != [
        str(decision.get("source_product_ownership_decision_id"))
    ]:
        errors.append(f"{label}: source_product_ownership_decision_refs must match source product decision id")
    if _string_list(report.get("source_authority_upgrade_decision_refs")) != [
        str(decision.get("source_authority_upgrade_decision_id"))
    ]:
        errors.append(f"{label}: source_authority_upgrade_decision_refs must match source authority-upgrade id")
    authority_fuse_refs = _string_list(report.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        errors.append(f"{label}: authority_fuse_refs must contain exactly one component authority-fuse ref")
    if _string_list(report.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: authority_fuse_blocking_refs must match authority_fuse_refs")
    if _string_list(decision.get("authority_fuse_refs")) != authority_fuse_refs:
        errors.append(f"{label}: terminal decision authority_fuse_refs must match report authority_fuse_refs")
    if _string_list(decision.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: terminal decision authority_fuse_blocking_refs must match report authority_fuse_refs")

    if set(_string_list(report.get("required_followup_decisions"))) != REQUIRED_FOLLOWUP_DECISIONS:
        errors.append(f"{label}: required_followup_decisions must match terminal follow-up set")
    if set(_string_list(report.get("missing_terminal_closure_witnesses"))) != MISSING_TERMINAL_CLOSURE_WITNESSES:
        errors.append(f"{label}: missing_terminal_closure_witnesses must match terminal witness set")

    expected_counts = {
        "terminal_closure_decision_count": 1,
        "terminal_closure_denial_count": 1 if decision.get("decision_state") == "denied" else 0,
        "terminal_closure_authorization_count": 1 if decision.get("terminal_closure_authorized") is True else 0,
        "terminal_certificate_mint_count": 1 if decision.get("terminal_certificate_minted") is True else 0,
        "terminal_closure_witness_count": len(_string_list(decision.get("terminal_closure_witness_refs"))),
        "terminal_closure_claim_count": 1 if decision.get("terminal_closure_claimed") is True else 0,
        "promotion_approval_count": 1 if decision.get("promotion_approved") is True else 0,
        "product_ownership_authorization_count": 1 if decision.get("product_ownership_authorized") is True else 0,
        "authority_upgrade_authorization_count": 1 if decision.get("authority_upgrade_authorized") is True else 0,
        "authority_grant_count": 1 if decision.get("authority_granted") is True else 0,
        "lifecycle_transition_authorization_count": 1 if decision.get("lifecycle_transition_authorized") is True else 0,
        "route_binding_authorization_count": 1 if decision.get("route_binding_authorized") is True else 0,
        "router_inventory_mutation_count": 1 if decision.get("mutates_router_inventory") is True else 0,
        "selected_component_binding_count": 1 if decision.get("selected_component_binding_authorized") is True else 0,
        "accepted_evidence_count": len(_string_list(decision.get("accepted_evidence_refs"))),
        "rejected_evidence_count": len(_string_list(decision.get("rejected_evidence_refs"))),
        "authority_fuse_blocking_count": len(_string_list(decision.get("authority_fuse_blocking_refs"))),
        "approval_artifact_requirement_count": len(_string_list(report.get("approval_evidence_required"))),
        "required_followup_decision_count": len(_string_list(report.get("required_followup_decisions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match terminal-closure decision")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")


def _validate_terminal_decision(decision: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "gate_id": "terminal_closure_gate",
        "product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "record_kind": "terminal_closure",
        "decision_state": "denied",
        "decision_basis": "product_ownership_decision_denial",
        "proof_state": "Pass",
    }
    for field_name, expected_value in expected_strings.items():
        if decision.get(field_name) != expected_value:
            errors.append(f"{label}: terminal decision {field_name} must be {expected_value}")
    for field_name in (
        "source_product_ownership_decision_denied",
        "authority_fuse_blocks_promotion",
        "requires_external_authority_upgrade_evidence",
        "requires_terminal_closure_certificate",
        "requires_product_ownership_witness",
        "requires_authority_upgrade_witness",
        "requires_lifecycle_transition_receipt",
        "requires_component_route_binding_receipt",
        "requires_router_inventory_delta",
        "decision_is_not_terminal_certificate",
        "decision_is_not_terminal_closure",
        "decision_is_not_promotion_approval",
        "decision_is_not_authority_grant",
        "foundation_fixture_decision_is_not_live_operator_evidence",
    ):
        if decision.get(field_name) is not True:
            errors.append(f"{label}: terminal decision {field_name} must be true")
    for field_name in (
        "terminal_closure_authorized",
        "terminal_certificate_minted",
        "terminal_closure_witness_emitted",
        "terminal_closure_claimed",
        "promotion_approved",
        "product_ownership_authorized",
        "authority_upgrade_authorized",
        "authority_granted",
        "lifecycle_transition_authorized",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if decision.get(field_name) is not False:
            errors.append(f"{label}: terminal decision {field_name} must be false")
    if _string_list(decision.get("source_product_ownership_decision_refs")) != [
        str(decision.get("source_product_ownership_decision_id"))
    ]:
        errors.append(f"{label}: source_product_ownership_decision_refs must contain only the source product id")
    if _string_list(decision.get("source_authority_upgrade_decision_refs")) != [
        str(decision.get("source_authority_upgrade_decision_id"))
    ]:
        errors.append(f"{label}: source_authority_upgrade_decision_refs must contain only the source authority id")
    authority_fuse_refs = _string_list(decision.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        errors.append(f"{label}: terminal decision authority_fuse_refs must contain exactly one component authority-fuse ref")
    if _string_list(decision.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: terminal decision authority_fuse_blocking_refs must match authority_fuse_refs")
    for field_name in (
        "terminal_closure_certificate_refs",
        "terminal_closure_witness_refs",
        "terminal_closure_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(decision.get(field_name)):
            errors.append(f"{label}: terminal decision {field_name} must remain empty")
    if set(_string_list(decision.get("missing_terminal_closure_witnesses"))) != MISSING_TERMINAL_CLOSURE_WITNESSES:
        errors.append(f"{label}: missing_terminal_closure_witnesses must match terminal witness set")
    if not decision.get("decision_reason"):
        errors.append(f"{label}: terminal decision must carry decision_reason")


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
    """Parse terminal-closure denial report validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness terminal-closure denial report.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for terminal-closure denial report validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_terminal_closure_denial_report_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION TERMINAL CLOSURE DENIAL REPORT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
