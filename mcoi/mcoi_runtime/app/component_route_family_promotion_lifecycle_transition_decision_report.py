"""Build Component Harness promotion lifecycle-transition decision reports.

Purpose: consume denied promotion route-binding decisions and record a
denial-only lifecycle transition decision without changing component lifecycle
state or granting route-family promotion authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion route-binding decision report
projection and component authority-fuse denial references.
Invariants:
  - Lifecycle transition decisions can deny without changing lifecycle state.
  - A denied lifecycle transition decision cannot emit a lifecycle transition
    receipt or promote a route family.
  - Lifecycle advancement remains blocked until a separate route-binding
    receipt, router-inventory delta, and lifecycle transition receipt exist.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_route_binding_decision_report import (
    ComponentRouteFamilyPromotionRouteBindingDecisionReportError,
    build_component_route_family_promotion_route_binding_decision_report,
)


SCHEMA_VERSION = 1
LIFECYCLE_TRANSITION_GATE_ID = "lifecycle_transition_gate"
CURRENT_LIFECYCLE_STATE = "approval_required"
REQUESTED_LIFECYCLE_STATE = "approved_live_action"
RESULTING_LIFECYCLE_STATE = CURRENT_LIFECYCLE_STATE
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_lifecycle_transition_decision_report_receipt",
    "component_route_family_promotion_route_binding_decision_report_receipt",
    "component_route_family_promotion_authority_decision_report_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "operator_approval_required_receipt",
    "terminal_closure_denial_receipt",
)
MISSING_LIFECYCLE_TRANSITION_WITNESSES = (
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
REQUIRED_FOLLOWUP_DECISIONS = (
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness_decision",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
)


class ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(ValueError):
    """Raised when a lifecycle-transition decision report cannot be compiled."""


def build_component_route_family_promotion_lifecycle_transition_decision_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    route_binding_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only lifecycle transition decision report.

    Input contract: target proof surface, target component, and optional
    route-binding decision report. Output contract: JSON-serializable lifecycle
    transition decision report. Error contract: raises
    ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError when the
    source report is unavailable, target-mismatched, malformed, or no longer
    denied and blocked.
    """

    route_binding_report = route_binding_decision_report or _build_route_binding_decision_report(
        surface_id=surface_id,
        component_id=component_id,
    )
    _validate_route_binding_report(route_binding_report, surface_id, component_id)
    authority_fuse_refs = _authority_fuse_refs(route_binding_report)
    source_decision = _source_route_binding_decision(route_binding_report)
    if list(_string_list(source_decision.get("authority_fuse_refs"))) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle source route-binding decision must cite the report authority fuse"
        )
    lifecycle_decision = _lifecycle_transition_decision(source_decision, surface_id)
    approval_evidence_required = list(_string_list(route_binding_report.get("approval_evidence_required")))
    return {
        "schema_version": SCHEMA_VERSION,
        "lifecycle_transition_decision_report_id": (
            f"component_route_family_promotion_lifecycle_transition_decision_report.{surface_id}.v1"
        ),
        "mode": str(route_binding_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "lifecycle_transition_decision_state": "denied_pending_route_binding_witness",
        "promotion_decision": "blocked_lifecycle_transition_not_authorized",
        "route_binding_decision_state": "denied_pending_router_inventory_witness",
        "current_lifecycle_state": CURRENT_LIFECYCLE_STATE,
        "requested_lifecycle_state": REQUESTED_LIFECYCLE_STATE,
        "resulting_lifecycle_state": RESULTING_LIFECYCLE_STATE,
        "record_evidence_satisfied": True,
        "action_requirement_satisfied": False,
        "lifecycle_transition_authorized": False,
        "lifecycle_state_changed": False,
        "authority_granted": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "route_family_ownership_authorized": False,
        "lifecycle_transition_decision_is_not_lifecycle_receipt": True,
        "lifecycle_transition_decision_is_not_state_change": True,
        "lifecycle_transition_decision_is_not_promotion_approval": True,
        "lifecycle_transition_decision_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_router_inventory_delta_required": True,
        "separate_route_binding_receipt_required": True,
        "separate_lifecycle_transition_receipt_required": True,
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
            "route_binding_decision_report": (
                "examples/"
                "component_route_family_promotion_route_binding_decision_report.governed_connector_framework.json"
            ),
            "authority_decision_report": (
                "examples/"
                "component_route_family_promotion_authority_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(lifecycle_decision, approval_evidence_required),
        "lifecycle_transition_decisions": [lifecycle_decision],
        "lifecycle_transition_decision_refs": [str(lifecycle_decision["lifecycle_transition_decision_id"])],
        "source_route_binding_decision_refs": [str(lifecycle_decision["source_route_binding_decision_id"])],
        "source_authority_decision_refs": [str(lifecycle_decision["source_authority_decision_id"])],
        "authority_fuse_refs": authority_fuse_refs,
        "authority_fuse_blocking_refs": authority_fuse_refs,
        "satisfied_gate_evaluation_refs": [str(lifecycle_decision["source_gate_evaluation_id"])],
        "accepted_record_refs": [str(lifecycle_decision["source_operator_submitted_record_id"])],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_lifecycle_transition_witnesses": list(MISSING_LIFECYCLE_TRANSITION_WITNESSES),
        "operator_submission_channels": list(_string_list(route_binding_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(route_binding_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_lifecycle_transition_decision_report_validator",
            "component_route_family_promotion_lifecycle_transition_decision_report_tests",
            "component_route_family_promotion_route_binding_decision_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create an authority-upgrade witness decision while lifecycle transition remains denied until "
            "a component route-binding receipt, router-inventory delta, and lifecycle transition receipt exist."
        ),
    }


def _build_route_binding_decision_report(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_route_binding_decision_report(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionRouteBindingDecisionReportError as exc:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(str(exc)) from exc


def _validate_route_binding_report(report: dict[str, Any], surface_id: str, component_id: str) -> None:
    if report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires blocked route-binding posture"
        )
    if report.get("route_binding_decision_state") != "denied_pending_router_inventory_witness":
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires denied route-binding decision state"
        )
    if report.get("promotion_decision") != "blocked_route_binding_not_authorized":
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires route-binding-not-authorized promotion posture"
        )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "route-binding decision report target does not match requested lifecycle transition decision report"
        )
    for field_name in (
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "authority_granted",
        "mutates_router_inventory",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
                f"route-binding report must keep {field_name} false before lifecycle decision"
            )


def _authority_fuse_refs(report: dict[str, Any]) -> list[str]:
    fuse_refs = list(_string_list(report.get("authority_fuse_refs")))
    blocking_refs = list(_string_list(report.get("authority_fuse_blocking_refs")))
    if len(fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires exactly one component authority-fuse reference"
        )
    if blocking_refs != fuse_refs:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires authority-fuse blocking refs to match authority-fuse refs"
        )
    return fuse_refs


def _source_route_binding_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("route_binding_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "route-binding decisions must be a list"
        )
    if len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "lifecycle transition decision report requires exactly one route-binding decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision must remain denied"
        )
    if decision.get("route_binding_authorized") is not False:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision must not authorize route binding"
        )
    if decision.get("requires_lifecycle_transition") is not True:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision must still require lifecycle transition"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision must remain blocked by authority fuse"
        )
    if len(_string_list(decision.get("authority_fuse_refs"))) != 1:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision must cite exactly one authority fuse"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != _string_list(decision.get("authority_fuse_refs")):
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(
            "source route-binding decision authority-fuse blocking refs must match authority-fuse refs"
        )
    return decision


