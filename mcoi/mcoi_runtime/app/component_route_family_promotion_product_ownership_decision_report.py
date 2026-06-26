"""Build Component Harness promotion product-ownership decisions.

Purpose: consume denied authority-upgrade decisions and record a denial-only
product-specific ownership decision for a route family without granting product
ownership, route binding, authority, execution, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion authority-upgrade witness
decision report projection and component authority-fuse denial refs.
Invariants:
  - Product-ownership decisions can deny without binding a route family to a
    product bundle.
  - A generic connector framework surface is not product-specific authority.
  - Denied product ownership cannot execute, call connectors, mutate router
    inventory, grant authority, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_authority_upgrade_witness_decision_report import (
    ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError,
    build_component_route_family_promotion_authority_upgrade_witness_decision_report,
)
from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)


SCHEMA_VERSION = 1
DEFAULT_PRODUCT_BUNDLE_ID = "personal_assistant_v0"
PRODUCT_OWNERSHIP_GATE_ID = "product_specific_ownership_gate"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_product_ownership_decision_report_receipt",
    "component_route_family_promotion_authority_upgrade_witness_decision_report_receipt",
    "component_route_family_promotion_lifecycle_transition_decision_report_receipt",
    "component_route_family_promotion_route_binding_decision_report_receipt",
    "component_route_family_promotion_authority_decision_report_receipt",
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "operator_approval_required_receipt",
    "terminal_closure_denial_receipt",
)
MISSING_PRODUCT_OWNERSHIP_WITNESSES = (
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
REQUIRED_FOLLOWUP_DECISIONS = (
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_decision",
)


class ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(ValueError):
    """Raised when a product-ownership decision report cannot be compiled."""


def build_component_route_family_promotion_product_ownership_decision_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    authority_upgrade_witness_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only product-ownership decision report.

    Input contract: target proof surface, target component, target product
    bundle, and optional authority-upgrade witness decision report. Output
    contract: JSON-serializable product-ownership decision report. Error
    contract: raises ComponentRouteFamilyPromotionProductOwnershipDecisionReportError
    when the source report is unavailable, malformed, target-mismatched, or no
    longer denial-only.
    """

    authority_upgrade_report = (
        authority_upgrade_witness_decision_report
        or _build_authority_upgrade_witness_decision_report(surface_id=surface_id, component_id=component_id)
    )
    _validate_authority_upgrade_report(authority_upgrade_report, surface_id, component_id)
    authority_fuse_refs = _authority_fuse_refs(authority_upgrade_report)
    source_decision = _source_authority_upgrade_decision(authority_upgrade_report)
    if _string_list(source_decision.get("authority_fuse_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision authority_fuse_refs must match report authority_fuse_refs"
        )
    product_ownership_decision = _product_ownership_decision(
        source_decision,
        surface_id,
        product_bundle_id,
        authority_fuse_refs,
    )
    approval_evidence_required = list(_string_list(authority_upgrade_report.get("approval_evidence_required")))
    return {
        "schema_version": SCHEMA_VERSION,
        "product_ownership_decision_report_id": (
            f"component_route_family_promotion_product_ownership_decision_report.{surface_id}.v1"
        ),
        "mode": str(authority_upgrade_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "product_ownership_decision_state": "denied_pending_product_specific_ownership_witness",
        "promotion_decision": "blocked_product_ownership_not_authorized",
        "authority_upgrade_decision_state": "denied_pending_authority_upgrade_witness",
        "product_ownership_decision_issued": True,
        "product_ownership_authorized": False,
        "product_bundle_binding_authorized": False,
        "product_ownership_witness_emitted": False,
        "product_route_ownership_bound": False,
        "route_family_ownership_authorized": False,
        "authority_upgrade_authorized": False,
        "authority_level_changed": False,
        "authority_witness_emitted": False,
        "authority_envelope_mutated": False,
        "authority_granted": False,
        "lifecycle_transition_authorized": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "product_ownership_decision_is_not_product_ownership_witness": True,
        "product_ownership_decision_is_not_product_bundle_binding": True,
        "product_ownership_decision_is_not_authority_grant": True,
        "product_ownership_decision_is_not_promotion_approval": True,
        "generic_connector_surface_is_not_product_specific_authority": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_product_ownership_witness_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_lifecycle_transition_receipt_required": True,
        "separate_route_binding_receipt_required": True,
        "separate_router_inventory_delta_required": True,
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
            "authority_upgrade_witness_decision_report": (
                "examples/"
                "component_route_family_promotion_authority_upgrade_witness_decision_report.governed_connector_framework.json"
            ),
            "lifecycle_transition_decision_report": (
                "examples/"
                "component_route_family_promotion_lifecycle_transition_decision_report.governed_connector_framework.json"
            ),
            "route_binding_decision_report": (
                "examples/"
                "component_route_family_promotion_route_binding_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(product_ownership_decision, approval_evidence_required),
        "product_ownership_decisions": [product_ownership_decision],
        "product_ownership_decision_refs": [str(product_ownership_decision["product_ownership_decision_id"])],
        "source_authority_upgrade_decision_refs": [
            str(product_ownership_decision["source_authority_upgrade_decision_id"])
        ],
        "source_lifecycle_transition_decision_refs": [
            str(product_ownership_decision["source_lifecycle_transition_decision_id"])
        ],
        "source_route_binding_decision_refs": [
            str(product_ownership_decision["source_route_binding_decision_id"])
        ],
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "product_ownership_witness_refs": [],
        "product_bundle_binding_refs": [],
        "authority_upgrade_witness_refs": [],
        "authority_envelope_mutation_refs": [],
        "authority_grant_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_product_ownership_witnesses": list(MISSING_PRODUCT_OWNERSHIP_WITNESSES),
        "operator_submission_channels": list(_string_list(authority_upgrade_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(authority_upgrade_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_product_ownership_decision_report_validator",
            "component_route_family_promotion_product_ownership_decision_report_tests",
            "component_route_family_promotion_authority_upgrade_witness_decision_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Create terminal-closure denial while product ownership, authority upgrade, lifecycle transition, "
            "route binding, and router-inventory mutation remain blocked."
        ),
    }


def _build_authority_upgrade_witness_decision_report(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_authority_upgrade_witness_decision_report(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionAuthorityUpgradeWitnessDecisionReportError as exc:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(str(exc)) from exc


def _validate_authority_upgrade_report(report: dict[str, Any], surface_id: str, component_id: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "authority_upgrade_decision_state": "denied_pending_authority_upgrade_witness",
        "promotion_decision": "blocked_authority_upgrade_not_authorized",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
                f"product-ownership decision requires {field_name}={expected_value}"
            )
    if report.get("target_surface_id") != surface_id or report.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "authority-upgrade decision report target does not match requested product-ownership decision report"
        )
    for field_name in (
        "authority_upgrade_authorized",
        "authority_level_changed",
        "authority_witness_emitted",
        "authority_envelope_mutated",
        "authority_granted",
        "lifecycle_transition_authorized",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "route_family_ownership_authorized",
        "mutates_router_inventory",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
                f"authority-upgrade report must keep {field_name} false before product-ownership decision"
            )


def _source_authority_upgrade_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("authority_upgrade_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "authority-upgrade decisions must be a list"
        )
    if len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "product-ownership decision report requires exactly one authority-upgrade decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision must remain denied"
        )
    if decision.get("authority_upgrade_authorized") is not False:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision must not authorize authority upgrade"
        )
    if decision.get("requires_product_ownership_decision") is not True:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision must still require product ownership decision"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision must keep authority_fuse_blocks_promotion true"
        )
    authority_fuse_refs = _string_list(decision.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "source authority-upgrade decision authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return decision


def _product_ownership_decision(
    source_decision: dict[str, Any],
    surface_id: str,
    product_bundle_id: str,
    authority_fuse_refs: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "product_ownership_decision_id": (
            f"promotion_product_ownership_decision.{surface_id}.{product_bundle_id}.v1"
        ),
        "source_authority_upgrade_decision_id": _required_text(
            source_decision,
            "authority_upgrade_decision_id",
            "source authority-upgrade decision",
        ),
        "source_lifecycle_transition_decision_id": _required_text(
            source_decision,
            "source_lifecycle_transition_decision_id",
            "source authority-upgrade decision",
        ),
        "source_route_binding_decision_id": _required_text(
            source_decision,
            "source_route_binding_decision_id",
            "source authority-upgrade decision",
        ),
        "gate_id": PRODUCT_OWNERSHIP_GATE_ID,
        "product_bundle_id": product_bundle_id,
        "record_kind": "product_specific_ownership",
        "decision_state": "denied",
        "decision_basis": "authority_upgrade_decision_denial",
        "proof_state": "Pass",
        "source_authority_upgrade_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "product_ownership_authorized": False,
        "product_bundle_binding_authorized": False,
        "product_ownership_witness_emitted": False,
        "product_route_ownership_bound": False,
        "route_family_ownership_authorized": False,
        "authority_upgrade_authorized": False,
        "authority_level_changed": False,
        "authority_witness_emitted": False,
        "authority_envelope_mutated": False,
        "authority_granted": False,
        "lifecycle_transition_authorized": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "promotion_approved": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "requires_product_ownership_witness": True,
        "requires_authority_upgrade_witness": True,
        "requires_lifecycle_transition_receipt": True,
        "requires_component_route_binding_receipt": True,
        "requires_router_inventory_delta": True,
        "requires_terminal_closure": True,
        "decision_is_not_product_ownership_witness": True,
        "decision_is_not_product_bundle_binding": True,
        "decision_is_not_authority_grant": True,
        "decision_is_not_promotion_approval": True,
        "generic_connector_surface_is_not_product_specific_authority": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "source_authority_upgrade_decision_refs": [
            _required_text(source_decision, "authority_upgrade_decision_id", "source authority-upgrade decision")
        ],
        "source_lifecycle_transition_decision_refs": [
            _required_text(
                source_decision,
                "source_lifecycle_transition_decision_id",
                "source authority-upgrade decision",
            )
        ],
        "source_route_binding_decision_refs": [
            _required_text(source_decision, "source_route_binding_decision_id", "source authority-upgrade decision")
        ],
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "product_ownership_witness_refs": [],
        "product_bundle_binding_refs": [],
        "authority_upgrade_witness_refs": [],
        "authority_envelope_mutation_refs": [],
        "authority_grant_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_product_ownership_witnesses": list(MISSING_PRODUCT_OWNERSHIP_WITNESSES),
        "decision_reason": (
            "product-specific ownership remains denied because the target surface is a generic connector "
            "framework, the component authority fuse remains blocked, and authority-upgrade, lifecycle, "
            "route-binding, router-inventory, and product ownership witnesses are absent"
        ),
    }


def _summary(product_ownership_decision: dict[str, Any], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "product_ownership_decision_count": 1,
        "product_ownership_denial_count": (
            1 if product_ownership_decision["decision_state"] == "denied" else 0
        ),
        "product_ownership_authorization_count": (
            1 if product_ownership_decision["product_ownership_authorized"] is True else 0
        ),
        "product_bundle_binding_count": (
            1 if product_ownership_decision["product_bundle_binding_authorized"] is True else 0
        ),
        "product_ownership_witness_count": len(product_ownership_decision["product_ownership_witness_refs"]),
        "product_route_ownership_bound_count": (
            1 if product_ownership_decision["product_route_ownership_bound"] is True else 0
        ),
        "route_family_ownership_authorization_count": (
            1 if product_ownership_decision["route_family_ownership_authorized"] is True else 0
        ),
        "authority_upgrade_authorization_count": (
            1 if product_ownership_decision["authority_upgrade_authorized"] is True else 0
        ),
        "authority_level_change_count": (
            1 if product_ownership_decision["authority_level_changed"] is True else 0
        ),
        "authority_witness_emission_count": (
            1 if product_ownership_decision["authority_witness_emitted"] is True else 0
        ),
        "authority_envelope_mutation_count": (
            1 if product_ownership_decision["authority_envelope_mutated"] is True else 0
        ),
        "authority_grant_count": 1 if product_ownership_decision["authority_granted"] is True else 0,
        "lifecycle_transition_authorization_count": (
            1 if product_ownership_decision["lifecycle_transition_authorized"] is True else 0
        ),
        "route_binding_authorization_count": (
            1 if product_ownership_decision["route_binding_authorized"] is True else 0
        ),
        "router_inventory_mutation_count": (
            1 if product_ownership_decision["mutates_router_inventory"] is True else 0
        ),
        "selected_component_binding_count": (
            1 if product_ownership_decision["selected_component_binding_authorized"] is True else 0
        ),
        "promotion_approval_count": 1 if product_ownership_decision["promotion_approved"] is True else 0,
        "terminal_closure_count": 1 if product_ownership_decision["can_claim_terminal_closure"] is True else 0,
        "accepted_evidence_count": len(product_ownership_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(product_ownership_decision["rejected_evidence_refs"]),
        "authority_fuse_blocking_count": len(product_ownership_decision["authority_fuse_blocking_refs"]),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _authority_fuse_refs(report: dict[str, Any]) -> tuple[str, ...]:
    refs = _string_list(report.get("authority_fuse_refs"))
    if len(refs) != 1:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "authority-upgrade report must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(report.get("authority_fuse_blocking_refs")) != refs:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            "authority-upgrade report authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return refs


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionProductOwnershipDecisionReportError(
            f"{label} must carry {field_name}"
        )
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
