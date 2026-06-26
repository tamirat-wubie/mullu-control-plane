"""Purpose: operator value-binding verifier execution approval request.
Governance scope: no-effect request for explicit operator approval before any
verifier execution, with private-payload redaction and authority denial.
Dependencies: personal-assistant verifier execution preflight runtime and
contracts.
Invariants:
  - Verifier execution approval may be requested, but no decision is collected.
  - The verifier is not executed and verifier refs are not validated or bound.
  - Evidence is not verified, accepted, rejected, value-bound, dispatched, or
    used to grant connector, memory, deployment, or public-readiness authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_GENERATED_AT = (
    "2026-06-14T00:50:00+00:00"
)

_REQUEST_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_[a-z0-9][a-z0-9_:-]*$"
)
_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_item_[a-z0-9][a-z0-9_:-]*$"
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
_TRUE_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_allowed": True,
    "verifier_execution_preflight_ref_binding_allowed": True,
    "operator_approval_request_preparation_allowed": True,
    "verifier_execution_requests_present": True,
    "verifier_refs_present": True,
    "verifier_ref_only": True,
}
_FALSE_EFFECT_BOUNDARY = {
    "raw_verifier_payload_present": False,
    "raw_evidence_payload_present": False,
    "raw_operator_value_present": False,
    "operator_approval_decision_present": False,
    "operator_approval_value_present": False,
    "operator_approval_granted": False,
    "operator_approval_rejected": False,
    "verifier_execution_allowed": False,
    "verifier_execution_started": False,
    "verifier_execution_completed": False,
    "verifier_result_present": False,
    "verifier_ref_validated": False,
    "verifier_ref_bound": False,
    "verifier_identity_bound": False,
    "verification_method_bound": False,
    "evidence_integrity_hash_bound": False,
    "source_ref_reachability_witness_bound": False,
    "decision_receipt_crosscheck_bound": False,
    "verification_requirement_satisfied": False,
    "evidence_verified": False,
    "evidence_accepted": False,
    "evidence_rejected": False,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "operator_value_bound": False,
    "operator_identity_ref_bound": False,
    "operator_signature_ref_bound": False,
    "decision_receipt_ref_bound": False,
    "accepted_value_present": False,
    "binding_record_candidate_accepted": False,
    "binding_record_created": False,
    "binding_record_admitted": False,
    "admission_approved": False,
    "authority_granted": False,
    "execution_worker_admission_allowed": False,
    "dispatch_allowed": False,
    "dispatch_lease_active": False,
    "live_connector_receipt_present": False,
    "live_connector_execution_allowed": False,
    "external_send_allowed": False,
    "calendar_write_allowed": False,
    "task_write_allowed": False,
    "memory_write_allowed": False,
    "connector_mutation_allowed": False,
    "system_of_record_write_allowed": False,
    "deployment_mutation_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_EFFECT_BOUNDARY = {**_TRUE_EFFECT_BOUNDARY, **_FALSE_EFFECT_BOUNDARY}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "verifier_execution_preflight_projection": "ref_only",
    "approval_request_projection": "request_metadata_only",
    "operator_decision_value_projection": "absent",
    "submitted_verifier_ref_projection": "ref_only",
    "verifier_execution_payload_projection": "absent",
    "verification_evidence_projection": "absent",
    "operator_identity_ref_projection": "absent",
    "operator_signature_ref_projection": "absent",
    "decision_receipt_projection": "absent",
}
_RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
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
        "raw_calendar_event",
        "raw_task_payload",
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
        "submitted_evidence_payload",
        "raw_submitted_evidence",
        "raw_verifier_payload",
        "verifier_payload",
        "verifier_execution_payload",
        "verifier_result",
        "submitted_value",
        "accepted_value",
        "verified_value",
    }
)
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_GENERATED_AT,
    verifier_execution_approval_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect verifier execution approval request."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
        generated_at=generated_at,
        verifier_execution_approval_request_id=verifier_execution_approval_request_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight: Mapping[str, Any],
    verifier_execution_approval_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_ID,
) -> dict[str, Any]:
    """Build blocked verifier execution approval request from execution preflight."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(verifier_execution_approval_request_id, "verifier_execution_approval_request_id", _REQUEST_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight")
    _assert_verifier_execution_preflight_boundary(source_envelope)
    source_preflight_id = _require_non_empty_text(source_envelope.get("verifier_execution_preflight_id"), "verifier_execution_preflight_id")
    source_records = _require_sequence(source_envelope.get("verifier_execution_preflights"), "verifier_execution_preflights")

    records: list[dict[str, Any]] = []
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("verifier execution approval request source record must be a mapping")
        _assert_verifier_execution_preflight_record_boundary(source_record)
        record = _approval_request_item(source_preflight_id, source_record, timestamp=timestamp)
        if record["verifier_execution_approval_request_item_id"] in item_ids:
            raise PersonalAssistantInvariantError(
                f"duplicate verifier_execution_approval_request_item_id {record['verifier_execution_approval_request_item_id']}"
            )
        item_ids.append(record["verifier_execution_approval_request_item_id"])
        receipt_ids.append(record["receipt"]["receipt_id"])
        records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("verifier execution approval request requires at least one verifier execution preflight")

    envelope = {
        "verifier_execution_approval_request_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight",
        "source_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_id": source_preflight_id,
        "approval_request_state": "approval_requested_not_decided_not_run",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "verifier_execution_approval_request_count": len(records),
        "verifier_execution_approval_request_item_ids": item_ids,
        "receipt_ids": receipt_ids,
        "verifier_execution_approval_requests": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "approval_request_only": True,
            "verifier_ref_only": True,
            "ready_for_operator_decision": False,
            "ready_for_verifier_execution": False,
            "ready_for_evidence_verification": False,
            "ready_for_evidence_acceptance": False,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "verifier_execution_preflight_required",
                "approval_request_prepared",
                "operator_decision_not_collected",
                "operator_approval_not_granted",
                "verifier_execution_not_allowed",
                "verifier_execution_not_started",
                "verifier_refs_not_validated",
                "submitted_evidence_refs_not_verified",
                "no_raw_verifier_payload_storage",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_decision_not_present",
                "operator_approval_not_granted",
                "verifier_execution_not_authorized",
                "evidence_not_verified",
                "value_binding_record_not_created",
                "execution_authority_not_granted",
            ],
            "next_action": "collect a separate explicit operator decision before any verifier execution",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request",
            "runtime_boundary": "approval_requested_not_decided_not_run",
            "approval_request_only": True,
            "verifier_ref_only": True,
            **dict(_FALSE_EFFECT_BOUNDARY),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _approval_request_item(
    source_preflight_id: str,
    source_record: Mapping[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any]:
    source_record_id = _require_non_empty_text(source_record.get("verifier_execution_preflight_record_id"), "verifier_execution_preflight_record_id")
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    requirement_kind = _require_non_empty_text(source_record.get("requirement_kind"), "requirement_kind")
    if evidence_kind not in _EVIDENCE_KINDS or requirement_kind not in _VERIFICATION_REQUIREMENT_KINDS:
        raise PersonalAssistantInvariantError("verifier execution approval request source kind must remain governed")
    approval_id = _require_non_empty_text(source_record.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_record.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_record.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_record.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_record.get("risk_level"), "risk_level")
    submitted_evidence_ref = _require_non_empty_text(source_record.get("submitted_evidence_ref"), "submitted_evidence_ref")
    submitted_verifier_ref = _require_non_empty_text(source_record.get("submitted_verifier_ref"), "submitted_verifier_ref")
    suffix = approval_id.removeprefix("pa_approval_")
    item_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_item_{evidence_kind}_{requirement_kind}_{suffix}",
        "verifier_execution_approval_request_item_id",
        _ITEM_ID_PATTERN,
    )
    return {
        "verifier_execution_approval_request_item_id": item_id,
        "source_verifier_execution_preflight_record_id": source_record_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "verifier_execution_preflight_ref": {
            "source_verifier_execution_preflight_id": source_preflight_id,
            "source_verifier_execution_preflight_record_id": source_record_id,
            "source_preflight_state": "verifier_execution_requested_not_run_not_validated",
            "source_outcome": "AwaitingEvidence",
            "source_verifier_execution_request_prepared": True,
            "source_verifier_execution_allowed": False,
            "source_verifier_execution_started": False,
            "source_verifier_result_present": False,
            "source_verifier_ref_validated": False,
            "source_evidence_verified": False,
            "source_authority_granted": False,
        },
        "approval_request": {
            "approval_requested": True,
            "operator_decision_required": True,
            "operator_decision_present": False,
            "operator_approval_granted": False,
            "operator_approval_rejected": False,
            "ready_for_operator_decision": False,
            "ready_for_verifier_execution": False,
            "verifier_execution_allowed": False,
            "verifier_execution_started": False,
            "verifier_result_present": False,
            "verifier_ref_validated": False,
            "evidence_verified": False,
            "evidence_accepted": False,
            "authority_granted": False,
            "blocking_reason": "operator_decision_not_present",
        },
        "authority_status": {
            "verifier_identity_bound": False,
            "verification_method_bound": False,
            "evidence_integrity_hash_bound": False,
            "source_ref_reachability_witness_bound": False,
            "decision_receipt_crosscheck_bound": False,
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
        },
        "receipt": _approval_request_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_{evidence_kind}_{requirement_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            requirement_kind=requirement_kind,
            timestamp=timestamp,
        ),
    }


