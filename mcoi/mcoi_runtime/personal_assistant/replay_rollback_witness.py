"""Purpose: replay and rollback witness envelopes for personal assistant.
Governance scope: replay plan refs, rollback plan refs, idempotency refs,
receipt alignment, private-payload redaction, and no-dispatch boundaries.
Dependencies: personal-assistant worker/replay preflight runtime and contracts.
Invariants:
  - Replay/rollback witness binding records refs and digests only.
  - Replay, rollback, worker binding, and dispatch are not executed here.
  - Live connector execution, external sends, connector mutation, memory writes,
    system-of-record writes, deployment mutation, and readiness claims remain
    false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .worker_replay_preflight import build_default_personal_assistant_worker_replay_preflight


DEFAULT_REPLAY_ROLLBACK_WITNESS_SET_ID = "pa_replay_rollback_witness_foundation_001"
DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT = "2026-06-14T00:06:00+00:00"

_WITNESS_SET_ID_PATTERN = re.compile(r"^pa_replay_rollback_witness_[a-z0-9][a-z0-9_:-]*$")
_WITNESS_ID_PATTERN = re.compile(r"^pa_replay_rollback_witness_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_FALSE_EFFECT_BOUNDARY = {
    "replay_rollback_witness_allowed": True,
    "replay_plan_binding_allowed": True,
    "rollback_plan_binding_allowed": True,
    "idempotency_ref_binding_allowed": True,
    "worker_binding_allowed": False,
    "dispatch_lease_binding_allowed": False,
    "replay_execution_allowed": False,
    "rollback_execution_allowed": False,
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
    "plan_payload_projection": "digest_only",
    "idempotency_key_projection": "digest_only",
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
        "raw_replay_plan",
        "raw_rollback_plan",
        "idempotency_key",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "plan_payload_projection",
        "idempotency_key_projection",
        "idempotency_key_digest",
        "idempotency_key_present",
        "idempotency_key_required",
        "idempotency_key_serialized",
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


def build_default_personal_assistant_replay_rollback_witness(
    *,
    generated_at: str = DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT,
    witness_set_id: str = DEFAULT_REPLAY_ROLLBACK_WITNESS_SET_ID,
) -> dict[str, Any]:
    """Build deterministic replay/rollback witness evidence."""
    return build_personal_assistant_replay_rollback_witness_envelope(
        generated_at=generated_at,
        witness_set_id=witness_set_id,
        worker_replay_preflight=build_default_personal_assistant_worker_replay_preflight(),
    )


def build_personal_assistant_replay_rollback_witness_envelope(
    *,
    generated_at: str,
    worker_replay_preflight: Mapping[str, Any],
    witness_set_id: str = DEFAULT_REPLAY_ROLLBACK_WITNESS_SET_ID,
) -> dict[str, Any]:
    """Build no-effect replay/rollback witness evidence from preflight."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(witness_set_id, "witness_set_id", _WITNESS_SET_ID_PATTERN)
    preflight_envelope = _require_mapping(worker_replay_preflight, "worker_replay_preflight")
    _scan_private_or_secret_payload(preflight_envelope, path="worker_replay_preflight")
    _assert_preflight_boundary(preflight_envelope)
    source_preflight_set_id = _require_non_empty_text(preflight_envelope.get("preflight_set_id"), "preflight_set_id")

    witnesses: list[dict[str, Any]] = []
    witness_ids: list[str] = []
    preflight_ids: list[str] = []
    receipt_ids: list[str] = []
    preflights = preflight_envelope.get("preflights")
    if isinstance(preflights, (str, bytes)) or not isinstance(preflights, Sequence):
        raise PersonalAssistantInvariantError("worker_replay_preflight.preflights must be a sequence")
    for preflight in preflights:
        if not isinstance(preflight, Mapping):
            raise PersonalAssistantInvariantError("worker/replay preflight item must be a mapping")
        witness = _witness_item(source_preflight_set_id, preflight, timestamp=timestamp)
        if witness["witness_id"] in witness_ids:
            raise PersonalAssistantInvariantError(f"duplicate witness_id {witness['witness_id']}")
        witness_ids.append(witness["witness_id"])
        preflight_ids.append(witness["preflight_id"])
        receipt_ids.append(witness["receipt"]["receipt_id"])
        witnesses.append(witness)
    if not witnesses:
        raise PersonalAssistantInvariantError("replay/rollback witness requires at least one worker/replay preflight")

    envelope = {
        "witness_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "worker_replay_preflight",
        "source_preflight_set_id": source_preflight_set_id,
        "witness_count": len(witnesses),
        "witness_ids": witness_ids,
        "preflight_ids": preflight_ids,
        "receipt_ids": receipt_ids,
        "witnesses": witnesses,
        "effect_boundary": dict(_FALSE_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_replay_rollback_witness_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "worker_replay_preflight_required",
                "replay_plan_ref_recorded",
                "rollback_plan_ref_recorded",
                "idempotency_ref_recorded",
                "worker_binding_still_absent",
                "live_connector_witness_still_absent",
                "dispatch_lease_still_absent",
                "operator_reapproval_still_required",
                "no_replay_execution",
                "no_rollback_execution",
                "no_external_send",
                "no_connector_mutation",
            ],
            "blocking_reasons": [
                "execution_worker_unbound",
                "live_connector_witness_absent",
                "dispatch_lease_absent",
                "operator_reapproval_required",
            ],
            "next_action": "bind live connector witness and dispatch lease, then request operator reapproval before execution-worker admission",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "replay_rollback_witness_evidence_only",
            "runtime_boundary": "witness_records_replay_rollback_refs_without_execution",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _witness_item(source_preflight_set_id: str, preflight: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    preflight_id = _require_non_empty_text(preflight.get("preflight_id"), "preflight_id")
    approval_id = _require_non_empty_text(preflight.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(preflight.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(preflight.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(preflight.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(preflight.get("risk_level"), "risk_level")
    replay_preflight = _require_mapping(preflight.get("replay_preflight"), "preflight.replay_preflight")
    worker_preflight = _require_mapping(preflight.get("worker_preflight"), "preflight.worker_preflight")
    source_receipt = _require_mapping(preflight.get("receipt"), "preflight.receipt")
    _assert_preflight_item_boundary(preflight_id, replay_preflight, worker_preflight, source_receipt)
    suffix = approval_id.removeprefix("pa_approval_")
    witness_id = _require_pattern(
        f"pa_replay_rollback_witness_item_{suffix}",
        "witness_id",
        _WITNESS_ID_PATTERN,
    )
    replay_digest = _digest_for("replay", approval_id, request_id, plan_id, skill_id)
    rollback_digest = _digest_for("rollback", approval_id, request_id, plan_id, skill_id)
    idempotency_digest = _digest_for("idempotency", approval_id, request_id, plan_id, skill_id)
    return {
        "witness_id": witness_id,
        "preflight_id": preflight_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "worker_replay_preflight_ref": {
            "source_preflight_set_id": source_preflight_set_id,
            "preflight_receipt_id": str(source_receipt.get("receipt_id", "")),
            "preflight_receipt_state": "deferred",
            "worker_binding_allowed": False,
            "replay_execution_allowed": False,
            "payload_digest_only": True,
        },
        "replay_plan_witness": {
            "replay_plan_required": True,
            "replay_plan_ref": f"proof://personal-assistant/replay-plan/{approval_id}",
            "replay_plan_digest": replay_digest,
            "replay_plan_state": "recorded_validated",
            "replay_plan_validated": True,
            "replay_scope": "single_approval_projection",
            "replay_payload_projection": "digest_only",
            "replay_execution_allowed": False,
        },
        "rollback_plan_witness": {
            "rollback_plan_required": True,
            "rollback_plan_ref": f"proof://personal-assistant/rollback-plan/{approval_id}",
            "rollback_plan_digest": rollback_digest,
            "rollback_plan_state": "recorded_validated",
            "rollback_plan_validated": True,
            "rollback_scope": "no_effect_before_execution",
            "compensation_required_after_execution": True,
            "rollback_execution_allowed": False,
        },
        "idempotency_witness": {
            "idempotency_key_required": True,
            "idempotency_key_ref": f"idempotency://personal-assistant/{approval_id}",
            "idempotency_key_digest": idempotency_digest,
            "idempotency_key_present": True,
            "idempotency_key_serialized": False,
            "idempotency_window_ref": f"temporal://personal-assistant/idempotency-window/{approval_id}",
            "idempotency_window_validated": True,
        },
        "dispatch_blockers": {
            "execution_worker_bound": False,
            "worker_binding_state": "unbound",
            "live_connector_witness_present": False,
            "dispatch_lease_present": False,
            "operator_reapproval_required": True,
            "execution_allowed": False,
        },
        "receipt": _witness_receipt(
            receipt_id=f"pa_receipt_replay_rollback_witness_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _witness_receipt(
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
        "inputs_used": ["worker_replay_preflight", "replay_rollback_witness_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "replay_plan_ref_recorded",
            "rollback_plan_ref_recorded",
            "idempotency_ref_recorded",
            "dispatch_blockers_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "execution_worker_not_bound",
            "dispatch_lease_not_bound",
            "replay_not_executed",
            "rollback_not_executed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": ["plan_refs_only", "plan_payload_digests_only", "idempotency_key_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/replay-rollback-witness/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/replay-rollback-witness/{approval_id}"],
        "outcome": "SolvedVerified",
        "metadata": {
            "foundation_only": True,
            "replay_rollback_witness_is_execution": False,
            "replay_plan_bound": True,
            "rollback_plan_bound": True,
            "idempotency_ref_bound": True,
            "worker_binding_allowed": False,
            "dispatch_lease_binding_allowed": False,
            "replay_execution_allowed": False,
            "rollback_execution_allowed": False,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _assert_preflight_boundary(preflight_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(preflight_envelope.get("effect_boundary"), "effect_boundary")
    if effect_boundary.get("worker_replay_preflight_allowed") is not True:
        raise PersonalAssistantInvariantError("worker/replay preflight must be allowed")
    for field_name in (
        "worker_binding_allowed",
        "replay_execution_allowed",
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"worker/replay preflight effect_boundary.{field_name} must be false")


def _assert_preflight_item_boundary(
    preflight_id: str,
    replay_preflight: Mapping[str, Any],
    worker_preflight: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
) -> None:
    if source_receipt.get("decision") != "deferred":
        raise PersonalAssistantInvariantError(f"{preflight_id}: preflight receipt must be deferred")
    if replay_preflight.get("replay_plan_state") != "required_not_recorded":
        raise PersonalAssistantInvariantError(f"{preflight_id}: replay plan must start as required_not_recorded")
    for field_name in ("replay_plan_required", "rollback_plan_required", "idempotency_key_required"):
        if replay_preflight.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{preflight_id}: replay_preflight.{field_name} must be true")
    for field_name in ("replay_plan_validated", "rollback_plan_validated", "idempotency_key_present", "replay_execution_allowed"):
        if replay_preflight.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{preflight_id}: replay_preflight.{field_name} must be false")
    for field_name in ("worker_binding_allowed", "execution_worker_bound", "live_connector_witness_present", "dispatch_lease_present"):
        if worker_preflight.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{preflight_id}: worker_preflight.{field_name} must be false")


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
