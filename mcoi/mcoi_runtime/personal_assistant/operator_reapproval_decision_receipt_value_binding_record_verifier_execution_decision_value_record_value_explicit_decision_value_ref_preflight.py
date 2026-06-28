"""Purpose: verifier execution explicit decision value-ref preflight.
Governance scope: no-effect required-ref preflight after explicit decision
candidate projection, without collecting, storing, admitting, or executing a
value.
Dependencies: personal-assistant explicit decision candidate runtime and
contracts.
Invariants:
  - Required value refs are checked as absent slots, not accepted values.
  - Explicit decision candidates remain class-only and unadmitted.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_GENERATED_AT = (
    "2026-06-14T01:55:00+00:00"
)

_PREFLIGHT_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_item_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_preflight_satisfied": False,
    "explicit_decision_value_refs_present": False,
    "explicit_decision_candidate_admitted": False,
    "explicit_decision_candidate_executed": False,
    "explicit_operator_decision_value_bound": False,
    "record_value_explicit_decision_value_ref_preflight_admitted": False,
    "record_value_explicit_decision_candidate_admitted": False,
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
        "explicit_decision_value_ref_preflight_satisfied",
        "explicit_decision_value_refs_present",
        "record_value_explicit_decision_value_ref_preflight_admitted",
    }
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_allowed": True,
    "explicit_decision_candidate_ref_binding_allowed": True,
    "explicit_decision_value_ref_preflight_projection_allowed": True,
    "explicit_decision_candidate_classes_present": True,
    "required_value_refs_declared": True,
    "required_value_refs_absent": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "explicit_decision_candidate_projection": "ref_only",
    "explicit_decision_value_ref_projection": "slot_only",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_GENERATED_AT,
    explicit_decision_value_ref_preflight_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision value-ref preflight packet."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_preflight_id=explicit_decision_value_ref_preflight_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate: Mapping[str, Any],
    explicit_decision_value_ref_preflight_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_ID,
) -> dict[str, Any]:
    """Build blocked explicit decision value-ref preflight from candidate evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(explicit_decision_value_ref_preflight_id, "explicit_decision_value_ref_preflight_id", _PREFLIGHT_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate")
    _assert_explicit_decision_candidate_boundary(source_envelope)
    source_candidate_id = _require_non_empty_text(source_envelope.get("explicit_decision_candidate_id"), "explicit_decision_candidate_id")
    source_records = _require_sequence(source_envelope.get("explicit_decision_candidates"), "explicit_decision_candidates")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref preflight source candidate must be a mapping")
        _assert_explicit_decision_candidate_item_boundary(source_record)
        record = _explicit_decision_value_ref_preflight_item(source_candidate_id, source_record, timestamp=timestamp)
        if record["explicit_decision_value_ref_preflight_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(
                f"duplicate explicit_decision_value_ref_preflight_item_id {record['explicit_decision_value_ref_preflight_item_id']}"
            )
        item_ids.append(record["explicit_decision_value_ref_preflight_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("explicit decision value-ref preflight requires at least one explicit decision candidate")

    envelope = {
        "explicit_decision_value_ref_preflight_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate",
        "source_explicit_decision_candidate_id": source_candidate_id,
        "explicit_decision_value_ref_preflight_state": "explicit_decision_value_refs_absent_not_bound",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "explicit_decision_value_ref_preflight_count": len(records),
        "explicit_decision_value_ref_preflight_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "explicit_decision_value_ref_preflights": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "explicit_decision_value_ref_preflight_only": True,
            "required_value_refs_declared": True,
            "required_value_refs_absent": True,
            "explicit_decision_value_ref_preflight_satisfied": False,
            "explicit_decision_value_refs_present": False,
            "explicit_operator_decision_value_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "operator_decision_value_ref_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_reapproval_decision_receipt_ref_absent",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "collect all required governed refs before value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight",
            "runtime_boundary": "explicit_decision_value_refs_absent_not_bound",
            "explicit_decision_value_ref_preflight_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _explicit_decision_value_ref_preflight_item(source_candidate_id: str, source_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("explicit_decision_candidate_item_id"), "explicit_decision_candidate_item_id")
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
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "explicit_decision_value_ref_preflight_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "explicit_decision_value_ref_preflight_item_id": item_id,
        "source_explicit_decision_candidate_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "explicit_decision_candidate_ref": {
            "source_explicit_decision_candidate_id": source_candidate_id,
            "source_explicit_decision_candidate_item_id": source_item_id,
            "source_explicit_decision_candidate_state": "explicit_operator_decision_candidate_projected_not_admitted",
            "source_outcome": "AwaitingEvidence",
            "source_explicit_decision_candidate_classes_projected": True,
            "source_actual_operator_decision_value_absent": True,
            "source_explicit_decision_candidate_admitted": False,
            "source_operator_decision_value_present": False,
            "source_operator_value_record_created": False,
            "source_verifier_execution_allowed": False,
            "source_authority_granted": False,
        },
        "explicit_decision_value_ref_preflight": {
            "record_contract_ready": True,
            "required_value_refs_declared": True,
            "required_value_refs": [_required_ref_slot(ref_name) for ref_name in _REQUIRED_VALUE_REFS],
            "required_value_ref_count": len(_REQUIRED_VALUE_REFS),
            "required_value_ref_absent_count": len(_REQUIRED_VALUE_REFS),
            "required_value_ref_present_count": 0,
            "requires_all_required_refs": True,
            "requires_actual_operator_decision_value": True,
            "required_value_refs_absent": True,
            **dict(_FALSE_FIELDS),
        },
        "authority_status": _authority_status(),
        "receipt": _explicit_decision_value_ref_preflight_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_{evidence_kind}_{requirement_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            requirement_kind=requirement_kind,
            timestamp=timestamp,
        ),
    }


def _required_ref_slot(ref_name: str) -> dict[str, Any]:
    return {
        "ref_name": ref_name,
        "required": True,
        "present": False,
        "bound": False,
        "validated": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
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


def _explicit_decision_value_ref_preflight_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate",
            "explicit_decision_value_ref_preflight_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_explicit_decision_value_ref_preflight_checked",
            "explicit_decision_value_ref_preflight_receipt_created",
        ],
        "actions_not_taken": [
            "required_value_refs_not_bound",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-preflight/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-preflight/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "explicit_decision_value_ref_preflight_only": True,
            "required_value_refs_absent": True,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    preflights = [_require_mapping(record.get("explicit_decision_value_ref_preflight"), "explicit_decision_value_ref_preflight") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    ref_slots = [
        slot
        for preflight in preflights
        for slot in _require_sequence(preflight.get("required_value_refs"), "required_value_refs")
        if isinstance(slot, Mapping)
    ]
    return {
        "explicit_decision_value_ref_preflight_count": len(records),
        "required_value_ref_slot_count": len(ref_slots),
        "required_value_ref_absent_count": sum(1 for slot in ref_slots if slot.get("present") is False),
        "required_value_ref_present_count": sum(1 for slot in ref_slots if slot.get("present") is True),
        "required_value_ref_bound_count": sum(1 for slot in ref_slots if slot.get("bound") is True),
        "explicit_decision_value_ref_preflight_satisfied_count": sum(1 for preflight in preflights if preflight.get("explicit_decision_value_ref_preflight_satisfied") is True),
        "explicit_operator_decision_value_bound_count": sum(1 for preflight in preflights if preflight.get("explicit_operator_decision_value_bound") is True),
        "operator_decision_value_present_count": sum(1 for preflight in preflights if preflight.get("operator_decision_value_present") is True),
        "operator_value_record_creation_count": sum(1 for preflight in preflights if preflight.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for preflight in preflights if preflight.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
    }


def _assert_explicit_decision_candidate_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_allowed",
        "generic_continuation_rejection_ref_binding_allowed",
        "explicit_decision_candidate_projection_allowed",
        "explicit_decision_candidate_classes_projected",
        "actual_operator_decision_value_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision candidate effect_boundary.{field_name} must be true")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in effect_boundary and effect_boundary.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"explicit decision candidate effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_candidate_state") != "explicit_operator_decision_candidate_projected_not_admitted":
        raise PersonalAssistantInvariantError("explicit decision candidate must remain projected not admitted")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision candidate must remain blocked AwaitingEvidence")


def _assert_explicit_decision_candidate_item_boundary(source_record: Mapping[str, Any]) -> None:
    candidate = _require_mapping(source_record.get("explicit_decision_candidate"), "explicit_decision_candidate")
    for field_name in (
        "record_contract_ready",
        "explicit_decision_candidate_classes_projected",
        "requires_actual_operator_decision_value",
        "actual_operator_decision_value_absent",
    ):
        if candidate.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision candidate.{field_name} must be true")
    if tuple(candidate.get("required_value_refs", ())) != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("explicit decision candidate required_value_refs drifted")
    for field_name, expected_value in _SOURCE_FALSE_FIELDS.items():
        if field_name in candidate and candidate.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"explicit decision candidate.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"explicit decision candidate authority_status.{field_name} must be false")


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
