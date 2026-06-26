"""Build Component Harness promotion authority decision reports.

Purpose: consume gate-satisfaction evidence and issue denial-only promotion
authority decisions without approving route-family promotion, mutating router
inventory, or granting live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion gate-satisfaction evaluator
projection.
Invariants:
  - Authority decisions can record denial without granting authority.
  - Record-satisfied gates are not action-satisfied gates.
  - Denial-only authority decisions cannot execute, call connectors, mutate
    router inventory, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_authority_fuse import (
    ComponentAuthorityFuseError,
    build_component_authority_fuse,
)
from mcoi_runtime.app.component_route_family_promotion_gate_satisfaction_evaluator import (
    ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError,
    build_component_route_family_promotion_gate_satisfaction_evaluator,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
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
REQUIRED_FOLLOWUP_DECISIONS = (
    "component_route_binding_decision",
    "component_lifecycle_transition_decision",
    "authority_upgrade_witness_decision",
    "product_specific_ownership_decision",
    "terminal_closure_decision",
)
MISSING_AUTHORITY_WITNESSES = (
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "terminal_closure_certificate",
)


class ComponentRouteFamilyPromotionAuthorityDecisionReportError(ValueError):
    """Raised when a promotion authority decision report cannot be compiled."""


def build_component_route_family_promotion_authority_decision_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    gate_satisfaction_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic denial-only promotion authority decisions.

    Input contract: target proof surface, target component, and optional
    gate-satisfaction evaluator report. Output contract: JSON-serializable
    promotion authority decision report. Error contract: raises
    ComponentRouteFamilyPromotionAuthorityDecisionReportError when the source
    gate-satisfaction report is unavailable, malformed, target-mismatched, or
    no longer blocked from authority.
    """

    gate_report = gate_satisfaction_report or _build_gate_satisfaction_report(
        surface_id=surface_id,
        component_id=component_id,
    )
    _validate_gate_report(gate_report, surface_id, component_id)
    authority_fuse_refs = _authority_fuse_refs(component_id)

    gate_evaluations = _gate_evaluations(gate_report)
    authority_decisions = [
        _authority_decision(gate_evaluation, surface_id, authority_fuse_refs)
        for gate_evaluation in gate_evaluations
    ]
    authority_decision_refs = [
        str(authority_decision["authority_decision_id"])
        for authority_decision in authority_decisions
    ]
    satisfied_gate_refs = [
        str(authority_decision["source_gate_evaluation_id"])
        for authority_decision in authority_decisions
    ]
    accepted_record_refs = [
        str(authority_decision["source_operator_submitted_record_id"])
        for authority_decision in authority_decisions
    ]
    approval_evidence_required = list(_string_list(gate_report.get("approval_evidence_required")))
    summary = _summary(authority_decisions, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "authority_decision_report_id": (
            f"component_route_family_promotion_authority_decision_report.{surface_id}.v1"
        ),
        "mode": str(gate_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "authority_decision_state": "denied_pending_governed_witnesses",
        "promotion_decision": "blocked_authority_not_granted",
        "all_record_evidence_gates_satisfied": True,
        "all_action_gates_satisfied": False,
        "all_authority_decisions_issued": True,
        "all_authority_decisions_denied": True,
        "all_authority_grants_blocked": True,
        "authority_fuse_enforced": True,
        "all_required_followup_decisions_pending": True,
        "authority_decision_is_not_authority_grant": True,
        "authority_decision_is_not_promotion_approval": True,
        "authority_decision_is_not_route_binding": True,
        "authority_decision_is_not_lifecycle_transition": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_route_binding_decision_required": True,
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
            "gate_satisfaction_evaluator": (
                "examples/"
                "component_route_family_promotion_gate_satisfaction_evaluator.governed_connector_framework.json"
            ),
            "operator_submitted_evidence_records": (
                "examples/"
                "component_route_family_promotion_operator_submitted_evidence_records.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "authority_decisions": authority_decisions,
        "authority_decision_refs": authority_decision_refs,
        "satisfied_gate_evaluation_refs": satisfied_gate_refs,
        "accepted_record_refs": accepted_record_refs,
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "route_binding_decision_refs": [],
        "lifecycle_transition_refs": [],
        "terminal_closure_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_authority_witnesses": list(MISSING_AUTHORITY_WITNESSES),
        "operator_submission_channels": list(_string_list(gate_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(gate_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_authority_decision_report_validator",
            "component_route_family_promotion_authority_decision_report_tests",
            "component_route_family_promotion_gate_satisfaction_evaluator_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create separate route-binding, lifecycle, authority-upgrade, product ownership, and "
            "terminal-closure decision witnesses before any route-family promotion can advance."
        ),
    }


def _build_gate_satisfaction_report(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_gate_satisfaction_evaluator(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError as exc:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(str(exc)) from exc


def _validate_gate_report(report: dict[str, Any], surface_id: str, component_id: str) -> None:
    if report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require blocked gate-satisfaction posture"
        )
    if report.get("gate_satisfaction_decision") != "record_evidence_satisfied_authority_pending":
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require record-evidence gate satisfaction"
        )
    if report.get("promotion_decision") != "blocked_pending_authority_decision":
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require pending promotion authority posture"
        )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "gate-satisfaction report target does not match requested authority decision report"
        )
    if report.get("all_record_evidence_gates_satisfied") is not True:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require all record-evidence gates to be satisfied"
        )
    if report.get("all_action_gates_satisfied") is not False:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require action gates to remain unsatisfied"
        )
    if report.get("gate_satisfaction_is_not_promotion_authority") is not True:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require gate satisfaction to remain non-authoritative"
        )
    if report.get("ready_for_promotion") is not False:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decisions require source report to remain not ready for promotion"
        )


