"""Purpose: runtime approval decision evidence envelopes for personal assistant.
Governance scope: PR6 approval decisions, queue precondition proof, receipt
alignment, private-payload redaction, and no-effect authority boundaries.
Dependencies: personal-assistant approval queue runtime and contracts.
Invariants:
  - Approval decisions record operator evidence only and never execute actions.
  - Approved and revised decisions defer execution to a later governed gate.
  - Rejected and expired decisions block execution.
  - Raw private connector payloads and secret-like values are rejected.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .approval import ApprovalDecision, ApprovalProposedAction, PersonalAssistantApprovalQueue
from .contracts import PersonalAssistantInvariantError
from .intake import ApprovalScope


DEFAULT_APPROVAL_DECISION_SET_ID = "pa_approval_decision_set_foundation_001"
DEFAULT_APPROVAL_DECISION_CREATED_AT = "2026-06-14T00:00:00+00:00"
DEFAULT_APPROVAL_DECISION_DECIDED_AT = "2026-06-14T00:03:00+00:00"

_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_DECISION_SET_ID_PATTERN = re.compile(r"^pa_approval_decision_set_[a-z0-9][a-z0-9_:-]*$")
_DECISION_ID_PATTERN = re.compile(r"^pa_approval_decision_[a-z0-9][a-z0-9_:-]*$")
_APPROVAL_ID_PATTERN = re.compile(r"^pa_approval_[a-z0-9][a-z0-9_:-]*$")
_RECEIPT_ID_PATTERN = re.compile(r"^pa_receipt_[a-z0-9][a-z0-9_:-]*$")
_RECEIPT_REQUEST_ID_PATTERN = re.compile(r"^pa_receipt_[a-z0-9][a-z0-9_:-]*_request$")
_REQUEST_ID_PATTERN = re.compile(r"^pa_request_[a-z0-9][a-z0-9_:-]*$")
_PLAN_ID_PATTERN = re.compile(r"^pa_plan_[a-z0-9][a-z0-9_:-]*$")
_EFFECT_BOUNDARY = {
    "approval_decision_records_allowed": True,
    "execution_allowed": False,
    "approval_is_execution": False,
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
    "decision_payload_projection": "bounded_operator_decision_record",
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


def build_default_personal_assistant_approval_decision_evidence(
    *,
    generated_at: str = DEFAULT_APPROVAL_DECISION_DECIDED_AT,
    created_at: str = DEFAULT_APPROVAL_DECISION_CREATED_AT,
    decision_set_id: str = DEFAULT_APPROVAL_DECISION_SET_ID,
) -> dict[str, Any]:
    """Build deterministic approval decision evidence for all decision states."""
    decision_records: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for index, decision in enumerate(_DECISION_VALUES, start=1):
        queue = PersonalAssistantApprovalQueue()
        approval_id = f"pa_approval_decision_{decision}_{index:03d}"
        record = queue.enqueue(
            request_id=f"pa_request_decision_{decision}_{index:03d}",
            plan_id=f"pa_plan_decision_{decision}_{index:03d}",
            approver_ref="operator:tamirat",
            approval_scope=ApprovalScope.PER_RECIPIENT,
            proposed_actions=(
                ApprovalProposedAction(
                    action_id="send_prepared_email_draft",
                    skill_id="email.send.with_approval",
                    risk_level="P4",
                    effect_boundary="external_email_send",
                    summary="Send one approved email draft to one named recipient.",
                ),
            ),
            forbidden_without_approval=("send", "forward", "recipient_unapproved", "connector_mutation"),
            evidence_refs=(f"proof://personal-assistant/approval/{decision}-{index:03d}",),
            created_at=_require_non_empty_text(created_at, "created_at"),
            approval_id=approval_id,
        )
        source_record = record.as_dict()
        updated = queue.record_decision(
            record.approval_id,
            decision=ApprovalDecision.coerce(decision),
            reason_codes=(f"operator_{decision}_preview",),
            decided_at=_require_non_empty_text(generated_at, "generated_at"),
            decision_evidence_ref=f"proof://personal-assistant/approval/operator-{decision}-{index:03d}",
            revision_request="Revise the draft before any future approval." if decision == "revised" else "",
        )
        decision_records.append((f"pa_approval_decision_{decision}_{index:03d}", source_record, updated.as_dict()))
    return build_personal_assistant_approval_decision_evidence_envelope(
        generated_at=generated_at,
        decision_set_id=decision_set_id,
        decision_records=tuple(decision_records),
    )


def build_personal_assistant_approval_decision_evidence_envelope(
    *,
    generated_at: str,
    decision_records: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
    decision_set_id: str = DEFAULT_APPROVAL_DECISION_SET_ID,
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around approval decisions."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(decision_set_id, "decision_set_id", _DECISION_SET_ID_PATTERN)
    if isinstance(decision_records, (str, bytes)) or not isinstance(decision_records, Sequence):
        raise PersonalAssistantInvariantError("decision_records must be a sequence")
    if not decision_records:
        raise PersonalAssistantInvariantError("decision_records must contain at least one decision")

    decisions: list[dict[str, Any]] = []
    decision_ids: list[str] = []
    approval_ids: list[str] = []
    receipt_ids: list[str] = []
    seen_decisions: set[str] = set()
    for decision_id, source_record, record in decision_records:
        normalized_decision_id = _require_pattern(decision_id, "decision_id", _DECISION_ID_PATTERN)
        if normalized_decision_id in decision_ids:
            raise PersonalAssistantInvariantError(f"duplicate decision_id {normalized_decision_id}")
        decision_ids.append(normalized_decision_id)

        decision = _decision_item(normalized_decision_id, source_record, record)
        receipt_id = decision["receipt"]["receipt_id"]
        if receipt_id in receipt_ids:
            raise PersonalAssistantInvariantError(f"duplicate receipt_id {receipt_id}")
        receipt_ids.append(receipt_id)
        approval_id = decision["approval_id"]
        if approval_id not in approval_ids:
            approval_ids.append(approval_id)
        seen_decisions.add(decision["decision"])
        decisions.append(decision)

    missing_decisions = set(_DECISION_VALUES).difference(seen_decisions)
    if missing_decisions:
        raise PersonalAssistantInvariantError(f"decisions must include {','.join(sorted(missing_decisions))}")

    envelope = {
        "decision_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_supplied_decision_evidence",
        "decision_count": len(decisions),
        "decision_ids": decision_ids,
        "approval_ids": approval_ids,
        "receipt_ids": receipt_ids,
        "decisions": decisions,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_approval_decision_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "approval_decision_is_not_execution",
                "approved_decision_deferred",
                "rejected_decision_blocks_execution",
                "revised_decision_deferred",
                "expired_decision_blocks_execution",
                "no_live_connector_execution",
                "no_external_send",
                "no_connector_mutation",
                "no_memory_write",
                "no_secret_value_serialization",
            ],
            "blocking_reasons": [],
            "next_action": "continue execution-gate hardening before any effect-bearing dispatch",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "approval_decision_evidence_only",
            "runtime_boundary": "decision_does_not_execute",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _decision_item(
    decision_id: str,
    source_record: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(source_record, Mapping):
        raise PersonalAssistantInvariantError(f"{decision_id}: source_record must be a mapping")
    if not isinstance(record, Mapping):
        raise PersonalAssistantInvariantError(f"{decision_id}: record must be a mapping")
    packet = _require_mapping(record.get("packet"), f"{decision_id}.packet")
    receipt = _latest_receipt(record, f"{decision_id}.receipts")
    decision_record = _require_mapping(packet.get("decision_record"), f"{decision_id}.packet.decision_record")
    decision = _require_decision_value(decision_record.get("decision"), f"{decision_id}.decision")
    approval_id = _require_pattern(
        str(packet.get("approval_id", record.get("approval_id", ""))),
        "approval_id",
        _APPROVAL_ID_PATTERN,
    )
    request_id = _require_pattern(str(packet.get("request_id", "")), "request_id", _REQUEST_ID_PATTERN)
    plan_id = _require_pattern(str(packet.get("plan_id", "")), "plan_id", _PLAN_ID_PATTERN)
    decided_at = _require_non_empty_text(decision_record.get("decided_at"), f"{decision_id}.decided_at")
    reason_codes = _require_unique_text_list(decision_record.get("reason_codes"), f"{decision_id}.reason_codes")

    if record.get("approval_id") != approval_id:
        raise PersonalAssistantInvariantError(f"{decision_id}: record approval_id must match packet")
    if packet.get("approval_state") != decision:
        raise PersonalAssistantInvariantError(f"{decision_id}: packet approval_state must match decision")
    _assert_receipt_alignment(
        decision_id=decision_id,
        decision=decision,
        approval_id=approval_id,
        request_id=request_id,
        receipt=receipt,
    )
    queue_ref = _queue_precondition_ref(source_record)
    _assert_queue_precondition_ref(
        decision_id=decision_id,
        ref=queue_ref,
        approval_id=approval_id,
        request_id=request_id,
        plan_id=plan_id,
        decision_receipt_id=receipt["receipt_id"],
    )
    _scan_private_or_secret_payload(packet, path=f"{decision_id}.packet")
    _scan_private_or_secret_payload(receipt, path=f"{decision_id}.receipt")
    return {
        "decision_id": decision_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "decision": decision,
        "decided_at": decided_at,
        "reason_codes": reason_codes,
        "queue_precondition_ref": queue_ref,
        "packet": dict(packet),
        "receipt": dict(receipt),
    }


def _assert_receipt_alignment(
    *,
    decision_id: str,
    decision: str,
    approval_id: str,
    request_id: str,
    receipt: Mapping[str, Any],
) -> None:
    _require_pattern(str(receipt.get("receipt_id", "")), "receipt.receipt_id", _RECEIPT_ID_PATTERN)
    if receipt.get("request_id") != request_id:
        raise PersonalAssistantInvariantError(f"{decision_id}: receipt.request_id must match decision")
    if receipt.get("approval_ref") != approval_id:
        raise PersonalAssistantInvariantError(f"{decision_id}: receipt.approval_ref must match approval_id")
    if receipt.get("approval_required") is not True:
        raise PersonalAssistantInvariantError(f"{decision_id}: receipt.approval_required must be true")
    expected_receipt_decision = "blocked" if decision in {"rejected", "expired"} else "deferred"
    if receipt.get("decision") != expected_receipt_decision:
        raise PersonalAssistantInvariantError(
            f"{decision_id}: receipt.decision must be {expected_receipt_decision} for {decision}"
        )
    if not _non_empty_string_sequence(receipt.get("actions_taken")):
        raise PersonalAssistantInvariantError(f"{decision_id}: receipt.actions_taken must be non-empty")
    if not _non_empty_string_sequence(receipt.get("actions_not_taken")):
        raise PersonalAssistantInvariantError(f"{decision_id}: receipt.actions_not_taken must be non-empty")

    metadata = _require_mapping(receipt.get("metadata"), f"{decision_id}.receipt.metadata")
    for field_name in (
        "approval_is_execution",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_write_allowed",
        "system_of_record_write_allowed",
        "money_legal_public_action_allowed",
    ):
        if metadata.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{decision_id}: receipt.metadata.{field_name} must be false")


def _queue_precondition_ref(source_record: Mapping[str, Any]) -> dict[str, Any]:
    source_packet = _require_mapping(source_record.get("packet"), "source_record.packet")
    source_metadata = _require_mapping(source_packet.get("metadata"), "source_record.packet.metadata")
    source_receipt = _latest_receipt(source_record, "source_record.receipts")
    review_packet_ref = _require_mapping(source_record.get("review_packet_ref"), "source_record.review_packet_ref")
    ref = {
        "source_projection": "personal_assistant_approval_queue_read_model",
        "approval_id": str(source_record.get("approval_id", source_packet.get("approval_id", ""))),
        "request_id": str(source_packet.get("request_id", "")),
        "plan_id": str(source_packet.get("plan_id", "")),
        "source_queue_state": str(source_metadata.get("queue_state", source_packet.get("approval_state", ""))),
        "source_receipt_id": str(source_receipt.get("receipt_id", "")),
        "source_review_packet_id": str(review_packet_ref.get("review_packet_id", "")),
        "source_review_packet_sha256": str(review_packet_ref.get("source_sha256", "")),
        "payload_digest_only": True,
        "decision_precondition_met": True,
        "execution_allowed": False,
        "approval_is_execution": False,
        "external_send_allowed": False,
        "connector_mutation_allowed": False,
        "system_of_record_write_allowed": False,
    }
    ref["queue_precondition_sha256"] = _queue_precondition_sha256(ref)
    return ref


def _assert_queue_precondition_ref(
    *,
    decision_id: str,
    ref: Mapping[str, Any],
    approval_id: str,
    request_id: str,
    plan_id: str,
    decision_receipt_id: str,
) -> None:
    expected_pairs = {
        "source_projection": "personal_assistant_approval_queue_read_model",
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "source_queue_state": "requested",
        "source_review_packet_id": "pa_approval_review_approval_review_packet_001",
    }
    for field_name, expected_value in expected_pairs.items():
        if ref.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(
                f"{decision_id}: queue_precondition_ref.{field_name} must be {expected_value}"
            )
    source_receipt_id = _require_pattern(
        str(ref.get("source_receipt_id", "")),
        "queue_precondition_ref.source_receipt_id",
        _RECEIPT_REQUEST_ID_PATTERN,
    )
    if source_receipt_id == decision_receipt_id:
        raise PersonalAssistantInvariantError(
            f"{decision_id}: queue_precondition_ref.source_receipt_id must differ from decision receipt"
        )
    for field_name in ("payload_digest_only", "decision_precondition_met"):
        if ref.get(field_name) is not True:
            raise PersonalAssistantInvariantError(
                f"{decision_id}: queue_precondition_ref.{field_name} must be true"
            )
    for field_name in (
        "execution_allowed",
        "approval_is_execution",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
    ):
        if ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(
                f"{decision_id}: queue_precondition_ref.{field_name} must be false"
            )
    source_sha = str(ref.get("source_review_packet_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha):
        raise PersonalAssistantInvariantError(
            f"{decision_id}: queue_precondition_ref.source_review_packet_sha256 must be a sha256 digest"
        )
    expected_digest = _queue_precondition_sha256(ref)
    if ref.get("queue_precondition_sha256") != expected_digest:
        raise PersonalAssistantInvariantError(
            f"{decision_id}: queue_precondition_ref.queue_precondition_sha256 drift"
        )


def _queue_precondition_sha256(ref: Mapping[str, Any]) -> str:
    material = {key: value for key, value in ref.items() if key != "queue_precondition_sha256"}
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _latest_receipt(record: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    receipts = record.get("receipts")
    if isinstance(receipts, (str, bytes)) or not isinstance(receipts, Sequence) or not receipts:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one receipt")
    latest = receipts[-1]
    if not isinstance(latest, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} latest receipt must be a mapping")
    return dict(latest)


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return dict(value)


def _require_decision_value(value: Any, field_name: str) -> str:
    text = _require_non_empty_text(value, field_name)
    if text not in _DECISION_VALUES:
        raise PersonalAssistantInvariantError(f"{field_name} must be one of {','.join(_DECISION_VALUES)}")
    return text


def _require_unique_text_list(value: Any, field_name: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    result: list[str] = []
    for index, item in enumerate(value):
        text = _require_non_empty_text(item, f"{field_name}[{index}]")
        if text in result:
            raise PersonalAssistantInvariantError(f"{field_name} must contain unique values")
        result.append(text)
    if not result:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one value")
    return result


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


def _non_empty_string_sequence(value: Any) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return False
    return bool(value) and all(isinstance(item, str) and bool(item.strip()) for item in value)


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
