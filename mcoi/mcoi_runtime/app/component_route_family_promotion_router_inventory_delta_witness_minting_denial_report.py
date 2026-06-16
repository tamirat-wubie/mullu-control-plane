"""Build router-inventory delta witness minting denial reports.

Purpose: consume a blocked router-inventory delta witness minting preflight and
record a denial-only minting decision without minting a witness, applying a
delta, mutating router inventory, granting authority, approving promotion, or
claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta witness
minting preflight report.
Invariants:
  - A minting denial report is not a router-inventory delta witness.
  - A blocked minting preflight cannot authorize witness minting.
  - Denial decisions cannot mutate router inventory or grant authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_preflight import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError,
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_requirements_receipt",
    "selected_component_bound_router_inventory_delta_witness_denial",
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


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(ValueError):
    """Raised when a router-inventory delta witness minting denial report cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    minting_preflight_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only witness minting decision report.

    Input contract: target proof surface, component, product bundle, and
    optional witness minting preflight report. Output contract:
    JSON-serializable denial report. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError
    when the source preflight is unavailable, malformed, target-mismatched, or
    no longer blocked and denial-only.
    """

    preflight_report = minting_preflight_report or _build_minting_preflight_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_minting_preflight_report(preflight_report, surface_id, component_id, product_bundle_id)
    source_checks = _source_preflight_checks(preflight_report)
    source_preflight_id = _required_text(
        preflight_report,
        "witness_minting_preflight_id",
        "router-inventory delta witness minting preflight",
    )
    denial_decision = _denial_decision(
        source_preflight_id=source_preflight_id,
        source_checks=source_checks,
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "witness_minting_denial_report_id": (
            f"component_route_family_promotion_router_inventory_delta_witness_minting_denial_report."
            f"{surface_id}.v1"
        ),
        "mode": str(preflight_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "denial_report_state": "denied_requirements_unmet",
        "source_minting_preflight_state": "blocked_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_denied",
        "denial_report_issued": True,
        "denial_report_is_not_delta": True,
        "denial_report_is_not_evidence": True,
        "denial_report_is_not_witness": True,
        "denial_report_is_not_route_binding": True,
        "denial_report_is_not_authority_grant": True,
        "denial_report_is_not_promotion_approval": True,
        "denial_report_is_not_terminal_closure": True,
        "minting_preflight_required": True,
        "minting_preflight_present": True,
        "requirements_unmet": True,
        "hard_constraint_unknown_blocks_minting": True,
        "witness_minting_denied": True,
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
            "router_inventory_delta_witness_minting_preflight": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight."
                "governed_connector_framework.json"
            ),
            "router_inventory_delta_witness_requirements": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_requirements."
                "governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(denial_decision, source_checks),
        "minting_denial_decisions": [denial_decision],
        "minting_denial_decision_refs": [str(denial_decision["denial_decision_id"])],
        "source_minting_preflight_refs": [source_preflight_id],
        "source_minting_preflight_check_refs": [str(check["check_id"]) for check in source_checks],
        "router_inventory_delta_witness_denial_refs": [str(denial_decision["denial_decision_id"])],
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
        "missing_witness_requirements": list(WITNESS_REQUIREMENTS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validator",
            "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_tests",
            "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validator",
        ],
        "next_action": (
            "Keep the router-inventory delta witness denied until the minting preflight is replaced by "
            "a separately authorized satisfied preflight with live evidence refs."
        ),
    }


def _build_minting_preflight_report(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingPreflightError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(str(exc)) from exc


def _validate_minting_preflight_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "minting_preflight_state": "blocked_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_preflight",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
                f"witness minting denial requires preflight {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
            "router-inventory delta witness minting preflight target does not match denial report"
        )
    for field_name in (
        "witness_minting_authorized",
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
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
                f"witness minting preflight must keep {field_name} false before denial report"
            )


def _source_preflight_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = report.get("minting_preflight_checks")
    if not isinstance(checks, list):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
            "minting preflight checks must be a list"
        )
    if len(checks) != len(WITNESS_REQUIREMENTS) or not all(isinstance(check, dict) for check in checks):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
            "witness minting denial requires exactly six minting preflight checks"
        )
    for check in checks:
        if check.get("check_state") != "blocked":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
                "source minting preflight checks must remain blocked"
            )
        if check.get("proof_state") != "Unknown":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
                "source minting preflight checks must keep Unknown proof state"
            )
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
                raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
                    f"source minting preflight check must keep {field_name} false"
                )
    return checks


def _denial_decision(
    *,
    source_preflight_id: str,
    source_checks: list[dict[str, Any]],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    source_check_refs = [str(check["check_id"]) for check in source_checks]
    return {
        "denial_decision_id": (
            f"router_inventory_delta_witness_minting_denial.{surface_id}.{component_id}.v1"
        ),
        "source_minting_preflight_id": source_preflight_id,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision_state": "denied",
        "decision_basis": "minting_preflight_blocked_requirements_unmet",
        "proof_state": "Pass",
        "source_preflight_blocked": True,
        "requirements_unmet": True,
        "hard_constraint_unknown_blocks_minting": True,
        "witness_minting_denied": True,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "selected_component_binding_created": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_claimed": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "decision_is_not_witness": True,
        "decision_is_not_delta": True,
        "decision_is_not_evidence": True,
        "decision_is_not_authority_grant": True,
        "decision_is_not_promotion_approval": True,
        "decision_is_not_terminal_closure": True,
        "source_minting_preflight_refs": [source_preflight_id],
        "source_minting_preflight_check_refs": source_check_refs,
        "router_inventory_delta_witness_refs": [],
        "router_inventory_delta_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "missing_witness_requirements": list(WITNESS_REQUIREMENTS),
        "decision_reason": (
            "router-inventory delta witness minting is denied because all source minting preflight "
            "checks remain blocked by Unknown hard requirements"
        ),
    }


def _summary(denial_decision: dict[str, Any], source_checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "source_minting_preflight_count": 1,
        "source_preflight_check_count": len(source_checks),
        "source_blocked_check_count": sum(1 for check in source_checks if check["check_state"] == "blocked"),
        "source_unknown_proof_state_count": sum(1 for check in source_checks if check["proof_state"] == "Unknown"),
        "denial_decision_count": 1,
        "denied_decision_count": 1 if denial_decision["decision_state"] == "denied" else 0,
        "witness_minting_denial_count": 1 if denial_decision["witness_minting_denied"] is True else 0,
        "witness_minting_authorization_count": (
            1 if denial_decision["witness_minting_authorized"] is True else 0
        ),
        "witness_mint_count": 1 if denial_decision["witness_minted"] is True else 0,
        "applied_delta_count": 1 if denial_decision["delta_applied"] is True else 0,
        "router_inventory_mutation_count": 1 if denial_decision["router_inventory_mutated"] is True else 0,
        "selected_component_binding_count": (
            1 if denial_decision["selected_component_binding_created"] is True else 0
        ),
        "authority_grant_count": 1 if denial_decision["authority_granted"] is True else 0,
        "promotion_approval_count": 1 if denial_decision["promotion_approved"] is True else 0,
        "terminal_closure_claim_count": 1 if denial_decision["terminal_closure_claimed"] is True else 0,
        "accepted_evidence_count": len(denial_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(denial_decision["rejected_evidence_refs"]),
        "missing_witness_requirement_count": len(denial_decision["missing_witness_requirements"]),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError(
            f"{label} must carry {field_name}"
        )
    return value
