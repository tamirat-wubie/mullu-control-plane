"""Build router-inventory delta witness requirement reports.

Purpose: consume dry-run router-inventory delta candidates and declare the
requirements for minting a selected-component router-inventory delta witness
without minting that witness, applying a delta, mutating router inventory,
granting authority, approving promotion, or claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion router-inventory delta
candidate report.
Invariants:
  - Witness requirements are not a router-inventory delta witness.
  - Requirement records cannot satisfy themselves.
  - Router inventory remains unchanged until a separate governed witness path
    authorizes and emits the delta.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_candidate import (
    ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError,
    build_component_route_family_promotion_router_inventory_delta_candidate,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
WITNESS_REQUIREMENTS = (
    "router_inventory_delta_operator_approval",
    "component_route_binding_authorization",
    "component_lifecycle_transition_authorization",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_certificate",
)
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_witness_requirements_receipt",
    "component_route_family_promotion_router_inventory_delta_candidate_receipt",
    "selected_component_bound_router_inventory_delta",
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


class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(ValueError):
    """Raised when router-inventory delta witness requirements cannot compile."""


def build_component_route_family_promotion_router_inventory_delta_witness_requirements(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    router_inventory_delta_candidate_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic unmet requirements for the delta witness path.

    Input contract: target proof surface, component, product bundle, and
    optional router-inventory delta candidate report. Output contract:
    JSON-serializable requirements report. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError
    when the source candidate is unavailable, malformed, target-mismatched, or
    no longer dry-run only.
    """

    candidate_report = router_inventory_delta_candidate_report or _build_candidate_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_candidate_report(candidate_report, surface_id, component_id, product_bundle_id)
    source_candidate = _source_candidate(candidate_report)
    requirements = [
        _requirement_record(requirement_id, source_candidate, surface_id, component_id, product_bundle_id)
        for requirement_id in WITNESS_REQUIREMENTS
    ]
    requirement_refs = [str(record["requirement_id"]) for record in requirements]
    return {
        "schema_version": SCHEMA_VERSION,
        "witness_requirements_report_id": (
            f"component_route_family_promotion_router_inventory_delta_witness_requirements.{surface_id}.v1"
        ),
        "mode": str(candidate_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "witness_status": "requirements_unmet",
        "promotion_decision": "blocked_router_inventory_delta_witness_not_authorized",
        "requirements_report_issued": True,
        "requirements_report_is_not_delta": True,
        "requirements_report_is_not_evidence": True,
        "requirements_report_is_not_witness": True,
        "requirements_report_is_not_route_binding": True,
        "requirements_report_is_not_authority_grant": True,
        "requirements_report_is_not_promotion_approval": True,
        "requirements_report_is_not_terminal_closure": True,
        "separate_router_inventory_delta_witness_required": True,
        "separate_operator_approval_required": True,
        "separate_route_binding_authorization_required": True,
        "separate_lifecycle_transition_authorization_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_product_ownership_witness_required": True,
        "separate_terminal_closure_certificate_required": True,
        "dry_run_candidate_required": True,
        "dry_run_candidate_present": True,
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
            "router_inventory_delta_candidate": (
                "examples/"
                "component_route_family_promotion_router_inventory_delta_candidate.governed_connector_framework.json"
            ),
            "missing_evidence_ledger": (
                "examples/"
                "component_route_family_promotion_missing_evidence_ledger.governed_connector_framework.json"
            ),
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(requirements),
        "witness_requirements": requirements,
        "witness_requirement_refs": requirement_refs,
        "source_router_inventory_delta_candidate_refs": [str(source_candidate["candidate_id"])],
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
            "component_route_family_promotion_router_inventory_delta_witness_requirements_validator",
            "component_route_family_promotion_router_inventory_delta_witness_requirements_tests",
            "component_route_family_promotion_router_inventory_delta_candidate_validator",
        ],
        "next_action": (
            "Keep witness minting blocked until all requirement records are replaced by separate "
            "approved evidence and authorization refs."
        ),
    }


