"""Build Component Harness promotion gate-satisfaction evaluator reports.

Purpose: evaluate accepted record-only promotion evidence for gate
satisfaction without approving route-family promotion, mutating router
inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion operator-submitted evidence
records projection.
Invariants:
  - Record evidence gate satisfaction is not promotion approval.
  - Gate satisfaction cannot grant execution, connector, mutation, router
    inventory, or terminal-closure authority.
  - Promotion remains blocked until separate authority, lifecycle, route, and
    terminal-closure decisions exist.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_authority_fuse import (
    ComponentAuthorityFuseError,
    build_component_authority_fuse,
)
from mcoi_runtime.app.component_route_family_promotion_operator_submitted_evidence_records import (
    ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError,
    build_component_route_family_promotion_operator_submitted_evidence_records,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
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


class ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(ValueError):
    """Raised when promotion gate-satisfaction evaluation cannot be compiled."""


def build_component_route_family_promotion_gate_satisfaction_evaluator(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    operator_submitted_records_report: dict[str, Any] | None = None,
    authority_fuse_set: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic record-evidence gate-satisfaction evaluations.

    Input contract: target proof surface, target component, and optional
    operator-submitted evidence records report. Output contract:
    JSON-serializable gate-satisfaction evaluator report. Error contract:
    raises ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError when
    accepted record-only evidence is unavailable, malformed, target-mismatched,
    or no longer blocked from authority.
    """

    records_report = operator_submitted_records_report or _build_operator_records(
        surface_id=surface_id,
        component_id=component_id,
    )
    if records_report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "gate-satisfaction evaluation requires blocked operator-submitted evidence posture"
        )
    if records_report.get("record_decision") != "submitted_for_review":
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "gate-satisfaction evaluation requires submitted-for-review records"
        )
    if records_report.get("acceptance_decision") != "rules_applied_record_only":
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "gate-satisfaction evaluation requires record-only applied acceptance rules"
        )
    if (
        records_report.get("target_surface_id") != surface_id
        or records_report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "operator-submitted evidence records target does not match requested evaluator"
        )
    if records_report.get("accepted_records_are_not_promotion_authority") is not True:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "gate-satisfaction evaluation requires accepted records to remain non-authoritative"
        )

    fuse_set = authority_fuse_set or _build_authority_fuse_set()
    authority_fuse = _target_authority_fuse(fuse_set, component_id)
    authority_fuse_id = _required_text(authority_fuse, "fuse_id", f"authority fuse for {component_id}")

    records = _operator_submitted_records(records_report)
    evaluations = [_gate_evaluation(record, surface_id, authority_fuse_id) for record in records]
    approval_evidence_required = list(_string_list(records_report.get("approval_evidence_required")))
    satisfied_gate_refs = [str(evaluation["gate_evaluation_id"]) for evaluation in evaluations]
    accepted_record_refs = [str(evaluation["source_operator_submitted_record_id"]) for evaluation in evaluations]
    authority_fuse_refs = [authority_fuse_id]
    summary = _summary(evaluations, approval_evidence_required, authority_fuse_refs)
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_satisfaction_evaluator_id": (
            f"component_route_family_promotion_gate_satisfaction_evaluator.{surface_id}.v1"
        ),
        "mode": str(records_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "gate_satisfaction_decision": "record_evidence_satisfied_authority_pending",
        "promotion_decision": "blocked_pending_authority_decision",
        "all_record_evidence_gates_satisfied": True,
        "all_action_gates_satisfied": False,
        "gate_satisfaction_is_not_execution_authority": True,
        "gate_satisfaction_is_not_promotion_authority": True,
        "foundation_fixture_gate_satisfaction_is_not_live_operator_evidence": True,
        "separate_authority_decision_required": True,
        "separate_route_binding_decision_required": True,
        "separate_lifecycle_transition_required": True,
        "terminal_closure_required": True,
        "authority_fuse_enforced": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "operator_submitted_evidence_records": (
                "examples/"
                "component_route_family_promotion_operator_submitted_evidence_records.governed_connector_framework.json"
            ),
            "submitted_evidence_payload_examples": (
                "examples/"
                "component_route_family_promotion_submitted_evidence_payload_examples.governed_connector_framework.json"
            ),
            "promotion_approval_intake": (
                "examples/component_route_family_promotion_approval_intake.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "gate_evaluations": evaluations,
        "satisfied_gate_evaluation_refs": satisfied_gate_refs,
        "accepted_record_refs": accepted_record_refs,
        "rejected_record_refs": [],
        "authority_decision_refs": [],
        "authority_fuse_refs": authority_fuse_refs,
        "authority_fuse_blocking_refs": authority_fuse_refs,
        "promotion_approval_refs": [],
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": list(_string_list(records_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(records_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_gate_satisfaction_evaluator_validator",
            "component_route_family_promotion_gate_satisfaction_evaluator_tests",
            "component_route_family_promotion_operator_submitted_evidence_records_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create a separate promotion authority decision report that can consume record-evidence gate "
            "satisfaction and authority-fuse denial while still requiring external upgrade evidence."
        ),
    }


