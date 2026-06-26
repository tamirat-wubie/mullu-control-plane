"""Purpose: no-effect worker and replay preflight envelopes for personal assistant.
Governance scope: execution-worker prerequisites, replay prerequisites, receipt
alignment, private-payload redaction, and no-dispatch authority boundaries.
Dependencies: personal-assistant execution gate runtime and contracts.
Invariants:
  - Worker/replay preflight does not bind an execution worker.
  - Replay plans are required but not recorded or executed by this module.
  - Live connector execution, external sends, connector mutation, memory writes,
    system-of-record writes, deployment mutation, and readiness claims remain
    false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .execution_gate import build_default_personal_assistant_execution_gate


DEFAULT_WORKER_REPLAY_PREFLIGHT_SET_ID = "pa_worker_replay_preflight_foundation_001"
DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT = "2026-06-14T00:05:00+00:00"

_PREFLIGHT_SET_ID_PATTERN = re.compile(r"^pa_worker_replay_preflight_[a-z0-9][a-z0-9_:-]*$")
_PREFLIGHT_ID_PATTERN = re.compile(r"^pa_worker_replay_preflight_item_[a-z0-9][a-z0-9_:-]*$")
_FALSE_EFFECT_BOUNDARY = {
    "worker_replay_preflight_allowed": True,
    "worker_binding_allowed": False,
    "replay_execution_allowed": False,
    "execution_allowed": False,
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
    "gate_payload_projection": "gate_ref_only",
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
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "gate_payload_projection",
        "payload_digest_only",
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


def build_default_personal_assistant_worker_replay_preflight(
    *,
    generated_at: str = DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT,
    preflight_set_id: str = DEFAULT_WORKER_REPLAY_PREFLIGHT_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect worker/replay preflight evidence."""
    return build_personal_assistant_worker_replay_preflight_envelope(
        generated_at=generated_at,
        preflight_set_id=preflight_set_id,
        execution_gate_evidence=build_default_personal_assistant_execution_gate(),
    )


