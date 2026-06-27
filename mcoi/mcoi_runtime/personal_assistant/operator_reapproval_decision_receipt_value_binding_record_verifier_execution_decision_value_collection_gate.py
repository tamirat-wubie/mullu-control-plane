"""Purpose: verifier execution operator decision-value collection gate.
Governance scope: no-effect gate after decision-value template projection,
without collecting, accepting, submitting, admitting, or executing a value.
Dependencies: personal-assistant verifier execution decision-value template
runtime and contracts.
Invariants:
  - Collection requires a future explicit operator decision value.
  - Generic continuation and template packets are rejected as values.
  - No operator value, approval, rejection, verifier execution, evidence
    acceptance, binding admission, or authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_COLLECTION_GATE_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_COLLECTION_GATE_GENERATED_AT = (
    "2026-06-14T01:25:00+00:00"
)

_COLLECTION_GATE_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_item_[a-z0-9][a-z0-9_:-]*$"
)
_EVIDENCE_KINDS = {
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
}
_VERIFICATION_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}
_ACCEPTED_DECISION_VALUES = ("approved", "rejected", "revise_requested", "expired")
_REJECTED_INPUT_KINDS = ("generic_continuation", "template_packet")
_REQUIRED_FIELDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_TRUE_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_allowed": True,
    "decision_value_template_ref_binding_allowed": True,
    "operator_decision_value_collection_gate_projection_allowed": True,
    "decision_value_templates_present": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "actual_operator_decision_value_required": True,
    "verifier_ref_only": True,
}
_FALSE_EFFECT_BOUNDARY = {
    "raw_operator_value_present": False,
    "collection_route_admitted": False,
    "template_accepted_as_value": False,
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
    "operator_decision_value_submitted": False,
    "operator_decision_value_admitted": False,
    "operator_decision_present": False,
    "operator_decision_intake_completed": False,
    "operator_approval_granted": False,
    "operator_approval_rejected": False,
    "operator_decision_value_accepted": False,
    "operator_decision_value_rejected": False,
    "ready_for_verifier_execution": False,
    "verifier_execution_allowed": False,
    "verifier_execution_started": False,
    "verifier_execution_completed": False,
    "verifier_result_present": False,
    "verifier_ref_validated": False,
    "evidence_verified": False,
    "evidence_accepted": False,
    "evidence_rejected": False,
    "binding_record_created": False,
    "binding_record_admitted": False,
    "authority_granted": False,
    "execution_worker_admission_allowed": False,
    "dispatch_allowed": False,
    "dispatch_lease_active": False,
    "live_connector_execution_allowed": False,
    "connector_mutation_allowed": False,
    "system_of_record_write_allowed": False,
    "memory_write_allowed": False,
    "deployment_mutation_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_EFFECT_BOUNDARY = {**_TRUE_EFFECT_BOUNDARY, **_FALSE_EFFECT_BOUNDARY}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "decision_value_template_projection": "ref_only",
    "operator_decision_value_projection": "absent",
    "operator_identity_ref_projection": "placeholder_only",
    "operator_signature_ref_projection": "placeholder_only",
    "decision_receipt_projection": "placeholder_only",
    "verifier_execution_payload_projection": "absent",
    "verification_evidence_projection": "absent",
}
_RAW_PRIVATE_FIELD_NAMES = {
    "raw_private_connector_payload",
    "raw_connector_payload",
    "private_connector_payload",
    "connector_response",
    "message_body",
    "email_body",
    "calendar_payload",
    "mailbox_payload",
    "raw_message",
    "raw_thread",
    "raw_chat_log",
    "chat_log",
    "transcript",
    "credential",
    "credentials",
    "token",
    "secret",
    "private_key",
    "authorization",
    "cookie",
    "raw_operator_decision",
    "operator_decision_value",
    "operator_identity",
    "operator_signature",
    "raw_decision_receipt",
    "raw_verifier_payload",
    "verifier_payload",
    "verifier_execution_payload",
    "verifier_result",
    "submitted_evidence_payload",
    "accepted_value",
    "verified_value",
}
_ALLOWED_POLICY_FIELD_NAMES = frozenset(_PRIVATE_PAYLOAD_POLICY) | {"private_payload_policy"}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_COLLECTION_GATE_GENERATED_AT,
    collection_gate_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_COLLECTION_GATE_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect verifier execution decision-value collection gate."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope(
        generated_at=generated_at,
        collection_gate_id=collection_gate_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template: Mapping[str, Any],
    collection_gate_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_COLLECTION_GATE_ID,
) -> dict[str, Any]:
    """Build blocked collection gate packet from decision-value template evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(collection_gate_id, "collection_gate_id", _COLLECTION_GATE_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template",
    )
    _scan_private_or_secret_payload(
        source_envelope,
        path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template",
    )
    _assert_decision_value_template_boundary(source_envelope)
    source_template_id = _require_non_empty_text(source_envelope.get("decision_value_template_id"), "decision_value_template_id")
    source_records = _require_sequence(source_envelope.get("decision_value_templates"), "decision_value_templates")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("decision-value collection gate source record must be a mapping")
        _assert_decision_value_template_record_boundary(source_record)
        record = _collection_gate_item(source_template_id, source_record, timestamp=timestamp)
        if record["collection_gate_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(f"duplicate collection_gate_item_id {record['collection_gate_item_id']}")
        item_ids.append(record["collection_gate_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("decision-value collection gate requires at least one decision-value template")

    envelope = {
        "collection_gate_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template",
        "source_decision_value_template_id": source_template_id,
        "collection_gate_state": "operator_decision_value_collection_gate_blocked_awaiting_explicit_operator_value",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "collection_gate_count": len(records),
        "collection_gate_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "collection_gates": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "collection_gate_only": True,
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "actual_operator_decision_value_required": True,
            "collection_route_admitted": False,
            "template_accepted_as_value": False,
            "operator_decision_value_present": False,
            "operator_decision_value_collected": False,
            "operator_decision_value_submitted": False,
            "operator_decision_value_admitted": False,
            "operator_decision_present": False,
            "operator_approval_granted": False,
            "operator_approval_rejected": False,
            "ready_for_verifier_execution": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "actual_operator_decision_value_absent",
                "collection_route_not_admitted",
                "template_packet_not_accepted_as_value",
                "operator_approval_not_granted",
                "operator_approval_not_rejected",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "record a governed explicit operator decision value in a separate value-record artifact",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate",
            "runtime_boundary": "operator_decision_value_collection_gate_blocked_awaiting_explicit_operator_value",
            "collection_gate_only": True,
            **dict(_FALSE_EFFECT_BOUNDARY),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _collection_gate_item(source_template_id: str, source_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("decision_value_template_item_id"), "decision_value_template_item_id")
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    requirement_kind = _require_non_empty_text(source_record.get("requirement_kind"), "requirement_kind")
    if evidence_kind not in _EVIDENCE_KINDS or requirement_kind not in _VERIFICATION_REQUIREMENT_KINDS:
        raise PersonalAssistantInvariantError("decision-value collection gate source kind must remain governed")
    approval_id = _require_non_empty_text(source_record.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_record.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_record.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_record.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_record.get("risk_level"), "risk_level")
    submitted_evidence_ref = _require_non_empty_text(source_record.get("submitted_evidence_ref"), "submitted_evidence_ref")
    submitted_verifier_ref = _require_non_empty_text(source_record.get("submitted_verifier_ref"), "submitted_verifier_ref")
    suffix = approval_id.removeprefix("pa_approval_")
    item_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "collection_gate_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "collection_gate_item_id": item_id,
        "source_decision_value_template_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "decision_value_template_ref": {
            "source_decision_value_template_id": source_template_id,
            "source_decision_value_template_item_id": source_item_id,
            "source_decision_value_template_state": "operator_decision_value_template_prepared_not_collected_not_admitted",
            "source_outcome": "AwaitingEvidence",
            "source_operator_decision_required": True,
            "source_operator_decision_value_required": True,
            "source_operator_decision_value_template_created": True,
            "source_operator_decision_value_present": False,
            "source_operator_decision_value_collected": False,
            "source_operator_decision_value_submitted": False,
            "source_operator_decision_value_admitted": False,
            "source_operator_decision_present": False,
            "source_operator_approval_granted": False,
            "source_operator_approval_rejected": False,
            "source_verifier_execution_allowed": False,
            "source_verifier_execution_started": False,
            "source_authority_granted": False,
        },
        "collection_gate": {
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "actual_operator_decision_value_required": True,
            "collection_gate_created": True,
            "accepted_decision_values": list(_ACCEPTED_DECISION_VALUES),
            "rejected_input_kinds": list(_REJECTED_INPUT_KINDS),
            "required_fields": list(_REQUIRED_FIELDS),
            "accepts_generic_continuation": False,
            "accepts_template_packet": False,
            "collection_route_admitted": False,
            "template_accepted_as_value": False,
            "operator_decision_value_present": False,
            "operator_decision_value_collected": False,
            "operator_decision_value_submitted": False,
            "operator_decision_value_admitted": False,
            "operator_decision_present": False,
            "operator_decision_intake_completed": False,
            "operator_approval_granted": False,
            "operator_approval_rejected": False,
            "operator_decision_value_accepted": False,
            "operator_decision_value_rejected": False,
            "ready_for_verifier_execution": False,
            "verifier_execution_allowed": False,
            "verifier_execution_started": False,
            "verifier_result_present": False,
            "verifier_ref_validated": False,
            "evidence_accepted": False,
            "authority_granted": False,
            "blocking_reason": "actual_operator_decision_value_absent",
        },
        "authority_status": _authority_status(),
        "receipt": _collection_gate_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_{evidence_kind}_{requirement_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            requirement_kind=requirement_kind,
            timestamp=timestamp,
        ),
    }


def _authority_status() -> dict[str, bool]:
    return {
        "operator_value_bound": False,
        "operator_identity_ref_bound": False,
        "operator_signature_ref_bound": False,
        "decision_receipt_ref_bound": False,
        "binding_record_created": False,
        "binding_record_admitted": False,
        "authority_granted": False,
        "execution_worker_admission_allowed": False,
        "dispatch_allowed": False,
        "dispatch_lease_active": False,
        "live_connector_receipt_present": False,
        "live_connector_execution_allowed": False,
        "connector_mutation_allowed": False,
        "system_of_record_write_allowed": False,
        "memory_write_allowed": False,
    }


def _collection_gate_receipt(
    *,
    receipt_id: str,
    request_id: str,
    skill_id: str,
    risk_level: str,
    approval_id: str,
    evidence_kind: str,
    requirement_kind: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level,
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template",
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_decision_value_collection_gate_projected",
            "operator_decision_value_collection_gate_created",
            "decision_value_collection_gate_receipt_created",
        ],
        "actions_not_taken": [
            "collection_route_not_admitted",
            "template_packet_not_accepted_as_value",
            "operator_decision_value_not_collected",
            "operator_decision_value_not_submitted",
            "operator_decision_value_not_admitted",
            "operator_decision_not_admitted",
            "operator_approval_not_granted",
            "operator_approval_not_rejected",
            "verifier_execution_not_allowed",
            "verifier_execution_not_started",
            "verifier_result_not_collected",
            "verifier_ref_not_validated",
            "operator_evidence_not_accepted",
            "binding_record_not_created",
            "execution_worker_not_admitted",
            "dispatch_not_started",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "operator_decision_value_not_serialized",
            "operator_identity_not_serialized",
            "operator_signature_not_serialized",
            "raw_verifier_payload_not_serialized",
            "verifier_result_not_serialized",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-collection-gate/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-collection-gate/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "collection_gate_only": True,
            "actual_operator_decision_value_required": True,
            "collection_gate_created": True,
            "collection_route_admitted": False,
            "template_accepted_as_value": False,
            "operator_decision_value_present": False,
            "operator_decision_value_collected": False,
            "operator_decision_value_submitted": False,
            "operator_decision_value_admitted": False,
            "operator_decision_present": False,
            "operator_decision_intake_completed": False,
            "operator_approval_granted": False,
            "operator_approval_rejected": False,
            "operator_decision_value_accepted": False,
            "operator_decision_value_rejected": False,
            "ready_for_verifier_execution": False,
            "verifier_execution_allowed": False,
            "verifier_execution_started": False,
            "verifier_result_present": False,
            "verifier_ref_validated": False,
            "evidence_accepted": False,
            "binding_record_created": False,
            "binding_record_admitted": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "dispatch_lease_active": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    gates = [_require_mapping(record.get("collection_gate"), "collection_gate") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "collection_gate_count": len(records),
        "operator_decision_required_count": sum(1 for record in gates if record.get("operator_decision_required") is True),
        "operator_decision_value_required_count": sum(1 for record in gates if record.get("operator_decision_value_required") is True),
        "actual_operator_decision_value_required_count": sum(1 for record in gates if record.get("actual_operator_decision_value_required") is True),
        "collection_gate_creation_count": sum(1 for record in gates if record.get("collection_gate_created") is True),
        "collection_route_admission_count": sum(1 for record in gates if record.get("collection_route_admitted") is True),
        "template_accepted_as_value_count": sum(1 for record in gates if record.get("template_accepted_as_value") is True),
        "operator_decision_value_present_count": sum(1 for record in gates if record.get("operator_decision_value_present") is True),
        "operator_decision_value_collected_count": sum(1 for record in gates if record.get("operator_decision_value_collected") is True),
        "operator_decision_value_submitted_count": sum(1 for record in gates if record.get("operator_decision_value_submitted") is True),
        "operator_decision_value_admitted_count": sum(1 for record in gates if record.get("operator_decision_value_admitted") is True),
        "operator_decision_present_count": sum(1 for record in gates if record.get("operator_decision_present") is True),
        "operator_approval_grant_count": sum(1 for record in gates if record.get("operator_approval_granted") is True),
        "operator_approval_rejection_count": sum(1 for record in gates if record.get("operator_approval_rejected") is True),
        "verifier_execution_allowed_count": sum(1 for record in gates if record.get("verifier_execution_allowed") is True),
        "verifier_execution_started_count": sum(1 for record in gates if record.get("verifier_execution_started") is True),
        "verifier_result_count": sum(1 for record in gates if record.get("verifier_result_present") is True),
        "validated_verifier_ref_count": sum(1 for record in gates if record.get("verifier_ref_validated") is True),
        "accepted_evidence_count": sum(1 for record in gates if record.get("evidence_accepted") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_decision_value_template_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template_allowed",
        "decision_value_request_ref_binding_allowed",
        "operator_decision_value_template_projection_allowed",
        "decision_value_requests_present",
        "operator_decision_required",
        "operator_decision_value_required",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision-value template effect_boundary.{field_name} must be true")
    for field_name in _FALSE_EFFECT_BOUNDARY:
        if field_name in effect_boundary and effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"decision-value template effect_boundary.{field_name} must be false")
    if source_envelope.get("decision_value_template_state") != "operator_decision_value_template_prepared_not_collected_not_admitted":
        raise PersonalAssistantInvariantError("decision-value template must remain prepared and unadmitted")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("decision-value template must remain blocked AwaitingEvidence")


def _assert_decision_value_template_record_boundary(source_record: Mapping[str, Any]) -> None:
    template = _require_mapping(source_record.get("decision_value_template"), "decision_value_template")
    for field_name in ("operator_decision_required", "operator_decision_value_required", "operator_decision_value_template_created"):
        if template.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision_value_template.{field_name} must be true")
    if tuple(template.get("accepted_decision_values", ())) != _ACCEPTED_DECISION_VALUES:
        raise PersonalAssistantInvariantError("decision_value_template.accepted_decision_values must use canonical values")
    if tuple(template.get("required_fields", ())) != _REQUIRED_FIELDS:
        raise PersonalAssistantInvariantError("decision_value_template.required_fields must use canonical required fields")
    for field_name in (
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_submitted",
        "operator_decision_value_admitted",
        "operator_decision_present",
        "operator_decision_intake_completed",
        "operator_approval_granted",
        "operator_approval_rejected",
        "operator_decision_value_accepted",
        "operator_decision_value_rejected",
        "ready_for_verifier_execution",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_accepted",
        "authority_granted",
    ):
        if template.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"decision_value_template.{field_name} must be false")
    if template.get("blocking_reason") != "operator_decision_value_template_prepared_not_collected":
        raise PersonalAssistantInvariantError("decision_value_template.blocking_reason must be operator_decision_value_template_prepared_not_collected")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    return value


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _require_pattern(value: Any, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.match(text):
        raise PersonalAssistantInvariantError(f"{field_name} has invalid format")
    return text


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in _RAW_PRIVATE_FIELD_NAMES and normalized_key not in _ALLOWED_POLICY_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")
