"""Build Component Harness route-family promotion preflight reports.

Purpose: evaluate whether a blocked route-family ownership promotion can move
forward, and emit a governed denial when route-binding, lifecycle, authority,
or product-specific evidence is missing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family ownership readiness projection.
Invariants:
  - Promotion preflight is read-only and never mutates router inventory.
  - A blocked preflight cannot grant execution, connector, mutation, or
    terminal-closure authority.
  - Unknown or missing hard evidence blocks promotion.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_ownership import (
    ComponentRouteFamilyOwnershipError,
    build_component_route_family_ownership_report,
)


SCHEMA_VERSION = 1
DEFAULT_TARGET_SURFACE_ID = "governed_connector_framework"
DEFAULT_TARGET_COMPONENT_ID = "gmail_account_binding_gate"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_preflight_receipt",
    "component_route_family_promotion_witness_requirements_receipt",
    "component_route_family_promotion_witness_evidence_receipt",
    "component_route_family_promotion_approval_candidates_receipt",
    "component_route_family_promotion_approval_intake_receipt",
    "component_route_family_promotion_submitted_evidence_verifier_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_ownership_receipt",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "component_authority_envelope_witness",
    "authority_upgrade_witness",
    "authority_denial_receipt",
)


class ComponentRouteFamilyPromotionPreflightError(ValueError):
    """Raised when route-family promotion preflight cannot be evaluated."""


def build_component_route_family_promotion_preflight(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    ownership_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic route-family promotion preflight report.

    Input contract: target proof surface, target component, and optional
    ownership readiness report. Output contract: JSON-serializable preflight
    report. Error contract: raises ComponentRouteFamilyPromotionPreflightError
    for missing records, component mismatch, malformed ownership data, or
    selected-bound targets that do not need promotion.
    """

    report = ownership_report or _build_ownership_report()
    record = _ownership_record(report, surface_id)
    component_ids = _string_list(record.get("component_ids"))
    if component_id not in component_ids:
        raise ComponentRouteFamilyPromotionPreflightError(
            f"route family {surface_id} is not associated with component {component_id}"
        )
    readiness_state = _required_text(record, "readiness_state", f"route family {surface_id}")
    if readiness_state == "selected_component_bound":
        raise ComponentRouteFamilyPromotionPreflightError(
            f"route family {surface_id} already has selected component ownership"
        )

    gate_results = _gate_results(record=record, component_id=component_id)
    blocked_actions = _blocked_actions(record)
    return {
        "schema_version": SCHEMA_VERSION,
        "preflight_id": f"component_route_family_promotion_preflight.{surface_id}.v1",
        "mode": str(report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "outcome": "GovernanceBlocked",
        "promotion_preflight_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "source_refs": {
            "ownership_readiness": "examples/component_route_family_ownership.foundation.json",
            "router_inventory": "examples/component_router_inventory.foundation.json",
            "component_proof_binding": "examples/component_proof_binding.foundation.json",
            "component_authority_envelope_witnesses": "examples/component_authority_envelope_witnesses.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "route_family_snapshot": _route_family_snapshot(record),
        "gate_results": gate_results,
        "missing_evidence": _missing_evidence(gate_results),
        "blocked_actions": blocked_actions,
        "required_next_evidence": list(_string_list(record.get("required_next_evidence"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_preflight_validator",
            "component_route_family_promotion_preflight_tests",
            "component_route_family_ownership_validator",
            "component_router_inventory_validator",
            "component_proof_binding_validator",
        ],
        "next_action": (
            "Keep governed connector framework unpromoted until product-specific route ownership, "
            "lifecycle, and authority witnesses exist."
        ),
    }


def _build_ownership_report() -> dict[str, Any]:
    try:
        return build_component_route_family_ownership_report()
    except ComponentRouteFamilyOwnershipError as exc:
        raise ComponentRouteFamilyPromotionPreflightError(str(exc)) from exc


def _ownership_record(report: dict[str, Any], surface_id: str) -> dict[str, Any]:
    records = report.get("ownership_records")
    if not isinstance(records, list):
        raise ComponentRouteFamilyPromotionPreflightError("ownership report records must be a list")
    for record in records:
        if not isinstance(record, dict):
            raise ComponentRouteFamilyPromotionPreflightError("ownership report records must be objects")
        if record.get("surface_id") == surface_id:
            return record
    raise ComponentRouteFamilyPromotionPreflightError(f"route family {surface_id} not found")


def _gate_results(*, record: dict[str, Any], component_id: str) -> list[dict[str, Any]]:
    blockers = set(_string_list(record.get("promotion_blockers")))
    candidate_proof_components = set(_string_list(record.get("candidate_proof_bound_component_ids")))
    return [
        _gate(
            "route_binding_gate",
            "Fail",
            "missing_selected_component_route_binding",
            "route family is classified but not selected-bound in router inventory",
        ),
        _gate(
            "proof_binding_gate",
            "Pass" if component_id in candidate_proof_components else "Fail",
            "component_proof_surface_binding_present"
            if component_id in candidate_proof_components
            else "missing_component_proof_surface_binding",
            "candidate component proof binding references the surface"
            if component_id in candidate_proof_components
            else "candidate component proof binding does not reference the surface",
        ),
        _gate(
            "lifecycle_gate",
            "Fail",
            "missing_lifecycle_transition_receipt",
            "no lifecycle transition receipt upgrades this route family to selected ownership",
        ),
        _gate(
            "current_authority_envelope_gate",
            "Pass",
            "component_authority_envelope_witness_present",
            "current component authority envelope witness exists and denies live effects",
        ),
        _gate(
            "authority_upgrade_gate",
            "Fail",
            "missing_authority_upgrade_witness",
            "no separate authority upgrade witness allows route execution or connector action",
        ),
        _gate(
            "product_specific_boundary_gate",
            "Fail" if "generic_connector_surface_not_product_specific_authority" in blockers else "Pass",
            "generic_connector_surface_not_product_specific_authority",
            "generic connector routes are not product-specific Gmail mailbox authority",
        ),
        _gate(
            "terminal_closure_gate",
            "Pass",
            "terminal_closure_blocked",
            "terminal closure remains denied for the promotion preflight",
        ),
    ]


def _gate(gate_id: str, proof_state: str, evidence_key: str, notes: str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "proof_state": proof_state,
        "evidence_key": evidence_key,
        "notes": notes,
        "gate_is_not_execution_authority": True,
    }


def _route_family_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface_id": _required_text(record, "surface_id", "route family record"),
        "binding_level": _required_text(record, "binding_level", "route family record"),
        "readiness_state": _required_text(record, "readiness_state", "route family record"),
        "component_ids": list(_string_list(record.get("component_ids"))),
        "selected_bound_component_ids": list(_string_list(record.get("selected_bound_component_ids"))),
        "candidate_proof_bound_component_ids": list(_string_list(record.get("candidate_proof_bound_component_ids"))),
        "declared_route_count": int(record.get("declared_route_count", 0)),
        "sample_routes": list(_string_list(record.get("sample_routes"))),
        "promotion_blockers": list(_string_list(record.get("promotion_blockers"))),
    }


def _missing_evidence(gate_results: list[dict[str, Any]]) -> list[str]:
    missing = [
        _required_text(gate, "evidence_key", "gate result")
        for gate in gate_results
        if gate.get("proof_state") == "Fail"
    ]
    return sorted(set(missing))


def _blocked_actions(record: dict[str, Any]) -> list[str]:
    actions = set(_string_list(record.get("blocked_actions")))
    actions.update(
        {
            "connector_call",
            "external_send",
            "live_dispatch",
            "route_execution",
            "runtime_mutation",
            "terminal_closure",
        }
    )
    return sorted(actions)


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionPreflightError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
