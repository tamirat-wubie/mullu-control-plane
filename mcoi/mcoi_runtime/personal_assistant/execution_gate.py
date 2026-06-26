"""Purpose: no-effect execution-gate envelopes for personal assistant.
Governance scope: approved-decision dispatch preflight, receipt alignment,
private-payload redaction, and no-execution authority boundaries.
Dependencies: personal-assistant approval decision evidence and contracts.
Invariants:
  - Execution gates evaluate future dispatch eligibility only.
  - Approved decisions are required but do not authorize execution by
    themselves.
  - Live connector execution, external sends, connector mutation, memory writes,
    system-of-record writes, deployment mutation, and readiness claims remain
    false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .approval_decision_evidence import build_default_personal_assistant_approval_decision_evidence
from .contracts import PersonalAssistantInvariantError


DEFAULT_EXECUTION_GATE_SET_ID = "pa_execution_gate_foundation_001"
DEFAULT_EXECUTION_GATE_GENERATED_AT = "2026-06-14T00:04:00+00:00"

_GATE_SET_ID_PATTERN = re.compile(r"^pa_execution_gate_[a-z0-9][a-z0-9_:-]*$")
_GATE_ID_PATTERN = re.compile(r"^pa_execution_gate_item_[a-z0-9][a-z0-9_:-]*$")
_FALSE_EFFECT_BOUNDARY = {
    "execution_gate_evaluation_allowed": True,
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
    "decision_payload_projection": "approved_decision_ref_only",
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
        "decision_payload_projection",
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


def build_default_personal_assistant_execution_gate(
    *,
    generated_at: str = DEFAULT_EXECUTION_GATE_GENERATED_AT,
    gate_set_id: str = DEFAULT_EXECUTION_GATE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect execution-gate evidence."""
    return build_personal_assistant_execution_gate_envelope(
        generated_at=generated_at,
        gate_set_id=gate_set_id,
        approval_decision_evidence=build_default_personal_assistant_approval_decision_evidence(),
    )


