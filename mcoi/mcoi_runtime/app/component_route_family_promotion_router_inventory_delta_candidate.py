"""Build Component Harness promotion router-inventory delta candidates.

Purpose: consume missing-evidence ledgers and define the selected component
router-inventory delta path without applying the delta, mutating router
inventory, creating evidence, granting authority, approving promotion, or
claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion missing-evidence ledger.
Invariants:
  - A delta candidate is not a router-inventory delta witness.
  - A dry-run candidate cannot mutate router inventory.
  - Selected component binding remains unauthorized until a separate witness
    and downstream receipts exist.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_missing_evidence_ledger import (
    ComponentRouteFamilyPromotionMissingEvidenceLedgerError,
    build_component_route_family_promotion_missing_evidence_ledger,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)


SCHEMA_VERSION = 1
TARGET_ARTIFACT_ID = "selected_component_bound_router_inventory_delta"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_router_inventory_delta_candidate_receipt",
    "component_route_family_promotion_missing_evidence_ledger_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_certificate",
)
DOWNSTREAM_REQUIRED_ARTIFACTS = (
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_certificate",
)
BLOCKED_ACTIONS = (
    "autonomous_execution",
    "connector_call",
    "external_send",
    "filesystem_write",
    "live_dispatch",
    "route_execution",
    "router_inventory_mutation",
    "runtime_mutation",
    "selected_component_binding",
    "terminal_closure",
)


class ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(ValueError):
    """Raised when a router-inventory delta candidate cannot be compiled."""


def build_component_route_family_promotion_router_inventory_delta_candidate(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    missing_evidence_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic dry-run router-inventory delta candidate.

    Input contract: target proof surface, component, product bundle, and
    optional missing-evidence ledger. Output contract: JSON-serializable
    dry-run candidate. Error contract: raises
    ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError when the
    source ledger is unavailable, malformed, target-mismatched, or no longer
    records the selected router-inventory delta as missing.
    """

    ledger = missing_evidence_ledger or _build_missing_evidence_ledger(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_missing_evidence_ledger(ledger, surface_id, component_id, product_bundle_id)
    source_record = _source_router_inventory_missing_record(ledger)
    candidate = _router_inventory_delta_candidate(source_record, surface_id, component_id, product_bundle_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "router_inventory_delta_candidate_report_id": (
            f"component_route_family_promotion_router_inventory_delta_candidate.{surface_id}.v1"
        ),
        "mode": str(ledger.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "candidate_status": "draft_not_applied",
        "promotion_decision": "blocked_router_inventory_delta_not_applied",
        "evidence_status": "candidate_defined_not_witnessed",
        "router_inventory_delta_candidate_issued": True,
        "router_inventory_delta_candidate_is_not_delta": True,
        "router_inventory_delta_candidate_is_not_evidence": True,
        "router_inventory_delta_candidate_is_not_witness": True,
        "router_inventory_delta_candidate_is_not_route_binding": True,
        "router_inventory_delta_candidate_is_not_authority_grant": True,
        "router_inventory_delta_candidate_is_not_promotion_approval": True,
        "router_inventory_delta_candidate_is_not_terminal_closure": True,
        "separate_router_inventory_delta_required": True,
        "separate_route_binding_receipt_required": True,
        "separate_lifecycle_transition_receipt_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_product_ownership_witness_required": True,
        "separate_terminal_closure_certificate_required": True,
        "dry_run_only": True,
        "delta_applied": False,
        "router_inventory_mutated": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "selected_component_binding_created": False,
        "route_binding_authorized": False,
        "lifecycle_transition_authorized": False,
        "authority_upgrade_authorized": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_certificate_minted": False,
        "terminal_closure_authorized": False,
        "terminal_closure_claimed": False,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "missing_evidence_ledger": (
                "examples/"
                "component_route_family_promotion_missing_evidence_ledger.governed_connector_framework.json"
            ),
            "terminal_closure_denial_report": (
                "examples/"
                "component_route_family_promotion_terminal_closure_denial_report.governed_connector_framework.json"
            ),
            "router_inventory": "examples/component_router_inventory.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(candidate),
        "router_inventory_delta_candidates": [candidate],
        "router_inventory_delta_candidate_refs": [str(candidate["candidate_id"])],
        "source_missing_evidence_record_refs": [str(candidate["source_missing_evidence_id"])],
        "source_missing_evidence_ledger_refs": [str(ledger["missing_evidence_ledger_id"])],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "route_binding_receipt_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "authority_upgrade_witness_refs": [],
        "authority_grant_refs": [],
        "product_ownership_witness_refs": [],
        "terminal_closure_certificate_refs": [],
        "terminal_closure_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "required_downstream_artifacts": list(DOWNSTREAM_REQUIRED_ARTIFACTS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_router_inventory_delta_candidate_validator",
            "component_route_family_promotion_router_inventory_delta_candidate_tests",
            "component_route_family_promotion_missing_evidence_ledger_validator",
        ],
        "next_action": (
            "Keep the candidate dry-run only; emit a separate selected-component router-inventory "
            "delta witness only through a governed mutation path."
        ),
    }


def _build_missing_evidence_ledger(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_missing_evidence_ledger(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionMissingEvidenceLedgerError as exc:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(str(exc)) from exc


def _validate_missing_evidence_ledger(
    ledger: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "evidence_status": "missing_required_witnesses",
        "promotion_decision": "blocked_missing_required_evidence",
    }
    for field_name, expected_value in expected_strings.items():
        if ledger.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
                f"router-inventory delta candidate requires ledger {field_name}={expected_value}"
            )
    if (
        ledger.get("target_surface_id") != surface_id
        or ledger.get("target_component_id") != component_id
        or ledger.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            "missing-evidence ledger target does not match requested router-inventory delta candidate"
        )
    for field_name in (
        "terminal_closure_authorized",
        "terminal_certificate_minted",
        "promotion_approved",
        "authority_granted",
        "mutates_router_inventory",
        "ready_for_promotion",
        "can_claim_terminal_closure",
    ):
        if ledger.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
                f"missing-evidence ledger must keep {field_name} false before delta candidate"
            )


def _source_router_inventory_missing_record(ledger: dict[str, Any]) -> dict[str, Any]:
    records = ledger.get("missing_evidence_records")
    if not isinstance(records, list):
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            "missing-evidence records must be a list"
        )
    matches = [
        record
        for record in records
        if isinstance(record, dict) and record.get("artifact_id") == TARGET_ARTIFACT_ID
    ]
    if len(matches) != 1:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            "router-inventory delta candidate requires exactly one selected-component delta missing record"
        )
    record = matches[0]
    if record.get("evidence_state") != "missing" or record.get("proof_state") != "Unknown":
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            "selected-component router-inventory delta source record must remain missing and Unknown"
        )
    if record.get("evidence_present") is not False or record.get("blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            "selected-component router-inventory delta source record must block promotion without evidence"
        )
    return record