def _build_operator_records(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_operator_submitted_evidence_records(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError as exc:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(str(exc)) from exc


def _build_authority_fuse_set() -> dict[str, Any]:
    try:
        return build_component_authority_fuse()
    except ComponentAuthorityFuseError as exc:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(str(exc)) from exc


def _target_authority_fuse(fuse_set: dict[str, Any], component_id: str) -> dict[str, Any]:
    if fuse_set.get("fuse_set_is_not_execution_authority") is not True:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "authority fuse set must remain non-execution authority"
        )
    if fuse_set.get("live_execution_enabled") is not False or fuse_set.get("live_connector_send_enabled") is not False:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            "authority fuse set must deny live execution and connector send"
        )
    fuses = fuse_set.get("fuses")
    if not isinstance(fuses, list):
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError("authority fuse set must contain fuses")
    matching = [fuse for fuse in fuses if isinstance(fuse, dict) and fuse.get("component_id") == component_id]
    if len(matching) != 1:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
            f"authority fuse set must contain exactly one fuse for {component_id}"
        )
    authority_fuse = matching[0]
    expected_values = {
        "fuse_state": "blocked",
        "decision": "blocked",
        "outcome": "GovernanceBlocked",
    }
    for field_name, expected_value in expected_values.items():
        if authority_fuse.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                f"authority fuse {component_id} {field_name} must be {expected_value}"
            )
    for field_name in (
        "self_upgrade_allowed",
        "can_upgrade_authority",
        "can_mutate_authority_envelope",
        "can_enable_live_action",
        "terminal_closure_allowed",
    ):
        if authority_fuse.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                f"authority fuse {component_id} {field_name} must be false"
            )
    for field_name in ("fuse_is_not_execution_authority", "fuse_is_not_terminal_closure"):
        if authority_fuse.get(field_name) is not True:
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                f"authority fuse {component_id} {field_name} must be true"
            )
    return authority_fuse


def _operator_submitted_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    records = report.get("operator_submitted_evidence_records")
    if not isinstance(records, list):
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError("operator-submitted records must be a list")
    if len(records) != 4:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError("gate-satisfaction evaluation requires four records")
    output: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError("operator-submitted record entries must be objects")
        if record.get("record_state") != "submitted_for_review":
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                "gate-satisfaction evaluation requires submitted-for-review records"
            )
        if record.get("verification_state") != "reviewed" or record.get("acceptance_state") != "accepted_record_only":
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                "gate-satisfaction evaluation requires reviewed accepted-record-only records"
            )
        if record.get("proof_state") != "Pass":
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                "gate-satisfaction evaluation requires Pass record proof state"
            )
        if record.get("accepted_record_is_not_promotion_authority") is not True:
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                "gate-satisfaction evaluation requires record acceptance to remain non-authoritative"
            )
        if record.get("satisfies_requirement") is not False or record.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(
                "gate-satisfaction evaluation requires source records that do not satisfy promotion by themselves"
            )
        output.append(record)
    return output


