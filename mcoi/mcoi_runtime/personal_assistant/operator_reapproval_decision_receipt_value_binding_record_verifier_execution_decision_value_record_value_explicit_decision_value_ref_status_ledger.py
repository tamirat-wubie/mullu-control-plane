"""Purpose: verifier execution explicit decision value-ref status ledger.
Governance scope: no-effect compact ledger over required operator decision
value refs after value-ref preflight, without collecting, storing, admitting,
or executing a value.
Dependencies: personal-assistant explicit decision value-ref preflight runtime
and contracts.
Invariants:
  - Required value refs are summarized as missing slots, not accepted values.
  - The ledger never binds operator identity, signature, decision value, or
    reapproval receipt values.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_STATUS_LEDGER_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_STATUS_LEDGER_GENERATED_AT = (
    "2026-06-14T02:00:00+00:00"
)

_LEDGER_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_[a-z0-9][a-z0-9_:-]*$"
)
_STATUS_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_status_ledger_satisfied": False,
    "explicit_decision_value_ref_preflight_satisfied": False,
    "explicit_decision_value_refs_present": False,
    "explicit_operator_decision_value_bound": False,
    "operator_value_record_created": False,
    "operator_value_record_admitted": False,
    "operator_decision_value_stored": False,
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
    "operator_decision_value_submitted": False,
    "operator_decision_value_admitted": False,
    "operator_approval_granted": False,
    "operator_approval_rejected": False,
    "ready_for_verifier_execution": False,
    "verifier_execution_allowed": False,
    "verifier_execution_started": False,
    "verifier_execution_completed": False,
    "verifier_result_present": False,
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
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_allowed": True,
    "explicit_decision_value_ref_preflight_ref_binding_allowed": True,
    "explicit_decision_value_ref_status_projection_allowed": True,
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
    "explicit_decision_value_ref_preflight_projection": "summary_only",
    "explicit_decision_value_ref_status_projection": "missing_ref_status_only",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_STATUS_LEDGER_GENERATED_AT,
    explicit_decision_value_ref_status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision value-ref status ledger."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_status_ledger_id=explicit_decision_value_ref_status_ledger_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight: Mapping[str, Any],
    explicit_decision_value_ref_status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build blocked value-ref status ledger from value-ref preflight evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    ledger_id = _require_pattern(explicit_decision_value_ref_status_ledger_id, "explicit_decision_value_ref_status_ledger_id", _LEDGER_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight")
    _assert_value_ref_preflight_boundary(source_envelope)

    source_preflight_id = _require_non_empty_text(source_envelope.get("explicit_decision_value_ref_preflight_id"), "explicit_decision_value_ref_preflight_id")
    source_records = _require_sequence(source_envelope.get("explicit_decision_value_ref_preflights"), "explicit_decision_value_ref_preflights")
    ref_statuses = [_ref_status(source_preflight_id, ref_name, source_records) for ref_name in _REQUIRED_VALUE_REFS]
    receipt = _status_ledger_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_status_ledger_id": ledger_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight",
        "source_explicit_decision_value_ref_preflight_id": source_preflight_id,
        "explicit_decision_value_ref_status_ledger_state": "required_explicit_decision_value_refs_missing_unbound",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "required_ref_status_count": len(ref_statuses),
        "required_ref_status_ids": [status["required_ref_status_id"] for status in ref_statuses],
        "required_ref_statuses": ref_statuses,
        "receipt": receipt,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(ref_statuses),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "status_ledger_only": True,
            "required_value_refs_declared": True,
            "required_value_refs_missing": True,
            "explicit_decision_value_ref_status_ledger_satisfied": False,
            "explicit_operator_decision_value_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "operator_decision_value_ref_missing",
                "operator_identity_ref_missing",
                "operator_signature_ref_missing",
                "operator_reapproval_decision_receipt_ref_missing",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "collect all required governed refs before value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
            "runtime_boundary": "required_explicit_decision_value_refs_missing_unbound",
            "status_ledger_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _ref_status(source_preflight_id: str, ref_name: str, source_records: Sequence[Any]) -> dict[str, Any]:
    observed_slots: list[Mapping[str, Any]] = []
    source_item_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref status source record must be a mapping")
        source_item_ids.append(_require_non_empty_text(source_record.get("explicit_decision_value_ref_preflight_item_id"), "explicit_decision_value_ref_preflight_item_id"))
        preflight = _require_mapping(source_record.get("explicit_decision_value_ref_preflight"), "explicit_decision_value_ref_preflight")
        for slot in _require_sequence(preflight.get("required_value_refs"), "required_value_refs"):
            if isinstance(slot, Mapping) and slot.get("ref_name") == ref_name:
                observed_slots.append(slot)
    if not observed_slots:
        raise PersonalAssistantInvariantError(f"{ref_name} must be observed in value-ref preflight source")
    status_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_{ref_name}",
        "required_ref_status_id",
        _STATUS_ID_PATTERN,
    )
    present_count = sum(1 for slot in observed_slots if slot.get("present") is True)
    bound_count = sum(1 for slot in observed_slots if slot.get("bound") is True)
    validated_count = sum(1 for slot in observed_slots if slot.get("validated") is True)
    authority_grant_count = sum(1 for slot in observed_slots if slot.get("grants_authority") is True)
    verifier_execution_grant_count = sum(1 for slot in observed_slots if slot.get("grants_verifier_execution") is True)
    return {
        "required_ref_status_id": status_id,
        "ref_name": ref_name,
        "source_explicit_decision_value_ref_preflight_id": source_preflight_id,
        "source_preflight_item_ids": source_item_ids,
        "source_preflight_item_count": len(source_records),
        "observed_slot_count": len(observed_slots),
        "required": True,
        "status": "missing_unbound",
        "missing": True,
        "present": False,
        "bound": False,
        "validated": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "present_count": present_count,
        "bound_count": bound_count,
        "validated_count": validated_count,
        "authority_grant_count": authority_grant_count,
        "verifier_execution_grant_count": verifier_execution_grant_count,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
        "blocking_reason": f"{ref_name}_missing",
    }


def _status_ledger_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
        "skill_id": "operator.reapproval.explicit_decision_ref_status",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight",
            "explicit_decision_value_ref_status_ledger_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_status_ledger_created",
            "missing_required_ref_statuses_projected",
        ],
        "actions_not_taken": [
            "required_value_refs_not_bound",
            "operator_decision_value_not_collected",
            "operator_identity_not_bound",
            "operator_signature_not_bound",
            "operator_reapproval_decision_receipt_not_bound",
            "operator_value_record_not_created",
            "verifier_execution_not_allowed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "operator_decision_value_not_serialized",
            "operator_identity_not_serialized",
            "operator_signature_not_serialized",
            "operator_reapproval_decision_receipt_not_serialized",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-status-ledger/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-status-ledger/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_is_execution": False,
            "status_ledger_only": True,
            "required_value_refs_missing": True,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(ref_statuses: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "required_ref_status_count": len(ref_statuses),
        "required_ref_missing_count": sum(1 for status in ref_statuses if status.get("missing") is True),
        "required_ref_present_count": sum(1 for status in ref_statuses if status.get("present") is True),
        "required_ref_bound_count": sum(1 for status in ref_statuses if status.get("bound") is True),
        "required_ref_validated_count": sum(1 for status in ref_statuses if status.get("validated") is True),
        "source_preflight_item_count": sum(int(status.get("source_preflight_item_count", 0)) for status in ref_statuses),
        "observed_slot_count": sum(int(status.get("observed_slot_count", 0)) for status in ref_statuses),
        "operator_value_record_creation_count": sum(1 for status in ref_statuses if status.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for status in ref_statuses if status.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for status in ref_statuses if status.get("authority_granted") is True),
    }


def _assert_value_ref_preflight_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_allowed",
        "explicit_decision_candidate_ref_binding_allowed",
        "explicit_decision_value_ref_preflight_projection_allowed",
        "required_value_refs_declared",
        "required_value_refs_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref preflight effect_boundary.{field_name} must be true")
    for field_name in (
        "explicit_decision_value_ref_preflight_satisfied",
        "explicit_decision_value_refs_present",
        "explicit_operator_decision_value_bound",
        "operator_value_record_created",
        "operator_decision_value_present",
        "verifier_execution_allowed",
        "authority_granted",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref preflight effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_value_ref_preflight_state") != "explicit_decision_value_refs_absent_not_bound":
        raise PersonalAssistantInvariantError("explicit decision value-ref preflight must remain absent not bound")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref preflight must remain blocked AwaitingEvidence")


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