def _gate_evaluations(report: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations = report.get("gate_evaluations")
    if not isinstance(evaluations, list):
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError("gate evaluations must be a list")
    if len(evaluations) != 4:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError("authority decision report requires four gates")
    output: list[dict[str, Any]] = []
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError("gate evaluation entries must be objects")
        if evaluation.get("evaluation_state") != "evaluated":
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError("authority decisions require evaluated gates")
        if evaluation.get("satisfaction_state") != "satisfied_record_only":
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
                "authority decisions require satisfied-record-only gates"
            )
        if evaluation.get("record_evidence_satisfies_gate") is not True:
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
                "authority decisions require record evidence to satisfy each gate"
            )
        if evaluation.get("satisfies_action_requirement") is not False:
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
                "authority decisions require source gates to leave action requirements unsatisfied"
            )
        if evaluation.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
                "authority decisions require source gates to keep promotion blocked"
            )
        output.append(evaluation)
    return output


def _authority_decision(
    gate_evaluation: dict[str, Any],
    surface_id: str,
    authority_fuse_refs: tuple[str, ...],
) -> dict[str, Any]:
    gate_id = _required_text(gate_evaluation, "gate_id", "gate evaluation")
    return {
        "authority_decision_id": f"promotion_authority_decision.{surface_id}.{gate_id}.v1",
        "source_gate_evaluation_id": _required_text(gate_evaluation, "gate_evaluation_id", f"gate {gate_id}"),
        "source_operator_submitted_record_id": _required_text(
            gate_evaluation,
            "source_operator_submitted_record_id",
            f"gate {gate_id}",
        ),
        "gate_id": gate_id,
        "record_kind": _required_text(gate_evaluation, "record_kind", f"gate {gate_id}"),
        "evidence_key": _required_text(gate_evaluation, "evidence_key", f"gate {gate_id}"),
        "decision_state": "denied",
        "decision_basis": "record_evidence_only",
        "proof_state": "Pass",
        "record_evidence_satisfied": True,
        "action_requirement_satisfied": False,
        "blocks_promotion": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "authority_granted": False,
        "route_binding_authorized": False,
        "lifecycle_transition_authorized": False,
        "connector_authority_authorized": False,
        "terminal_closure_authorized": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "requires_route_binding_decision": True,
        "requires_lifecycle_transition": True,
        "requires_authority_upgrade_witness": True,
        "requires_product_ownership_decision": True,
        "requires_terminal_closure": True,
        "decision_is_not_authority_grant": True,
        "decision_is_not_promotion_approval": True,
        "decision_is_not_route_binding": True,
        "decision_is_not_lifecycle_transition": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "satisfied_gate_evaluation_refs": [
            _required_text(gate_evaluation, "gate_evaluation_id", f"gate {gate_id}")
        ],
        "accepted_record_refs": [
            _required_text(gate_evaluation, "source_operator_submitted_record_id", f"gate {gate_id}")
        ],
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_authority_witnesses": list(MISSING_AUTHORITY_WITNESSES),
        "decision_reason": (
            f"{gate_id} has record-evidence satisfaction, but authority remains denied until "
            "separate route-binding, lifecycle, authority-upgrade, product ownership, and "
            "terminal-closure witnesses exist"
        ),
    }


def _summary(authority_decisions: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "authority_decision_count": len(authority_decisions),
        "authority_denial_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["decision_state"] == "denied"
        ),
        "authority_grant_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["authority_granted"] is True
        ),
        "record_evidence_satisfied_gate_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["record_evidence_satisfied"] is True
        ),
        "action_satisfied_gate_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["action_requirement_satisfied"] is True
        ),
        "blocking_decision_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["blocks_promotion"] is True
        ),
        "route_binding_authorization_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["route_binding_authorized"] is True
        ),
        "lifecycle_transition_authorization_count": sum(
            1
            for authority_decision in authority_decisions
            if authority_decision["lifecycle_transition_authorized"] is True
        ),
        "connector_authorization_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["connector_authority_authorized"] is True
        ),
        "terminal_closure_authorization_count": sum(
            1 for authority_decision in authority_decisions if authority_decision["terminal_closure_authorized"] is True
        ),
        "promotion_approval_count": sum(
            len(authority_decision["promotion_approval_refs"]) for authority_decision in authority_decisions
        ),
        "accepted_evidence_count": sum(
            len(authority_decision["accepted_evidence_refs"]) for authority_decision in authority_decisions
        ),
        "rejected_evidence_count": sum(
            len(authority_decision["rejected_evidence_refs"]) for authority_decision in authority_decisions
        ),
        "accepted_record_count": sum(
            len(authority_decision["accepted_record_refs"]) for authority_decision in authority_decisions
        ),
        "authority_fuse_blocking_count": len(
            {
                authority_fuse_ref
                for authority_decision in authority_decisions
                for authority_fuse_ref in authority_decision["authority_fuse_blocking_refs"]
            }
        ),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _authority_fuse_refs(component_id: str) -> tuple[str, ...]:
    try:
        fuse_set = build_component_authority_fuse()
    except ComponentAuthorityFuseError as exc:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(str(exc)) from exc
    fuse_records = fuse_set.get("fuses")
    if not isinstance(fuse_records, list):
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError("component authority fuse set must carry fuses")
    refs = [
        str(record["fuse_id"])
        for record in fuse_records
        if isinstance(record, dict)
        and record.get("component_id") == component_id
        and record.get("fuse_state") == "blocked"
        and record.get("self_upgrade_allowed") is False
        and isinstance(record.get("fuse_id"), str)
    ]
    if len(refs) != 1:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(
            "authority decision report requires exactly one blocked component authority-fuse ref"
        )
    return tuple(refs)


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionAuthorityDecisionReportError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
