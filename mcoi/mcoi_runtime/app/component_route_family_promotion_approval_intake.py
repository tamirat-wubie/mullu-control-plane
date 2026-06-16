"""Build Component Harness route-family promotion approval intake.

Purpose: describe open operator evidence intake requests for blocked
route-family promotion approval candidates without approving promotion,
changing router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion approval candidates projection.
Invariants:
  - Approval intake is request-only and never mutates router inventory.
  - Intake requests do not satisfy promotion requirements.
  - Intake requests cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_approval_candidates import (
    ComponentRouteFamilyPromotionApprovalCandidatesError,
    build_component_route_family_promotion_approval_candidates,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
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


class ComponentRouteFamilyPromotionApprovalIntakeError(ValueError):
    """Raised when promotion approval intake cannot be compiled."""


def build_component_route_family_promotion_approval_intake(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    approval_candidates_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic intake requests for blocked promotion candidates.

    Input contract: target proof surface, target component, and optional
    promotion approval candidates report. Output contract: JSON-serializable
    approval intake report. Error contract: raises
    ComponentRouteFamilyPromotionApprovalIntakeError when approval candidates
    are unavailable, malformed, target-mismatched, or no longer blocked.
    """

    candidates_report = approval_candidates_report or _build_approval_candidates(
        surface_id=surface_id,
        component_id=component_id,
    )
    if candidates_report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval intake requires blocked candidates")
    if candidates_report.get("candidate_decision") != "not_approved":
        raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval intake requires not-approved candidates")
    if (
        candidates_report.get("target_surface_id") != surface_id
        or candidates_report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionApprovalIntakeError(
            "approval candidates target does not match requested approval intake"
        )

    candidates = _approval_candidates(candidates_report)
    intake_requests = [_intake_request(candidate, surface_id) for candidate in candidates]
    approval_evidence_required = list(_string_list(candidates_report.get("approval_evidence_required")))
    summary = _summary(intake_requests, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_intake_id": f"component_route_family_promotion_approval_intake.{surface_id}.v1",
        "mode": str(candidates_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "intake_decision": "awaiting_operator_evidence",
        "approval_intake_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "terminal_closure_required": True,
        "source_refs": {
            "promotion_approval_candidates": (
                "examples/component_route_family_promotion_approval_candidates.governed_connector_framework.json"
            ),
            "promotion_witness_evidence": (
                "examples/component_route_family_promotion_witness_evidence.governed_connector_framework.json"
            ),
            "promotion_witness_requirements": (
                "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "approval_requests": intake_requests,
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": approval_evidence_required,
        "blocked_actions": list(_string_list(candidates_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_approval_intake_validator",
            "component_route_family_promotion_approval_intake_tests",
            "component_route_family_promotion_approval_candidates_validator",
        ],
        "next_action": (
            "Collect submitted evidence as pending review records, then validate those records with a separate "
            "approval verifier before any promotion gate can be satisfied."
        ),
    }


def _build_approval_candidates(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_approval_candidates(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionApprovalCandidatesError as exc:
        raise ComponentRouteFamilyPromotionApprovalIntakeError(str(exc)) from exc


def _approval_candidates(candidates_report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = candidates_report.get("approval_candidates")
    if not isinstance(candidates, list):
        raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval candidates must be a list")
    if len(candidates) != 4:
        raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval intake requires four candidates")
    output: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval candidate entries must be objects")
        if candidate.get("approval_state") != "not_approved" or candidate.get("candidate_state") != "draft_only":
            raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval intake requires draft candidates")
        if candidate.get("satisfies_requirement") is not False or candidate.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionApprovalIntakeError("promotion approval intake requires blocking candidates")
        output.append(candidate)
    return output


def _intake_request(candidate: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(candidate, "gate_id", "promotion approval candidate")
    required_artifacts = list(_string_list(candidate.get("approval_required_artifacts")))
    preconditions = list(_string_list(candidate.get("approval_preconditions")))
    return {
        "request_id": f"promotion_approval_intake.{surface_id}.{gate_id}.v1",
        "source_candidate_id": _required_text(candidate, "candidate_id", f"promotion approval candidate {gate_id}"),
        "gate_id": gate_id,
        "request_kind": _required_text(candidate, "candidate_kind", f"promotion approval candidate {gate_id}"),
        "evidence_key": _required_text(candidate, "evidence_key", f"promotion approval candidate {gate_id}"),
        "intake_state": "open",
        "approval_state": "not_approved",
        "evidence_submission_state": "not_submitted",
        "proof_state": "Unknown",
        "operator_required": True,
        "blocks_promotion": True,
        "satisfies_requirement": False,
        "request_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "required_artifacts": sorted(set(required_artifacts + preconditions)),
        "acceptance_criteria": _acceptance_criteria(gate_id),
        "rejection_conditions": _rejection_conditions(gate_id),
        "submitted_evidence_refs": [],
    }


def _acceptance_criteria(gate_id: str) -> list[str]:
    criteria_by_gate = {
        "route_binding_gate": [
            "router_inventory_delta_names_selected_component",
            "component_route_binding_receipt_schema_valid",
            "route_binding_validator_passes",
        ],
        "lifecycle_gate": [
            "lifecycle_transition_receipt_schema_valid",
            "transition_cause_links_to_denial_witness",
            "operator_approval_if_external_effect_present",
        ],
        "authority_upgrade_gate": [
            "authority_upgrade_witness_schema_valid",
            "connector_action_operator_approval_present",
            "authority_envelope_validator_passes",
        ],
        "product_specific_boundary_gate": [
            "product_specific_ownership_decision_schema_valid",
            "gmail_account_binding_evidence_receipt_present",
            "ownership_decision_links_to_registered_component",
        ],
    }
    return criteria_by_gate.get(gate_id, ["submitted_evidence_schema_valid"])


def _rejection_conditions(gate_id: str) -> list[str]:
    common = [
        "submitted_evidence_claims_live_execution",
        "submitted_evidence_mutates_router_inventory",
        "submitted_evidence_grants_terminal_closure",
        "operator_approval_receipt_missing",
    ]
    gate_specific = {
        "route_binding_gate": ["route_binding_delta_missing"],
        "lifecycle_gate": ["lifecycle_transition_receipt_missing"],
        "authority_upgrade_gate": ["authority_upgrade_witness_missing"],
        "product_specific_boundary_gate": ["product_specific_ownership_decision_missing"],
    }
    return common + gate_specific.get(gate_id, ["required_artifact_missing"])


def _summary(intake_requests: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "intake_request_count": len(intake_requests),
        "open_request_count": sum(1 for request in intake_requests if request["intake_state"] == "open"),
        "not_submitted_request_count": sum(
            1 for request in intake_requests if request["evidence_submission_state"] == "not_submitted"
        ),
        "submitted_evidence_count": sum(len(request["submitted_evidence_refs"]) for request in intake_requests),
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_operator_approval_count": sum(1 for request in intake_requests if request["operator_required"] is True),
        "authority_grant_count": sum(
            1
            for request in intake_requests
            if request["grants_execution_authority"]
            or request["grants_connector_authority"]
            or request["grants_terminal_closure"]
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionApprovalIntakeError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
