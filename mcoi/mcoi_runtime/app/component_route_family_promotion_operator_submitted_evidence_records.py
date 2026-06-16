"""Build Component Harness promotion operator-submitted evidence records.

Purpose: apply submitted-evidence payload acceptance rules to local
foundation submitted-for-review records without approving route-family
promotion, mutating router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion submitted-evidence payload
examples projection.
Invariants:
  - Accepted records are record-only evidence and never promotion authority.
  - Applied acceptance rules cannot grant execution, connector, mutation, or
    terminal-closure authority.
  - Promotion remains blocked until a separate gate-satisfaction and authority
    decision exists.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_payload_examples import (
    ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError,
    build_component_route_family_promotion_submitted_evidence_payload_examples,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_promotion_submitted_evidence_records_receipt",
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


class ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(ValueError):
    """Raised when operator-submitted evidence records cannot be compiled."""


def build_component_route_family_promotion_operator_submitted_evidence_records(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    payload_examples_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic submitted-for-review evidence records.

    Input contract: target proof surface, target component, and optional
    submitted-evidence payload examples report. Output contract:
    JSON-serializable operator-submitted evidence record report. Error
    contract: raises
    ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError when
    payload examples are unavailable, malformed, target-mismatched, or no
    longer example-only and blocked.
    """

    payload_examples_report = payload_examples_report or _build_payload_examples(
        surface_id=surface_id,
        component_id=component_id,
    )
    if payload_examples_report.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            "operator-submitted records require blocked payload-example posture"
        )
    if payload_examples_report.get("payload_decision") != "example_only":
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            "operator-submitted records require example-only source payloads"
        )
    if payload_examples_report.get("acceptance_decision") != "defined_not_applied":
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            "operator-submitted records require defined-but-unapplied source rules"
        )
    if (
        payload_examples_report.get("target_surface_id") != surface_id
        or payload_examples_report.get("target_component_id") != component_id
    ):
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            "submitted-evidence payload examples target does not match requested records"
        )

    payload_examples = _payload_examples(payload_examples_report)
    records = [_operator_submitted_record(payload_example, surface_id) for payload_example in payload_examples]
    approval_evidence_required = list(_string_list(payload_examples_report.get("approval_evidence_required")))
    submitted_record_refs = [str(record["operator_submitted_record_id"]) for record in records]
    summary = _summary(records, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "operator_submitted_evidence_records_id": (
            f"component_route_family_promotion_operator_submitted_evidence_records.{surface_id}.v1"
        ),
        "mode": str(payload_examples_report.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "record_decision": "submitted_for_review",
        "acceptance_decision": "rules_applied_record_only",
        "submission_source": "local_foundation_fixture",
        "operator_submitted_evidence_records_are_not_execution_authority": True,
        "accepted_records_are_not_promotion_authority": True,
        "foundation_fixture_records_are_not_live_operator_evidence": True,
        "acceptance_rules_are_not_execution_authority": True,
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
            "submitted_evidence_payload_examples": (
                "examples/"
                "component_route_family_promotion_submitted_evidence_payload_examples.governed_connector_framework.json"
            ),
            "submitted_evidence_records": (
                "examples/"
                "component_route_family_promotion_submitted_evidence_records.governed_connector_framework.json"
            ),
            "submitted_evidence_verifier": (
                "examples/"
                "component_route_family_promotion_submitted_evidence_verifier.governed_connector_framework.json"
            ),
            "promotion_approval_intake": (
                "examples/component_route_family_promotion_approval_intake.governed_connector_framework.json"
            ),
            "promotion_preflight": "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "operator_submitted_evidence_records": records,
        "submitted_record_refs": submitted_record_refs,
        "accepted_record_refs": submitted_record_refs,
        "rejected_record_refs": [],
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": list(_string_list(payload_examples_report.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(payload_examples_report.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_operator_submitted_evidence_records_validator",
            "component_route_family_promotion_operator_submitted_evidence_records_tests",
            "component_route_family_promotion_submitted_evidence_payload_examples_validator",
        ],
        "next_action": (
            "Create a separate promotion gate-satisfaction evaluator that can consume accepted record-only evidence "
            "without granting lifecycle, route, connector, mutation, or terminal-closure authority."
        ),
    }


def _build_payload_examples(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_submitted_evidence_payload_examples(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError as exc:
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(str(exc)) from exc


def _payload_examples(report: dict[str, Any]) -> list[dict[str, Any]]:
    examples = report.get("payload_examples")
    if not isinstance(examples, list):
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError("payload examples must be a list")
    if len(examples) != 4:
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError("operator-submitted records require four payload examples")
    output: list[dict[str, Any]] = []
    for payload_example in examples:
        if not isinstance(payload_example, dict):
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError("payload example entries must be objects")
        if payload_example.get("payload_state") != "example_only":
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                "operator-submitted records require example-only payloads"
            )
        if payload_example.get("submission_state") != "not_submitted":
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                "operator-submitted records require source payloads that are not already submitted"
            )
        if payload_example.get("acceptance_state") != "not_evaluated":
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                "operator-submitted records require source rules that are not evaluated"
            )
        if payload_example.get("payload_values_present") is not True:
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                "operator-submitted records require source payload values"
            )
        if payload_example.get("satisfies_requirement") is not False or payload_example.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                "operator-submitted records require blocking source payloads"
            )
        output.append(payload_example)
    return output


