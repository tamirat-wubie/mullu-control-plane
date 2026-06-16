"""Build router-inventory delta witness remediation plans.

Purpose: consume a router-inventory delta witness minting denial report and
declare the non-executing remediation steps required before any future witness
minting path can be reconsidered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta witness
minting denial report.
Invariants:
  - A remediation plan is not evidence, authorization, a witness, or a delta.
  - Planned remediation cannot satisfy witness requirements.
  - The plan cannot mutate router inventory, grant authority, approve
    promotion, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_denial_report import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError,
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_receipt",
    "selected_component_bound_router_inventory_delta_witness_remediation_plan",
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


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(ValueError):
    """Raised when a router-inventory delta witness remediation plan cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    minting_denial_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic non-executing witness remediation plan.

    Input contract: target proof surface, component, product bundle, and
    optional witness minting denial report. Output contract: JSON-serializable
    remediation plan. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError
    when the source denial report is unavailable, malformed,
    target-mismatched, or no longer denial-only.
    """

    denial_report = minting_denial_report or _build_denial_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_denial_report(denial_report, surface_id, component_id, product_bundle_id)
    source_denial = _source_denial_decision(denial_report)
    source_denial_id = _required_text(source_denial, "denial_decision_id", "source denial decision")
    steps = [_remediation_step(requirement, source_denial_id, surface_id, component_id, product_bundle_id) for requirement in WITNESS_REQUIREMENTS]
    return {
        "schema_version": SCHEMA_VERSION,
        "remediation_plan_id": (
            f"component_route_family_promotion_router_inventory_delta_witness_remediation_plan.{surface_id}.v1"
        ),
        "mode": str(denial_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "remediation_plan_state": "planned_not_executed",
        "source_denial_report_state": "denied_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_remediation_pending",
        "remediation_plan_issued": True,
        "remediation_plan_is_not_delta": True,
        "remediation_plan_is_not_evidence": True,
        "remediation_plan_is_not_authorization": True,
        "remediation_plan_is_not_witness": True,
        "remediation_plan_is_not_authority_grant": True,
        "remediation_plan_is_not_promotion_approval": True,
        "remediation_plan_is_not_terminal_closure": True,
        "source_denial_report_required": True,
        "source_denial_report_present": True,
        "requirements_unmet": True,
        "witness_minting_denied": True,
        "remediation_required": True,
        "remediation_executed": False,
        "evidence_submitted": False,
        "evidence_accepted": False,
        "requirements_satisfied": False,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_created": False,
        "route_binding_authorized": False,
        "lifecycle_transition_authorized": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_certificate_minted": False,
        "terminal_closure_claimed": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "router_inventory_delta_witness_minting_denial_report": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report."
                "governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(steps),
        "remediation_steps": steps,
        "remediation_step_refs": [str(step["step_id"]) for step in steps],
        "source_minting_denial_decision_refs": [source_denial_id],
        "accepted_evidence_refs": [],
        "submitted_evidence_refs": [],
        "authorization_refs": [],
        "router_inventory_delta_witness_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validator",
            "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_tests",
            "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validator",
        ],
        "next_action": (
            "Collect separate approved evidence for each remediation step before rebuilding the minting preflight."
        ),
    }


def _build_denial_report(surface_id: str, component_id: str, product_bundle_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessMintingDenialReportError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(str(exc)) from exc


def _validate_denial_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "denial_report_state": "denied_requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_minting_denied",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
                f"remediation plan requires denial report {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
            "router-inventory delta witness minting denial target does not match remediation plan"
        )
    for field_name in (
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
                f"witness minting denial report must keep {field_name} false before remediation plan"
            )


def _source_denial_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("minting_denial_decisions")
    if not isinstance(decisions, list) or len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
            "remediation plan requires exactly one minting denial decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied" or decision.get("witness_minting_denied") is not True:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
            "source minting denial decision must remain denied"
        )
    return decision


def _remediation_step(
    requirement_artifact: str,
    source_denial_id: str,
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    return {
        "step_id": f"router_inventory_delta_witness_remediation.{surface_id}.{requirement_artifact}.v1",
        "requirement_artifact": requirement_artifact,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "source_denial_decision_id": source_denial_id,
        "source_denial_decision_refs": [source_denial_id],
        "step_state": "planned",
        "proof_state": "Unknown",
        "required": True,
        "plan_only": True,
        "evidence_required": True,
        "evidence_submitted": False,
        "evidence_accepted": False,
        "authorization_present": False,
        "requirement_satisfied": False,
        "remediation_executed": False,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_claimed": False,
        "blocks_witness_minting": True,
        "blocks_promotion": True,
        "step_is_not_evidence": True,
        "step_is_not_authorization": True,
        "step_is_not_witness": True,
        "step_is_not_delta": True,
        "step_is_not_authority_grant": True,
        "step_is_not_promotion_approval": True,
        "step_is_not_terminal_closure": True,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "authorization_refs": [],
        "witness_refs": [],
        "router_inventory_delta_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": f"{requirement_artifact} requires separate approved evidence before witness minting",
    }


def _summary(steps: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "source_denial_decision_count": 1,
        "remediation_step_count": len(steps),
        "planned_step_count": sum(1 for step in steps if step["step_state"] == "planned"),
        "executed_step_count": sum(1 for step in steps if step["remediation_executed"] is True),
        "submitted_evidence_count": sum(1 for step in steps if step["evidence_submitted"] is True),
        "accepted_evidence_count": sum(1 for step in steps if step["evidence_accepted"] is True),
        "authorization_present_count": sum(1 for step in steps if step["authorization_present"] is True),
        "satisfied_requirement_count": sum(1 for step in steps if step["requirement_satisfied"] is True),
        "unknown_proof_state_count": sum(1 for step in steps if step["proof_state"] == "Unknown"),
        "witness_minting_authorization_count": sum(
            1 for step in steps if step["witness_minting_authorized"] is True
        ),
        "witness_mint_count": sum(1 for step in steps if step["witness_minted"] is True),
        "applied_delta_count": sum(1 for step in steps if step["delta_applied"] is True),
        "router_inventory_mutation_count": sum(1 for step in steps if step["router_inventory_mutated"] is True),
        "authority_grant_count": sum(1 for step in steps if step["authority_granted"] is True),
        "promotion_approval_count": sum(1 for step in steps if step["promotion_approved"] is True),
        "terminal_closure_claim_count": sum(1 for step in steps if step["terminal_closure_claimed"] is True),
        "blocking_step_count": sum(1 for step in steps if step["blocks_witness_minting"] is True),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError(
            f"{label} must carry {field_name}"
        )
    return value
