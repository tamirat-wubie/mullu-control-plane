"""Build router-inventory delta witness remediation evidence requests.

Purpose: consume a router-inventory delta witness remediation plan and expose
the exact operator evidence slots required before witness minting can be
reconsidered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta witness
remediation plan.
Invariants:
  - An evidence request is not submitted evidence or accepted evidence.
  - Request slots cannot satisfy requirements or authorize witness minting.
  - The request cannot mutate router inventory, grant authority, approve
    promotion, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_plan import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError,
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_receipt",
    "selected_component_bound_router_inventory_delta_witness_remediation_evidence_request",
    *WITNESS_REQUIREMENTS,
)
BLOCKED_ACTIONS = (
    "autonomous_execution",
    "connector_call",
    "evidence_acceptance",
    "evidence_submission",
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


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(ValueError):
    """Raised when a router-inventory delta witness remediation evidence request cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    remediation_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic request-only remediation evidence envelope.

    Input contract: target proof surface, component, product bundle, and
    optional remediation plan. Output contract: JSON-serializable evidence
    request. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError
    when the source remediation plan is unavailable, malformed,
    target-mismatched, or no longer request-only.
    """

    plan = remediation_plan or _build_remediation_plan(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_remediation_plan(plan, surface_id, component_id, product_bundle_id)
    source_plan_id = _required_text(plan, "remediation_plan_id", "source remediation plan")
    source_steps = _source_remediation_steps(plan)
    requests = [
        _evidence_request_slot(
            source_step=step,
            source_plan_id=source_plan_id,
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
        for step in source_steps
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_request_id": (
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request."
            f"{surface_id}.v1"
        ),
        "mode": str(plan.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "evidence_request_state": "requested_not_submitted",
        "source_remediation_plan_state": "planned_not_executed",
        "promotion_decision": "blocked_router_inventory_delta_witness_evidence_request_pending",
        "evidence_request_issued": True,
        "evidence_request_is_not_evidence": True,
        "evidence_request_is_not_submission": True,
        "evidence_request_is_not_acceptance": True,
        "evidence_request_is_not_authorization": True,
        "evidence_request_is_not_witness": True,
        "evidence_request_is_not_delta": True,
        "evidence_request_is_not_authority_grant": True,
        "evidence_request_is_not_promotion_approval": True,
        "evidence_request_is_not_terminal_closure": True,
        "source_remediation_plan_required": True,
        "source_remediation_plan_present": True,
        "requirements_unmet": True,
        "evidence_required": True,
        "operator_input_required": True,
        "witness_minting_denied": True,
        "evidence_submitted": False,
        "evidence_accepted": False,
        "evidence_rejected": False,
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
            "router_inventory_delta_witness_remediation_plan": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan."
                "governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(requests),
        "evidence_requests": requests,
        "evidence_request_refs": [str(request["request_id"]) for request in requests],
        "source_remediation_plan_refs": [source_plan_id],
        "source_remediation_step_refs": [str(step["step_id"]) for step in source_steps],
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
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
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_validator",
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_tests",
            "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validator",
        ],
        "next_action": "Submit separate governed evidence packets for each request slot; this request does not accept them.",
    }


def _build_remediation_plan(surface_id: str, component_id: str, product_bundle_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationPlanError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(str(exc)) from exc


def _validate_remediation_plan(
    plan: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "remediation_plan_state": "planned_not_executed",
        "promotion_decision": "blocked_router_inventory_delta_witness_remediation_pending",
    }
    for field_name, expected_value in expected_strings.items():
        if plan.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
                f"evidence request requires remediation plan {field_name}={expected_value}"
            )
    if (
        plan.get("target_surface_id") != surface_id
        or plan.get("target_component_id") != component_id
        or plan.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
            "router-inventory delta witness remediation plan target does not match evidence request"
        )
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "requirements_satisfied",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
        "ready_for_promotion",
    ):
        if plan.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
                f"remediation plan must keep {field_name} false before evidence request"
            )


def _source_remediation_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = plan.get("remediation_steps")
    if not isinstance(steps, list) or len(steps) != len(WITNESS_REQUIREMENTS):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
            "evidence request requires six remediation plan steps"
        )
    result: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
                "remediation plan steps must be objects"
            )
        if step.get("step_state") != "planned" or step.get("proof_state") != "Unknown":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
                "remediation plan steps must remain planned with Unknown proof state"
            )
        result.append(step)
    if {str(step.get("requirement_artifact")) for step in result} != set(WITNESS_REQUIREMENTS):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
            "remediation plan steps must match witness requirements"
        )
    return result


def _evidence_request_slot(
    *,
    source_step: dict[str, Any],
    source_plan_id: str,
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    requirement_artifact = _required_text(source_step, "requirement_artifact", "source remediation step")
    source_step_id = _required_text(source_step, "step_id", "source remediation step")
    return {
        "request_id": f"router_inventory_delta_witness_remediation_evidence_request.{surface_id}.{requirement_artifact}.v1",
        "requirement_artifact": requirement_artifact,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "source_remediation_plan_id": source_plan_id,
        "source_remediation_plan_refs": [source_plan_id],
        "source_remediation_step_id": source_step_id,
        "source_remediation_step_refs": [source_step_id],
        "request_state": "requested",
        "proof_state": "Unknown",
        "required": True,
        "request_only": True,
        "evidence_required": True,
        "operator_input_required": True,
        "evidence_submitted": False,
        "evidence_accepted": False,
        "evidence_rejected": False,
        "authorization_present": False,
        "requirement_satisfied": False,
        "witness_minting_authorized": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_claimed": False,
        "blocks_witness_minting": True,
        "blocks_promotion": True,
        "slot_is_not_evidence": True,
        "slot_is_not_submission": True,
        "slot_is_not_acceptance": True,
        "slot_is_not_authorization": True,
        "slot_is_not_witness": True,
        "slot_is_not_delta": True,
        "slot_is_not_authority_grant": True,
        "slot_is_not_promotion_approval": True,
        "slot_is_not_terminal_closure": True,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authorization_refs": [],
        "witness_refs": [],
        "router_inventory_delta_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "evidence_expectation": f"Submit governed evidence for {requirement_artifact} in a later evidence packet.",
        "decision_reason": f"{requirement_artifact} evidence is requested but not submitted or accepted by this artifact",
    }


def _summary(requests: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "source_remediation_plan_count": 1,
        "source_remediation_step_count": len(requests),
        "evidence_request_count": len(requests),
        "requested_slot_count": sum(1 for request in requests if request["request_state"] == "requested"),
        "operator_input_required_count": sum(1 for request in requests if request["operator_input_required"] is True),
        "submitted_evidence_count": sum(1 for request in requests if request["evidence_submitted"] is True),
        "accepted_evidence_count": sum(1 for request in requests if request["evidence_accepted"] is True),
        "rejected_evidence_count": sum(1 for request in requests if request["evidence_rejected"] is True),
        "satisfied_requirement_count": sum(1 for request in requests if request["requirement_satisfied"] is True),
        "unknown_proof_state_count": sum(1 for request in requests if request["proof_state"] == "Unknown"),
        "witness_minting_authorization_count": sum(
            1 for request in requests if request["witness_minting_authorized"] is True
        ),
        "witness_mint_count": sum(1 for request in requests if request["witness_minted"] is True),
        "applied_delta_count": sum(1 for request in requests if request["delta_applied"] is True),
        "router_inventory_mutation_count": sum(1 for request in requests if request["router_inventory_mutated"] is True),
        "authority_grant_count": sum(1 for request in requests if request["authority_granted"] is True),
        "promotion_approval_count": sum(1 for request in requests if request["promotion_approved"] is True),
        "terminal_closure_claim_count": sum(1 for request in requests if request["terminal_closure_claimed"] is True),
        "blocking_request_count": sum(1 for request in requests if request["blocks_witness_minting"] is True),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError(
            f"{label} must carry {field_name}"
        )
    return value
