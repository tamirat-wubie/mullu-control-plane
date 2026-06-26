"""Purpose: operator reapproval gate envelopes for personal assistant.
Governance scope: reapproval request refs, wait-state evidence, connector lease
refs, receipt alignment, private-payload redaction, and no-dispatch boundaries.
Dependencies: personal-assistant connector/lease witness runtime and contracts.
Invariants:
  - Operator reapproval gates record request and wait-state refs only.
  - Fresh operator decisions are required but not claimed by this module.
  - Live connector execution, execution-worker admission, dispatch, external
    sends, connector mutation, memory writes, system-of-record writes,
    deployment mutation, and readiness claims remain false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .connector_lease_witness import build_default_personal_assistant_connector_lease_witness
from .contracts import PersonalAssistantInvariantError


DEFAULT_OPERATOR_REAPPROVAL_GATE_SET_ID = "pa_operator_reapproval_gate_foundation_001"
DEFAULT_OPERATOR_REAPPROVAL_GATE_GENERATED_AT = "2026-06-14T00:08:00+00:00"

_GATE_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_gate_[a-z0-9][a-z0-9_:-]*$")
_GATE_ID_PATTERN = re.compile(r"^pa_operator_reapproval_gate_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_EFFECT_BOUNDARY = {
    "operator_reapproval_gate_allowed": True,
    "operator_reapproval_request_packet_allowed": True,
    "connector_lease_witness_ref_binding_allowed": True,
    "fresh_operator_decision_required": True,
    "operator_reapproval_present": False,
    "fresh_operator_decision_present": False,
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
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "connector_payload_projection": "ref_only",
    "lease_payload_projection": "digest_only",
    "approval_payload_projection": "ref_only",
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
        "raw_connector_witness",
        "raw_lease_payload",
        "raw_reapproval_payload",
        "raw_operator_decision",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "lease_payload_projection",
        "approval_payload_projection",
        "connector_ref_digest",
        "dispatch_lease_digest",
        "reapproval_request_digest",
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


def build_default_personal_assistant_operator_reapproval_gate(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_GATE_GENERATED_AT,
    gate_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_GATE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic operator reapproval gate evidence."""
    return build_personal_assistant_operator_reapproval_gate_envelope(
        generated_at=generated_at,
        gate_set_id=gate_set_id,
        connector_lease_witness=build_default_personal_assistant_connector_lease_witness(),
    )


