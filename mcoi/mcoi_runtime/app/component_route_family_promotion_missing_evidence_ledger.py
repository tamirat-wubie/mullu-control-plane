"""Build Component Harness promotion missing-evidence ledgers.

Purpose: consume terminal-closure denial reports and record the unresolved
promotion evidence gap set without creating witnesses, terminal certificates,
authority grants, router mutations, promotion approvals, or closure claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion terminal-closure denial report
and component authority-fuse denial refs.
Invariants:
  - A missing-evidence ledger is not missing evidence.
  - Unknown proof state on required evidence keeps promotion blocked.
  - Missing-evidence records cannot execute, mutate, call connectors, grant
    authority, emit witnesses, approve promotion, or claim terminal closure.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_terminal_closure_denial_report import (
    ComponentRouteFamilyPromotionTerminalClosureDenialReportError,
    build_component_route_family_promotion_terminal_closure_denial_report,
)


SCHEMA_VERSION = 1
MISSING_EVIDENCE_STAGES = {
    "selected_component_bound_router_inventory_delta": "router_inventory_delta",
    "component_route_binding_receipt": "route_binding",
    "component_lifecycle_transition_receipt": "lifecycle_transition",
    "authority_upgrade_witness": "authority_upgrade",
    "product_specific_ownership_witness": "product_ownership",
    "terminal_closure_certificate": "terminal_closure",
}
MISSING_EVIDENCE_ORDER = tuple(MISSING_EVIDENCE_STAGES.keys())
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_missing_evidence_ledger_receipt",
    "component_route_family_promotion_terminal_closure_denial_report_receipt",
    "terminal_closure_certificate",
    "product_specific_ownership_witness",
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "selected_component_bound_router_inventory_delta",
)


class ComponentRouteFamilyPromotionMissingEvidenceLedgerError(ValueError):
    """Raised when a missing-evidence ledger cannot be compiled."""


def build_component_route_family_promotion_missing_evidence_ledger(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    product_bundle_id: str = DEFAULT_PRODUCT_BUNDLE_ID,
    terminal_closure_denial_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic ledger of required evidence that is still absent.

    Input contract: target proof surface, target component, target product
    bundle, and optional terminal-closure denial report. Output contract:
    JSON-serializable missing-evidence ledger. Error contract: raises
    ComponentRouteFamilyPromotionMissingEvidenceLedgerError when the source
    report is unavailable, malformed, target-mismatched, or no longer
    denial-only.
    """

    terminal_report = terminal_closure_denial_report or _build_terminal_denial_report(
        surface_id=surface_id,
        component_id=component_id,
        product_bundle_id=product_bundle_id,
    )
    _validate_terminal_denial_report(terminal_report, surface_id, component_id, product_bundle_id)
    authority_fuse_refs = _authority_fuse_refs(terminal_report)
    terminal_decision = _source_terminal_closure_decision(terminal_report)
    if _string_list(terminal_decision.get("authority_fuse_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision authority_fuse_refs must match report authority_fuse_refs"
        )
    missing_records = [
        _missing_evidence_record(artifact_id, terminal_decision, surface_id, product_bundle_id, authority_fuse_refs)
        for artifact_id in MISSING_EVIDENCE_ORDER
    ]
    missing_record_refs = [str(record["missing_evidence_id"]) for record in missing_records]
    blocked_actions = list(_string_list(terminal_report.get("blocked_actions")))
    return {
        "schema_version": SCHEMA_VERSION,
        "missing_evidence_ledger_id": (
            f"component_route_family_promotion_missing_evidence_ledger.{surface_id}.v1"
        ),
        "mode": str(terminal_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "target_product_bundle_id": product_bundle_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "evidence_status": "missing_required_witnesses",
        "promotion_decision": "blocked_missing_required_evidence",
        "terminal_closure_decision_state": "denied_pending_terminal_closure_certificate",
        "terminal_closure_denial_issued": True,
        "evidence_ledger_issued": True,
        "missing_evidence_ledger_is_not_evidence": True,
        "missing_evidence_ledger_is_not_witness": True,
        "missing_evidence_ledger_is_not_terminal_certificate": True,
        "missing_evidence_ledger_is_not_terminal_closure": True,
        "missing_evidence_ledger_is_not_promotion_approval": True,
        "missing_evidence_ledger_is_not_authority_grant": True,
        "unknown_required_evidence_blocks_promotion": True,
        "foundation_fixture_decision_is_not_live_operator_evidence": True,
        "separate_terminal_closure_certificate_required": True,
        "separate_product_ownership_witness_required": True,
        "separate_authority_upgrade_witness_required": True,
        "separate_lifecycle_transition_receipt_required": True,
        "separate_route_binding_receipt_required": True,
        "separate_router_inventory_delta_required": True,
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
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "ready_for_promotion": False,
        "source_refs": {
            "terminal_closure_denial_report": (
                "examples/"
                "component_route_family_promotion_terminal_closure_denial_report.governed_connector_framework.json"
            ),
            "product_ownership_decision_report": (
                "examples/"
                "component_route_family_promotion_product_ownership_decision_report.governed_connector_framework.json"
            ),
            "component_authority_fuse": "examples/component_authority_fuse.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": _summary(missing_records),
        "missing_evidence_records": missing_records,
        "missing_evidence_record_refs": missing_record_refs,
        "missing_required_artifacts": list(MISSING_EVIDENCE_ORDER),
        "source_terminal_closure_decision_refs": [
            str(terminal_decision["terminal_closure_decision_id"])
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
        "operator_submission_channels": list(_string_list(terminal_report.get("operator_submission_channels"))),
        "blocked_actions": blocked_actions,
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_missing_evidence_ledger_validator",
            "component_route_family_promotion_missing_evidence_ledger_tests",
            "component_route_family_promotion_terminal_closure_denial_report_validator",
            "component_authority_fuse_validator",
        ],
        "next_action": (
            "Collect the six named evidence artifacts in order; do not promote until each missing "
            "record is replaced by a separate witness or receipt."
        ),
    }


def _build_terminal_denial_report(
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_terminal_closure_denial_report(
            surface_id=surface_id,
            component_id=component_id,
            product_bundle_id=product_bundle_id,
        )
    except ComponentRouteFamilyPromotionTerminalClosureDenialReportError as exc:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(str(exc)) from exc


def _validate_terminal_denial_report(
    report: dict[str, Any],
    surface_id: str,
    component_id: str,
    product_bundle_id: str,
) -> None:
    expected_strings = {
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "terminal_closure_decision_state": "denied_pending_terminal_closure_certificate",
        "promotion_decision": "blocked_terminal_closure_not_authorized",
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
                f"missing-evidence ledger requires terminal denial {field_name}={expected_value}"
            )
    if (
        report.get("target_surface_id") != surface_id
        or report.get("target_component_id") != component_id
        or report.get("target_product_bundle_id") != product_bundle_id
    ):
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "terminal-closure denial report target does not match requested missing-evidence ledger"
        )
    for field_name in (
        "terminal_closure_authorized",
        "terminal_certificate_minted",
        "terminal_closure_witness_emitted",
        "terminal_closure_claimed",
        "promotion_approved",
        "authority_granted",
        "mutates_router_inventory",
        "ready_for_promotion",
        "can_claim_terminal_closure",
    ):
        if report.get(field_name) is not False:
            raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
                f"terminal-closure denial report must keep {field_name} false before evidence ledger"
            )
    if set(_string_list(report.get("missing_terminal_closure_witnesses"))) != set(MISSING_EVIDENCE_ORDER):
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "terminal-closure denial report missing witness set does not match evidence ledger requirements"
        )


def _source_terminal_closure_decision(report: dict[str, Any]) -> dict[str, Any]:
    decisions = report.get("terminal_closure_decisions")
    if not isinstance(decisions, list):
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "terminal-closure decisions must be a list"
        )
    if len(decisions) != 1 or not isinstance(decisions[0], dict):
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "missing-evidence ledger requires exactly one terminal-closure denial decision"
        )
    decision = decisions[0]
    if decision.get("decision_state") != "denied":
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision must remain denied"
        )
    if decision.get("terminal_closure_authorized") is not False:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision must not authorize closure"
        )
    if decision.get("authority_fuse_blocks_promotion") is not True:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision must keep authority_fuse_blocks_promotion true"
        )
    authority_fuse_refs = _string_list(decision.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(decision.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "source terminal-closure decision authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return decision


def _missing_evidence_record(
    artifact_id: str,
    terminal_decision: dict[str, Any],
    surface_id: str,
    product_bundle_id: str,
    authority_fuse_refs: tuple[str, ...],
) -> dict[str, Any]:
    required_stage = MISSING_EVIDENCE_STAGES[artifact_id]
    terminal_decision_id = _required_text(
        terminal_decision,
        "terminal_closure_decision_id",
        "source terminal-closure decision",
    )
    return {
        "missing_evidence_id": f"missing_evidence.{surface_id}.{artifact_id}.v1",
        "artifact_id": artifact_id,
        "required_stage": required_stage,
        "product_bundle_id": product_bundle_id,
        "source_terminal_closure_decision_id": terminal_decision_id,
        "source_terminal_closure_decision_refs": [terminal_decision_id],
        "source_terminal_closure_decision_denied": True,
        "authority_fuse_blocks_promotion": True,
        "authority_fuse_refs": list(authority_fuse_refs),
        "authority_fuse_blocking_refs": list(authority_fuse_refs),
        "evidence_state": "missing",
        "proof_state": "Unknown",
        "hard_constraint_unknown_blocks_action": True,
        "required": True,
        "evidence_present": False,
        "witness_emitted": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_certificate_minted": False,
        "terminal_closure_authorized": False,
        "terminal_closure_claimed": False,
        "blocks_promotion": True,
        "blocks_terminal_closure": True,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "mutates_router_inventory": False,
        "record_is_not_evidence": True,
        "record_is_not_witness": True,
        "record_is_not_authority_grant": True,
        "record_is_not_terminal_certificate": True,
        "record_is_not_terminal_closure": True,
        "record_is_not_promotion_approval": True,
        "accepted_evidence_refs": [],
        "witness_refs": [],
        "authority_grant_refs": [],
        "promotion_approval_refs": [],
        "terminal_closure_refs": [],
        "decision_reason": (
            f"{artifact_id} is required for promotion but is absent; Unknown proof state blocks action"
        ),
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    stage_counts = {
        f"{stage}_missing_count": sum(1 for record in records if record["required_stage"] == stage)
        for stage in MISSING_EVIDENCE_STAGES.values()
    }
    return {
        "missing_evidence_record_count": len(records),
        "required_evidence_count": sum(1 for record in records if record["required"] is True),
        "present_evidence_count": sum(1 for record in records if record["evidence_present"] is True),
        "unknown_proof_state_count": sum(1 for record in records if record["proof_state"] == "Unknown"),
        "blocking_record_count": sum(1 for record in records if record["blocks_promotion"] is True),
        "witness_emission_count": sum(1 for record in records if record["witness_emitted"] is True),
        "authority_grant_count": sum(1 for record in records if record["authority_granted"] is True),
        "promotion_approval_count": sum(1 for record in records if record["promotion_approved"] is True),
        "terminal_certificate_mint_count": sum(
            1 for record in records if record["terminal_certificate_minted"] is True
        ),
        "terminal_closure_authorization_count": sum(
            1 for record in records if record["terminal_closure_authorized"] is True
        ),
        "terminal_closure_claim_count": sum(
            1 for record in records if record["terminal_closure_claimed"] is True
        ),
        "router_inventory_mutation_count": sum(
            1 for record in records if record["mutates_router_inventory"] is True
        ),
        "authority_fuse_blocking_count": sum(
            len(record["authority_fuse_blocking_refs"]) for record in records
        ),
        **stage_counts,
    }


def _authority_fuse_refs(report: dict[str, Any]) -> tuple[str, ...]:
    refs = _string_list(report.get("authority_fuse_refs"))
    if len(refs) != 1:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "terminal-closure denial report must carry exactly one authority_fuse_refs entry"
        )
    if _string_list(report.get("authority_fuse_blocking_refs")) != refs:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            "terminal-closure denial report authority_fuse_blocking_refs must match authority_fuse_refs"
        )
    return refs


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionMissingEvidenceLedgerError(
            f"{label} must carry {field_name}"
        )
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
