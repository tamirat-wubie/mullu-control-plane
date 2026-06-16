"""Build router-inventory delta witness remediation evidence request status ledgers.

Purpose: consume a router-inventory delta witness remediation evidence request
and expose a read-only status ledger for every requested evidence slot.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta witness
remediation evidence request.
Invariants:
  - A status ledger is not evidence, submission, acceptance, authorization, a
    witness, a router-inventory delta, an authority grant, promotion approval,
    or terminal closure.
  - Status records cannot satisfy requirements or authorize witness minting.
  - The ledger cannot mutate router inventory or grant execution authority.
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
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError,
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_receipt",
    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_receipt",
    "selected_component_bound_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
    *WITNESS_REQUIREMENTS,
)
BLOCKED_ACTIONS = (
    "autonomous_execution",
    "connector_call",
    "evidence_acceptance",
    "evidence_rejection",
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


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(ValueError):
    """Raised when a remediation evidence request status ledger cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    evidence_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only status ledger for request slots.

    Input contract: target proof surface, component, product bundle, and
    optional remediation evidence request. Output contract: JSON-serializable
    status ledger. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError
    when the source evidence request is unavailable, malformed,
    target-mismatched, or no longer request-only.
    """

    request = evidence_request or _build_evidence_request(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_evidence_request(request, surface_id, component_id, product_bundle_id)
    source_request_id = _required_text(request, "evidence_request_id", "source evidence request")
    request_slots = _source_request_slots(request)
    status_records = [
        _status_record(
            source_slot=slot,
            source_request_id=source_request_id,
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
        for slot in request_slots
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_id": (
            "component_route_family_promotion_router_inventory_delta_witness_remediation_"
            f"evidence_request_status_ledger.{surface_id}.v1"
        ),
        "mode": str(request.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "ledger_state": "request_status_only",
        "source_evidence_request_state": "requested_not_submitted",
        "promotion_decision": "blocked_router_inventory_delta_witness_evidence_request_status_pending",
        "status_ledger_issued": True,
        "status_ledger_is_not_evidence": True,
        "status_ledger_is_not_submission": True,
        "status_ledger_is_not_acceptance": True,
        "status_ledger_is_not_rejection": True,
        "status_ledger_is_not_authorization": True,
        "status_ledger_is_not_witness": True,
        "status_ledger_is_not_delta": True,
        "status_ledger_is_not_authority_grant": True,
        "status_ledger_is_not_promotion_approval": True,
        "status_ledger_is_not_terminal_closure": True,
        "source_evidence_request_required": True,
        "source_evidence_request_present": True,
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
            "router_inventory_delta_witness_remediation_evidence_request": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request."
                "governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(status_records),
        "status_records": status_records,
        "status_record_refs": [str(record["status_record_id"]) for record in status_records],
        "source_evidence_request_refs": [source_request_id],
        "source_evidence_request_slot_refs": [str(slot["request_id"]) for slot in request_slots],
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
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validator",
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_tests",
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_validator",
        ],
        "next_action": "Submit governed evidence packets separately; this ledger only reports unresolved request status.",
    }


def _build_evidence_request(surface_id: str, component_id: str, product_bundle_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
            str(exc)
        ) from exc


def _validate_evidence_request(
    request: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "evidence_request_state": "requested_not_submitted",
        "promotion_decision": "blocked_router_inventory_delta_witness_evidence_request_pending",
    }
    for field_name, expected_value in expected_strings.items():
        if request.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
                f"status ledger requires evidence request {field_name}={expected_value}"
            )
    if (
        request.get("target_surface_id") != surface_id
        or request.get("target_component_id") != component_id
        or request.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
            "router-inventory delta witness remediation evidence request target does not match status ledger"
        )
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
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
        if request.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
                f"evidence request must keep {field_name} false before status ledger"
            )


def _source_request_slots(request: dict[str, Any]) -> list[dict[str, Any]]:
    slots = request.get("evidence_requests")
    if not isinstance(slots, list) or len(slots) != len(WITNESS_REQUIREMENTS):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
            "status ledger requires six evidence request slots"
        )
    result: list[dict[str, Any]] = []
    for slot in slots:
        if not isinstance(slot, dict):
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
                "evidence request slots must be objects"
            )
        if slot.get("request_state") != "requested" or slot.get("proof_state") != "Unknown":
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
                "evidence request slots must remain requested with Unknown proof state"
            )
        result.append(slot)
    if {str(slot.get("requirement_artifact")) for slot in result} != set(WITNESS_REQUIREMENTS):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
            "evidence request slots must match witness requirements"
        )
    return result


def _status_record(
    *,
    source_slot: dict[str, Any],
    source_request_id: str,
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    requirement_artifact = _required_text(source_slot, "requirement_artifact", "source evidence request slot")
    source_slot_id = _required_text(source_slot, "request_id", "source evidence request slot")
    return {
        "status_record_id": f"router_inventory_delta_witness_remediation_evidence_request_status.{surface_id}.{requirement_artifact}.v1",
        "requirement_artifact": requirement_artifact,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "source_evidence_request_id": source_request_id,
        "source_evidence_request_refs": [source_request_id],
        "source_evidence_request_slot_id": source_slot_id,
        "source_evidence_request_slot_refs": [source_slot_id],
        "status": "awaiting_operator_evidence",
        "proof_state": "Unknown",
        "required": True,
        "status_only": True,
        "evidence_required": True,
        "operator_input_required": True,
        "blocks_witness_minting": True,
        "blocks_promotion": True,
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
        "status_is_not_evidence": True,
        "status_is_not_submission": True,
        "status_is_not_acceptance": True,
        "status_is_not_rejection": True,
        "status_is_not_authorization": True,
        "status_is_not_witness": True,
        "status_is_not_delta": True,
        "status_is_not_authority_grant": True,
        "status_is_not_promotion_approval": True,
        "status_is_not_terminal_closure": True,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authorization_refs": [],
        "witness_refs": [],
        "router_inventory_delta_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": f"{requirement_artifact} remains awaiting operator evidence; no evidence is recorded here",
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "source_evidence_request_count": 1,
        "source_evidence_request_slot_count": len(records),
        "status_record_count": len(records),
        "awaiting_operator_evidence_count": sum(
            1 for record in records if record["status"] == "awaiting_operator_evidence"
        ),
        "operator_input_required_count": sum(1 for record in records if record["operator_input_required"] is True),
        "submitted_evidence_count": sum(1 for record in records if record["evidence_submitted"] is True),
        "accepted_evidence_count": sum(1 for record in records if record["evidence_accepted"] is True),
        "rejected_evidence_count": sum(1 for record in records if record["evidence_rejected"] is True),
        "satisfied_requirement_count": sum(1 for record in records if record["requirement_satisfied"] is True),
        "unknown_proof_state_count": sum(1 for record in records if record["proof_state"] == "Unknown"),
        "witness_minting_authorization_count": sum(
            1 for record in records if record["witness_minting_authorized"] is True
        ),
        "witness_mint_count": sum(1 for record in records if record["witness_minted"] is True),
        "applied_delta_count": sum(1 for record in records if record["delta_applied"] is True),
        "router_inventory_mutation_count": sum(1 for record in records if record["router_inventory_mutated"] is True),
        "authority_grant_count": sum(1 for record in records if record["authority_granted"] is True),
        "promotion_approval_count": sum(1 for record in records if record["promotion_approved"] is True),
        "terminal_closure_claim_count": sum(1 for record in records if record["terminal_closure_claimed"] is True),
        "blocking_status_count": sum(1 for record in records if record["blocks_witness_minting"] is True),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerError(
            f"{label} must carry {field_name}"
        )
    return value
