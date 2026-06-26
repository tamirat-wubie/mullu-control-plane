"""Purpose: operator value-binding verifier reference intake.
Governance scope: ref-only verifier requirement intake, private-payload
redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding record evidence verification preflight runtime and contracts.
Invariants:
  - Verifier refs may be recorded as refs only.
  - Raw verifier payloads, operator values, identity payloads, signatures,
    decision receipts, connector payloads, and secrets are not collected or
    serialized.
  - Verifier refs are not validated, bound, used to verify evidence, accepted,
    admitted, dispatched, or used to grant connector, memory, deployment, or
    public-readiness authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_REF_INTAKE_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_REF_INTAKE_GENERATED_AT = (
    "2026-06-14T00:35:00+00:00"
)

_INTAKE_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_[a-z0-9][a-z0-9_:-]*$"
)
_RECORD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_record_[a-z0-9][a-z0-9_:-]*$"
)
_EVIDENCE_KINDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_VERIFICATION_REQUIREMENT_KINDS = (
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
)
_TRUE_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_allowed": True,
    "evidence_verification_preflight_ref_binding_allowed": True,
    "verifier_ref_recording_allowed": True,
    "verifier_refs_present": True,
    "verifier_ref_only": True,
    "submitted_evidence_refs_present": True,
    "verification_requirement_source_is_preflight": True,
}
_FALSE_EFFECT_BOUNDARY = {
    "raw_verifier_payload_present": False,
    "raw_evidence_payload_present": False,
    "raw_operator_value_present": False,
    "verifier_ref_validated": False,
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
    "evidence_verification_preflight_projection": "requirements_only",
    "submitted_verifier_ref_projection": "ref_only",
    "verification_evidence_projection": "absent",
    "operator_decision_value_projection": "absent",
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
        "submitted_value",
        "accepted_value",
        "verified_value",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "evidence_verification_preflight_projection",
        "submitted_verifier_ref_projection",
        "verification_evidence_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
    }
)
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_REF_INTAKE_GENERATED_AT,
    verifier_ref_intake_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_REF_INTAKE_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect verifier ref intake."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
        generated_at=generated_at,
        verifier_ref_intake_id=verifier_ref_intake_id,
        operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight: Mapping[str, Any],
    verifier_ref_intake_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_REF_INTAKE_ID,
) -> dict[str, Any]:
    """Build blocked verifier ref intake from verification preflight requirements."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(verifier_ref_intake_id, "verifier_ref_intake_id", _INTAKE_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight,
        "operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight")
    _assert_verification_preflight_boundary(source_envelope)
    source_preflight_id = _require_non_empty_text(source_envelope.get("evidence_verification_preflight_id"), "evidence_verification_preflight_id")

    source_records = source_envelope.get("verification_preflights")
    if isinstance(source_records, (str, bytes)) or not isinstance(source_records, Sequence):
        raise PersonalAssistantInvariantError("verifier ref intake requires verification_preflights sequence")
    records: list[dict[str, Any]] = []
    record_ids: list[str] = []
    submitted_verifier_refs: list[str] = []
    receipt_ids: list[str] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise PersonalAssistantInvariantError("verifier ref intake source record must be a mapping")
        _assert_verification_preflight_record_boundary(source_record)
        for requirement in _require_sequence(
            _require_mapping(source_record.get("verification_preflight"), "verification_preflight").get("verification_requirements"),
            "verification_requirements",
        ):
            if not isinstance(requirement, Mapping):
                raise PersonalAssistantInvariantError("verification requirement must be a mapping")
            record = _verifier_ref_record(source_preflight_id, source_record, requirement, timestamp=timestamp)
            if record["verifier_ref_record_id"] in record_ids:
                raise PersonalAssistantInvariantError(f"duplicate verifier_ref_record_id {record['verifier_ref_record_id']}")
            record_ids.append(record["verifier_ref_record_id"])
            submitted_verifier_refs.append(record["submitted_verifier_ref"])
            receipt_ids.append(record["receipt"]["receipt_id"])
            records.append(record)
    if not records:
        raise PersonalAssistantInvariantError("verifier ref intake requires at least one verifier ref record")

    envelope = {
        "verifier_ref_intake_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight",
        "source_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_id": source_preflight_id,
        "intake_state": "verifier_refs_recorded_not_validated_not_bound",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "verifier_ref_record_count": len(records),
        "verifier_ref_record_ids": record_ids,
        "submitted_verifier_refs": submitted_verifier_refs,
        "receipt_ids": receipt_ids,
        "verifier_ref_records": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "verifier_ref_only": True,
            "ready_for_verifier_ref_validation": False,
            "ready_for_evidence_verification": False,
            "ready_for_evidence_acceptance": False,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "evidence_verification_preflight_required",
                "verification_requirements_present",
                "verifier_refs_recorded_as_refs_only",
                "verifier_refs_not_validated",
                "verification_requirements_not_satisfied",
                "submitted_evidence_refs_not_verified",
                "no_raw_verifier_payload_storage",
                "no_value_binding_record_admission",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "verifier_refs_require_separate_governed_validation",
                "verification_requirements_not_satisfied",
                "evidence_not_verified",
                "value_binding_record_not_created",
                "execution_authority_not_granted",
            ],
            "next_action": "validate verifier refs in a separate governed verifier before any evidence verification or value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake",
            "runtime_boundary": "verifier_refs_recorded_not_validated_not_bound",
            "verifier_ref_only": True,
            **dict(_FALSE_EFFECT_BOUNDARY),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _verifier_ref_record(
    source_preflight_id: str,
    source_record: Mapping[str, Any],
    requirement: Mapping[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any]:
    source_item_id = _require_non_empty_text(source_record.get("verification_preflight_item_id"), "source_verification_preflight_item_id")
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    requirement_kind = _require_non_empty_text(requirement.get("requirement_kind"), "requirement_kind")
    if requirement_kind not in _VERIFICATION_REQUIREMENT_KINDS:
        raise PersonalAssistantInvariantError("verification requirement kind must remain governed")
    approval_id = _require_non_empty_text(source_record.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_record.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_record.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_record.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_record.get("risk_level"), "risk_level")
    submitted_evidence_ref = _require_non_empty_text(source_record.get("submitted_evidence_ref"), "submitted_evidence_ref")
    suffix = approval_id.removeprefix("pa_approval_")
    record_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_record_{evidence_kind}_{requirement_kind}_{suffix}",
        "verifier_ref_record_id",
        _RECORD_ID_PATTERN,
    )
    submitted_verifier_ref = (
        "verifier-ref://personal-assistant/operator-reapproval-decision-receipt-value-binding-record/"
        f"{approval_id}/{evidence_kind}/{requirement_kind}"
    )
    return {
        "verifier_ref_record_id": record_id,
        "source_verification_preflight_item_id": source_item_id,
        "evidence_kind": evidence_kind,
        "requirement_kind": requirement_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_verifier_ref": submitted_verifier_ref,
        "evidence_verification_preflight_ref": {
            "source_evidence_verification_preflight_id": source_preflight_id,
            "source_verification_preflight_item_id": source_item_id,
            "source_verification_state": "submitted_refs_scoped_not_verified",
            "source_outcome": "AwaitingEvidence",
            "source_requirement_kind": requirement_kind,
            "source_requirement_required": True,
            "source_requirement_ref_present": False,
            "source_requirement_satisfied": False,
            "source_evidence_verified": False,
            "source_authority_granted": False,
        },
        "verifier_ref": {
            "submitted_verifier_ref": submitted_verifier_ref,
            "requirement_kind": requirement_kind,
            "verifier_ref_only": True,
            "verifier_ref_present": True,
            "raw_verifier_payload_present": False,
            "verifier_ref_submitted": True,
            "verifier_ref_validated": False,
            "verifier_ref_bound": False,
            "verification_requirement_satisfied": False,
            "evidence_verified": False,
            "evidence_accepted": False,
            "evidence_rejected": False,
            "requirement_satisfied": False,
            "blocking_reason": "submitted_verifier_ref_not_validated",
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
        "receipt": _verifier_ref_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_{evidence_kind}_{requirement_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            requirement_kind=requirement_kind,
            timestamp=timestamp,
        ),
    }


def _verifier_ref_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight",
            "operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_{requirement_kind}_verifier_ref_recorded",
            "verifier_ref_intake_receipt_created",
        ],
        "actions_not_taken": [
            "raw_verifier_payload_not_collected",
            "raw_operator_decision_value_not_collected",
            "raw_submitted_evidence_payload_not_collected",
            "verifier_ref_not_validated",
            "verification_requirement_not_satisfied",
            "submitted_evidence_ref_not_verified",
            "operator_evidence_not_accepted",
            "operator_evidence_not_rejected",
            "operator_decision_value_not_bound",
            "binding_record_candidate_not_accepted",
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
            "operator_decision_value_ref_only",
            "operator_identity_ref_only",
            "operator_signature_ref_only",
            "decision_receipt_ref_only",
            "submitted_evidence_payload_not_serialized",
            "verification_payload_not_serialized",
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
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-ref-intake/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-ref-intake/{approval_id}/{evidence_kind}/{requirement_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_is_execution": False,
            "evidence_kind": evidence_kind,
            "requirement_kind": requirement_kind,
            "verifier_ref_only": True,
            "raw_verifier_payload_present": False,
            "raw_evidence_payload_present": False,
            "raw_operator_value_present": False,
            "verifier_ref_validated": False,
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
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    verifier_refs = [_require_mapping(record.get("verifier_ref"), "verifier_ref") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "verifier_ref_record_count": len(records),
        "submitted_verifier_ref_count": sum(1 for record in verifier_refs if record.get("verifier_ref_submitted") is True),
        "raw_verifier_payload_count": sum(1 for record in verifier_refs if record.get("raw_verifier_payload_present") is True),
        "validated_verifier_ref_count": sum(1 for record in verifier_refs if record.get("verifier_ref_validated") is True),
        "bound_verifier_ref_count": sum(1 for record in verifier_refs if record.get("verifier_ref_bound") is True),
        "satisfied_verification_requirement_count": sum(1 for record in verifier_refs if record.get("verification_requirement_satisfied") is True),
        "verified_evidence_count": sum(1 for record in verifier_refs if record.get("evidence_verified") is True),
        "accepted_evidence_count": sum(1 for record in verifier_refs if record.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for record in verifier_refs if record.get("evidence_rejected") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_verification_preflight_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_allowed",
        "evidence_acceptance_preflight_ref_binding_allowed",
        "submitted_evidence_ref_scope_check_allowed",
        "verification_requirement_planning_allowed",
        "evidence_verification_preflight_decision_allowed",
        "submitted_evidence_refs_present",
        "evidence_submitted",
        "evidence_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"evidence verification preflight effect_boundary.{field_name} must be true")
    for field_name in (
        "raw_evidence_payload_present",
        "raw_operator_value_present",
        "verifier_identity_bound",
        "verification_method_bound",
        "evidence_integrity_hash_bound",
        "source_ref_reachability_witness_bound",
        "decision_receipt_crosscheck_bound",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "operator_value_bound",
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
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence verification preflight effect_boundary.{field_name} must be false")
    if source_envelope.get("verification_state") != "submitted_refs_scoped_not_verified":
        raise PersonalAssistantInvariantError("evidence verification preflight must remain submitted_refs_scoped_not_verified")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("evidence verification preflight must remain blocked AwaitingEvidence")


def _assert_verification_preflight_record_boundary(source_record: Mapping[str, Any]) -> None:
    evidence_kind = _require_non_empty_text(source_record.get("evidence_kind"), "evidence_kind")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise PersonalAssistantInvariantError("evidence verification preflight record kind must remain governed")
    verification_preflight = _require_mapping(source_record.get("verification_preflight"), "verification_preflight")
    requirements = _require_sequence(verification_preflight.get("verification_requirements"), "verification_requirements")
    if len(requirements) != len(_VERIFICATION_REQUIREMENT_KINDS):
        raise PersonalAssistantInvariantError("verification_preflight.verification_requirements must cover all governed requirement kinds")
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise PersonalAssistantInvariantError("verification requirement must be a mapping")
        if requirement.get("requirement_kind") not in _VERIFICATION_REQUIREMENT_KINDS:
            raise PersonalAssistantInvariantError("verification requirement kind must remain governed")
        for field_name, expected_value in {"required": True, "ref_present": False, "satisfied": False}.items():
            if requirement.get(field_name) is not expected_value:
                raise PersonalAssistantInvariantError(f"verification requirement {field_name} must be {expected_value}")
    for field_name in (
        "raw_evidence_payload_present",
        "raw_operator_value_present",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "requirement_satisfied",
    ):
        if verification_preflight.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"verification_preflight.{field_name} must be false")
    authority_status = _require_mapping(source_record.get("authority_status"), "authority_status")
    for field_name in (
        "verifier_identity_bound",
        "verification_method_bound",
        "evidence_integrity_hash_bound",
        "source_ref_reachability_witness_bound",
        "decision_receipt_crosscheck_bound",
        "operator_value_bound",
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
            raise PersonalAssistantInvariantError(f"evidence verification preflight authority_status.{field_name} must be false")


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
