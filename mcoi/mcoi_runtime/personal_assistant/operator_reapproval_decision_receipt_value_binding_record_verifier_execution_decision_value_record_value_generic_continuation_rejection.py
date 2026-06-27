"""Purpose: verifier execution record value generic continuation rejection.
Governance scope: no-effect rejection of generic continuation after record
value absence, without collecting, storing, admitting, or executing a value.
Dependencies: personal-assistant verifier execution decision-value record value
absence runtime and contracts.
Invariants:
  - Generic continuation is never accepted as an operator decision value.
  - The source record value absence remains blocked and unadmitted.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_GENERATED_AT = (
    "2026-06-14T01:45:00+00:00"
)

_REJECTION_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_item_[a-z0-9][a-z0-9_:-]*$"
)
_REJECTION_RULE_IDS = (
    "generic-continuation-is-not-explicit-operator-approval",
    "generic-continuation-is-not-explicit-operator-rejection",
    "generic-continuation-is-not-explicit-operator-revision",
    "generic-continuation-is-not-explicit-operator-expiry",
    "generic-continuation-grants-no-verifier-authority",
)
_FALSE_FIELDS = {
    "generic_continuation_accepted_as_value": False,
    "generic_continuation_accepted_as_decision": False,
    "record_value_generic_continuation_rejection_admitted": False,
    "record_value_absence_admitted": False,
    "record_value_collection_gate_satisfied": False,
    "record_value_template_admitted": False,
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
_SOURCE_FALSE_FIELDS = {
    field_name: False
    for field_name in _FALSE_FIELDS
    if field_name
    not in {
        "generic_continuation_accepted_as_value",
        "generic_continuation_accepted_as_decision",
        "record_value_generic_continuation_rejection_admitted",
    }
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_allowed": True,
    "decision_value_record_value_absence_ref_binding_allowed": True,
    "generic_continuation_rejection_projection_allowed": True,
    "generic_continuation_rejected": True,
    "actual_operator_decision_value_absent": True,
    "record_value_absences_present": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "record_value_absence_projection": "ref_only",
    "generic_continuation_projection": "rejected_non_value",
    "operator_decision_value_projection": "absent",
    "operator_value_record_projection": "absent",
    "verifier_execution_payload_projection": "absent",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_GENERATED_AT,
    generic_continuation_rejection_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect record value generic continuation rejection packet."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope(
        generated_at=generated_at,
        generic_continuation_rejection_id=generic_continuation_rejection_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence: Mapping[str, Any],
    generic_continuation_rejection_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_ID,
) -> dict[str, Any]:
    """Build blocked generic continuation rejection packet from record value absence evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(generic_continuation_rejection_id, "generic_continuation_rejection_id", _REJECTION_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence")
    _assert_record_value_absence_boundary(source_envelope)
    source_record_value_absence_id = _require_non_empty_text(source_envelope.get("record_value_absence_id"), "record_value_absence_id")
    source_records = _require_sequence(source_envelope.get("record_value_absences"), "record_value_absences")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("record value generic continuation rejection source absence must be a mapping")
        _assert_record_value_absence_item_boundary(source_record)
        record = _generic_continuation_rejection_item(source_record_value_absence_id, source_record, timestamp=timestamp)
        if record["generic_continuation_rejection_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(
                f"duplicate generic_continuation_rejection_item_id {record['generic_continuation_rejection_item_id']}"
            )
        item_ids.append(record["generic_continuation_rejection_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("record value generic continuation rejection requires at least one record value absence")

    envelope = {
        "generic_continuation_rejection_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence",
        "source_record_value_absence_id": source_record_value_absence_id,
        "generic_continuation_rejection_state": "generic_continuation_rejected_not_operator_value",
        "decision": "blocked",
        "outcome": "SolvedVerified",
        "generic_continuation_rejection_count": len(records),
        "generic_continuation_rejection_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "generic_continuation_rejections": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "generic_continuation_rejection_only": True,
            "generic_continuation_rejected": True,
            "actual_operator_decision_value_absent": True,
            "generic_continuation_accepted_as_value": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "generic_continuation_is_not_operator_decision_value",
                "actual_operator_decision_value_absent",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "collect an explicit governed operator decision value; generic continuations remain rejected",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection",
            "runtime_boundary": "generic_continuation_rejected_not_operator_value",
            "generic_continuation_rejection_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _generic_continuation_rejection_item(source_record_value_absence_id: str, source_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("record_value_absence_item_id"), "record_value_absence_item_id")
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
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "generic_continuation_rejection_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "generic_continuation_rejection_item_id": item_id,
        "source_record_value_absence_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "record_value_absence_ref": {
            "source_record_value_absence_id": source_record_value_absence_id,
            "source_record_value_absence_item_id": source_item_id,
            "source_record_value_absence_state": "operator_decision_value_record_value_absent_not_collected_not_admitted",
            "source_outcome": "AwaitingEvidence",
            "source_record_contract_ready": True,
            "source_actual_operator_decision_value_absent": True,
            "source_operator_decision_value_present": False,
            "source_operator_value_record_created": False,
            "source_verifier_execution_allowed": False,
            "source_authority_granted": False,
        },
        "generic_continuation_rejection": {
            "generic_continuation_rejected": True,
            "observed_input_kind": "generic_continuation",
            "rejected_input_kind": "generic_continuation",
            "rejected_reason": "not_explicit_operator_decision_value",
            "actual_operator_decision_value_absent": True,
            "rejection_rules": [
                {
                    "rule_id": rule_id,
                    "applies": True,
                    "decision": "reject",
                    "grants_authority": False,
                    "grants_verifier_execution": False,
                }
                for rule_id in _REJECTION_RULE_IDS
            ],
            **dict(_FALSE_FIELDS),
        },
        "authority_status": _authority_status(),
        "receipt": _generic_continuation_rejection_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_{evidence_kind}_{requirement_kind}_{suffix}",
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


def _generic_continuation_rejection_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence",
            "generic_continuation_rejection_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_generic_continuation_rejected",
            "generic_continuation_rejection_receipt_created",
        ],
        "actions_not_taken": [
            "generic_continuation_not_accepted_as_operator_value",
            "operator_decision_value_not_collected",
            "operator_value_record_not_created",
            "verifier_execution_not_allowed",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-generic-continuation-rejection/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-generic-continuation-rejection/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "SolvedVerified",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "generic_continuation_rejected": True,
            "actual_operator_decision_value_absent": True,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    rejections = [_require_mapping(record.get("generic_continuation_rejection"), "generic_continuation_rejection") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "generic_continuation_rejection_count": len(records),
        "generic_continuation_rejected_count": sum(1 for record in rejections if record.get("generic_continuation_rejected") is True),
        "actual_operator_decision_value_absent_count": sum(1 for record in rejections if record.get("actual_operator_decision_value_absent") is True),
        "generic_continuation_accepted_as_value_count": sum(1 for record in rejections if record.get("generic_continuation_accepted_as_value") is True),
        "generic_continuation_accepted_as_decision_count": sum(1 for record in rejections if record.get("generic_continuation_accepted_as_decision") is True),
        "operator_decision_value_present_count": sum(1 for record in rejections if record.get("operator_decision_value_present") is True),
        "operator_value_record_creation_count": sum(1 for record in rejections if record.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for record in rejections if record.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "rule_count": sum(len(record.get("rejection_rules", ())) for record in rejections),
    }


def _assert_record_value_absence_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence_allowed",
        "decision_value_record_value_collection_gate_ref_binding_allowed",
        "operator_decision_value_record_value_absence_projection_allowed",
        "record_value_collection_gates_present",
        "actual_operator_decision_value_absent",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision-value record value absence effect_boundary.{field_name} must be true")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in effect_boundary and effect_boundary.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"decision-value record value absence effect_boundary.{field_name} must be false")
    if source_envelope.get("record_value_absence_state") != "operator_decision_value_record_value_absent_not_collected_not_admitted":
        raise PersonalAssistantInvariantError("decision-value record value absence must remain blocked absent")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("decision-value record value absence must remain blocked AwaitingEvidence")


def _assert_record_value_absence_item_boundary(source_record: Mapping[str, Any]) -> None:
    absence = _require_mapping(source_record.get("record_value_absence"), "record_value_absence")
    for field_name in (
        "record_contract_ready",
        "operator_decision_required",
        "operator_decision_value_required",
        "actual_operator_decision_value_required",
        "actual_operator_decision_value_absent",
    ):
        if absence.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"decision-value record value absence record_value_absence.{field_name} must be true")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in absence and absence.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"decision-value record value absence record_value_absence.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"decision-value record value absence authority_status.{field_name} must be false")


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
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
        raise PersonalAssistantInvariantError(f"{field_name} is not a governed identifier")
    return text


def _scan_private_or_secret_payload(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _RAW_PRIVATE_FIELD_NAMES and key_text not in _ALLOWED_POLICY_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{child_path} must not serialize raw private payload")
            _scan_private_or_secret_payload(child, path=child_path)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _scan_private_or_secret_payload(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise PersonalAssistantInvariantError(f"{path} secret-like value must not be serialized")
