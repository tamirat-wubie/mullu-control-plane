"""Build Component Harness route-family promotion witness evidence.

Purpose: record concrete non-authoritative evidence for blocked promotion gates
without changing router inventory or authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion witness requirements projection.
Invariants:
  - Witness evidence is projection-only and never mutates router inventory.
  - Denial witnesses do not satisfy promotion requirements.
  - Witness evidence cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_witness_requirements import (
    ComponentRouteFamilyPromotionWitnessRequirementsError,
    build_component_route_family_promotion_witness_requirements,
)


SCHEMA_VERSION = 1
TARGET_WITNESS_GATES = (
    "route_binding_gate",
    "lifecycle_gate",
    "authority_upgrade_gate",
    "product_specific_boundary_gate",
)
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_witness_evidence_receipt",
    "component_route_family_promotion_approval_candidates_receipt",
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_promotion_witness_requirements_receipt",
    "component_route_family_promotion_preflight_receipt",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
    "authority_denial_receipt",
    "terminal_closure_denial_receipt",
)


class ComponentRouteFamilyPromotionWitnessEvidenceError(ValueError):
    """Raised when promotion witness evidence cannot be compiled."""


def build_component_route_family_promotion_witness_evidence(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    requirements_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic denial evidence for blocked promotion gates.

    Input contract: target proof surface, target component, and optional
    promotion witness requirements report. Output contract: JSON-serializable
    witness evidence report. Error contract: raises
    ComponentRouteFamilyPromotionWitnessEvidenceError when requirements are
    unavailable, malformed, target-mismatched, or no longer blocked.
    """

    requirements = requirements_report or _build_requirements(surface_id=surface_id, component_id=component_id)
    if requirements.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionWitnessEvidenceError("promotion witness evidence requires blocked requirements")
    if requirements.get("target_surface_id") != surface_id or requirements.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionWitnessEvidenceError("requirements target does not match requested witness evidence")

    requirement_by_gate = _requirement_by_gate(requirements)
    witness_records = [_witness_record(requirement_by_gate[gate_id], surface_id) for gate_id in TARGET_WITNESS_GATES]
    remaining_missing = _remaining_missing_evidence(requirements, witness_records)
    approval_evidence_required = _approval_evidence_required(witness_records)
    summary = _summary(requirements, witness_records, remaining_missing)
    summary["approval_evidence_required_count"] = len(approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": f"component_route_family_promotion_witness_evidence.{surface_id}.v1",
        "mode": str(requirements.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "evidence_decision": "denied",
        "witness_evidence_is_not_execution_authority": True,
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
            "promotion_witness_requirements": (
                "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "router_inventory": "examples/component_router_inventory.foundation.json",
            "component_authority_envelope_witnesses": "examples/component_authority_envelope_witnesses.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "witness_records": witness_records,
        "witnessed_evidence_keys": sorted(record["evidence_key"] for record in witness_records),
        "remaining_missing_evidence": remaining_missing,
        "approval_evidence_required": approval_evidence_required,
        "blocked_actions": list(_string_list(requirements.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_witness_evidence_validator",
            "component_route_family_promotion_witness_evidence_tests",
            "component_route_family_promotion_witness_requirements_validator",
        ],
        "next_action": (
            "Replace denial witnesses with approved route-binding, lifecycle, authority-upgrade, and product-specific "
            "ownership evidence before any router inventory or authority promotion can be reconsidered."
        ),
    }


def _build_requirements(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_witness_requirements(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionWitnessRequirementsError as exc:
        raise ComponentRouteFamilyPromotionWitnessEvidenceError(str(exc)) from exc


def _requirement_by_gate(requirements: dict[str, Any]) -> dict[str, dict[str, Any]]:
    requirement_records = requirements.get("promotion_witness_requirements")
    if not isinstance(requirement_records, list):
        raise ComponentRouteFamilyPromotionWitnessEvidenceError("promotion witness requirements must be a list")
    by_gate: dict[str, dict[str, Any]] = {}
    for requirement in requirement_records:
        if not isinstance(requirement, dict):
            raise ComponentRouteFamilyPromotionWitnessEvidenceError("promotion witness requirements entries must be objects")
        gate_id = _required_text(requirement, "gate_id", "promotion witness requirement")
        by_gate[gate_id] = requirement
    missing_gates = sorted(set(TARGET_WITNESS_GATES) - set(by_gate))
    if missing_gates:
        raise ComponentRouteFamilyPromotionWitnessEvidenceError(
            f"promotion witness requirements missing target gates: {missing_gates}"
        )
    return by_gate


def _witness_record(requirement: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(requirement, "gate_id", "promotion witness requirement")
    evidence_key = _required_text(requirement, "evidence_key", f"promotion witness requirement {gate_id}")
    witness_kind = _required_text(requirement, "witness_kind", f"promotion witness requirement {gate_id}")
    if requirement.get("proof_state") != "Fail":
        raise ComponentRouteFamilyPromotionWitnessEvidenceError(f"{gate_id} must still be a failed requirement")
    return {
        "witness_id": f"promotion_witness_evidence.{surface_id}.{gate_id}.v1",
        "requirement_id": _required_text(requirement, "requirement_id", f"promotion witness requirement {gate_id}"),
        "gate_id": gate_id,
        "witness_kind": witness_kind,
        "evidence_key": evidence_key,
        "proof_state": "Fail",
        "witness_state": "present_denial",
        "satisfies_requirement": False,
        "blocks_promotion": True,
        "required_before_promotion": True,
        "witness_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "observed_state": _observed_state(gate_id),
        "denial_reason": _denial_reason(gate_id),
        "source_refs": _source_refs(gate_id),
        "required_next_artifacts": list(_string_list(requirement.get("required_artifacts"))),
    }


def _observed_state(gate_id: str) -> str:
    observed_by_gate = {
        "route_binding_gate": (
            "router inventory classifies governed_connector_framework as proof-surface-bound, "
            "not selected-component-bound"
        ),
        "lifecycle_gate": (
            "no lifecycle transition receipt upgrades governed_connector_framework from blocked promotion "
            "to selected component ownership"
        ),
        "authority_upgrade_gate": (
            "current authority envelope denies execute, mutate, connector call, external send, "
            "and terminal closure"
        ),
        "product_specific_boundary_gate": (
            "generic governed connector framework is not a product-specific Gmail mailbox ownership surface"
        ),
    }
    return observed_by_gate.get(gate_id, "promotion gate remains unresolved")


def _denial_reason(gate_id: str) -> str:
    reasons_by_gate = {
        "route_binding_gate": "selected component router binding delta is absent",
        "lifecycle_gate": "lifecycle transition receipt is absent",
        "authority_upgrade_gate": "no authority upgrade witness or operator approval exists",
        "product_specific_boundary_gate": "product-specific Gmail ownership decision is absent",
    }
    return reasons_by_gate.get(gate_id, "required promotion witness is absent")


def _source_refs(gate_id: str) -> list[str]:
    refs_by_gate = {
        "route_binding_gate": [
            "examples/component_router_inventory.foundation.json",
            "examples/component_route_family_ownership.foundation.json",
        ],
        "lifecycle_gate": [
            "examples/component_lifecycle_transition_receipts.foundation.json",
            "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json",
        ],
        "authority_upgrade_gate": [
            "examples/component_authority_envelope_witnesses.foundation.json",
            "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json",
        ],
        "product_specific_boundary_gate": [
            "examples/component_registry.foundation.json",
            "examples/component_route_family_ownership.foundation.json",
        ],
    }
    return refs_by_gate.get(gate_id, ["examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json"])


def _remaining_missing_evidence(requirements: dict[str, Any], witness_records: list[dict[str, Any]]) -> list[str]:
    witnessed = {str(record["evidence_key"]) for record in witness_records}
    missing = set(_string_list(requirements.get("missing_evidence")))
    return sorted(missing - witnessed)


def _approval_evidence_required(witness_records: list[dict[str, Any]]) -> list[str]:
    required: set[str] = set()
    for record in witness_records:
        required.update(_string_list(record.get("required_next_artifacts")))
    return sorted(required)


def _summary(
    requirements: dict[str, Any],
    witness_records: list[dict[str, Any]],
    remaining_missing: list[str],
) -> dict[str, int]:
    requirements_summary = requirements.get("summary", {})
    missing_count = int(requirements_summary.get("missing_witness_count", 0)) if isinstance(requirements_summary, dict) else 0
    satisfied_count = sum(1 for record in witness_records if record["satisfies_requirement"] is True)
    return {
        "witness_record_count": len(witness_records),
        "witnessed_blocker_count": sum(1 for record in witness_records if record["blocks_promotion"] is True),
        "satisfied_requirement_count": satisfied_count,
        "unsatisfied_requirement_count": len(witness_records) - satisfied_count,
        "remaining_unwitnessed_blocker_count": len(remaining_missing),
        "original_missing_requirement_count": missing_count,
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionWitnessEvidenceError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
