"""Build Component Harness promotion submitted-evidence payload examples.

Purpose: define concrete example payload values and acceptance-rule contracts
for blocked route-family promotion submitted-evidence record envelopes without
submitting evidence, approving promotion, changing router inventory, or
granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component route-family promotion submitted-evidence record
envelope projection.
Invariants:
  - Payload examples are example-only and never become submitted evidence.
  - Acceptance rules are defined but not applied in foundation mode.
  - Payload examples and acceptance rules cannot grant execution, connector,
    mutation, or terminal-closure authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    DEFAULT_TARGET_COMPONENT_ID,
    DEFAULT_TARGET_SURFACE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_records import (
    ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError,
    build_component_route_family_promotion_submitted_evidence_records,
)


SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
    "component_route_family_promotion_operator_submitted_evidence_records_receipt",
    "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
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
COMMON_PAYLOAD_FIELDS = (
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
)


class ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(ValueError):
    """Raised when submitted-evidence payload examples cannot be compiled."""


def build_component_route_family_promotion_submitted_evidence_payload_examples(
    *,
    surface_id: str = DEFAULT_TARGET_SURFACE_ID,
    component_id: str = DEFAULT_TARGET_COMPONENT_ID,
    submitted_evidence_records_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic example payloads and acceptance-rule contracts.

    Input contract: target proof surface, target component, and optional
    submitted-evidence records report. Output contract: JSON-serializable
    payload examples report. Error contract: raises
    ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError when
    record envelopes are unavailable, malformed, target-mismatched, or no
    longer template-only and blocked.
    """

    records = submitted_evidence_records_report or _build_records(
        surface_id=surface_id,
        component_id=component_id,
    )
    if records.get("decision") != "blocked":
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
            "submitted-evidence payload examples require blocked records posture"
        )
    if records.get("record_decision") != "template_only":
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
            "submitted-evidence payload examples require template-only record envelopes"
        )
    if records.get("target_surface_id") != surface_id or records.get("target_component_id") != component_id:
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
            "submitted-evidence records target does not match requested payload examples"
        )

    record_envelopes = _record_envelopes(records)
    payload_examples = [_payload_example(envelope, surface_id) for envelope in record_envelopes]
    approval_evidence_required = list(_string_list(records.get("approval_evidence_required")))
    summary = _summary(payload_examples, approval_evidence_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "payload_examples_id": (
            f"component_route_family_promotion_submitted_evidence_payload_examples.{surface_id}.v1"
        ),
        "mode": str(records.get("mode", "foundation")),
        "governed": True,
        "target_surface_id": surface_id,
        "target_component_id": component_id,
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "payload_decision": "example_only",
        "acceptance_decision": "defined_not_applied",
        "payload_examples_are_not_submitted_evidence": True,
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
        "payload_examples": payload_examples,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "approval_evidence_required": approval_evidence_required,
        "operator_submission_channels": list(_string_list(records.get("operator_submission_channels"))),
        "blocked_actions": list(_string_list(records.get("blocked_actions"))),
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_route_family_promotion_submitted_evidence_payload_examples_validator",
            "component_route_family_promotion_submitted_evidence_payload_examples_tests",
            "component_route_family_promotion_submitted_evidence_records_validator",
        ],
        "next_action": (
            "Create actual operator-submitted evidence records only after acceptance rules are applied to real "
            "artifact refs and remain blocked from granting authority by themselves."
        ),
    }


def _build_records(surface_id: str, component_id: str) -> dict[str, Any]:
    try:
        return build_component_route_family_promotion_submitted_evidence_records(
            surface_id=surface_id,
            component_id=component_id,
        )
    except ComponentRouteFamilyPromotionSubmittedEvidenceRecordsError as exc:
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(str(exc)) from exc


def _record_envelopes(records: dict[str, Any]) -> list[dict[str, Any]]:
    envelopes = records.get("record_envelopes")
    if not isinstance(envelopes, list):
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError("record envelopes must be a list")
    if len(envelopes) != 4:
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError("payload examples require four envelopes")
    output: list[dict[str, Any]] = []
    for envelope in envelopes:
        if not isinstance(envelope, dict):
            raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError("record envelopes entries must be objects")
        if envelope.get("envelope_state") != "template_only":
            raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
                "payload examples require template-only envelopes"
            )
        if envelope.get("submission_state") != "not_submitted":
            raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
                "payload examples require not-submitted envelopes"
            )
        if envelope.get("payload_values_present") is not False:
            raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
                "payload examples require source envelopes without payload values"
            )
        if envelope.get("satisfies_requirement") is not False or envelope.get("blocks_promotion") is not True:
            raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(
                "payload examples require blocking envelopes"
            )
        output.append(envelope)
    return output


