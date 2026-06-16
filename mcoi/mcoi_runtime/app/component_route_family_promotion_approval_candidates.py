"""Build Component Harness route-family promotion approval candidates.

Purpose: describe non-mutating approval candidates for blocked promotion gates
without approving promotion, changing router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion witness evidence projection.
Invariants:
  - Approval candidates are draft-only and never mutate router inventory.
  - Candidate records do not satisfy promotion requirements.
  - Candidate records cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_witness_evidence import (
    ComponentRouteFamilyPromotionWitnessEvidenceError,
    build_component_route_family_promotion_witness_evidence,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_approval_candidates_receipt",
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
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


class ComponentRouteFamilyPromotionApprovalCandidatesError(ValueError):
    """Raised when promotion approval candidates cannot be compiled."""


def build_component_route_family_promotion_approval_candidates(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    witness_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic approval candidates for one blocked promotion.

    Input contract: target proof surface, target component, and optional
    promotion witness evidence report. Output contract: JSON-serializable
    approval candidate report. Error contract: raises
    ComponentRouteFamilyPromotionApprovalCandidatesError when witness evidence
    is unavailable, malformed, target-mismatched, or no longer blocked.
    """

    evidence = witness_evidence_report or _build_witness_evidence(surface_id=surface_id, component_id=component_id)
    if evidence.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionApprovalCandidatesError("promotion approval candidates require blocked evidence")
    if evidence.get("target_surface_id") != surface_id or evidence.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionApprovalCandidatesError(
            "witness evidence target does not match requested approval candidates"
        )

    witness_records = _witness_records(evidence)
    candidates = [_approval_candidate(record, surface_id) for record in witness_records]
    approval_evidence_required = _approval_evidence_required(candidates)
    summary = _summary(candidates, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_candidates_id": f"component_route_family_promotion_approval_candidates.{surface_id}.v1",
        "mode": str(evidence.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "candidate_decision": "not_approved",
        "approval_candidates_are_not_execution_authority": True,
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
            "promotion_witness_evidence": (
                "examples/component_route_family_promotion_witness_evidence.governed_connector_framework.json"
            ),
            "promotion_witness_requirements": (
                "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "router_inventory": "examples/component_router_inventory.foundation.json",
            "component_lifecycle_transition_receipts": "examples/component_lifecycle_transition_receipts.foundation.json",
            "component_authority_envelope_witnesses": "examples/component_authority_envelope_witnesses.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "approval_candidates": candidates,
        "approval_evidence_required": approval_evidence_required,
        "blocked_actions": list(_string_list(evidence.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_approval_candidates_validator",
            "component_route_family_promotion_approval_candidates_tests",
            "component_route_family_promotion_witness_evidence_validator",
        ],
        "next_action": (
            "Collect operator-governed approval artifacts for each candidate before replacing denial witnesses "
            "or mutating router inventory."
        ),
    }


def _build_witness_evidence(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_witness_evidence(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionWitnessEvidenceError as exc:
        raise ComponentRouteFamilyPromotionApprovalCandidatesError(str(exc)) from exc


def _witness_records(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    records = evidence.get("witness_records")
    if not isinstance(records, list):
        raise ComponentRouteFamilyPromotionApprovalCandidatesError("promotion witness records must be a list")
    if len(records) != 4:
        raise ComponentRouteFamilyPromotionApprovalCandidatesError("promotion approval candidates require four denial witnesses")
    output: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ComponentRouteFamilyPromotionApprovalCandidatesError("promotion witness records entries must be objects")
        if record.get("proof_state") != "Fail" or record.get("witness_state") != "present_denial":
            raise ComponentRouteFamilyPromotionApprovalCandidatesError("promotion approval candidates require denial witnesses")
        output.append(record)
    return output


def _approval_candidate(record: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(record, "gate_id", "promotion witness record")
    required_artifacts = list(_string_list(record.get("required_next_artifacts")))
    return {
        "candidate_id": f"promotion_approval_candidate.{surface_id}.{gate_id}.v1",
        "source_witness_id": _required_text(record, "witness_id", f"promotion witness {gate_id}"),
        "gate_id": gate_id,
        "candidate_kind": _required_text(record, "witness_kind", f"promotion witness {gate_id}"),
        "evidence_key": _required_text(record, "evidence_key", f"promotion witness {gate_id}"),
        "approval_state": "not_approved",
        "candidate_state": "draft_only",
        "proof_state": "Unknown",
        "satisfies_requirement": False,
        "blocks_promotion": True,
        "requires_operator_approval": True,
        "required_before_promotion": True,
        "candidate_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "approval_would_replace_denial": True,
        "approval_required_artifacts": required_artifacts,
        "candidate_scope": _candidate_scope(gate_id),
        "approval_preconditions": _approval_preconditions(gate_id),
    }


def _candidate_scope(gate_id: str) -> str:
    scopes_by_gate = {
        "route_binding_gate": "selected component router binding candidate",
        "lifecycle_gate": "component lifecycle transition candidate",
        "authority_upgrade_gate": "component authority upgrade candidate",
        "product_specific_boundary_gate": "Gmail product-specific ownership candidate",
    }
    return scopes_by_gate.get(gate_id, "promotion approval candidate")


def _approval_preconditions(gate_id: str) -> list[str]:
    preconditions_by_gate = {
        "route_binding_gate": [
            "selected_component_bound_router_inventory_delta",
            "component_route_binding_receipt",
        ],
        "lifecycle_gate": [
            "component_lifecycle_transition_receipt",
            "operator_approval_if_external_effect",
        ],
        "authority_upgrade_gate": [
            "authority_upgrade_witness",
            "operator_approval_if_connector_action_requested",
        ],
        "product_specific_boundary_gate": [
            "product_specific_ownership_decision",
            "gmail_account_binding_evidence_receipt",
        ],
    }
    return preconditions_by_gate.get(gate_id, ["promotion_approval_receipt"])


def _approval_evidence_required(candidates: list[dict[str, Any]]) -> list[str]:
    required: set[str] = set()
    for candidate in candidates:
        required.update(_string_list(candidate.get("approval_required_artifacts")))
        required.update(_string_list(candidate.get("approval_preconditions")))
    return sorted(required)


def _summary(candidates: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "approval_candidate_count": len(candidates),
        "not_approved_candidate_count": sum(1 for candidate in candidates if candidate["approval_state"] == "not_approved"),
        "draft_only_candidate_count": sum(1 for candidate in candidates if candidate["candidate_state"] == "draft_only"),
        "satisfied_requirement_count": sum(1 for candidate in candidates if candidate["satisfies_requirement"] is True),
        "blocking_candidate_count": sum(1 for candidate in candidates if candidate["blocks_promotion"] is True),
        "approval_evidence_required_count": len(approval_evidence_required),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionApprovalCandidatesError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