def build_personal_assistant_operator_reapproval_gate_envelope(
    *,
    generated_at: str,
    connector_lease_witness: Mapping[str, Any],
    gate_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_GATE_SET_ID,
) -> dict[str, Any]:
    """Build no-effect operator reapproval gates from connector lease evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(gate_set_id, "gate_set_id", _GATE_SET_ID_PATTERN)
    source_envelope = _require_mapping(connector_lease_witness, "connector_lease_witness")
    _scan_private_or_secret_payload(source_envelope, path="connector_lease_witness")
    _assert_connector_lease_boundary(source_envelope)
    source_witness_set_id = _require_non_empty_text(source_envelope.get("witness_set_id"), "witness_set_id")

    gates: list[dict[str, Any]] = []
    gate_ids: list[str] = []
    source_witness_ids: list[str] = []
    receipt_ids: list[str] = []
    source_witnesses = source_envelope.get("witnesses")
    if isinstance(source_witnesses, (str, bytes)) or not isinstance(source_witnesses, Sequence):
        raise PersonalAssistantInvariantError("connector_lease_witness.witnesses must be a sequence")
    for source_witness in source_witnesses:
        if not isinstance(source_witness, Mapping):
            raise PersonalAssistantInvariantError("connector/lease witness item must be a mapping")
        gate = _gate_item(source_witness_set_id, source_witness, timestamp=timestamp)
        if gate["gate_id"] in gate_ids:
            raise PersonalAssistantInvariantError(f"duplicate gate_id {gate['gate_id']}")
        gate_ids.append(gate["gate_id"])
        source_witness_ids.append(gate["source_witness_id"])
        receipt_ids.append(gate["receipt"]["receipt_id"])
        gates.append(gate)
    if not gates:
        raise PersonalAssistantInvariantError("operator reapproval gate requires at least one connector/lease witness")

    envelope = {
        "gate_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "connector_lease_witness",
        "source_connector_lease_witness_set_id": source_witness_set_id,
        "gate_count": len(gates),
        "gate_ids": gate_ids,
        "source_witness_ids": source_witness_ids,
        "receipt_ids": receipt_ids,
        "gates": gates,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_gate_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "connector_lease_witness_required",
                "connector_witness_ref_bound",
                "dispatch_lease_ref_bound",
                "dispatch_lease_still_inactive",
                "operator_reapproval_request_packet_prepared",
                "fresh_operator_decision_still_absent",
                "wait_state_recorded",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "fresh_operator_decision_absent",
                "operator_identity_ref_absent",
                "operator_reapproval_receipt_absent",
                "dispatch_lease_inactive",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect a fresh operator reapproval decision receipt, then evaluate execution-worker admission without bypassing connector and dispatch evidence gates",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_gate_evidence_only",
            "runtime_boundary": "gate_records_reapproval_request_and_wait_state_without_execution_worker_admission",
            "operator_reapproval_present": False,
            "fresh_operator_decision_present": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _gate_item(source_witness_set_id: str, source_witness: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_witness_id = _require_non_empty_text(source_witness.get("witness_id"), "source_witness_id")
    approval_id = _require_non_empty_text(source_witness.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_witness.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_witness.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_witness.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_witness.get("risk_level"), "risk_level")
    source_receipt = _require_mapping(source_witness.get("receipt"), "source_witness.receipt")
    connector_witness = _require_mapping(source_witness.get("connector_witness"), "source_witness.connector_witness")
    dispatch_lease_witness = _require_mapping(
        source_witness.get("dispatch_lease_witness"),
        "source_witness.dispatch_lease_witness",
    )
    operator_reapproval_gate = _require_mapping(
        source_witness.get("operator_reapproval_gate"),
        "source_witness.operator_reapproval_gate",
    )
    _assert_connector_lease_item_boundary(
        source_witness_id,
        source_receipt,
        connector_witness,
        dispatch_lease_witness,
        operator_reapproval_gate,
    )
    suffix = approval_id.removeprefix("pa_approval_")
    gate_id = _require_pattern(f"pa_operator_reapproval_gate_item_{suffix}", "gate_id", _GATE_ID_PATTERN)
    reapproval_request_digest = _digest_for("operator-reapproval", approval_id, request_id, plan_id, skill_id)
    return {
        "gate_id": gate_id,
        "source_witness_id": source_witness_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "connector_lease_witness_ref": {
            "source_witness_set_id": source_witness_set_id,
            "source_receipt_id": str(source_receipt.get("receipt_id", "")),
            "source_receipt_state": "deferred",
            "connector_witness_ref_bound": True,
            "dispatch_lease_ref_bound": True,
            "dispatch_lease_active": False,
            "operator_reapproval_required": True,
            "operator_reapproval_present": False,
            "live_connector_receipt_present": False,
            "execution_worker_admission_allowed": False,
        },
        "reapproval_request": {
            "reapproval_request_ref": f"approval://personal-assistant/reapproval-request/{approval_id}",
            "reapproval_request_digest": reapproval_request_digest,
            "reapproval_reason": "required_after_connector_lease_binding",
            "fresh_operator_decision_required": True,
            "fresh_operator_decision_present": False,
            "operator_identity_ref_required": True,
            "operator_identity_ref_present": False,
            "operator_reapproval_receipt_required": True,
            "operator_reapproval_receipt_present": False,
            "approval_scope": "single_approval_projection",
            "approval_ref": approval_id,
            "request_packet_serialized": True,
            "raw_operator_decision_serialized": False,
        },
        "wait_state": {
            "wait_state_id": f"wait://personal-assistant/operator-reapproval/{approval_id}",
            "state": "awaiting_operator_reapproval",
            "timeout_policy": "suspend_without_dispatch",
            "resume_condition": "fresh_operator_reapproval_receipt_bound",
            "on_timeout": "remain_blocked",
            "dispatch_allowed_while_waiting": False,
            "execution_worker_admission_allowed_while_waiting": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_operator_reapproval",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _gate_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_gate_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _gate_receipt(
    *,
    receipt_id: str,
    request_id: str,
    skill_id: str,
    risk_level: str,
    approval_id: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level,
        "inputs_used": ["connector_lease_witness", "operator_reapproval_gate_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "connector_lease_witness_ref_recorded",
            "operator_reapproval_request_packet_prepared",
            "operator_reapproval_wait_state_recorded",
            "execution_worker_admission_blocker_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_not_collected",
            "fresh_operator_decision_not_claimed",
            "execution_worker_not_admitted",
            "dispatch_lease_not_activated",
            "dispatch_not_started",
            "live_connector_receipt_not_collected",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "connector_refs_only",
            "lease_payload_digest_only",
            "operator_decision_not_serialized",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-gate/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-gate/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_gate_is_execution": False,
            "connector_lease_witness_ref_bound": True,
            "operator_reapproval_request_packet_prepared": True,
            "operator_reapproval_wait_state_recorded": True,
            "operator_reapproval_required": True,
            "execution_allowed_after_reapproval_only": True,
            "operator_reapproval_present": False,
            "fresh_operator_decision_present": False,
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


def _assert_connector_lease_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "connector_lease_witness_allowed",
        "connector_witness_ref_binding_allowed",
        "dispatch_lease_ref_binding_allowed",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"connector/lease witness effect_boundary.{field_name} must be true")
    for field_name in (
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "task_write_allowed",
        "memory_write_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"connector/lease witness effect_boundary.{field_name} must be false")
    assurance = _require_mapping(source_envelope.get("assurance"), "assurance")
    if assurance.get("ready_for_live_execution") is not False:
        raise PersonalAssistantInvariantError("connector/lease witness must not be ready for live execution")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        raise PersonalAssistantInvariantError("connector/lease witness must not be ready for customer readiness")


def _assert_connector_lease_item_boundary(
    source_witness_id: str,
    source_receipt: Mapping[str, Any],
    connector_witness: Mapping[str, Any],
    dispatch_lease_witness: Mapping[str, Any],
    operator_reapproval_gate: Mapping[str, Any],
) -> None:
    if source_receipt.get("decision") != "deferred":
        raise PersonalAssistantInvariantError(f"{source_witness_id}: connector/lease receipt must be deferred")
    if connector_witness.get("live_connector_witness_ref_bound") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: connector witness ref must be bound")
    for field_name in ("live_connector_receipt_present", "live_connector_execution_allowed", "connector_mutation_allowed"):
        if connector_witness.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_witness_id}: connector_witness.{field_name} must be false")
    if dispatch_lease_witness.get("dispatch_lease_ref_bound") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: dispatch lease ref must be bound")
    if dispatch_lease_witness.get("dispatch_lease_state") != "candidate_inactive":
        raise PersonalAssistantInvariantError(f"{source_witness_id}: dispatch lease must remain candidate_inactive")
    for field_name in ("dispatch_lease_active", "dispatch_allowed", "execution_worker_admission_allowed"):
        if dispatch_lease_witness.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_witness_id}: dispatch_lease_witness.{field_name} must be false")
    if operator_reapproval_gate.get("operator_reapproval_required") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: operator reapproval must remain required")
    if operator_reapproval_gate.get("execution_allowed_after_reapproval_only") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: execution must require reapproval")
    for field_name in ("operator_reapproval_present", "execution_worker_admission_allowed"):
        if operator_reapproval_gate.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_witness_id}: operator_reapproval_gate.{field_name} must be false")


def _digest_for(kind: str, approval_id: str, request_id: str, plan_id: str, skill_id: str) -> str:
    material = f"personal-assistant:{kind}:{approval_id}:{request_id}:{plan_id}:{skill_id}".encode("utf-8")
    digest = f"sha256:{hashlib.sha256(material).hexdigest()}"
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise PersonalAssistantInvariantError(f"{kind} digest has invalid shape")
    return digest


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return dict(value)


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
    elif isinstance(payload, str):
        if any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
            raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")