def _approval_request_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight",
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_verifier_execution_approval_request_prepared",
            "verifier_execution_approval_request_receipt_created",
        ],
        "actions_not_taken": [
            "operator_decision_not_collected",
            "operator_approval_not_granted",
            "operator_approval_not_rejected",
            "raw_verifier_payload_not_collected",
            "verifier_execution_not_allowed",
            "verifier_execution_not_started",
            "verifier_result_not_collected",
            "verifier_ref_not_validated",
            "verification_requirement_not_satisfied",
            "submitted_evidence_ref_not_verified",
            "operator_evidence_not_accepted",
            "operator_decision_value_not_bound",
            "binding_record_not_created",
            "binding_record_not_admitted",
            "execution_worker_not_admitted",
            "dispatch_not_started",
            "live_connector_receipt_not_collected",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "submitted_verifier_ref_only",
            "approval_request_metadata_only",
            "operator_decision_value_not_serialized",
            "raw_verifier_payload_not_serialized",
            "verifier_result_not_serialized",
            "submitted_evidence_payload_not_serialized",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-approval-request/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-approval-request/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "approval_request_only": True,
            "operator_decision_present": False,
            "operator_approval_granted": False,
            "verifier_execution_allowed": False,
            "verifier_execution_started": False,
            "verifier_result_present": False,
            "verifier_ref_validated": False,
            "evidence_verified": False,
            "evidence_accepted": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    requests = [_require_mapping(record.get("approval_request"), "approval_request") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "verifier_execution_approval_request_count": len(records),
        "approval_requested_count": sum(1 for record in requests if record.get("approval_requested") is True),
        "operator_decision_present_count": sum(1 for record in requests if record.get("operator_decision_present") is True),
        "operator_approval_grant_count": sum(1 for record in requests if record.get("operator_approval_granted") is True),
        "operator_approval_rejection_count": sum(1 for record in requests if record.get("operator_approval_rejected") is True),
        "verifier_execution_allowed_count": sum(1 for record in requests if record.get("verifier_execution_allowed") is True),
        "verifier_execution_started_count": sum(1 for record in requests if record.get("verifier_execution_started") is True),
        "verifier_result_count": sum(1 for record in requests if record.get("verifier_result_present") is True),
        "validated_verifier_ref_count": sum(1 for record in requests if record.get("verifier_ref_validated") is True),
        "verified_evidence_count": sum(1 for record in requests if record.get("evidence_verified") is True),
        "accepted_evidence_count": sum(1 for record in requests if record.get("evidence_accepted") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_verifier_execution_preflight_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_allowed",
        "verifier_validation_preflight_ref_binding_allowed",
        "verifier_execution_request_preparation_allowed",
        "verifier_execution_policy_check_allowed",
        "verifier_refs_present",
        "verifier_ref_only",
        "shape_scope_preflight_source_present",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"verifier execution preflight effect_boundary.{field_name} must be true")
    for field_name in (
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
        "authority_granted",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"verifier execution preflight effect_boundary.{field_name} must be false")
    if source_envelope.get("verifier_execution_preflight_state") != "verifier_execution_requested_not_run_not_validated":
        raise PersonalAssistantInvariantError("verifier execution preflight must remain requested but not run")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("verifier execution preflight must remain blocked AwaitingEvidence")


def _assert_verifier_execution_preflight_record_boundary(source_record: Mapping[str, Any]) -> None:
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    requirement_kind = _require_non_empty_text(source_record.get("requirement_kind"), "requirement_kind")
    if evidence_kind not in _EVIDENCE_KINDS or requirement_kind not in _VERIFICATION_REQUIREMENT_KINDS:
        raise PersonalAssistantInvariantError("verifier execution preflight record kind must remain governed")
    preflight = _require_mapping(source_record.get("verifier_execution_preflight"), "verifier_execution_preflight")
    for field_name in ("verifier_ref_only", "verifier_ref_present", "execution_preflight_created", "verifier_execution_request_prepared"):
        if preflight.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"verifier_execution_preflight.{field_name} must be true")
    for field_name in (
        "raw_verifier_payload_present",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
    ):
        if preflight.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"verifier_execution_preflight.{field_name} must be false")
    authority_status = _require_mapping(source_record.get("authority_status"), "authority_status")
    for field_name in (
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if authority_status.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"verifier execution preflight authority_status.{field_name} must be false")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return dict(value)


def _require_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    return value


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
        raise PersonalAssistantInvariantError(f"{field_name} has invalid governed identifier shape")
    return text


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in _ALLOWED_POLICY_FIELD_NAMES and normalized_key in _RAW_PRIVATE_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")
