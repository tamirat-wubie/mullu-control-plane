"""Build Component Harness promotion terminal-closure denial reports.

Purpose: consume denied product-ownership decisions and record a denial-only
terminal-closure decision without minting a terminal certificate, granting
authority, mutating router inventory, or claiming promotion closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion product-ownership decision
report projection and component authority-fuse denial refs.
Invariants:
  - Terminal-closure denial is not terminal closure.
  - A denied product-ownership decision cannot mint a terminal certificate.
  - Denied terminal closure cannot execute, call connectors, mutate router
    inventory, grant authority, approve promotion, or claim closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
    ComponentRouteFamilyPromotionProductOwnershipDecisionReportError,
    build_component_route_family_promotion_product_ownership_decision_report,
)


SCHEMA_VERSION = 1
TERMINAL_CLOSURE_GATE_ID = "terminal_closure_gate"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_terminal_closure_denial_report_receipt",
    "component_route_family_promotion_product_ownership_decision_report_receipt",
    "component_route_family_promotion_authority_upgrade_witness_decision_report_receipt",
    "component_route_family_promotion_lifecycle_transition_decision_report_receipt",
    "component_route_family_promotion_route_binding_decision_report_receipt",
    "terminal_closure_denial_receipt",
    "terminal_closure_certificate",
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
MISSING_TERMINAL_CLOSURE_WITNESSES = (
    "terminal_closure_certificate",
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)
REQUIRED_FOLLOWUP_DECISIONS = (
    "selected_component_bound_router_inventory_delta",
    "component_route_binding_receipt",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_witness",
    "terminal_closure_certificate",
)


class ComponentRouteFamilyPromotionTerminalClosureDenialReportError(ValueError):
    """Raised when a terminal-closure denial report cannot be compiled."""


def build_component_route_family_promotion_terminal_closure_denial_report(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    product_ownership_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic denial-only terminal-closure report.

    Input contract: target proof surface, target component, target product
    bundle, and optional product-ownership decision report. Output contract:
    JSON-serializable terminal-closure denial report. Error contract: raises
    ComponentRouteFamilyPromotionTerminalClosureDenialReportError when the
    source report is unavailable, malformed, target-mismatched, or no longer
    denial-only.
    """

    product_report = product_ownership_decision_report or _build_product_ownership_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_product_ownership_report(product_report, surface_id, component_id, product_bundle_id)
    authority_fuse_refs = _authority_fuse_refs(product_report)
    source_decision = _source_product_ownership_decision(product_report)
    if _string_list(source_decision.get("authority_fuse_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision authority_fuse_refs must match report authority_fuse_refs"
        )
    terminal_decision = _terminal_closure_decision(
        source_decision,
        surface_id,
        product_bundle_id,
        authority_fuse_refs,
    )
    approval_evidence_required = list(_string_list(product_report.get("approval_evidence_required")))
    return {
        "schema_version": SCHEMA_VERSION,
        "terminal_closure_denial_report_id": (
            f"component_route_family_promotion_terminal_closure_denial_report.{surface_id}.v1"
        ),
        "mode": str(product_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "terminal_closure_decision_state": "denied_pending_terminal_closure_certificate",
        "promotion_decision": "blocked_terminal_closure_not_authorized",
        "product_ownership_decision_state": "denied_pending_product_specific_ownership_witness",
        "terminal_closure_denial_issued": True,
        "terminal_closure_authorized": False,
        "terminal_certificate_minted": False,
        "terminal_closure_witness_emitted": False,
        "terminal_closure_claimed": False,
        "promotion_approved": False,
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
        "terminal_closure_denial_is_not_terminal_certificate": True,
        "terminal_closure_denial_is_not_terminal_closure": True,
        "terminal_closure_denial_is_not_promotion_approval": True,
        "terminal_closure_denial_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_terminal_closure_certificate_required": True,
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
            "product_ownership_decision_report": (
                "examples/"
                "component_route_family_promotion_product_ownership_decision_report.governed_connector_framework.json"
            ),
            "authority_upgrade_witness_decision_report": (
                "examples/"
                "component_route_family_promotion_authority_upgrade_witness_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(terminal_decision, approval_evidence_required),
        "terminal_closure_decisions": [terminal_decision],
        "terminal_closure_decision_refs": [str(terminal_decision["terminal_closure_decision_id"])],
        "source_product_ownership_decision_refs": [
            str(terminal_decision["source_product_ownership_decision_id"])
        ],
        "source_authority_upgrade_decision_refs": [
            str(terminal_decision["source_authority_upgrade_decision_id"])
        ],
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "terminal_closure_certificate_refs": [],
        "terminal_closure_witness_refs": [],
        "terminal_closure_refs": [],
        "promotion_approval_refs": [],
        "product_ownership_witness_refs": [],
        "product_bundle_binding_refs": [],
        "authority_upgrade_witness_refs": [],
        "authority_envelope_mutation_refs": [],
        "authority_grant_refs": [],
        "lifecycle_transition_receipt_refs": [],
        "route_binding_receipt_refs": [],
        "router_inventory_delta_refs": [],
        "selected_component_binding_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "required_followup_decisions": list(REQUIRED_FOLLOWUP_DECISIONS),
        "missing_terminal_closure_witnesses": list(MISSING_TERMINAL_CLOSURE_WITNESSES),
        "operator_submission_channels": list(_string_list(product_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(product_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_terminal_closure_denial_report_validator",
            "component_route_family_promotion_terminal_closure_denial_report_tests",
            "component_route_family_promotion_product_ownership_decision_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Keep promotion blocked until route-binding, lifecycle, authority-upgrade, product ownership, "
            "router-inventory, and terminal-closure certificate evidence exists."
        ),
    }


def _build_product_ownership_report(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_product_ownership_decision_report(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionProductOwnershipDecisionReportError as exc:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(str(exc)) from exc


def _validate_product_ownership_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "product_ownership_decision_state": "denied_pending_product_specific_ownership_witness",
        "promotion_decision": "blocked_product_ownership_not_authorized",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
                f"terminal-closure denial requires {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "product-ownership decision report target does not match requested terminal-closure denial report"
        )
    for field_name in (
        "product_ownership_authorized",
        "product_bundle_binding_authorized",
        "product_ownership_witness_emitted",
        "product_route_ownership_bound",
        "authority_granted",
        "mutates_router_inventory",
        "ready_for_promotion",
        "can_claim_terminal_closure",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
                f"product-ownership report must keep {field_name} false before terminal-closure denial"
            )


def _source_product_ownership_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("product_ownership_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "product-ownership decisions must be a list"
        )
    if len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "terminal-closure denial report requires exactly one product-ownership decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision must remain denied"
        )
    if decision.get("product_ownership_authorized") is not False:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision must not authorize product ownership"
        )
    if decision.get("requires_terminal_closure") is not True:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision must still require terminal closure"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision must keep authority_fuse_blocks_promotion true"
        )
    authority_fuse_refs = _string_list(decision.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "source product-ownership decision authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return decision


def _terminal_closure_decision(
    source_decision: dict[str, Any],
    surface_id: str,
    product_bundle_id: str,
    authority_fuse_refs: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "terminal_closure_decision_id": (
            f"promotion_terminal_closure_denial.{surface_id}.{product_bundle_id}.v1"
        ),
        "source_product_ownership_decision_id": _required_text(
            source_decision,
            "product_ownership_decision_id",
            "source product-ownership decision",
        ),
        "source_authority_upgrade_decision_id": _required_text(
            source_decision,
            "source_authority_upgrade_decision_id",
            "source product-ownership decision",
        ),
        "gate_id": TERMINAL_CLOSURE_GATE_ID,
        "product_bundle_id": product_bundle_id,
        "record_kind": "terminal_closure",
        "decision_state": "denied",
        "decision_basis": "product_ownership_decision_denial",
        "proof_state": "Pass",
        "source_product_ownership_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "requires_external_authority_upgrade_evidence": True,
        "terminal_closure_authorized": False,
        "terminal_certificate_minted": False,
        "terminal_closure_witness_emitted": False,
        "terminal_closure_claimed": False,
        "promotion_approved": False,
        "product_ownership_authorized": False,
        "authority_upgrade_authorized": False,
        "authority_granted": False,
        "lifecycle_transition_authorized": False,
        "route_binding_authorized": False,
        "router_inventory_delta_authorized": False,
        "selected_component_binding_authorized": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "requires_terminal_closure_certificate": True,
        "requires_product_ownership_witness": True,
        "requires_authority_upgrade_witness": True,
        "requires_lifecycle_transition_receipt": True,
        "requires_component_route_binding_receipt": True,
        "requires_router_inventory_delta": True,
        "decision_is_not_terminal_certificate": True,
        "decision_is_not_terminal_closure": True,
        "decision_is_not_promotion_approval": True,
        "decision_is_not_authority_grant": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "source_product_ownership_decision_refs": [
            _required_text(source_decision, "product_ownership_decision_id", "source product-ownership decision")
        ],
        "source_authority_upgrade_decision_refs": [
            _required_text(
                source_decision,
                "source_authority_upgrade_decision_id",
                "source product-ownership decision",
            )
        ],
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "terminal_closure_certificate_refs": [],
        "terminal_closure_witness_refs": [],
        "terminal_closure_refs": [],
        "promotion_approval_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_terminal_closure_witnesses": list(MISSING_TERMINAL_CLOSURE_WITNESSES),
        "decision_reason": (
            "terminal closure remains denied because the component authority fuse remains blocked and product "
            "ownership, authority-upgrade, lifecycle, route-binding, router-inventory, and terminal-certificate "
            "witnesses are absent"
        ),
    }


def _summary(terminal_decision: dict[str, Any], approval_evidence_required: list[str]) -> dict[str, int]:
    return {
        "terminal_closure_decision_count": 1,
        "terminal_closure_denial_count": 1 if terminal_decision["decision_state"] == "denied" else 0,
        "terminal_closure_authorization_count": (
            1 if terminal_decision["terminal_closure_authorized"] is True else 0
        ),
        "terminal_certificate_mint_count": (
            1 if terminal_decision["terminal_certificate_minted"] is True else 0
        ),
        "terminal_closure_witness_count": len(terminal_decision["terminal_closure_witness_refs"]),
        "terminal_closure_claim_count": 1 if terminal_decision["terminal_closure_claimed"] is True else 0,
        "promotion_approval_count": 1 if terminal_decision["promotion_approved"] is True else 0,
        "product_ownership_authorization_count": (
            1 if terminal_decision["product_ownership_authorized"] is True else 0
        ),
        "authority_upgrade_authorization_count": (
            1 if terminal_decision["authority_upgrade_authorized"] is True else 0
        ),
        "authority_grant_count": 1 if terminal_decision["authority_granted"] is True else 0,
        "lifecycle_transition_authorization_count": (
            1 if terminal_decision["lifecycle_transition_authorized"] is True else 0
        ),
        "route_binding_authorization_count": 1 if terminal_decision["route_binding_authorized"] is True else 0,
        "router_inventory_mutation_count": 1 if terminal_decision["mutates_router_inventory"] is True else 0,
        "selected_component_binding_count": (
            1 if terminal_decision["selected_component_binding_authorized"] is True else 0
        ),
        "accepted_evidence_count": len(terminal_decision["accepted_evidence_refs"]),
        "rejected_evidence_count": len(terminal_decision["rejected_evidence_refs"]),
        "authority_fuse_blocking_count": len(terminal_decision["authority_fuse_blocking_refs"]),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "required_followup_decision_count": len(REQUIRED_FOLLOWUP_DECISIONS),
    }


def _authority_fuse_refs(report: dict[str, Any]) -> tuple[str, ...]:
    refs = _string_list(report.get("authority_fuse_refs"))
    if len(refs) != 1:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "product-ownership report must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(report.get("authority_fuse_blocking_refs")) != refs:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            "product-ownership report authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return refs


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionTerminalClosureDenialReportError(
            f"{label} must carry {field_name}"
        )
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
