"""Purpose: verifier execution explicit decision value-ref verification preflight.
Governance scope: no-effect preflight over submitted explicit decision ref
identifiers, without accepting, binding, storing, admitting, or executing any
value.
Dependencies: personal-assistant explicit decision value-ref submitted-ref
intake runtime and contracts.
Invariants:
  - Submitted refs are preflight-checked as identifiers only.
  - Verification preflight is not ref acceptance, value binding, value storage,
    verifier execution, or authority.
  - No connector payload, operator value, identity payload, signature payload,
    decision receipt payload, verifier payload, or secret is serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_PREFLIGHT_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_PREFLIGHT_GENERATED_AT = (
    "2026-06-14T02:15:00+00:00"
)

_PREFLIGHT_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_[a-z0-9][a-z0-9_:-]*$"
)
_VERIFICATION_RECORD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_record_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_verification_preflight_satisfied": False,
    "explicit_decision_value_ref_submitted_ref_intake_satisfied": False,
    "explicit_decision_value_refs_verified": False,
    "explicit_decision_value_refs_accepted": False,
    "explicit_decision_value_refs_bound": False,
    "explicit_decision_value_refs_validated": False,
    "explicit_decision_value_refs_stored": False,
    "explicit_operator_decision_value_bound": False,
    "operator_value_record_created": False,
    "operator_value_record_admitted": False,
    "operator_decision_value_stored": False,
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
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
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_allowed": True,
    "explicit_decision_value_ref_submitted_ref_intake_ref_binding_allowed": True,
    "explicit_decision_value_ref_verification_preflight_projection_allowed": True,
    "required_value_refs_declared": True,
    "required_value_refs_submitted": True,
    "submitted_ref_only": True,
    "verification_preflight_checked": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "explicit_decision_value_ref_submitted_ref_projection": "ref_identifier_only",
    "explicit_decision_value_ref_verification_projection": "preflight_status_only",
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
    "submitted_ref_payload",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_PREFLIGHT_GENERATED_AT,
    explicit_decision_value_ref_verification_preflight_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_PREFLIGHT_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision value-ref verification preflight."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_verification_preflight_id=explicit_decision_value_ref_verification_preflight_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake: Mapping[str, Any],
    explicit_decision_value_ref_verification_preflight_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_PREFLIGHT_ID,
) -> dict[str, Any]:
    """Build blocked verification preflight from submitted explicit decision refs."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    preflight_id = _require_pattern(explicit_decision_value_ref_verification_preflight_id, "explicit_decision_value_ref_verification_preflight_id", _PREFLIGHT_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake")
    _assert_submitted_ref_intake_boundary(source_envelope)

    source_intake_id = _require_non_empty_text(source_envelope.get("explicit_decision_value_ref_submitted_ref_intake_id"), "explicit_decision_value_ref_submitted_ref_intake_id")
    source_records = _require_sequence(source_envelope.get("submitted_ref_records"), "submitted_ref_records")
    verification_records = [_verification_record(source_intake_id, ref_name, source_records) for ref_name in _REQUIRED_VALUE_REFS]
    receipt = _preflight_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_verification_preflight_id": preflight_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake",
        "source_explicit_decision_value_ref_submitted_ref_intake_id": source_intake_id,
        "explicit_decision_value_ref_verification_preflight_state": "submitted_refs_checked_not_verified",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "verification_record_count": len(verification_records),
        "verification_record_ids": [record["verification_record_id"] for record in verification_records],
        "source_submitted_ref_record_ids": [record["source_submitted_ref_record_id"] for record in verification_records],
        "submitted_ref_uris": [record["submitted_ref_uri"] for record in verification_records],
        "verification_records": verification_records,
        "receipt": receipt,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(verification_records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "verification_preflight_only": True,
            "required_value_refs_submitted": True,
            "submitted_ref_only": True,
            "verification_preflight_checked": True,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            "explicit_decision_value_refs_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "submitted_refs_not_verified",
                "submitted_refs_not_accepted",
                "submitted_refs_not_bound",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "verify submitted refs with governed evidence before acceptance",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight",
            "runtime_boundary": "submitted_refs_checked_not_verified",
            "verification_preflight_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _verification_record(source_intake_id: str, ref_name: str, source_records: Sequence[Any]) -> dict[str, Any]:
    matching_records = [record for record in source_records if isinstance(record, Mapping) and record.get("ref_name") == ref_name]
    if len(matching_records) != 1:
        raise PersonalAssistantInvariantError(f"{ref_name} must have exactly one submitted ref before verification preflight")
    source_record = matching_records[0]
    _assert_submitted_ref_record_open(source_record, ref_name)
    record_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_record_{ref_name}",
        "verification_record_id",
        _VERIFICATION_RECORD_ID_PATTERN,
    )
    return {
        "verification_record_id": record_id,
        "ref_name": ref_name,
        "source_submitted_ref_record_id": _require_non_empty_text(source_record.get("submitted_ref_record_id"), "submitted_ref_record_id"),
        "source_explicit_decision_value_ref_submitted_ref_intake_id": source_intake_id,
        "submitted_ref_uri": _require_non_empty_text(source_record.get("submitted_ref_uri"), "submitted_ref_uri"),
        "verification_status": "preflight_checked_not_verified",
        "verification_preflight_checked": True,
        "submitted_ref_observed": True,
        "submitted_ref_only": True,
        "raw_ref_payload_present": False,
        "raw_operator_value_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
        "blocking_reason": f"{ref_name}_not_verified",
    }


