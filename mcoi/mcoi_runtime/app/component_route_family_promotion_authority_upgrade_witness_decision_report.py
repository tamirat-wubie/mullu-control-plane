"""Build Component Harness promotion authority-upgrade witness decisions.

Purpose: consume denied promotion lifecycle-transition decisions and record a
denial-only authority-upgrade witness decision without granting authority or
mutating the component authority envelope.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion lifecycle-transition decision
report projection and component authority-fuse denial references.
Invariants:
  - Authority-upgrade decisions can deny without changing authority level.
  - A denied authority-upgrade decision cannot emit an authority-upgrade witness
    or mutate authority envelopes.
  - Authority upgrade remains blocked until separate route-binding,
    lifecycle-transition, and authority-upgrade witnesses exist.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_lifecycle_transition_decision_report import (
    ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError,
    build_component_route_family_promotion_lifecycle_transition_decision_report,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
AUTHORITY_UPGRADE_GATE_ID = "authority_upgrade_gate"
CURRENT_AUTHORITY_LEVEL = "approval_required"
REQUESTED_AUTHORITY_LEVEL = "approved_live_action"
RESULTING_AUTHORITY_LEVEL = CURRENT_AUTHORITY_LEVEL
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_authority_upgrade_witness_decision_report_receipt",
    "component_route_family_promotion_lifecycle_transition_decision_report_receipt",
    "component_route_family_promotion_route_binding_decision_report_receipt",
    "component_route_family_promotion_authority_decision_report_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "operator_approval_required_receipt",
    "terminal_closure_denial_receipt",
)
MISSING_AUTHORITY_UPGRADE_WITNESSES = (
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
REQUIRED_FOLLOWUP_DECISIONS = (
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
)


class ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(ValueError):
    """Raised when an authority-upgrade witness decision report cannot be compiled."""


def build_component_route_family_promotion_authority_upgrade_witness_decision_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    lifecycle_transition_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only authority-upgrade decision report.

    Input contract: target proof surface, target component, and optional
    lifecycle-transition decision report. Output contract: JSON-serializable
    authority-upgrade witness decision report. Error contract: raises
    ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError when
    the source report is unavailable, target-mismatched, malformed, or no
    longer denied and blocked.
    """

    lifecycle_report = lifecycle_transition_decision_report or _build_lifecycle_transition_decision_report(
        surface_id=surface_id,
        component_id=component_id,
    )
    _validate_lifecycle_report(lifecycle_report, surface_id, component_id)
    authority_fuse_refs = _authority_fuse_refs(lifecycle_report)
    source_decision = _source_lifecycle_transition_decision(lifecycle_report)
    if list(_string_list(source_decision.get("authority_fuse_refs"))) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade source lifecycle decision must cite the report authority fuse"
        )
    authority_decision = _authority_upgrade_witness_decision(source_decision, surface_id)
    approval_evidence_required = list(_string_list(lifecycle_report.get("approval_evidence_required")))
    return {
        "schema_version": SCHEMA_VERSION,
        "authority_upgrade_witness_decision_report_id": (
            f"component_route_family_promotion_authority_upgrade_witness_decision_report.{surface_id}.v1"
        ),
        "mode": str(lifecycle_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "authority_upgrade_decision_state": "denied_pending_authority_upgrade_witness",
        "promotion_decision": "blocked_authority_upgrade_not_authorized",
        "lifecycle_transition_decision_state": "denied_pending_route_binding_witness",
        "current_authority_level": CURRENT_AUTHORITY_LEVEL,
        "requested_authority_level": REQUESTED_AUTHORITY_LEVEL,
        "resulting_authority_level": RESULTING_AUTHORITY_LEVEL,
        "record_evidence_satisfied": True,
        "action_requirement_satisfied": False,
        "authority_upgrade_authorized": False,
        "authority_level_changed": False,
        "authority_witness_emitted": False,
        "authority_envelope_mutated": False,
        "authority_granted": False,
        "lifecycle_transition_authorized": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "route_family_ownership_authorized": False,
        "authority_upgrade_decision_is_not_authority_witness": True,
        "authority_upgrade_decision_is_not_authority_envelope_mutation": True,
        "authority_upgrade_decision_is_not_authority_grant": True,
        "authority_upgrade_decision_is_not_promotion_approval": True,
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
            "lifecycle_transition_decision_report": (
                "examples/"
                "component_route_family_promotion_lifecycle_transition_decision_report.governed_connector_framework.json"
            ),
            "route_binding_decision_report": (
                "examples/"
                "component_route_family_promotion_route_binding_decision_report.governed_connector_framework.json"
            ),
            "authority_decision_report": (
                "examples/"
                "component_route_family_promotion_authority_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(authority_decision, approval_evidence_required),
        "authority_upgrade_decisions": [authority_decision],
        "authority_upgrade_decision_refs": [str(authority_decision["authority_upgrade_decision_id"])],
        "source_lifecycle_transition_decision_refs": [
            str(authority_decision["source_lifecycle_transition_decision_id"])
        ],
        "source_route_binding_decision_refs": [str(authority_decision["source_route_binding_decision_id"])],
        "source_authority_decision_refs": [str(authority_decision["source_authority_decision_id"])],
        "authority_fuse_refs": authority_fuse_refs,
        "authority_fuse_blocking_refs": authority_fuse_refs,
        "satisfied_gate_evaluation_refs": [str(authority_decision["source_gate_evaluation_id"])],
        "accepted_record_refs": [str(authority_decision["source_operator_submitted_record_id"])],
        "authority_upgrade_witness_refs": [],
        "authority_envelope_mutation_refs": [],
        "authority_grant_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_authority_upgrade_witnesses": list(MISSING_AUTHORITY_UPGRADE_WITNESSES),
        "operator_submission_channels": list(_string_list(lifecycle_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(lifecycle_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_authority_upgrade_witness_decision_report_validator",
            "component_route_family_promotion_authority_upgrade_witness_decision_report_tests",
            "component_route_family_promotion_lifecycle_transition_decision_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create a product-specific ownership decision while authority upgrade remains denied until separate "
            "authority-upgrade, lifecycle-transition, route-binding, and router-inventory evidence exists."
        ),
    }


def _build_lifecycle_transition_decision_report(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_lifecycle_transition_decision_report(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionLifecycleTransitionDecisionReportError as exc:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(str(exc)) from exc


def _validate_lifecycle_report(report: dict[str, Any], surface_id: str, component_id: str) -> None:
    if report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires blocked lifecycle posture"
        )
    if report.get("lifecycle_transition_decision_state") != "denied_pending_route_binding_witness":
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires denied lifecycle transition decision state"
        )
    if report.get("promotion_decision") != "blocked_lifecycle_transition_not_authorized":
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires lifecycle-transition-not-authorized promotion posture"
        )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "lifecycle transition decision report target does not match requested authority-upgrade decision report"
        )
    for field_name in (
        "lifecycle_transition_authorized",
        "lifecycle_state_changed",
        "route_binding_authorized",
        "authority_granted",
        "mutates_router_inventory",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
                f"lifecycle report must keep {field_name} false before authority-upgrade decision"
            )


def _authority_fuse_refs(report: dict[str, Any]) -> list[str]:
    fuse_refs = list(_string_list(report.get("authority_fuse_refs")))
    blocking_refs = list(_string_list(report.get("authority_fuse_blocking_refs")))
    if len(fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires exactly one component authority-fuse reference"
        )
    if blocking_refs != fuse_refs:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires authority-fuse blocking refs to match authority-fuse refs"
        )
    return fuse_refs


def _source_lifecycle_transition_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("lifecycle_transition_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "lifecycle transition decisions must be a list"
        )
    if len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "authority-upgrade decision report requires exactly one lifecycle transition decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision must remain denied"
        )
    if decision.get("lifecycle_transition_authorized") is not False:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision must not authorize lifecycle transition"
        )
    if decision.get("requires_authority_upgrade_witness") is not True:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision must still require authority-upgrade witness"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision must remain blocked by authority fuse"
        )
    if len(_string_list(decision.get("authority_fuse_refs"))) != 1:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision must cite exactly one authority fuse"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != _string_list(decision.get("authority_fuse_refs")):
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            "source lifecycle transition decision authority-fuse blocking refs must match authority-fuse refs"
        )
    return decision


