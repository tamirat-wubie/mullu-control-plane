"""Purpose: verifier execution record value explicit decision candidate projection.
Governance scope: no-effect candidate projection after generic continuation
rejection, without collecting, storing, admitting, or executing a value.
Dependencies: personal-assistant record value generic continuation rejection
runtime and contracts.
Invariants:
  - Explicit decision candidates are projected as classes, not accepted values.
  - Generic continuation rejection remains preserved.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_CANDIDATE_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_CANDIDATE_GENERATED_AT = (
    "2026-06-14T01:50:00+00:00"
)

_CANDIDATE_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_item_[a-z0-9][a-z0-9_:-]*$"
)
_EXPLICIT_DECISION_CANDIDATE_KINDS = (
    "explicit_operator_approval",
    "explicit_operator_rejection",
    "explicit_operator_revision_request",
    "explicit_operator_expiry",
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_candidate_admitted": False,
    "explicit_decision_candidate_executed": False,
    "explicit_operator_decision_value_bound": False,
    "generic_continuation_accepted_as_value": False,
    "generic_continuation_accepted_as_decision": False,
    "record_value_explicit_decision_candidate_admitted": False,
    "record_value_generic_continuation_rejection_admitted": False,
    "record_value_absence_admitted": False,
    "record_value_collection_gate_satisfied": False,
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
        "explicit_decision_candidate_admitted",
        "explicit_decision_candidate_executed",
        "explicit_operator_decision_value_bound",
        "record_value_explicit_decision_candidate_admitted",
    }
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_allowed": True,
    "generic_continuation_rejection_ref_binding_allowed": True,
    "explicit_decision_candidate_projection_allowed": True,
    "explicit_decision_candidate_classes_projected": True,
    "generic_continuation_rejection_preserved": True,
    "actual_operator_decision_value_absent": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "generic_continuation_rejection_projection": "ref_only",
    "explicit_decision_candidate_projection": "class_only",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_CANDIDATE_GENERATED_AT,
    explicit_decision_candidate_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_CANDIDATE_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision candidate packet."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope(
        generated_at=generated_at,
        explicit_decision_candidate_id=explicit_decision_candidate_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection: Mapping[str, Any],
    explicit_decision_candidate_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_CANDIDATE_ID,
) -> dict[str, Any]:
    """Build blocked explicit decision candidate packet from generic-continuation rejection evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(explicit_decision_candidate_id, "explicit_decision_candidate_id", _CANDIDATE_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection")
    _assert_generic_continuation_rejection_boundary(source_envelope)
    source_rejection_id = _require_non_empty_text(source_envelope.get("generic_continuation_rejection_id"), "generic_continuation_rejection_id")
    source_records = _require_sequence(source_envelope.get("generic_continuation_rejections"), "generic_continuation_rejections")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("explicit decision candidate source rejection must be a mapping")
        _assert_generic_continuation_rejection_item_boundary(source_record)
        record = _explicit_decision_candidate_item(source_rejection_id, source_record, timestamp=timestamp)
        if record["explicit_decision_candidate_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(
                f"duplicate explicit_decision_candidate_item_id {record['explicit_decision_candidate_item_id']}"
            )
        item_ids.append(record["explicit_decision_candidate_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("explicit decision candidate projection requires at least one generic continuation rejection")

    envelope = {
        "explicit_decision_candidate_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection",
        "source_generic_continuation_rejection_id": source_rejection_id,
        "explicit_decision_candidate_state": "explicit_operator_decision_candidate_projected_not_admitted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "explicit_decision_candidate_count": len(records),
        "explicit_decision_candidate_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "explicit_decision_candidates": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "explicit_decision_candidate_only": True,
            "explicit_decision_candidate_classes_projected": True,
            "generic_continuation_rejection_preserved": True,
            "actual_operator_decision_value_absent": True,
            "explicit_decision_candidate_admitted": False,
            "explicit_operator_decision_value_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "candidate_class_is_not_operator_decision_value",
                "actual_operator_decision_value_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "collect one explicit governed operator decision value with required refs before value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate",
            "runtime_boundary": "explicit_operator_decision_candidate_projected_not_admitted",
            "explicit_decision_candidate_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _explicit_decision_candidate_item(source_rejection_id: str, source_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("generic_continuation_rejection_item_id"), "generic_continuation_rejection_item_id")
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
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "explicit_decision_candidate_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "explicit_decision_candidate_item_id": item_id,
        "source_generic_continuation_rejection_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "generic_continuation_rejection_ref": {
            "source_generic_continuation_rejection_id": source_rejection_id,
            "source_generic_continuation_rejection_item_id": source_item_id,
            "source_generic_continuation_rejection_state": "generic_continuation_rejected_not_operator_value",
            "source_outcome": "SolvedVerified",
            "source_generic_continuation_rejected": True,
            "source_actual_operator_decision_value_absent": True,
            "source_generic_continuation_accepted_as_value": False,
            "source_operator_decision_value_present": False,
            "source_operator_value_record_created": False,
            "source_verifier_execution_allowed": False,
            "source_authority_granted": False,
        },
        "explicit_decision_candidate": {
            "record_contract_ready": True,
            "explicit_decision_candidate_classes_projected": True,
            "candidate_kind_count": len(_EXPLICIT_DECISION_CANDIDATE_KINDS),
            "candidate_kinds": [_candidate_kind(kind) for kind in _EXPLICIT_DECISION_CANDIDATE_KINDS],
            "required_value_refs": list(_REQUIRED_VALUE_REFS),
            "requires_actual_operator_decision_value": True,
            "requires_operator_identity_ref": True,
            "requires_operator_signature_ref": True,
            "requires_operator_reapproval_decision_receipt_ref": True,
            "candidate_class_is_value": False,
            "candidate_class_grants_authority": False,
            "candidate_class_grants_verifier_execution": False,
            "actual_operator_decision_value_absent": True,
            **dict(_FALSE_FIELDS),
        },
        "authority_status": _authority_status(),
        "receipt": _explicit_decision_candidate_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_{evidence_kind}_{requirement_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            requirement_kind=requirement_kind,
            timestamp=timestamp,
        ),
    }


def _candidate_kind(candidate_kind: str) -> dict[str, Any]:
    return {
        "candidate_kind": candidate_kind,
        "candidate_detectable": True,
        "candidate_admitted": False,
        "candidate_executed": False,
        "candidate_value_bound": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "required_value_refs": list(_REQUIRED_VALUE_REFS),
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


def _explicit_decision_candidate_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection",
            "explicit_decision_candidate_projection_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_explicit_decision_candidate_classes_projected",
            "explicit_decision_candidate_receipt_created",
        ],
        "actions_not_taken": [
            "candidate_class_not_accepted_as_operator_value",
            "operator_decision_value_not_collected",
            "operator_decision_value_not_bound",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-candidate/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-candidate/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "explicit_decision_candidate_only": True,
            "explicit_decision_candidate_classes_projected": True,
            "actual_operator_decision_value_absent": True,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    candidate_payloads = [_require_mapping(record.get("explicit_decision_candidate"), "explicit_decision_candidate") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    candidate_classes = [
        candidate
        for payload in candidate_payloads
        for candidate in _require_sequence(payload.get("candidate_kinds"), "candidate_kinds")
        if isinstance(candidate, Mapping)
    ]
    return {
        "explicit_decision_candidate_count": len(records),
        "explicit_decision_candidate_class_count": len(candidate_classes),
        "explicit_decision_candidate_detectable_count": sum(1 for candidate in candidate_classes if candidate.get("candidate_detectable") is True),
        "explicit_decision_candidate_admission_count": sum(1 for candidate in candidate_classes if candidate.get("candidate_admitted") is True),
        "explicit_decision_candidate_execution_count": sum(1 for candidate in candidate_classes if candidate.get("candidate_executed") is True),
        "explicit_operator_decision_value_bound_count": sum(1 for candidate in candidate_classes if candidate.get("candidate_value_bound") is True),
        "generic_continuation_rejection_preserved_count": len(records),
        "actual_operator_decision_value_absent_count": sum(1 for payload in candidate_payloads if payload.get("actual_operator_decision_value_absent") is True),
        "operator_decision_value_present_count": sum(1 for payload in candidate_payloads if payload.get("operator_decision_value_present") is True),
        "operator_value_record_creation_count": sum(1 for payload in candidate_payloads if payload.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for payload in candidate_payloads if payload.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
    }


def _assert_generic_continuation_rejection_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_allowed",
        "decision_value_record_value_absence_ref_binding_allowed",
        "generic_continuation_rejection_projection_allowed",
        "generic_continuation_rejected",
        "actual_operator_decision_value_absent",
        "record_value_absences_present",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"generic continuation rejection effect_boundary.{field_name} must be true")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in effect_boundary and effect_boundary.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"generic continuation rejection effect_boundary.{field_name} must be false")
    if source_envelope.get("generic_continuation_rejection_state") != "generic_continuation_rejected_not_operator_value":
        raise PersonalAssistantInvariantError("generic continuation rejection must remain rejected not operator value")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "SolvedVerified":
        raise PersonalAssistantInvariantError("generic continuation rejection must remain blocked SolvedVerified")


def _assert_generic_continuation_rejection_item_boundary(source_record: Mapping[str, Any]) -> None:
    rejection = _require_mapping(source_record.get("generic_continuation_rejection"), "generic_continuation_rejection")
    for field_name in ("generic_continuation_rejected", "actual_operator_decision_value_absent"):
        if rejection.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"generic continuation rejection.{field_name} must be true")
    if rejection.get("observed_input_kind") != "generic_continuation":
        raise PersonalAssistantInvariantError("generic continuation rejection observed_input_kind drifted")
    if rejection.get("rejected_reason") != "not_explicit_operator_decision_value":
        raise PersonalAssistantInvariantError("generic continuation rejection reason drifted")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in rejection and rejection.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"generic continuation rejection.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"generic continuation rejection authority_status.{field_name} must be false")


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