def _operator_submitted_record(payload_example: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(payload_example, "gate_id", "submitted-evidence payload example")
    source_payload = payload_example.get("example_payload")
    if not isinstance(source_payload, dict) or not source_payload:
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            f"payload example {gate_id} must carry example_payload"
        )
    required_payload_fields = list(_string_list(payload_example.get("required_payload_fields")))
    acceptance_rules = [
        _applied_acceptance_rule(rule, payload_example)
        for rule in _source_acceptance_rules(payload_example, gate_id)
    ]
    return {
        "operator_submitted_record_id": f"promotion_operator_submitted_evidence_record.{surface_id}.{gate_id}.v1",
        "source_payload_example_id": _required_text(
            payload_example,
            "payload_example_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "source_record_envelope_id": _required_text(
            payload_example,
            "source_record_envelope_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "source_verifier_request_id": _required_text(
            payload_example,
            "source_verifier_request_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "source_intake_request_id": _required_text(
            payload_example,
            "source_intake_request_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "gate_id": gate_id,
        "record_kind": _required_text(payload_example, "record_kind", f"submitted-evidence payload example {gate_id}"),
        "evidence_key": _required_text(payload_example, "evidence_key", f"submitted-evidence payload example {gate_id}"),
        "record_state": "submitted_for_review",
        "submission_state": "submitted",
        "verification_state": "reviewed",
        "acceptance_state": "accepted_record_only",
        "proof_state": "Pass",
        "submission_source": "local_foundation_fixture",
        "payload_source_state": "foundation_fixture_from_payload_example",
        "blocks_promotion": True,
        "satisfies_requirement": False,
        "accepted_record_is_not_execution_authority": True,
        "accepted_record_is_not_promotion_authority": True,
        "foundation_fixture_record_is_not_live_operator_evidence": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "payload_values_present": True,
        "payload_values_are_foundation_fixture": True,
        "required_artifacts": list(_string_list(payload_example.get("required_artifacts"))),
        "required_payload_fields": required_payload_fields,
        "submitted_payload": dict(source_payload),
        "applied_acceptance_rules": acceptance_rules,
        "rejection_conditions": list(_string_list(payload_example.get("rejection_conditions"))),
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "promotion_approval_refs": [],
        "blocking_reason": f"{gate_id} accepted record requires separate promotion gate satisfaction",
    }


def _source_acceptance_rules(payload_example: dict[str, Any], gate_id: str) -> list[dict[str, Any]]:
    rules = payload_example.get("acceptance_rules")
    if not isinstance(rules, list) or not rules:
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
            f"payload example {gate_id} must carry acceptance rules"
        )
    output: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                f"payload example {gate_id} acceptance rules must be objects"
            )
        if rule.get("rule_state") != "defined_not_applied" or rule.get("proof_state") != "Unknown":
            raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(
                f"payload example {gate_id} acceptance rules must be defined but not applied"
            )
        output.append(rule)
    return output


def _applied_acceptance_rule(rule: dict[str, Any], payload_example: dict[str, Any]) -> dict[str, Any]:
    gate_id = _required_text(payload_example, "gate_id", "submitted-evidence payload example")
    return {
        "rule_id": _required_text(rule, "rule_id", f"submitted-evidence payload example {gate_id} acceptance rule"),
        "source_record_envelope_id": _required_text(
            payload_example,
            "source_record_envelope_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "source_payload_example_id": _required_text(
            payload_example,
            "payload_example_id",
            f"submitted-evidence payload example {gate_id}",
        ),
        "gate_id": gate_id,
        "rule_state": "applied",
        "proof_state": "Pass",
        "rule_result": "pass",
        "required_for_submission": True,
        "blocks_submission_until_pass": True,
        "rule_is_not_execution_authority": True,
        "record_acceptance_only": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "source_payload_fields": list(_string_list(rule.get("source_payload_fields"))),
        "failure_condition": _required_text(
            rule,
            "failure_condition",
            f"submitted-evidence payload example {gate_id} acceptance rule",
        ),
        "evaluation_detail": f"{rule.get('rule_id')} passed against local foundation fixture record payload",
    }


def _summary(records: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    acceptance_rule_count = sum(len(record["applied_acceptance_rules"]) for record in records)
    return {
        "submitted_record_count": len(records),
        "reviewed_record_count": sum(1 for record in records if record["verification_state"] == "reviewed"),
        "accepted_record_count": sum(1 for record in records if record["acceptance_state"] == "accepted_record_only"),
        "rejected_record_count": 0,
        "submitted_payload_count": len(records),
        "accepted_evidence_count": sum(len(record["accepted_evidence_refs"]) for record in records),
        "rejected_evidence_count": sum(len(record["rejected_evidence_refs"]) for record in records),
        "acceptance_rule_count": acceptance_rule_count,
        "applied_acceptance_rule_count": acceptance_rule_count,
        "passing_acceptance_rule_count": sum(
            1
            for record in records
            for rule in record["applied_acceptance_rules"]
            if rule["proof_state"] == "Pass" and rule["rule_result"] == "pass"
        ),
        "failing_acceptance_rule_count": 0,
        "satisfied_requirement_count": sum(1 for record in records if record["satisfies_requirement"] is True),
        "blocking_record_count": sum(1 for record in records if record["blocks_promotion"] is True),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "authority_grant_count": sum(
            1
            for record in records
            if record["grants_execution_authority"]
            or record["grants_connector_authority"]
            or record["grants_terminal_closure"]
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