def build_personal_assistant_worker_replay_preflight_envelope(
    *,
    generated_at: str,
    execution_gate_evidence: Mapping[str, Any],
    preflight_set_id: str = DEFAULT_WORKER_REPLAY_PREFLIGHT_SET_ID,
) -> dict[str, Any]:
    """Build no-effect worker/replay preflight from execution gate evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(preflight_set_id, "preflight_set_id", _PREFLIGHT_SET_ID_PATTERN)
    gate_evidence = _require_mapping(execution_gate_evidence, "execution_gate_evidence")
    _scan_private_or_secret_payload(gate_evidence, path="execution_gate_evidence")
    _assert_execution_gate_boundary(gate_evidence)
    source_gate_set_id = _require_non_empty_text(gate_evidence.get("gate_set_id"), "gate_set_id")

    preflights: list[dict[str, Any]] = []
    preflight_ids: list[str] = []
    gate_ids: list[str] = []
    receipt_ids: list[str] = []
    gates = gate_evidence.get("gates")
    if isinstance(gates, (str, bytes)) or not isinstance(gates, Sequence):
        raise PersonalAssistantInvariantError("execution_gate_evidence.gates must be a sequence")
    for gate in gates:
        if not isinstance(gate, Mapping):
            raise PersonalAssistantInvariantError("execution gate item must be a mapping")
        preflight = _preflight_item(source_gate_set_id, gate, timestamp=timestamp)
        if preflight["preflight_id"] in preflight_ids:
            raise PersonalAssistantInvariantError(f"duplicate preflight_id {preflight['preflight_id']}")
        preflight_ids.append(preflight["preflight_id"])
        gate_ids.append(preflight["gate_id"])
        receipt_ids.append(preflight["receipt"]["receipt_id"])
        preflights.append(preflight)
    if not preflights:
        raise PersonalAssistantInvariantError("worker/replay preflight requires at least one execution gate")

    envelope = {
        "preflight_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "execution_gate_evidence",
        "source_gate_set_id": source_gate_set_id,
        "preflight_count": len(preflights),
        "preflight_ids": preflight_ids,
        "gate_ids": gate_ids,
        "receipt_ids": receipt_ids,
        "preflights": preflights,
        "effect_boundary": dict(_FALSE_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_worker_replay_preflight_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "execution_gate_required",
                "worker_binding_not_allowed",
                "execution_worker_unbound",
                "live_connector_witness_absent",
                "dispatch_lease_absent",
                "replay_plan_required",
                "replay_plan_not_validated",
                "rollback_plan_required",
                "idempotency_key_absent",
                "no_external_send",
                "no_connector_mutation",
            ],
            "blocking_reasons": [],
            "next_action": "record replay and rollback plans, bind live connector witness, bind dispatch lease, then request operator reapproval",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "worker_replay_preflight_evidence_only",
            "runtime_boundary": "preflight_does_not_bind_worker_or_execute_replay",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _preflight_item(source_gate_set_id: str, gate: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    gate_id = _require_non_empty_text(gate.get("gate_id"), "gate_id")
    approval_id = _require_non_empty_text(gate.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(gate.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(gate.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(gate.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(gate.get("risk_level"), "risk_level")
    gate_receipt = _require_mapping(gate.get("receipt"), "gate.receipt")
    dispatch_preconditions = _require_mapping(gate.get("dispatch_preconditions"), "gate.dispatch_preconditions")
    if gate_receipt.get("decision") != "deferred":
        raise PersonalAssistantInvariantError(f"{gate_id}: gate receipt must be deferred")
    if dispatch_preconditions.get("execution_allowed") is not False:
        raise PersonalAssistantInvariantError(f"{gate_id}: execution gate must not allow execution")
    if dispatch_preconditions.get("execution_worker_bound") is not False:
        raise PersonalAssistantInvariantError(f"{gate_id}: execution worker must remain unbound")
    suffix = approval_id.removeprefix("pa_approval_")
    preflight_id = _require_pattern(
        f"pa_worker_replay_preflight_item_{suffix}",
        "preflight_id",
        _PREFLIGHT_ID_PATTERN,
    )
    return {
        "preflight_id": preflight_id,
        "gate_id": gate_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "execution_gate_ref": {
            "source_gate_set_id": source_gate_set_id,
            "gate_receipt_id": str(gate_receipt.get("receipt_id", "")),
            "gate_receipt_state": "deferred",
            "execution_gate_evaluated": True,
            "execution_allowed": False,
            "payload_digest_only": True,
        },
        "worker_preflight": {
            "worker_family": "personal_assistant_execution_worker",
            "worker_binding_state": "unbound",
            "worker_binding_allowed": False,
            "execution_worker_bound": False,
            "live_connector_witness_required": True,
            "live_connector_witness_present": False,
            "dispatch_lease_required": True,
            "dispatch_lease_present": False,
            "operator_reapproval_required": True,
        },
        "replay_preflight": {
            "replay_plan_required": True,
            "replay_plan_state": "required_not_recorded",
            "replay_plan_validated": False,
            "rollback_plan_required": True,
            "rollback_plan_validated": False,
            "idempotency_key_required": True,
            "idempotency_key_present": False,
            "replay_execution_allowed": False,
        },
        "receipt": _preflight_receipt(
            receipt_id=f"pa_receipt_worker_replay_preflight_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _preflight_receipt(
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
        "inputs_used": ["execution_gate_evidence", "worker_replay_preflight_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": ["worker_replay_preflight_evaluated", "missing_dispatch_witnesses_recorded", "receipt_created"],
        "actions_not_taken": [
            "execution_worker_not_bound",
            "replay_not_executed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": ["gate_refs_only", "private_connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/worker-replay-preflight/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/worker-replay-preflight/{approval_id}"],
        "outcome": "SolvedVerified",
        "metadata": {
            "foundation_only": True,
            "worker_replay_preflight_is_execution": False,
            "worker_binding_allowed": False,
            "replay_execution_allowed": False,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _assert_execution_gate_boundary(gate_evidence: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(gate_evidence.get("effect_boundary"), "effect_boundary")
    if effect_boundary.get("execution_gate_evaluation_allowed") is not True:
        raise PersonalAssistantInvariantError("execution gate evaluation must be allowed")
    for field_name in (
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"execution gate effect_boundary.{field_name} must be false")


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
