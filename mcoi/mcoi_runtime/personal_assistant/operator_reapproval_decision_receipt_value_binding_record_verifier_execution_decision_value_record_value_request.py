"""Purpose: verifier execution operator decision-value record value request.
Governance scope: no-effect value request after decision-value record-path
projection, without collecting, storing, admitting, or executing an operator
value.
Dependencies: personal-assistant verifier execution decision-value
record-admission-gate runtime and contracts.
Invariants:
  - The value-record value request is projected but not admitted.
  - The source record admission gate remains unadmitted.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_REQUEST_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_REQUEST_GENERATED_AT = (
    "2026-06-14T01:35:00+00:00"
)

_RECORD_VALUE_REQUEST_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_item_[a-z0-9][a-z0-9_:-]*$"
)
_ACCEPTED_RECORD_KINDS = (
    "explicit_operator_approval",
    "explicit_operator_rejection",
    "explicit_operator_revision_request",
    "explicit_operator_expiry",
)
_REJECTED_INPUT_KINDS = ("generic_continuation", "template_packet")
_REQUIRED_FIELDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_RECORD_FLAGS = {
    "record_value_request_admitted": False,
    "record_admission_gate_admitted": False,
    "record_path_admitted": False,
    "collection_gate_satisfied": False,
    "operator_value_record_created": False,
    "operator_value_record_admitted": False,
    "operator_decision_value_stored": False,
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
_SOURCE_FALSE_RECORD_FLAGS = {
    field_name: False for field_name in _FALSE_RECORD_FLAGS if field_name != "record_value_request_admitted"
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_allowed": True,
    "decision_value_record_admission_gate_ref_binding_allowed": True,
    "operator_decision_value_record_value_request_projection_allowed": True,
    "record_admission_gates_present": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "actual_operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_RECORD_FLAGS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "record_admission_gate_projection": "ref_only",
    "operator_decision_value_projection": "absent",
    "operator_value_record_projection": "absent",
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
    "raw_operator_value_record",
    "operator_value_record",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_REQUEST_GENERATED_AT,
    record_value_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_REQUEST_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect verifier execution decision-value record value request."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_envelope(
        generated_at=generated_at,
        record_value_request_id=record_value_request_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate: Mapping[str, Any],
    record_value_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_REQUEST_ID,
) -> dict[str, Any]:
    """Build blocked value-record value request packet from admission-gate evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(record_value_request_id, "record_value_request_id", _RECORD_VALUE_REQUEST_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate")
    _assert_record_path_boundary(source_envelope)
    source_record_admission_gate_id = _require_non_empty_text(source_envelope.get("record_admission_gate_id"), "record_admission_gate_id")
    source_records = _require_sequence(source_envelope.get("record_admission_gates"), "record_admission_gates")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("decision-value record value request source record must be a mapping")
        _assert_record_path_item_boundary(source_record)
        record = _record_value_request_item(source_record_admission_gate_id, source_record, timestamp=timestamp)
        if record["record_value_request_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(f"duplicate record_value_request_item_id {record['record_value_request_item_id']}")
        item_ids.append(record["record_value_request_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("decision-value record value request requires at least one record admission gate")

    envelope = {
        "record_value_request_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate",
        "source_record_admission_gate_id": source_record_admission_gate_id,
        "record_value_request_state": "operator_decision_value_record_value_request_blocked_awaiting_actual_operator_value",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "record_value_request_count": len(records),
        "record_value_request_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "record_value_requests": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "record_value_request_only": True,
            "record_contract_ready": True,
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "actual_operator_decision_value_required": True,
            "record_value_request_admitted": False,
            "record_admission_gate_admitted": False,
            "record_path_admitted": False,
            "collection_gate_satisfied": False,
            "operator_value_record_created": False,
            "operator_value_record_admitted": False,
            "operator_decision_value_stored": False,
            "operator_decision_value_present": False,
            "operator_decision_value_admitted": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "actual_operator_decision_value_absent",
                "record_admission_gate_not_admitted",
                "record_path_not_admitted",
                "collection_gate_not_satisfied",
                "operator_value_record_not_created",
                "operator_value_record_not_admitted",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "collect a governed explicit operator decision value before admitting the value-record request",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request",
            "runtime_boundary": "operator_decision_value_record_value_request_blocked_awaiting_actual_operator_value",
            "record_value_request_only": True,
            **dict(_FALSE_RECORD_FLAGS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _record_value_request_item(source_record_admission_gate_id: str, source_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("record_admission_gate_item_id"), "record_admission_gate_item_id")
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    requirement_kind = _require_non_empty_text(source_record.get("requirement_kind"), "requirement_kind")
    approval_id = _require_non_empty_text(source_record.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_record.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_record.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_record.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_record.get("risk_level"), "risk_level")
    submitted_evidence_ref = _require_non_empty_text(source_record.get("submitted_evidence_ref"), "submitted_evidence_ref")
    submitted_verifier_ref = _require_non_empty_text(source_record.get("submitted_verifier_ref"), "submitted_verifier_ref")
    suffix = approval_id.removeprefix("pa_approval_")
    item_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "record_value_request_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "record_value_request_item_id": item_id,
        "source_record_admission_gate_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "record_admission_gate_ref": {
            "source_record_admission_gate_id": source_record_admission_gate_id,
            "source_record_admission_gate_item_id": source_item_id,
            "source_record_admission_gate_state": "operator_decision_value_record_admission_gate_blocked_awaiting_actual_operator_value",
            "source_outcome": "AwaitingEvidence",
            "source_record_contract_ready": True,
            "source_record_admission_gate_created": True,
            "source_operator_decision_required": True,
            "source_operator_decision_value_required": True,
            "source_actual_operator_decision_value_required": True,
            "source_record_admission_gate_admitted": False,
            "source_record_path_admitted": False,
            "source_collection_gate_satisfied": False,
            "source_operator_value_record_created": False,
            "source_operator_decision_value_stored": False,
            "source_operator_decision_value_present": False,
            "source_operator_decision_value_admitted": False,
            "source_verifier_execution_allowed": False,
            "source_verifier_execution_started": False,
            "source_authority_granted": False,
        },
        "record_value_request": {
            "record_contract_ready": True,
            "record_value_request_created": True,
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "actual_operator_decision_value_required": True,
            "accepted_record_kinds": list(_ACCEPTED_RECORD_KINDS),
            "rejected_input_kinds": list(_REJECTED_INPUT_KINDS),
            "required_fields": list(_REQUIRED_FIELDS),
            "requires_record_admission_gate_admitted": True,
            "requires_record_path_admitted": True,
            "requires_collection_gate_satisfied": True,
            "requires_actual_operator_value": True,
            "accepts_generic_continuation": False,
            "accepts_template_packet": False,
            **dict(_FALSE_RECORD_FLAGS),
            "blocking_reason": "actual_operator_decision_value_absent_record_admission_gate_unadmitted",
        },
        "authority_status": _authority_status(),
        "receipt": _record_value_request_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_{evidence_kind}_{requirement_kind}_{suffix}",
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
        "operator_value_record_created": False,
        "operator_value_record_admitted": False,
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


def _record_value_request_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate",
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_decision_value_record_value_request_projected",
            "operator_decision_value_record_value_request_checked",
            "decision_value_record_value_request_receipt_created",
        ],
        "actions_not_taken": [
            "record_value_request_not_admitted",
            "record_admission_gate_not_admitted",
            "record_path_not_admitted",
            "collection_gate_not_satisfied",
            "operator_decision_value_not_collected",
            "operator_decision_value_not_stored",
            "operator_decision_value_not_admitted",
            "operator_value_record_not_created",
            "operator_value_record_not_admitted",
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
            "operator_value_record_not_serialized",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-request/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-request/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_request_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "record_value_request_only": True,
            "record_contract_ready": True,
            "record_value_request_created": True,
            **dict(_FALSE_RECORD_FLAGS),
            "external_write_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    admission_gates = [_require_mapping(record.get("record_value_request"), "record_value_request") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "record_value_request_count": len(records),
        "record_contract_ready_count": sum(1 for record in admission_gates if record.get("record_contract_ready") is True),
        "operator_decision_required_count": sum(1 for record in admission_gates if record.get("operator_decision_required") is True),
        "operator_decision_value_required_count": sum(1 for record in admission_gates if record.get("operator_decision_value_required") is True),
        "actual_operator_decision_value_required_count": sum(1 for record in admission_gates if record.get("actual_operator_decision_value_required") is True),
        "record_value_request_creation_count": sum(1 for record in admission_gates if record.get("record_value_request_created") is True),
        "record_value_request_admission_count": sum(1 for record in admission_gates if record.get("record_value_request_admitted") is True),
        "record_admission_gate_admission_count": sum(1 for record in admission_gates if record.get("record_admission_gate_admitted") is True),
        "record_path_admission_count": sum(1 for record in admission_gates if record.get("record_path_admitted") is True),
        "collection_gate_satisfied_count": sum(1 for record in admission_gates if record.get("collection_gate_satisfied") is True),
        "operator_value_record_creation_count": sum(1 for record in admission_gates if record.get("operator_value_record_created") is True),
        "operator_value_record_admission_count": sum(1 for record in admission_gates if record.get("operator_value_record_admitted") is True),
        "operator_decision_value_storage_count": sum(1 for record in admission_gates if record.get("operator_decision_value_stored") is True),
        "operator_decision_value_present_count": sum(1 for record in admission_gates if record.get("operator_decision_value_present") is True),
        "operator_decision_value_admitted_count": sum(1 for record in admission_gates if record.get("operator_decision_value_admitted") is True),
        "operator_approval_grant_count": sum(1 for record in admission_gates if record.get("operator_approval_granted") is True),
        "operator_approval_rejection_count": sum(1 for record in admission_gates if record.get("operator_approval_rejected") is True),
        "verifier_execution_allowed_count": sum(1 for record in admission_gates if record.get("verifier_execution_allowed") is True),
        "verifier_execution_started_count": sum(1 for record in admission_gates if record.get("verifier_execution_started") is True),
        "verifier_result_count": sum(1 for record in admission_gates if record.get("verifier_result_present") is True),
        "validated_verifier_ref_count": sum(1 for record in admission_gates if record.get("verifier_ref_validated") is True),
        "accepted_evidence_count": sum(1 for record in admission_gates if record.get("evidence_accepted") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_record_path_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate_allowed",
        "decision_value_record_path_ref_binding_allowed",
        "operator_decision_value_record_admission_gate_projection_allowed",
        "record_paths_present",
        "operator_decision_required",
        "operator_decision_value_required",
        "actual_operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision-value record admission gate effect_boundary.{field_name} must be true")
    for field_name, expected_value in _SOURCE_FALSE_RECORD_FLAGS.items():
        if field_name in effect_boundary and effect_boundary.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"decision-value record admission gate effect_boundary.{field_name} must be false")
    if source_envelope.get("record_admission_gate_state") != "operator_decision_value_record_admission_gate_blocked_awaiting_actual_operator_value":
        raise PersonalAssistantInvariantError("decision-value record admission gate must remain blocked awaiting explicit value")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("decision-value record admission gate must remain blocked AwaitingEvidence")


def _assert_record_path_item_boundary(source_record: Mapping[str, Any]) -> None:
    path = _require_mapping(source_record.get("record_admission_gate"), "record_admission_gate")
    for field_name in (
        "record_contract_ready",
        "record_admission_gate_created",
        "operator_decision_required",
        "operator_decision_value_required",
        "actual_operator_decision_value_required",
        "requires_record_path_admitted",
        "requires_collection_gate_satisfied",
        "requires_actual_operator_value",
    ):
        if path.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision-value record admission gate record_admission_gate.{field_name} must be true")
    if tuple(path.get("accepted_record_kinds", ())) != _ACCEPTED_RECORD_KINDS:
        raise PersonalAssistantInvariantError("decision-value record admission gate accepted_record_kinds drifted")
    if tuple(path.get("rejected_input_kinds", ())) != _REJECTED_INPUT_KINDS:
        raise PersonalAssistantInvariantError("decision-value record admission gate rejected_input_kinds drifted")
    if tuple(path.get("required_fields", ())) != _REQUIRED_FIELDS:
        raise PersonalAssistantInvariantError("decision-value record admission gate required_fields drifted")
    for field_name, expected_value in _SOURCE_FALSE_RECORD_FLAGS.items():
        if field_name in path and path.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"decision-value record admission gate record_admission_gate.{field_name} must be false")
    authority_status = _require_mapping(source_record.get("authority_status"), "authority_status")
    for field_name in (
        "operator_value_bound",
        "operator_value_record_created",
        "operator_value_record_admitted",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if authority_status.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"decision-value record admission gate authority_status.{field_name} must be false")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    return value


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be non-empty text")
    return value


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
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