def _lifecycle_transition_decision(source_decision: dict[str, Any], surface_id: str) -> dict[str, Any]:
    return {
        "lifecycle_transition_decision_id": (
            f"promotion_lifecycle_transition_decision.{surface_id}.lifecycle_transition_gate.v1"
        ),
        "source_route_binding_decision_id": _required_text(
            source_decision,
            "route_binding_decision_id",
            "source route-binding decision",
        ),
        "source_authority_decision_id": _required_text(
            source_decision,
            "source_authority_decision_id",
            "source route-binding decision",
        ),
        "source_gate_evaluation_id": _required_text(
            source_decision,
            "source_gate_evaluation_id",
            "source route-binding decision",
        ),
        "source_operator_submitted_record_id": _required_text(
            source_decision,
            "source_operator_submitted_record_id",
            "source route-binding decision",
        ),
        "gate_id": LIFECYCLE_TRANSITION_GATE_ID,
        "record_kind": "lifecycle_transition",
        "decision_state": "denied",
        "decision_basis": "route_binding_decision_denial",
        "proof_state": "Pass",
        "current_lifecycle_state": CURRENT_LIFECYCLE_STATE,
        "requested_lifecycle_state": REQUESTED_LIFECYCLE_STATE,
        "resulting_lifecycle_state": RESULTING_LIFECYCLE_STATE,
        "record_evidence_satisfied": True,
        "source_route_binding_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "action_requirement_satisfied": False,
        "lifecycle_transition_authorized": False,
        "lifecycle_state_changed": False,
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
        "requires_component_route_binding_receipt": True,
        "requires_router_inventory_delta": True,
        "requires_lifecycle_transition_receipt": True,
        "requires_authority_upgrade_witness": True,
        "requires_product_ownership_decision": True,
        "requires_terminal_closure": True,
        "decision_is_not_lifecycle_receipt": True,
        "decision_is_not_state_change": True,
        "decision_is_not_promotion_approval": True,
        "decision_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "source_route_binding_decision_refs": [
            _required_text(source_decision, "route_binding_decision_id", "source route-binding decision")
        ],
        "source_authority_decision_refs": [
            _required_text(source_decision, "source_authority_decision_id", "source route-binding decision")
        ],
        "authority_fuse_refs": list(_string_list(source_decision.get("authority_fuse_refs"))),
        "authority_fuse_blocking_refs": list(_string_list(source_decision.get("authority_fuse_refs"))),
        "satisfied_gate_evaluation_refs": [
            _required_text(source_decision, "source_gate_evaluation_id", "source route-binding decision")
        ],
        "accepted_record_refs": [
            _required_text(source_decision, "source_operator_submitted_record_id", "source route-binding decision")
        ],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_lifecycle_transition_witnesses": list(MISSING_LIFECYCLE_TRANSITION_WITNESSES),
        "decision_reason": (
            "lifecycle_transition_gate remains denied because route binding, router inventory delta, "
            "lifecycle transition receipt witnesses are absent, and the component authority fuse remains blocked"
        ),
    }