def _payload_example(envelope: dict[str, Any], surface_id: str) -> dict[str, Any]:
    gate_id = _required_text(envelope, "gate_id", "submitted-evidence record envelope")
    required_payload_fields = list(_string_list(envelope.get("payload_field_names")))
    example_payload = _example_payload(envelope, surface_id, required_payload_fields)
    acceptance_rules = [
        _acceptance_rule(rule_id, envelope)
        for rule_id in _string_list(envelope.get("validation_rules"))
    ]
    return {
        "payload_example_id": f"promotion_submitted_evidence_payload_example.{surface_id}.{gate_id}.v1",
        "source_record_envelope_id": _required_text(
            envelope,
            "record_envelope_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "source_verifier_request_id": _required_text(
            envelope,
            "source_verifier_request_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "source_intake_request_id": _required_text(
            envelope,
            "source_intake_request_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "gate_id": gate_id,
        "record_kind": _required_text(envelope, "record_kind", f"submitted-evidence record envelope {gate_id}"),
        "evidence_key": _required_text(envelope, "evidence_key", f"submitted-evidence record envelope {gate_id}"),
        "payload_state": "example_only",
        "submission_state": "not_submitted",
        "verification_state": "not_verified",
        "acceptance_state": "not_evaluated",
        "proof_state": "Unknown",
        "blocks_promotion": True,
        "satisfies_requirement": False,
        "payload_values_present": True,
        "payload_values_are_examples_only": True,
        "payload_example_is_not_submitted_evidence": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "required_artifacts": list(_string_list(envelope.get("required_artifacts"))),
        "required_payload_fields": required_payload_fields,
        "example_payload": example_payload,
        "acceptance_rules": acceptance_rules,
        "rejection_conditions": list(_string_list(envelope.get("rejection_conditions"))),
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "missing_submission_reason": f"{gate_id} payload is an example and has not been submitted",
    }


def _example_payload(envelope: dict[str, Any], surface_id: str, required_payload_fields: list[str]) -> dict[str, Any]:
    gate_id = _required_text(envelope, "gate_id", "submitted-evidence record envelope")
    required_artifacts = list(_string_list(envelope.get("required_artifacts")))
    payload: dict[str, Any] = {
        "submitted_evidence_id": f"example.submitted_evidence.{surface_id}.{gate_id}.v1",
        "source_verifier_request_id": _required_text(
            envelope,
            "source_verifier_request_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "source_intake_request_id": _required_text(
            envelope,
            "source_intake_request_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "gate_id": gate_id,
        "submitted_by": "operator://local_control_studio/example",
        "submitted_at_epoch": 0,
        "artifact_refs": [f"example://artifact/{artifact}" for artifact in required_artifacts],
        "operator_approval_refs": _operator_approval_refs(required_artifacts, gate_id),
        "witness_refs": [f"example://witness/{artifact}" for artifact in required_artifacts],
        "authority_claims": {
            "can_execute": False,
            "can_mutate": False,
            "can_call_connector": False,
            "can_claim_terminal_closure": False,
        },
        "terminal_closure_claim": False,
        "no_router_mutation_claim": True,
    }
    payload.update(_gate_specific_payload(gate_id))
    for field_name in required_payload_fields:
        payload.setdefault(field_name, f"example://missing-field/{surface_id}/{gate_id}/{field_name}")
    return {field_name: payload[field_name] for field_name in required_payload_fields}


def _gate_specific_payload(gate_id: str) -> dict[str, str]:
    values_by_gate = {
        "route_binding_gate": {
            "selected_component_bound_router_inventory_delta_ref": (
                "example://router-inventory-delta/governed_connector_framework/gmail_account_binding_gate"
            ),
            "component_route_binding_receipt_ref": (
                "example://receipt/component_route_binding/governed_connector_framework"
            ),
        },
        "lifecycle_gate": {
            "component_lifecycle_transition_receipt_ref": (
                "example://receipt/component_lifecycle_transition/gmail_account_binding_gate"
            ),
            "external_effect_operator_approval_ref": "example://operator-approval/external-effect/lifecycle_gate",
        },
        "authority_upgrade_gate": {
            "authority_upgrade_witness_ref": "example://witness/authority_upgrade/gmail_account_binding_gate",
            "connector_action_operator_approval_ref": (
                "example://operator-approval/connector-action/authority_upgrade_gate"
            ),
        },
        "product_specific_boundary_gate": {
            "product_specific_ownership_decision_ref": (
                "example://decision/product_specific_ownership/gmail_account_binding_gate"
            ),
            "gmail_account_binding_evidence_receipt_ref": (
                "example://receipt/gmail_account_binding_evidence/gmail_account_binding_gate"
            ),
        },
    }
    return values_by_gate.get(gate_id, {"promotion_specific_artifact_ref": f"example://artifact/{gate_id}"})


def _operator_approval_refs(required_artifacts: list[str], gate_id: str) -> list[str]:
    approvals = [
        artifact
        for artifact in required_artifacts
        if artifact.startswith("operator_approval") or artifact.endswith("operator_approval")
    ]
    return [f"example://operator-approval/{gate_id}/{approval}" for approval in approvals]


def _acceptance_rule(rule_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
    gate_id = _required_text(envelope, "gate_id", "submitted-evidence record envelope")
    return {
        "rule_id": rule_id,
        "source_record_envelope_id": _required_text(
            envelope,
            "record_envelope_id",
            f"submitted-evidence record envelope {gate_id}",
        ),
        "gate_id": gate_id,
        "rule_state": "defined_not_applied",
        "proof_state": "Unknown",
        "required_for_submission": True,
        "blocks_submission_until_pass": True,
        "rule_is_not_execution_authority": True,
        "mutates_router_inventory": False,
        "grants_execution_authority": False,
        "grants_connector_authority": False,
        "grants_terminal_closure": False,
        "source_payload_fields": _rule_payload_fields(rule_id, gate_id),
        "failure_condition": f"{rule_id}_not_proven",
    }


def _rule_payload_fields(rule_id: str, gate_id: str) -> list[str]:
    if "source_intake" in rule_id or "links_to_source" in rule_id:
        return ["source_intake_request_id", "source_verifier_request_id", "gate_id"]
    if "operator_approval" in rule_id:
        return ["operator_approval_refs"]
    if "grant_authority" in rule_id or "authority_by_itself" in rule_id:
        return ["authority_claims", "terminal_closure_claim"]
    if "route_binding" in rule_id or "router_inventory" in rule_id:
        return ["selected_component_bound_router_inventory_delta_ref", "component_route_binding_receipt_ref"]
    if "lifecycle" in rule_id or "transition" in rule_id:
        return ["component_lifecycle_transition_receipt_ref", "external_effect_operator_approval_ref"]
    if "authority" in rule_id:
        return ["authority_upgrade_witness_ref", "connector_action_operator_approval_ref"]
    if "gmail" in rule_id or "ownership" in rule_id:
        return ["product_specific_ownership_decision_ref", "gmail_account_binding_evidence_receipt_ref"]
    return list(COMMON_PAYLOAD_FIELDS[:4])


def _summary(payload_examples: list[dict[str, Any]], approval_evidence_required: list[str]) -> dict[str, int]:
    acceptance_rule_count = sum(len(example["acceptance_rules"]) for example in payload_examples)
    return {
        "payload_example_count": len(payload_examples),
        "example_only_payload_count": sum(1 for example in payload_examples if example["payload_state"] == "example_only"),
        "not_submitted_payload_count": sum(1 for example in payload_examples if example["submission_state"] == "not_submitted"),
        "not_evaluated_payload_count": sum(1 for example in payload_examples if example["acceptance_state"] == "not_evaluated"),
        "submitted_payload_count": sum(len(example["submitted_evidence_refs"]) for example in payload_examples),
        "accepted_evidence_count": sum(len(example["accepted_evidence_refs"]) for example in payload_examples),
        "rejected_evidence_count": sum(len(example["rejected_evidence_refs"]) for example in payload_examples),
        "acceptance_rule_count": acceptance_rule_count,
        "applied_acceptance_rule_count": 0,
        "passing_acceptance_rule_count": 0,
        "failing_acceptance_rule_count": 0,
        "satisfied_requirement_count": sum(1 for example in payload_examples if example["satisfies_requirement"] is True),
        "blocking_payload_count": sum(1 for example in payload_examples if example["blocks_promotion"] is True),
        "approval_artifact_requirement_count": len(approval_evidence_required),
        "authority_grant_count": sum(
            1
            for example in payload_examples
            if example["grants_execution_authority"]
            or example["grants_connector_authority"]
            or example["grants_terminal_closure"]
        ),
    }


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