def _authority_upgrade_witness_decision(source_decision: dict[str, Any], surface_id: str) -> dict[str, Any]:
    return {
        "authority_upgrade_decision_id": (
            f"promotion_authority_upgrade_decision.{surface_id}.authority_upgrade_gate.v1"
        ),
        "source_lifecycle_transition_decision_id": _required_text(
            source_decision,
            "lifecycle_transition_decision_id",
            "source lifecycle transition decision",
        ),
        "source_route_binding_decision_id": _required_text(
            source_decision,
            "source_route_binding_decision_id",
            "source lifecycle transition decision",
        ),
        "source_authority_decision_id": _required_text(
            source_decision,
            "source_authority_decision_id",
            "source lifecycle transition decision",
        ),
        "source_gate_evaluation_id": _required_text(
            source_decision,
            "source_gate_evaluation_id",
            "source lifecycle transition decision",
        ),
        "source_operator_submitted_record_id": _required_text(
            source_decision,
            "source_operator_submitted_record_id",
            "source lifecycle transition decision",
        ),
        "gate_id": AUTHORITY_UPGRADE_GATE_ID,
        "record_kind": "authority_upgrade",
        "decision_state": "denied",
        "decision_basis": "lifecycle_transition_decision_denial",
        "proof_state": "Pass",
        "current_authority_level": CURRENT_AUTHORITY_LEVEL,
        "requested_authority_level": REQUESTED_AUTHORITY_LEVEL,
        "resulting_authority_level": RESULTING_AUTHORITY_LEVEL,
        "record_evidence_satisfied": True,
        "source_lifecycle_transition_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "action_requirement_satisfied": False,
        "authority_upgrade_authorized": False,
        "authority_level_changed": False,
        "authority_witness_emitted": False,
        "authority_envelope_mutated": False,
        "authority_granted": False,
        "lifecycle_transition_authorized": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "route_family_ownership_authorized": False,
        "promotion_approved": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "requires_authority_upgrade_witness": True,
        "requires_lifecycle_transition_receipt": True,
        "requires_component_route_binding_receipt": True,
        "requires_router_inventory_delta": True,
        "requires_product_ownership_decision": True,
        "requires_terminal_closure": True,
        "decision_is_not_authority_witness": True,
        "decision_is_not_authority_envelope_mutation": True,
        "decision_is_not_authority_grant": True,
        "decision_is_not_promotion_approval": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "source_lifecycle_transition_decision_refs": [
            _required_text(source_decision, "lifecycle_transition_decision_id", "source lifecycle transition decision")
        ],
        "source_route_binding_decision_refs": [
            _required_text(source_decision, "source_route_binding_decision_id", "source lifecycle transition decision")
        ],
        "source_authority_decision_refs": [
            _required_text(source_decision, "source_authority_decision_id", "source lifecycle transition decision")
        ],
        "authority_fuse_refs": list(_string_list(source_decision.get("authority_fuse_refs"))),
        "authority_fuse_blocking_refs": list(_string_list(source_decision.get("authority_fuse_refs"))),
        "satisfied_gate_evaluation_refs": [
            _required_text(source_decision, "source_gate_evaluation_id", "source lifecycle transition decision")
        ],
        "accepted_record_refs": [
            _required_text(source_decision, "source_operator_submitted_record_id", "source lifecycle transition decision")
        ],
        "authority_upgrade_witness_refs": [],
        "authority_envelope_mutation_refs": [],
        "authority_grant_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_authority_upgrade_witnesses": list(MISSING_AUTHORITY_UPGRADE_WITNESSES),
        "decision_reason": (
            "authority_upgrade_gate remains denied because authority-upgrade, lifecycle, route-binding, "
            "router-inventory witnesses are absent, and the component authority fuse remains blocked"
        ),
    }