def build_personal_assistant_execution_gate_envelope(
    *,
    generated_at: str,
    approval_decision_evidence: Mapping[str, Any],
    gate_set_id: str = DEFAULT_EXECUTION_GATE_SET_ID,
) -> dict[str, Any]:
    """Build a future-dispatch gate envelope from approved decision evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(gate_set_id, "gate_set_id", _GATE_SET_ID_PATTERN)
    evidence = _require_mapping(approval_decision_evidence, "approval_decision_evidence")
    _scan_private_or_secret_payload(evidence, path="approval_decision_evidence")
    _assert_decision_evidence_boundary(evidence)
    source_decision_set_id = _require_non_empty_text(evidence.get("decision_set_id"), "decision_set_id")

    gates: list[dict[str, Any]] = []
    gate_ids: list[str] = []
    approval_ids: list[str] = []
    receipt_ids: list[str] = []
    decisions = evidence.get("decisions")
    if isinstance(decisions, (str, bytes)) or not isinstance(decisions, Sequence):
        raise PersonalAssistantInvariantError("approval_decision_evidence.decisions must be a sequence")
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise PersonalAssistantInvariantError("approval decision item must be a mapping")
        if decision.get("decision") != "approved":
            continue
        gate = _gate_item(source_decision_set_id, decision)
        if gate["gate_id"] in gate_ids:
            raise PersonalAssistantInvariantError(f"duplicate gate_id {gate['gate_id']}")
        gate_ids.append(gate["gate_id"])
        approval_ids.append(gate["approval_id"])
        receipt_ids.append(gate["receipt"]["receipt_id"])
        gates.append(gate)
    if not gates:
        raise PersonalAssistantInvariantError("execution gate requires at least one approved decision")

    envelope = {
        "gate_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "approval_decision_evidence",
        "source_decision_set_id": source_decision_set_id,
        "gate_count": len(gates),
        "gate_ids": gate_ids,
        "approval_ids": approval_ids,
        "receipt_ids": receipt_ids,
        "gates": gates,
        "effect_boundary": dict(_FALSE_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_execution_gate_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "approved_decision_required",
                "decision_receipt_deferred",
                "execution_gate_is_not_execution",
                "live_connector_witness_absent",
                "execution_worker_unbound",
                "operator_reapproval_required",
                "replay_plan_required",
                "no_external_send",
                "no_connector_mutation",
            ],
            "blocking_reasons": [],
            "next_action": "bind live connector witness, execution worker, replay plan, and operator reapproval before dispatch",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "execution_gate_evidence_only",
            "runtime_boundary": "gate_does_not_execute",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _gate_item(source_decision_set_id: str, decision: Mapping[str, Any]) -> dict[str, Any]:
    decision_id = _require_non_empty_text(decision.get("decision_id"), "decision_id")
    approval_id = _require_non_empty_text(decision.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(decision.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(decision.get("plan_id"), "plan_id")
    packet = _require_mapping(decision.get("packet"), "decision.packet")
    decision_receipt = _require_mapping(decision.get("receipt"), "decision.receipt")
    queue_ref = _require_mapping(decision.get("queue_precondition_ref"), "decision.queue_precondition_ref")
    proposed_actions = _sequence_of_mappings(packet.get("proposed_actions"))
    if not proposed_actions:
        raise PersonalAssistantInvariantError(f"{decision_id}: proposed_actions must be non-empty")
    if decision_receipt.get("decision") != "deferred":
        raise PersonalAssistantInvariantError(f"{decision_id}: decision receipt must be deferred")
    gate_id = _require_pattern(
        f"pa_execution_gate_item_{approval_id.removeprefix('pa_approval_')}",
        "gate_id",
        _GATE_ID_PATTERN,
    )
    skill_id = _require_non_empty_text(proposed_actions[0].get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(proposed_actions[0].get("risk_level"), "risk_level")
    if risk_level not in {"P3", "P4", "P5"}:
        raise PersonalAssistantInvariantError(f"{decision_id}: execution gate risk must be P3, P4, or P5")
    receipt_id = f"pa_receipt_execution_gate_{approval_id.removeprefix('pa_approval_')}"
    return {
        "gate_id": gate_id,
        "decision_id": decision_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "proposed_actions": proposed_actions,
        "approval_decision_ref": {
            "source_decision_set_id": source_decision_set_id,
            "decision": "approved",
            "decision_receipt_id": str(decision_receipt.get("receipt_id", "")),
            "decision_receipt_state": "deferred",
            "queue_precondition_sha256": _require_non_empty_text(
                queue_ref.get("queue_precondition_sha256"),
                "queue_precondition_sha256",
            ),
            "payload_digest_only": True,
            "approved_but_not_executed": True,
        },
        "dispatch_preconditions": {
            "approval_decision_approved": True,
            "decision_receipt_deferred": True,
            "live_connector_witness_present": False,
            "execution_worker_bound": False,
            "operator_reapproval_required": True,
            "replay_plan_required": True,
            "execution_allowed": False,
        },
        "receipt": _gate_receipt(
            receipt_id=receipt_id,
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=str(decision.get("decided_at", "")),
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
        "inputs_used": ["approval_decision_evidence", "execution_gate_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": ["execution_gate_evaluated", "dispatch_preconditions_recorded", "receipt_created"],
        "actions_not_taken": [
            "proposed_action_not_executed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": ["approval_refs_only", "private_connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp or DEFAULT_EXECUTION_GATE_GENERATED_AT,
        "evidence_refs": [f"proof://personal-assistant/execution-gate/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/execution-gate/{approval_id}"],
        "outcome": "SolvedVerified",
        "metadata": {
            "foundation_only": True,
            "execution_gate_is_execution": False,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _assert_decision_evidence_boundary(evidence: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(evidence.get("effect_boundary"), "effect_boundary")
    if effect_boundary.get("approval_decision_records_allowed") is not True:
        raise PersonalAssistantInvariantError("approval decision records must be allowed")
    for field_name in (
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"approval evidence effect_boundary.{field_name} must be false")


def _sequence_of_mappings(values: Any) -> list[dict[str, Any]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        return []
    return [dict(value) for value in values if isinstance(value, Mapping)]


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
