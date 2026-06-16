"""Build Component Harness promotion submitted-evidence verifier.

Purpose: verify the current submitted-evidence posture for blocked
route-family promotion intake requests without approving promotion, changing
router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion approval intake projection.
Invariants:
  - Submitted-evidence verification is read-only and never mutates router inventory.
  - Missing submitted evidence keeps all promotion gates blocked.
  - Verification requests cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_approval_intake import (
    ComponentRouteFamilyPromotionApprovalIntakeError,
    build_component_route_family_promotion_approval_intake,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
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


class ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(ValueError):
    """Raised when submitted-evidence verifier projection cannot be compiled."""


def build_component_route_family_promotion_submitted_evidence_verifier(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    approval_intake_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic verifier posture for promotion evidence intake.

    Input contract: target proof surface, target component, and optional
    promotion approval intake report. Output contract: JSON-serializable
    submitted-evidence verifier report. Error contract: raises
    ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError when approval
    intake is unavailable, malformed, target-mismatched, or no longer blocked.
    """

    intake = approval_intake_report or _build_approval_intake(surface_id=surface_id, component_id=component_id)
    if intake.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(
            "promotion submitted-evidence verifier requires blocked intake"
        )
    if intake.get("intake_decision") != "awaiting_operator_evidence":
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(
            "promotion submitted-evidence verifier requires awaiting intake"
        )
    if intake.get("target_surface_id") != surface_id or intake.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(
            "approval intake target does not match requested submitted-evidence verifier"
        )

    intake_requests = _approval_requests(intake)
    verification_requests = [_verification_request(request, surface_id) for request in intake_requests]
    approval_evidence_required = list(_string_list(intake.get("approval_evidence_required")))
    summary = _summary(verification_requests, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "submitted_evidence_verifier_id": (
            f"component_route_family_promotion_submitted_evidence_verifier.{surface_id}.v1"
        ),
        "mode": str(intake.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "verifier_decision": "awaiting_submitted_evidence",
        "submitted_evidence_verifier_is_not_execution_authority": True,
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
            "promotion_approval_intake": (
                "examples/component_route_family_promotion_approval_intake.governed_connector_framework.json"
            ),
            "promotion_approval_candidates": (
                "examples/component_route_family_promotion_approval_candidates.governed_connector_framework.json"
            ),
            "promotion_witness_evidence": (
                "examples/component_route_family_promotion_witness_evidence.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "verification_requests": verification_requests,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": list(_string_list(intake.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(intake.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_submitted_evidence_verifier_validator",
            "component_route_family_promotion_submitted_evidence_verifier_tests",
            "component_route_family_promotion_approval_intake_validator",
        ],
        "next_action": (
            "Define submitted-evidence record envelopes before any verifier request can evaluate evidence or "
            "replace a denial witness."
        ),
    }


def _build_approval_intake(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_approval_intake(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionApprovalIntakeError as exc:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(str(exc)) from exc


def _approval_requests(intake: dict[str, Any]) -> list[dict[str, Any]]:
    requests = intake.get("approval_requests")
    if not isinstance(requests, list):
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError("promotion approval requests must be a list")
    if len(requests) != 4:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError("submitted-evidence verifier requires four requests")
    output: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, dict):
            raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError("promotion approval request entries must be objects")
        if request.get("approval_state") != "not_approved" or request.get("intake_state") != "open":
            raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError("submitted-evidence verifier requires open requests")
        if request.get("evidence_submission_state") != "not_submitted":
            raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(
                "submitted-evidence verifier requires not-submitted requests"
            )
        if request.get("satisfies_requirement") is not False or request.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(
                "submitted-evidence verifier requires blocking requests"
            )
        output.append(request)
    return output


def _verification_request(request: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(request, "gate_id", "promotion approval request")
    return {
        "verifier_request_id": f"promotion_submitted_evidence_verifier.{surface_id}.{gate_id}.v1",
        "source_intake_request_id": _required_text(request, "request_id", f"promotion approval request {gate_id}"),
        "gate_id": gate_id,
        "verifier_kind": _required_text(request, "request_kind", f"promotion approval request {gate_id}"),
        "evidence_key": _required_text(request, "evidence_key", f"promotion approval request {gate_id}"),
        "intake_state": "open",
        "evidence_submission_state": "not_submitted",
        "verifier_state": "awaiting_submitted_evidence",
        "verification_state": "not_verified",
        "proof_state": "Unknown",
        "blocks_promotion": True,
        "satisfies_requirement": False,
        "verifier_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "required_artifacts": list(_string_list(request.get("required_artifacts"))),
        "verification_criteria": _verification_criteria(request),
        "rejection_conditions": _rejection_conditions(request),
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_submission_reason": f"{gate_id} has no submitted evidence refs",
    }


def _verification_criteria(request: dict[str, Any]) -> list[str]:
    criteria = set(_string_list(request.get("acceptance_criteria")))
    criteria.update(
        (
            "submitted_evidence_record_schema_valid",
            "submitted_evidence_links_to_source_intake_request",
            "submitted_evidence_carries_operator_approval_when_required",
            "submitted_evidence_does_not_grant_authority_by_itself",
        )
    )
    return sorted(criteria)


def _rejection_conditions(request: dict[str, Any]) -> list[str]:
    conditions = set(_string_list(request.get("rejection_conditions")))
    conditions.update(
        (
            "submitted_evidence_record_missing",
            "submitted_evidence_record_schema_invalid",
            "submitted_evidence_unlinked_to_intake_request",
            "submitted_evidence_claims_terminal_closure",
        )
    )
    return sorted(conditions)


def _summary(verification_requests: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "verification_request_count": len(verification_requests),
        "awaiting_submitted_evidence_count": sum(
            1 for request in verification_requests if request["verifier_state"] == "awaiting_submitted_evidence"
        ),
        "not_verified_request_count": sum(
            1 for request in verification_requests if request["verification_state"] == "not_verified"
        ),
        "submitted_evidence_count": sum(len(request["submitted_evidence_refs"]) for request in verification_requests),
        "accepted_evidence_count": sum(len(request["accepted_evidence_refs"]) for request in verification_requests),
        "rejected_evidence_count": sum(len(request["rejected_evidence_refs"]) for request in verification_requests),
        "satisfied_requirement_count": sum(
            1 for request in verification_requests if request["satisfies_requirement"] is True
        ),
        "blocking_request_count": sum(1 for request in verification_requests if request["blocks_promotion"] is True),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "authority_grant_count": sum(
            1
            for request in verification_requests
            if request["grants_execution_authority"]
            or request["grants_connector_authority"]
            or request["grants_terminal_closure"]
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