def _summary(authority_decision: dict[str, Any], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "authority_upgrade_decision_count": 1,
        "authority_upgrade_denial_count": 1 if authority_decision["decision_state"] == "denied" else 0,
        "authority_upgrade_authorization_count": (
            1 if authority_decision["authority_upgrade_authorized"] is True else 0
        ),
        "authority_level_change_count": 1 if authority_decision["authority_level_changed"] is True else 0,
        "authority_witness_emission_count": 1 if authority_decision["authority_witness_emitted"] is True else 0,
        "authority_envelope_mutation_count": 1 if authority_decision["authority_envelope_mutated"] is True else 0,
        "authority_grant_count": 1 if authority_decision["authority_granted"] is True else 0,
        "lifecycle_transition_authorization_count": (
            1 if authority_decision["lifecycle_transition_authorized"] is True else 0
        ),
        "route_binding_authorization_count": 1 if authority_decision["route_binding_authorized"] is True else 0,
        "router_inventory_mutation_count": 1 if authority_decision["mutates_router_inventory"] is True else 0,
        "selected_component_binding_count": (
            1 if authority_decision["selected_component_binding_authorized"] is True else 0
        ),
        "promotion_approval_count": 1 if authority_decision["promotion_approved"] is True else 0,
        "terminal_closure_count": 1 if authority_decision["can_claim_terminal_closure"] is True else 0,
        "accepted_evidence_count": len(authority_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(authority_decision["rejected_evidence_refs"]),
        "accepted_record_count": len(authority_decision["accepted_record_refs"]),
        "authority_upgrade_witness_count": len(authority_decision["authority_upgrade_witness_refs"]),
        "authority_envelope_mutation_ref_count": len(authority_decision["authority_envelope_mutation_refs"]),
        "authority_fuse_blocking_count": len(authority_decision["authority_fuse_blocking_refs"]),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError(
            f"{label} must carry {field_name}"
        )
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
