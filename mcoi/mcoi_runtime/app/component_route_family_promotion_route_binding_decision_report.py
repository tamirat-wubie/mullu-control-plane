"""Build Component Harness promotion route-binding decision reports.

Purpose: consume denied promotion authority decisions and record a denial-only
route-binding decision without mutating router inventory or promoting a route
family.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion authority decision report
projection and component authority-fuse denial references.
Invariants:
  - Route-binding decisions can deny without binding a route family.
  - A denied route-binding decision cannot mutate router inventory.
  - Route binding remains blocked until a separate router-inventory delta and
    component route-binding receipt exist.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_authority_decision_report import (
    ComponentRouteFamilyPromotionAuthorityDecisionReportError,
    build_component_route_family_promotion_authority_decision_report,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
ROUTE_BINDING_GATE_ID = "route_binding_gate"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_route_binding_decision_report_receipt",
    "component_route_family_promotion_authority_decision_report_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_approval_candidates_receipt",
    "component_route_family_promotion_witness_evidence_receipt",
    "component_route_family_promotion_witness_requirements_receipt",
    "component_route_family_promotion_preflight_receipt",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "operator_approval_required_receipt",
    "terminal_closure_denial_receipt",
)
MISSING_ROUTE_BINDING_WITNESSES = (
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
REQUIRED_FOLLOWUP_DECISIONS = (
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_decision",
    "authority_upgrade_witness_decision",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
)


class ComponentRouteFamilyPromotionRouteBindingDecisionReportError(ValueError):
    """Raised when a route-binding decision report cannot be compiled."""


def build_component_route_family_promotion_route_binding_decision_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    authority_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only route-binding decision report.

    Input contract: target proof surface, target component, and optional
    authority decision report. Output contract: JSON-serializable route-binding
    decision report. Error contract: raises
    ComponentRouteFamilyPromotionRouteBindingDecisionReportError when the
    authority report is unavailable, malformed, target-mismatched, or no longer
    denied and blocked.
    """

    authority_report = authority_decision_report or _build_authority_decision_report(
        surface_id=surface_id,
        component_id=component_id,
    )
    _validate_authority_report(authority_report, surface_id, component_id)
    authority_fuse_refs = _authority_fuse_refs(authority_report)
    source_decision = _route_binding_authority_decision(authority_report)
    if list(_string_list(source_decision.get("authority_fuse_refs"))) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding source authority decision must cite the report authority fuse"
        )
    route_binding_decision = _route_binding_decision(source_decision, surface_id)
    approval_evidence_required = list(_string_list(authority_report.get("approval_evidence_required")))
    return {
        "schema_version": SCHEMA_VERSION,
        "route_binding_decision_report_id": (
            f"component_route_family_promotion_route_binding_decision_report.{surface_id}.v1"
        ),
        "mode": str(authority_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "route_binding_decision_state": "denied_pending_router_inventory_witness",
        "promotion_decision": "blocked_route_binding_not_authorized",
        "authority_decision_state": "denied_pending_governed_witnesses",
        "record_evidence_satisfied": True,
        "action_requirement_satisfied": False,
        "authority_granted": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "route_family_ownership_authorized": False,
        "route_binding_decision_is_not_router_mutation": True,
        "route_binding_decision_is_not_promotion_approval": True,
        "route_binding_decision_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_router_inventory_delta_required": True,
        "separate_route_binding_receipt_required": True,
        "separate_lifecycle_transition_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_product_ownership_decision_required": True,
        "terminal_closure_required": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "authority_decision_report": (
                "examples/"
                "component_route_family_promotion_authority_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "gate_satisfaction_evaluator": (
                "examples/"
                "component_route_family_promotion_gate_satisfaction_evaluator.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(route_binding_decision, approval_evidence_required),
        "route_binding_decisions": [route_binding_decision],
        "route_binding_decision_refs": [str(route_binding_decision["route_binding_decision_id"])],
        "source_authority_decision_refs": [str(route_binding_decision["source_authority_decision_id"])],
        "authority_fuse_refs": authority_fuse_refs,
        "authority_fuse_blocking_refs": authority_fuse_refs,
        "satisfied_gate_evaluation_refs": [str(route_binding_decision["source_gate_evaluation_id"])],
        "accepted_record_refs": [str(route_binding_decision["source_operator_submitted_record_id"])],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "lifecycle_transition_refs": [],
        "terminal_closure_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_route_binding_witnesses": list(MISSING_ROUTE_BINDING_WITNESSES),
        "operator_submission_channels": list(_string_list(authority_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(authority_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_route_binding_decision_report_validator",
            "component_route_family_promotion_route_binding_decision_report_tests",
            "component_route_family_promotion_authority_decision_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create a lifecycle transition decision witness after a separate route-binding receipt and "
            "router-inventory delta exist; until then route-family promotion remains blocked."
        ),
    }


def _build_authority_decision_report(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_authority_decision_report(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionAuthorityDecisionReportError as exc:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(str(exc)) from exc


def _validate_authority_report(report: dict[str, Any], surface_id: str, component_id: str) -> None:
    if report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires blocked authority decision posture"
        )
    if report.get("authority_decision_state") != "denied_pending_governed_witnesses":
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires denied authority decisions"
        )
    if report.get("promotion_decision") != "blocked_authority_not_granted":
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires authority-not-granted promotion posture"
        )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "authority decision report target does not match requested route-binding decision report"
        )
    if report.get("all_authority_decisions_denied") is not True:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires all source authority decisions denied"
        )
    if report.get("authority_fuse_enforced") is not True:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires enforced component authority fuse"
        )
    if report.get("ready_for_promotion") is not False:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires source report to remain not ready for promotion"
        )


