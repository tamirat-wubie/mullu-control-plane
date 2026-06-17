"""Build Component Harness promotion submitted-evidence record envelopes.

Purpose: define template-only submitted-evidence record envelopes for blocked
route-family promotion verifier requests without accepting evidence, approving
promotion, changing router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion submitted-evidence verifier
projection.
Invariants:
  - Submitted-evidence record envelopes are templates and never mutate router inventory.
  - Template-only envelopes do not satisfy promotion requirements.
  - Record envelopes cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_verifier import (
    ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError,
    build_component_route_family_promotion_submitted_evidence_verifier,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
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


class ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(ValueError):
    """Raised when submitted-evidence record envelopes cannot be compiled."""


def build_component_route_family_promotion_submitted_evidence_records(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    submitted_evidence_verifier_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic template-only submitted-evidence record envelopes.

    Input contract: target proof surface, target component, and optional
    submitted-evidence verifier report. Output contract: JSON-serializable
    record-envelope report. Error contract: raises
    ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError when verifier
    posture is unavailable, malformed, target-mismatched, or no longer blocked.
    """

    verifier = submitted_evidence_verifier_report or _build_verifier(
        surface_id=surface_id,
        component_id=component_id,
    )
    if verifier.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(
            "submitted-evidence records require blocked verifier posture"
        )
    if verifier.get("verifier_decision") != "awaiting_submitted_evidence":
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(
            "submitted-evidence records require awaiting verifier posture"
        )
    if verifier.get("target_surface_id") != surface_id or verifier.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(
            "submitted-evidence verifier target does not match requested record envelopes"
        )

    verifier_requests = _verification_requests(verifier)
    record_envelopes = [_record_envelope(request, surface_id) for request in verifier_requests]
    approval_evidence_required = list(_string_list(verifier.get("approval_evidence_required")))
    summary = _summary(record_envelopes, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "submitted_evidence_records_id": (
            f"component_route_family_promotion_submitted_evidence_records.{surface_id}.v1"
        ),
        "mode": str(verifier.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "record_decision": "template_only",
        "submitted_evidence_records_are_not_execution_authority": True,
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
            "submitted_evidence_verifier": (
                "examples/"
                "component_route_family_promotion_submitted_evidence_verifier.governed_connector_framework.json"
            ),
            "promotion_approval_intake": (
                "examples/component_route_family_promotion_approval_intake.governed_connector_framework.json"
            ),
            "promotion_approval_candidates": (
                "examples/component_route_family_promotion_approval_candidates.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "record_envelopes": record_envelopes,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": list(_string_list(verifier.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(verifier.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_submitted_evidence_records_validator",
            "component_route_family_promotion_submitted_evidence_records_tests",
            "component_route_family_promotion_submitted_evidence_verifier_validator",
        ],
        "next_action": (
            "Create concrete submitted-evidence payload examples and verifier acceptance rules before any envelope "
            "can become a submitted record."
        ),
    }


def _build_verifier(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_submitted_evidence_verifier(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionSubmittedEvidenceVerifierError as exc:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(str(exc)) from exc


def _verification_requests(verifier: dict[str, Any]) -> list[dict[str, Any]]:
    requests = verifier.get("verification_requests")
    if not isinstance(requests, list):
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("verification requests must be a list")
    if len(requests) != 4:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("record envelopes require four verifier requests")
    output: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, dict):
            raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("verification request entries must be objects")
        if request.get("verifier_state") != "awaiting_submitted_evidence":
            raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("record envelopes require awaiting verifier requests")
        if request.get("verification_state") != "not_verified":
            raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("record envelopes require unverified requests")
        if request.get("satisfies_requirement") is not False or request.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError("record envelopes require blocking requests")
        output.append(request)
    return output


def _record_envelope(request: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(request, "gate_id", "promotion verifier request")
    return {
        "record_envelope_id": f"promotion_submitted_evidence_record_envelope.{surface_id}.{gate_id}.v1",
        "source_verifier_request_id": _required_text(
            request,
            "verifier_request_id",
            f"promotion verifier request {gate_id}",
        ),
        "source_intake_request_id": _required_text(
            request,
            "source_intake_request_id",
            f"promotion verifier request {gate_id}",
        ),
        "gate_id": gate_id,
        "record_kind": _required_text(request, "verifier_kind", f"promotion verifier request {gate_id}"),
        "evidence_key": _required_text(request, "evidence_key", f"promotion verifier request {gate_id}"),
        "envelope_state": "template_only",
        "submission_state": "not_submitted",
        "verification_state": "not_verified",
        "proof_state": "Unknown",
        "blocks_promotion": True,
        "satisfies_requirement": False,
        "record_envelope_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "required_artifacts": list(_string_list(request.get("required_artifacts"))),
        "payload_field_names": _payload_field_names(gate_id),
        "validation_rules": list(_string_list(request.get("verification_criteria"))),
        "rejection_conditions": list(_string_list(request.get("rejection_conditions"))),
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "payload_values_present": False,
        "operator_submission_state": "awaiting_operator",
        "missing_submission_reason": f"{gate_id} record envelope has no submitted payload",
    }


def _payload_field_names(gate_id: str) -> list[str]:
    common_fields = [
        "submitted_evidence_id",
        "source_verifier_request_id",
        "source_intake_request_id",
        "gate_id",
        "submitted_by",
        "submitted_at_epoch",
        "artifact_refs",
        "operator_approval_refs",
        "witness_refs",
        "authority_claims",
        "terminal_closure_claim",
        "no_router_mutation_claim",
    ]
    gate_fields = {
        "route_binding_gate": [
            "selected_component_bound_router_inventory_delta_ref",
            "component_route_binding_receipt_ref",
        ],
        "lifecycle_gate": [
            "component_lifecycle_transition_receipt_ref",
            "external_effect_operator_approval_ref",
        ],
        "authority_upgrade_gate": [
            "authority_upgrade_witness_ref",
            "connector_action_operator_approval_ref",
        ],
        "product_specific_boundary_gate": [
            "product_specific_ownership_decision_ref",
            "gmail_account_binding_evidence_receipt_ref",
        ],
    }
    return common_fields + gate_fields.get(gate_id, ["promotion_specific_artifact_ref"])


def _summary(record_envelopes: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "record_envelope_count": len(record_envelopes),
        "template_only_envelope_count": sum(1 for envelope in record_envelopes if envelope["envelope_state"] == "template_only"),
        "not_submitted_envelope_count": sum(1 for envelope in record_envelopes if envelope["submission_state"] == "not_submitted"),
        "submitted_record_count": sum(len(envelope["submitted_evidence_refs"]) for envelope in record_envelopes),
        "valid_record_count": 0,
        "accepted_evidence_count": sum(len(envelope["accepted_evidence_refs"]) for envelope in record_envelopes),
        "rejected_evidence_count": sum(len(envelope["rejected_evidence_refs"]) for envelope in record_envelopes),
        "satisfied_requirement_count": sum(1 for envelope in record_envelopes if envelope["satisfies_requirement"] is True),
        "blocking_envelope_count": sum(1 for envelope in record_envelopes if envelope["blocks_promotion"] is True),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "authority_grant_count": sum(
            1
            for envelope in record_envelopes
            if envelope["grants_execution_authority"]
            or envelope["grants_connector_authority"]
            or envelope["grants_terminal_closure"]
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