def _summary(lifecycle_decision: dict[str, Any], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "lifecycle_transition_decision_count": 1,
        "lifecycle_transition_denial_count": 1 if lifecycle_decision["decision_state"] == "denied" else 0,
        "lifecycle_transition_authorization_count": (
            1 if lifecycle_decision["lifecycle_transition_authorized"] is True else 0
        ),
        "lifecycle_state_change_count": 1 if lifecycle_decision["lifecycle_state_changed"] is True else 0,
        "route_binding_authorization_count": 1 if lifecycle_decision["route_binding_authorized"] is True else 0,
        "router_inventory_mutation_count": 1 if lifecycle_decision["mutates_router_inventory"] is True else 0,
        "selected_component_binding_count": (
            1 if lifecycle_decision["selected_component_binding_authorized"] is True else 0
        ),
        "authority_grant_count": 1 if lifecycle_decision["authority_granted"] is True else 0,
        "promotion_approval_count": 1 if lifecycle_decision["promotion_approved"] is True else 0,
        "terminal_closure_count": 1 if lifecycle_decision["can_claim_terminal_closure"] is True else 0,
        "accepted_evidence_count": len(lifecycle_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(lifecycle_decision["rejected_evidence_refs"]),
        "accepted_record_count": len(lifecycle_decision["accepted_record_refs"]),
        "lifecycle_transition_receipt_count": len(lifecycle_decision["lifecycle_transition_receipt_refs"]),
        "route_binding_receipt_count": len(lifecycle_decision["route_binding_receipt_refs"]),
        "authority_fuse_blocking_count": len(lifecycle_decision["authority_fuse_blocking_refs"]),
        "router_inventory_delta_ref_count": len(lifecycle_decision["router_inventory_delta_refs"]),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
