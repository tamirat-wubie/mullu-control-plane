"""Build Component Harness route-family promotion witness requirements.

Purpose: compile the witness contract required before a blocked route-family
promotion can be reconsidered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion preflight projection.
Invariants:
  - Witness requirements are projection-only and never mutate router inventory.
  - Missing hard witnesses keep promotion blocked.
  - Satisfied current witnesses do not grant execution or connector authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
    ComponentRouteFamilyPromotionPreflightError,
    build_component_route_family_promotion_preflight,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_witness_requirements_receipt",
    "component_route_family_promotion_witness_evidence_receipt",
    "component_route_family_promotion_approval_candidates_receipt",
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_promotion_preflight_receipt",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "terminal_closure_denial_receipt",
)


class ComponentRouteFamilyPromotionWitnessRequirementsError(ValueError):
    """Raised when promotion witness requirements cannot be compiled."""


def build_component_route_family_promotion_witness_requirements(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    preflight_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic witness requirements for one blocked promotion.

    Input contract: target proof surface, target component, and optional
    promotion preflight report. Output contract: JSON-serializable witness
    requirements report. Error contract: raises
    ComponentRouteFamilyPromotionWitnessRequirementsError when the preflight is
    unavailable, malformed, or no longer blocked.
    """

    preflight = preflight_report or _build_preflight(surface_id=surface_id, component_id=component_id)
    if preflight.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionWitnessRequirementsError("promotion witness requirements require blocked preflight")
    if preflight.get("target_surface_id") != surface_id or preflight.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionWitnessRequirementsError("preflight target does not match requested witness target")

    requirements = _requirements(preflight)
    summary = _summary(requirements)
    return {
        "schema_version": SCHEMA_VERSION,
        "requirements_id": f"component_route_family_promotion_witness_requirements.{surface_id}.v1",
        "mode": str(preflight.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "requirements_are_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "ready_for_promotion": False,
        "source_refs": {
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "ownership_readiness": "examples/component_route_family_ownership.foundation.json",
            "router_inventory": "examples/component_router_inventory.foundation.json",
            "component_proof_binding": "examples/component_proof_binding.foundation.json",
            "component_authority_envelope_witnesses": "examples/component_authority_envelope_witnesses.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "promotion_witness_requirements": requirements,
        "missing_evidence": list(_string_list(preflight.get("missing_evidence"))),
        "blocked_actions": list(_string_list(preflight.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_witness_requirements_validator",
            "component_route_family_promotion_witness_requirements_tests",
            "component_route_family_promotion_preflight_validator",
            "component_route_family_ownership_validator",
        ],
        "next_action": (
            "Create route-binding, lifecycle, authority-upgrade, and product-specific ownership witnesses "
            "before mutating router inventory."
        ),
    }


def _build_preflight(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_preflight(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionPreflightError as exc:
        raise ComponentRouteFamilyPromotionWitnessRequirementsError(str(exc)) from exc


def _requirements(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    gate_results = preflight.get("gate_results")
    if not isinstance(gate_results, list):
        raise ComponentRouteFamilyPromotionWitnessRequirementsError("preflight gate_results must be a list")
    requirements = [_requirement(gate) for gate in gate_results if isinstance(gate, dict)]
    if len(requirements) != len(gate_results):
        raise ComponentRouteFamilyPromotionWitnessRequirementsError("preflight gate_results entries must be objects")
    return requirements


def _requirement(gate: dict[str, Any]) -> dict[str, Any]:
    gate_id = _required_text(gate, "gate_id", "preflight gate")
    proof_state = _required_text(gate, "proof_state", f"preflight gate {gate_id}")
    evidence_key = _required_text(gate, "evidence_key", f"preflight gate {gate_id}")
    requirement_state = "satisfied" if proof_state == "Pass" else "missing"
    return {
        "requirement_id": f"promotion_witness.{gate_id}",
        "gate_id": gate_id,
        "witness_kind": _witness_kind(gate_id),
        "evidence_key": evidence_key,
        "proof_state": proof_state,
        "requirement_state": requirement_state,
        "blocks_promotion": proof_state != "Pass",
        "required_before_promotion": True,
        "required_artifacts": _required_artifacts(gate_id),
        "notes": _required_text(gate, "notes", f"preflight gate {gate_id}"),
        "witness_is_not_execution_authority": True,
    }


def _witness_kind(gate_id: str) -> str:
    return {
        "route_binding_gate": "route_binding",
        "proof_binding_gate": "proof_binding",
        "lifecycle_gate": "lifecycle_transition",
        "current_authority_envelope_gate": "current_authority_envelope",
        "authority_upgrade_gate": "authority_upgrade",
        "product_specific_boundary_gate": "product_specific_ownership",
        "terminal_closure_gate": "terminal_closure_denial",
    }.get(gate_id, "unknown")


def _required_artifacts(gate_id: str) -> list[str]:
    artifacts_by_gate = {
        "route_binding_gate": [
            "component_route_binding_receipt",
            "selected_component_bound_router_inventory_delta",
        ],
        "proof_binding_gate": [
            "component_proof_surface_binding",
            "docs/40_proof_coverage_matrix.md#governed_connector_framework",
        ],
        "lifecycle_gate": [
            "component_lifecycle_transition_receipt",
            "operator_approval_if_external_effect",
        ],
        "current_authority_envelope_gate": [
            "examples/component_authority_envelope_witnesses.foundation.json",
        ],
        "authority_upgrade_gate": [
            "authority_upgrade_witness",
            "operator_approval_if_connector_action_requested",
        ],
        "product_specific_boundary_gate": [
            "product_specific_ownership_decision",
            "gmail_account_binding_evidence_receipt",
        ],
        "terminal_closure_gate": [
            "terminal_closure_denial_receipt",
        ],
    }
    return artifacts_by_gate.get(gate_id, ["unclassified_promotion_witness"])


def _summary(requirements: list[dict[str, Any]]) -> dict[str, int]:
    missing = [requirement for requirement in requirements if requirement["requirement_state"] == "missing"]
    satisfied = [requirement for requirement in requirements if requirement["requirement_state"] == "satisfied"]
    return {
        "witness_requirement_count": len(requirements),
        "satisfied_witness_count": len(satisfied),
        "missing_witness_count": len(missing),
        "hard_blocker_count": sum(1 for requirement in requirements if requirement["blocks_promotion"] is True),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionWitnessRequirementsError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