def _gate_evaluation(record: dict[str, Any], surface_id: str, authority_fuse_id: str) -> dict[str, Any]:
    gate_id = _required_text(record, "gate_id", "operator-submitted evidence record")
    return {
        "gate_evaluation_id": f"promotion_gate_satisfaction_evaluation.{surface_id}.{gate_id}.v1",
        "source_operator_submitted_record_id": _required_text(
            record,
            "operator_submitted_record_id",
            f"operator-submitted evidence record {gate_id}",
        ),
        "source_payload_example_id": _required_text(
            record,
            "source_payload_example_id",
            f"operator-submitted evidence record {gate_id}",
        ),
        "source_record_envelope_id": _required_text(
            record,
            "source_record_envelope_id",
            f"operator-submitted evidence record {gate_id}",
        ),
        "source_verifier_request_id": _required_text(
            record,
            "source_verifier_request_id",
            f"operator-submitted evidence record {gate_id}",
        ),
        "source_intake_request_id": _required_text(
            record,
            "source_intake_request_id",
            f"operator-submitted evidence record {gate_id}",
        ),
        "gate_id": gate_id,
        "record_kind": _required_text(record, "record_kind", f"operator-submitted evidence record {gate_id}"),
        "evidence_key": _required_text(record, "evidence_key", f"operator-submitted evidence record {gate_id}"),
        "evaluation_state": "evaluated",
        "satisfaction_state": "satisfied_record_only",
        "proof_state": "Pass",
        "record_acceptance_state": "accepted_record_only",
        "record_proof_state": "Pass",
        "record_evidence_satisfies_gate": True,
        "satisfies_evidence_requirement": True,
        "satisfies_action_requirement": False,
        "blocks_promotion": True,
        "requires_separate_authority_decision": True,
        "requires_external_authority_upgrade_evidence": True,
        "authority_fuse_blocks_promotion": True,
        "requires_route_binding_decision": True,
        "requires_lifecycle_transition": True,
        "requires_terminal_closure": True,
        "gate_satisfaction_is_not_execution_authority": True,
        "gate_satisfaction_is_not_promotion_authority": True,
        "foundation_fixture_gate_satisfaction_is_not_live_operator_evidence": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "accepted_record_refs": [_required_text(record, "operator_submitted_record_id", f"operator-submitted evidence record {gate_id}")],
        "authority_decision_refs": [],
        "authority_fuse_refs": [authority_fuse_id],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "blocking_reason": (
            f"{gate_id} has record-evidence satisfaction but authority fuse {authority_fuse_id} "
            "still blocks promotion"
        ),
    }


def _summary(
    evaluations: list[dict[str, Any]],
    approval_evidence_required: list[str],
    authority_fuse_refs: list[str],
) -> dict[str, int]:
    return {
        "gate_evaluation_count": len(evaluations),
        "evaluated_gate_count": sum(1 for evaluation in evaluations if evaluation["evaluation_state"] == "evaluated"),
        "record_evidence_satisfied_gate_count": sum(
            1 for evaluation in evaluations if evaluation["record_evidence_satisfies_gate"] is True
        ),
        "action_satisfied_gate_count": sum(1 for evaluation in evaluations if evaluation["satisfies_action_requirement"] is True),
        "blocking_gate_count": sum(1 for evaluation in evaluations if evaluation["blocks_promotion"] is True),
        "accepted_record_count": sum(len(evaluation["accepted_record_refs"]) for evaluation in evaluations),
        "rejected_record_count": 0,
        "satisfied_evidence_requirement_count": sum(
            1 for evaluation in evaluations if evaluation["satisfies_evidence_requirement"] is True
        ),
        "satisfied_action_requirement_count": sum(
            1 for evaluation in evaluations if evaluation["satisfies_action_requirement"] is True
        ),
        "authority_decision_count": sum(len(evaluation["authority_decision_refs"]) for evaluation in evaluations),
        "promotion_approval_count": sum(len(evaluation["promotion_approval_refs"]) for evaluation in evaluations),
        "accepted_evidence_count": sum(len(evaluation["accepted_evidence_refs"]) for evaluation in evaluations),
        "rejected_evidence_count": sum(len(evaluation["rejected_evidence_refs"]) for evaluation in evaluations),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "authority_grant_count": sum(
            1
            for evaluation in evaluations
            if evaluation["grants_execution_authority"]
            or evaluation["grants_connector_authority"]
                or evaluation["grants_terminal_closure"]
        ),
        "authority_fuse_blocking_count": len(authority_fuse_refs),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionGateSatisfactionEvaluatorError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