def _build_candidate_report(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_router_inventory_delta_candidate(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(str(exc)) from exc


def _validate_candidate_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "candidate_status": "draft_not_applied",
        "promotion_decision": "blocked_router_inventory_delta_not_applied",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
                f"witness requirements require candidate {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            "router-inventory delta candidate target does not match witness requirements"
        )
    for field_name in (
        "delta_applied",
        "router_inventory_mutated",
        "selected_component_binding_created",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
                f"router-inventory delta candidate must keep {field_name} false before witness requirements"
            )


def _source_candidate(report: dict[str, Any]) -> dict[str, Any]:
    candidates = report.get("router_inventory_delta_candidates")
    if not isinstance(candidates, list):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            "router-inventory delta candidates must be a list"
        )
    if len(candidates) != 1 or not isinstance(candidates[0], dict):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            "witness requirements require exactly one router-inventory delta candidate"
        )
    candidate = candidates[0]
    if candidate.get("candidate_state") != "draft_not_applied" or candidate.get("dry_run_only") is not True:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            "source router-inventory delta candidate must remain dry-run draft"
        )
    if candidate.get("delta_applied") is not False or candidate.get("router_inventory_mutated") is not False:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            "source router-inventory delta candidate must not apply delta or mutate router inventory"
        )
    return candidate


def _requirement_record(
    requirement_artifact: str,
    source_candidate: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    source_candidate_id = _required_text(source_candidate, "candidate_id", "source candidate")
    return {
        "requirement_id": f"router_inventory_delta_witness_requirement.{surface_id}.{requirement_artifact}.v1",
        "requirement_artifact": requirement_artifact,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "source_candidate_id": source_candidate_id,
        "source_candidate_refs": [source_candidate_id],
        "requirement_state": "unmet",
        "proof_state": "Unknown",
        "hard_constraint_unknown_blocks_witness": True,
        "required": True,
        "satisfied": False,
        "evidence_present": False,
        "authorization_present": False,
        "witness_minted": False,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "selected_component_binding_created": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_claimed": False,
        "blocks_witness_minting": True,
        "blocks_promotion": True,
        "record_is_not_evidence": True,
        "record_is_not_authorization": True,
        "record_is_not_witness": True,
        "record_is_not_delta": True,
        "record_is_not_authority_grant": True,
        "record_is_not_promotion_approval": True,
        "record_is_not_terminal_closure": True,
        "evidence_refs": [],
        "authorization_refs": [],
        "witness_refs": [],
        "router_inventory_delta_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": (
            f"{requirement_artifact} is required before minting selected-component router-inventory delta witness"
        ),
    }


def _summary(requirements: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "requirement_count": len(requirements),
        "unmet_requirement_count": sum(1 for record in requirements if record["requirement_state"] == "unmet"),
        "satisfied_requirement_count": sum(1 for record in requirements if record["satisfied"] is True),
        "unknown_proof_state_count": sum(1 for record in requirements if record["proof_state"] == "Unknown"),
        "present_evidence_count": sum(1 for record in requirements if record["evidence_present"] is True),
        "authorization_present_count": sum(
            1 for record in requirements if record["authorization_present"] is True
        ),
        "witness_mint_count": sum(1 for record in requirements if record["witness_minted"] is True),
        "applied_delta_count": sum(1 for record in requirements if record["delta_applied"] is True),
        "router_inventory_mutation_count": sum(
            1 for record in requirements if record["router_inventory_mutated"] is True
        ),
        "selected_component_binding_count": sum(
            1 for record in requirements if record["selected_component_binding_created"] is True
        ),
        "authority_grant_count": sum(1 for record in requirements if record["authority_granted"] is True),
        "promotion_approval_count": sum(1 for record in requirements if record["promotion_approved"] is True),
        "terminal_closure_claim_count": sum(
            1 for record in requirements if record["terminal_closure_claimed"] is True
        ),
        "blocking_requirement_count": sum(
            1 for record in requirements if record["blocks_witness_minting"] is True
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRequirementsError(
            f"{label} must carry {field_name}"
        )
    return value
