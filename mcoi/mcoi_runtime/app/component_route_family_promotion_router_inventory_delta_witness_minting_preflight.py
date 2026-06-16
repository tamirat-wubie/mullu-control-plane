"""Build router-inventory delta witness minting preflight reports.

Purpose: consume router-inventory delta witness requirements and deny witness
minting while any required evidence, authorization, or terminal certificate is
absent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta witness
requirements report.
Invariants:
  - A minting preflight is not a router-inventory delta witness.
  - Unmet requirements cannot authorize witness minting.
  - The preflight cannot apply deltas, mutate router inventory, grant
    authority, approve promotion, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_requirements import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError,
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_requirements,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_requirements_receipt",
    "component_route_family_promotion_router_inventory_delta_candidate_receipt",
    "selected_component_bound_router_inventory_delta_witness",
    *WITNESS_REQUIREMENTS,
)
BLOCKED_ACTIONS = (
    "autonomous_execution",
    "connector_call",
    "external_send",
    "filesystem_write",
    "live_dispatch",
    "route_execution",
    "router_inventory_mutation",
    "runtime_mutation",
    "selected_component_binding",
    "terminal_closure",
    "witness_minting",
)


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(ValueError):
    """Raised when a router-inventory delta witness minting preflight cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    witness_requirements_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only witness minting preflight.

    Input contract: target proof surface, component, product bundle, and
    optional witness requirements report. Output contract: JSON-serializable
    minting preflight report. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError
    when the source requirements are unavailable, malformed, target-mismatched,
    or no longer unmet and denial-only.
    """

    requirements_report = witness_requirements_report or _build_requirements_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_requirements_report(requirements_report, surface_id, component_id, product_bundle_id)
    source_requirements = _source_requirements(requirements_report)
    preflight_checks = [
        _preflight_check(requirement, surface_id, component_id, product_bundle_id)
        for requirement in source_requirements
    ]
    check_refs = [str(check["check_id"]) for check in preflight_checks]
    source_requirement_refs = [str(requirement["requirement_id"]) for requirement in source_requirements]
    source_report_id = _required_text(
        requirements_report,
        "witness_requirements_report_id",
        "router-inventory delta witness requirements report",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "witness_minting_preflight_id": (
            f"component_route_family_promotion_router_inventory_delta_witness_minting_preflight.{surface_id}.v1"
        ),
        "mode": str(requirements_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "minting_preflight_state": "blocked_requirements_unmet",
        "source_witness_requirements_status": "requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_preflight",
        "minting_preflight_issued": True,
        "minting_preflight_is_not_delta": True,
        "minting_preflight_is_not_evidence": True,
        "minting_preflight_is_not_witness": True,
        "minting_preflight_is_not_route_binding": True,
        "minting_preflight_is_not_authority_grant": True,
        "minting_preflight_is_not_promotion_approval": True,
        "minting_preflight_is_not_terminal_closure": True,
        "requirements_report_required": True,
        "requirements_report_present": True,
        "requirements_unmet": True,
        "hard_constraint_unknown_blocks_minting": True,
        "separate_router_inventory_delta_witness_required": True,
        "separate_operator_approval_required": True,
        "separate_route_binding_authorization_required": True,
        "separate_lifecycle_transition_authorization_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_product_ownership_witness_required": True,
        "separate_terminal_closure_certificate_required": True,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "selected_component_binding_created": False,
        "route_binding_authorized": False,
        "lifecycle_transition_authorized": False,
        "authority_upgrade_authorized": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_certificate_minted": False,
        "terminal_closure_authorized": False,
        "terminal_closure_claimed": False,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "router_inventory_delta_witness_requirements": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_requirements."
                "governed_connector_framework.json"
            ),
            "router_inventory_delta_candidate": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_candidate.governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(preflight_checks),
        "minting_preflight_checks": preflight_checks,
        "minting_preflight_check_refs": check_refs,
        "source_witness_requirements_report_refs": [source_report_id],
        "source_witness_requirement_refs": source_requirement_refs,
        "router_inventory_delta_witness_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "route_binding_authorization_refs": [],
        "lifecycle_transition_authorization_refs": [],
        "authority_upgrade_witness_refs": [],
        "authority_grant_refs": [],
        "product_ownership_witness_refs": [],
        "terminal_closure_certificate_refs": [],
        "terminal_closure_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validator",
            "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_tests",
            "component_route_family_promotion_router_inventory_delta_witness_requirements_validator",
        ],
        "next_action": (
            "Keep router-inventory delta witness minting blocked until all source requirements have "
            "separate satisfied evidence and authorization refs."
        ),
    }


def _build_requirements_report(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_witness_requirements(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(str(exc)) from exc


def _validate_requirements_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "witness_status": "requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_not_authorized",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
                f"witness minting preflight requires requirements report {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
            "router-inventory delta witness requirements target does not match minting preflight"
        )
    for field_name in (
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "selected_component_binding_created",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
                f"witness requirements report must keep {field_name} false before minting preflight"
            )


def _source_requirements(report: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = report.get("witness_requirements")
    if not isinstance(requirements, list):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
            "witness requirements must be a list"
        )
    if len(requirements) != len(WITNESS_REQUIREMENTS) or not all(
        isinstance(requirement, dict) for requirement in requirements
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
            "witness minting preflight requires exactly six witness requirements"
        )
    for requirement in requirements:
        if requirement.get("requirement_state") != "unmet":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
                "source witness requirements must remain unmet"
            )
        if requirement.get("proof_state") != "Unknown":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
                "source witness requirements must keep Unknown proof state"
            )
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
                raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
                    f"source witness requirement must keep {field_name} false"
                )
    return requirements


def _preflight_check(
    source_requirement: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    requirement_artifact = _required_text(source_requirement, "requirement_artifact", "source requirement")
    source_requirement_id = _required_text(source_requirement, "requirement_id", "source requirement")
    return {
        "check_id": f"router_inventory_delta_witness_minting_preflight.{surface_id}.{requirement_artifact}.v1",
        "requirement_artifact": requirement_artifact,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "source_requirement_id": source_requirement_id,
        "source_requirement_refs": [source_requirement_id],
        "check_state": "blocked",
        "proof_state": "Unknown",
        "required": True,
        "satisfied": False,
        "evidence_present": False,
        "authorization_present": False,
        "hard_constraint_unknown_blocks_minting": True,
        "blocks_witness_minting": True,
        "blocks_promotion": True,
        "check_is_not_evidence": True,
        "check_is_not_authorization": True,
        "check_is_not_witness": True,
        "check_is_not_delta": True,
        "check_is_not_authority_grant": True,
        "check_is_not_promotion_approval": True,
        "check_is_not_terminal_closure": True,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "selected_component_binding_created": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_claimed": False,
        "evidence_refs": [],
        "authorization_refs": [],
        "witness_refs": [],
        "router_inventory_delta_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": (
            f"{requirement_artifact} remains unmet, so router-inventory delta witness minting is blocked"
        ),
    }


def _summary(preflight_checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "source_requirements_report_count": 1,
        "minting_preflight_count": 1,
        "preflight_check_count": len(preflight_checks),
        "blocked_check_count": sum(1 for check in preflight_checks if check["check_state"] == "blocked"),
        "satisfied_check_count": sum(1 for check in preflight_checks if check["satisfied"] is True),
        "unknown_proof_state_count": sum(1 for check in preflight_checks if check["proof_state"] == "Unknown"),
        "present_evidence_count": sum(1 for check in preflight_checks if check["evidence_present"] is True),
        "authorization_present_count": sum(
            1 for check in preflight_checks if check["authorization_present"] is True
        ),
        "witness_minting_authorization_count": sum(
            1 for check in preflight_checks if check["witness_minting_authorized"] is True
        ),
        "witness_mint_count": sum(1 for check in preflight_checks if check["witness_minted"] is True),
        "applied_delta_count": sum(1 for check in preflight_checks if check["delta_applied"] is True),
        "router_inventory_mutation_count": sum(
            1 for check in preflight_checks if check["router_inventory_mutated"] is True
        ),
        "selected_component_binding_count": sum(
            1 for check in preflight_checks if check["selected_component_binding_created"] is True
        ),
        "authority_grant_count": sum(1 for check in preflight_checks if check["authority_granted"] is True),
        "promotion_approval_count": sum(1 for check in preflight_checks if check["promotion_approved"] is True),
        "terminal_closure_claim_count": sum(
            1 for check in preflight_checks if check["terminal_closure_claimed"] is True
        ),
        "blocking_minting_check_count": sum(
            1 for check in preflight_checks if check["blocks_witness_minting"] is True
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError(
            f"{label} must carry {field_name}"
        )
    return value