def _preflight_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight",
        "skill_id": "operator.reapproval.explicit_decision_ref_verification_preflight",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake",
            "explicit_decision_value_ref_verification_preflight_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_verification_preflight_created",
            "submitted_ref_identifiers_preflight_checked",
        ],
        "actions_not_taken": [
            "raw_operator_values_not_collected",
            "submitted_refs_not_verified",
            "submitted_refs_not_accepted",
            "submitted_refs_not_bound",
            "operator_decision_value_not_stored",
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
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-preflight/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-preflight/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight_is_execution": False,
            "verification_preflight_only": True,
            "submitted_ref_only": True,
            "verification_preflight_checked": True,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(verification_records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "verification_record_count": len(verification_records),
        "verification_preflight_checked_count": sum(1 for record in verification_records if record.get("verification_preflight_checked") is True),
        "submitted_ref_observed_count": sum(1 for record in verification_records if record.get("submitted_ref_observed") is True),
        "submitted_ref_only_count": sum(1 for record in verification_records if record.get("submitted_ref_only") is True),
        "verified_ref_count": sum(1 for record in verification_records if record.get("verified") is True),
        "accepted_ref_count": sum(1 for record in verification_records if record.get("accepted") is True),
        "bound_ref_count": sum(1 for record in verification_records if record.get("bound") is True),
        "validated_ref_count": sum(1 for record in verification_records if record.get("validated") is True),
        "stored_ref_count": sum(1 for record in verification_records if record.get("stored") is True),
        "raw_ref_payload_count": sum(1 for record in verification_records if record.get("raw_ref_payload_present") is True),
        "raw_operator_value_count": sum(1 for record in verification_records if record.get("raw_operator_value_present") is True),
        "operator_value_record_creation_count": sum(1 for record in verification_records if record.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for record in verification_records if record.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for record in verification_records if record.get("authority_granted") is True),
    }


def _assert_submitted_ref_intake_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_allowed",
        "explicit_decision_value_ref_request_ref_binding_allowed",
        "explicit_decision_value_ref_submitted_ref_recording_allowed",
        "required_value_refs_declared",
        "required_value_refs_requested",
        "required_value_refs_submitted",
        "submitted_ref_only",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref submitted-ref intake effect_boundary.{field_name} must be true")
    for field_name in (
        "explicit_decision_value_ref_submitted_ref_intake_satisfied",
        "explicit_decision_value_refs_accepted",
        "explicit_decision_value_refs_bound",
        "explicit_decision_value_refs_validated",
        "explicit_decision_value_refs_stored",
        "operator_value_record_created",
        "operator_decision_value_present",
        "operator_decision_value_collected",
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
            raise PersonalAssistantInvariantError(f"explicit decision value-ref submitted-ref intake effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_value_ref_submitted_ref_intake_state") != "submitted_refs_recorded_not_accepted":
        raise PersonalAssistantInvariantError("explicit decision value-ref submitted-ref intake must remain recorded not accepted")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref submitted-ref intake must remain blocked AwaitingEvidence")

    source_records = _require_sequence(source_envelope.get("submitted_ref_records"), "submitted_ref_records")
    record_names = tuple(record.get("ref_name") for record in source_records if isinstance(record, Mapping))
    if record_names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("explicit decision value-ref submitted-ref intake must expose canonical required refs")
    for record in source_records:
        if not isinstance(record, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref submitted-ref record must be a mapping")
        _assert_submitted_ref_record_open(record, _require_non_empty_text(record.get("ref_name"), "ref_name"))


def _assert_submitted_ref_record_open(record: Mapping[str, Any], ref_name: str) -> None:
    expected = {
        "submitted_ref_status": "submitted_not_accepted",
        "submitted_ref_recorded": True,
        "submitted_ref_only": True,
        "raw_ref_payload_present": False,
        "raw_operator_value_present": False,
        "present": True,
        "collected": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if record.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} submitted_ref.{field_name} must be {str(expected_value).lower()}")


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