def _router_inventory_delta_candidate(
    source_record: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    source_missing_evidence_id = _required_text(source_record, "missing_evidence_id", "source missing record")
    return {
        "candidate_id": f"router_inventory_delta_candidate.{surface_id}.{component_id}.v1",
        "artifact_id": TARGET_ARTIFACT_ID,
        "candidate_state": "draft_not_applied",
        "delta_kind": "selected_component_bound_router_inventory_delta",
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "product_bundle_id": product_bundle_id,
        "source_missing_evidence_id": source_missing_evidence_id,
        "source_missing_evidence_refs": [source_missing_evidence_id],
        "source_evidence_state": "missing",
        "source_proof_state": "Unknown",
        "proposed_binding_state": "selected_component_bound",
        "proposed_binding_is_not_current_state": True,
        "dry_run_only": True,
        "delta_applied": False,
        "evidence_present": False,
        "witness_emitted": False,
        "router_inventory_mutated": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "selected_component_binding_created": False,
        "route_binding_authorized": False,
        "lifecycle_transition_authorized": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_authorized": False,
        "terminal_closure_claimed": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "candidate_is_not_delta": True,
        "candidate_is_not_evidence": True,
        "candidate_is_not_witness": True,
        "candidate_is_not_route_binding": True,
        "candidate_is_not_authority_grant": True,
        "candidate_is_not_promotion_approval": True,
        "candidate_is_not_terminal_closure": True,
        "required_downstream_artifacts": list(DOWNSTREAM_REQUIRED_ARTIFACTS),
        "proposed_delta": {
            "would_bind_surface_id": surface_id,
            "would_bind_component_id": component_id,
            "would_bind_product_bundle_id": product_bundle_id,
            "would_preserve_blocked_actions": list(BLOCKED_ACTIONS),
            "would_require_separate_witness": True,
            "would_not_enable_live_action": True,
        },
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "accepted_evidence_refs": [],
        "witness_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": (
            "candidate defines the selected-component router-inventory delta path but does not apply it"
        ),
    }


def _summary(candidate: dict[str, Any]) -> dict[str, int]:
    return {
        "candidate_count": 1,
        "draft_candidate_count": 1 if candidate["candidate_state"] == "draft_not_applied" else 0,
        "applied_delta_count": 1 if candidate["delta_applied"] is True else 0,
        "present_evidence_count": 1 if candidate["evidence_present"] is True else 0,
        "witness_emission_count": 1 if candidate["witness_emitted"] is True else 0,
        "router_inventory_mutation_count": 1 if candidate["router_inventory_mutated"] is True else 0,
        "router_inventory_delta_authorization_count": (
            1 if candidate["router_inventory_delta_authorized"] is True else 0
        ),
        "selected_component_binding_count": (
            1 if candidate["selected_component_binding_created"] is True else 0
        ),
        "route_binding_authorization_count": 1 if candidate["route_binding_authorized"] is True else 0,
        "authority_grant_count": 1 if candidate["authority_granted"] is True else 0,
        "promotion_approval_count": 1 if candidate["promotion_approved"] is True else 0,
        "terminal_closure_authorization_count": (
            1 if candidate["terminal_closure_authorized"] is True else 0
        ),
        "terminal_closure_claim_count": 1 if candidate["terminal_closure_claimed"] is True else 0,
        "accepted_evidence_count": len(candidate["accepted_evidence_refs"]),
        "required_downstream_artifact_count": len(candidate["required_downstream_artifacts"]),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateError(
            f"{label} must carry {field_name}"
        )
    return value