def _authority_fuse_refs(report: dict[str, Any]) -> list[str]:
    fuse_refs = list(_string_list(report.get("authority_fuse_refs")))
    blocking_refs = list(_string_list(report.get("authority_fuse_blocking_refs")))
    if len(fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires exactly one component authority-fuse reference"
        )
    if blocking_refs != fuse_refs:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires authority-fuse blocking refs to match authority-fuse refs"
        )
    return fuse_refs


def _route_binding_authority_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("authority_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError("authority decisions must be a list")
    matches = [
        decision
        for decision in decisions
        if isinstance(decision, dict) and decision.get("gate_id") == ROUTE_BINDING_GATE_ID
    ]
    if len(matches) != 1:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding decision report requires exactly one route-binding authority decision"
        )
    decision = matches[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must remain denied"
        )
    if decision.get("route_binding_authorized") is not False:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must not authorize route binding"
        )
    if decision.get("authority_granted") is not False:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must not grant authority"
        )
    if decision.get("mutates_router_inventory") is not False:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must not mutate router inventory"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must remain blocked by authority fuse"
        )
    if len(_string_list(decision.get("authority_fuse_refs"))) != 1:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision must cite exactly one authority fuse"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != _string_list(decision.get("authority_fuse_refs")):
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(
            "route-binding authority decision authority-fuse blocking refs must match authority-fuse refs"
        )
    return decision


def _route_binding_decision(authority_decision: dict[str, Any], surface_id: str) -> dict[str, Any]:
    return {
        "route_binding_decision_id": f"promotion_route_binding_decision.{surface_id}.route_binding_gate.v1",
        "source_authority_decision_id": _required_text(
            authority_decision,
            "authority_decision_id",
            "route-binding authority decision",
        ),
        "source_gate_evaluation_id": _required_text(
            authority_decision,
            "source_gate_evaluation_id",
            "route-binding authority decision",
        ),
        "source_operator_submitted_record_id": _required_text(
            authority_decision,
            "source_operator_submitted_record_id",
            "route-binding authority decision",
        ),
        "gate_id": ROUTE_BINDING_GATE_ID,
        "record_kind": "route_binding",
        "evidence_key": _required_text(authority_decision, "evidence_key", "route-binding authority decision"),
        "decision_state": "denied",
        "decision_basis": "authority_decision_denial",
        "proof_state": "Pass",
        "record_evidence_satisfied": True,
        "source_authority_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "action_requirement_satisfied": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "route_family_ownership_authorized": False,
        "authority_granted": False,
        "promotion_approved": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "requires_router_inventory_delta": True,
        "requires_component_route_binding_receipt": True,
        "requires_lifecycle_transition": True,
        "requires_authority_upgrade_witness": True,
        "requires_product_ownership_decision": True,
        "requires_terminal_closure": True,
        "decision_is_not_router_mutation": True,
        "decision_is_not_promotion_approval": True,
        "decision_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "source_authority_decision_refs": [
            _required_text(authority_decision, "authority_decision_id", "route-binding authority decision")
        ],
        "authority_fuse_refs": list(_string_list(authority_decision.get("authority_fuse_refs"))),
        "authority_fuse_blocking_refs": list(_string_list(authority_decision.get("authority_fuse_refs"))),
        "satisfied_gate_evaluation_refs": [
            _required_text(authority_decision, "source_gate_evaluation_id", "route-binding authority decision")
        ],
        "accepted_record_refs": [
            _required_text(authority_decision, "source_operator_submitted_record_id", "route-binding authority decision")
        ],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_route_binding_witnesses": list(MISSING_ROUTE_BINDING_WITNESSES),
        "decision_reason": (
            "route_binding_gate remains denied because no component route-binding receipt or "
            "selected-component router-inventory delta exists and the component authority fuse remains blocked"
        ),
    }


def _summary(route_binding_decision: dict[str, Any], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "route_binding_decision_count": 1,
        "route_binding_denial_count": 1 if route_binding_decision["decision_state"] == "denied" else 0,
        "route_binding_authorization_count": (
            1 if route_binding_decision["route_binding_authorized"] is True else 0
        ),
        "router_inventory_delta_authorization_count": (
            1 if route_binding_decision["router_inventory_delta_authorized"] is True else 0
        ),
        "router_inventory_mutation_count": 1 if route_binding_decision["mutates_router_inventory"] is True else 0,
        "selected_component_binding_count": (
            1 if route_binding_decision["selected_component_binding_authorized"] is True else 0
        ),
        "authority_grant_count": 1 if route_binding_decision["authority_granted"] is True else 0,
        "promotion_approval_count": 1 if route_binding_decision["promotion_approved"] is True else 0,
        "accepted_evidence_count": len(route_binding_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(route_binding_decision["rejected_evidence_refs"]),
        "accepted_record_count": len(route_binding_decision["accepted_record_refs"]),
        "route_binding_receipt_count": len(route_binding_decision["route_binding_receipt_refs"]),
        "authority_fuse_blocking_count": len(route_binding_decision["authority_fuse_blocking_refs"]),
        "router_inventory_delta_ref_count": len(route_binding_decision["router_inventory_delta_refs"]),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouteBindingDecisionReportError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
