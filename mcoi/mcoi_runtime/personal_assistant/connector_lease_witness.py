"""Purpose: connector and dispatch lease witness envelopes for personal assistant.
Governance scope: connector witness refs, inactive dispatch lease refs, tenant
and scope refs, receipt alignment, private-payload redaction, and no-dispatch
boundaries.
Dependencies: personal-assistant replay/rollback witness runtime and contracts.
Invariants:
  - Connector and lease witnesses record refs and digests only.
  - Dispatch lease candidates are inactive and cannot dispatch from this module.
  - Live connector execution, execution-worker admission, external sends,
    connector mutation, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .replay_rollback_witness import build_default_personal_assistant_replay_rollback_witness


DEFAULT_CONNECTOR_LEASE_WITNESS_SET_ID = "pa_connector_lease_witness_foundation_001"
DEFAULT_CONNECTOR_LEASE_WITNESS_GENERATED_AT = "2026-06-14T00:07:00+00:00"

_WITNESS_SET_ID_PATTERN = re.compile(r"^pa_connector_lease_witness_[a-z0-9][a-z0-9_:-]*$")
_WITNESS_ID_PATTERN = re.compile(r"^pa_connector_lease_witness_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_FALSE_EFFECT_BOUNDARY = {
    "connector_lease_witness_allowed": True,
    "connector_witness_ref_binding_allowed": True,
    "dispatch_lease_ref_binding_allowed": True,
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
    "tenant_payload_projection": "ref_only",
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
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "lease_payload_projection",
        "tenant_payload_projection",
        "connector_ref_digest",
        "dispatch_lease_digest",
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


def build_default_personal_assistant_connector_lease_witness(
    *,
    generated_at: str = DEFAULT_CONNECTOR_LEASE_WITNESS_GENERATED_AT,
    witness_set_id: str = DEFAULT_CONNECTOR_LEASE_WITNESS_SET_ID,
) -> dict[str, Any]:
    """Build deterministic connector/lease witness evidence."""
    return build_personal_assistant_connector_lease_witness_envelope(
        generated_at=generated_at,
        witness_set_id=witness_set_id,
        replay_rollback_witness=build_default_personal_assistant_replay_rollback_witness(),
    )


def build_personal_assistant_connector_lease_witness_envelope(
    *,
    generated_at: str,
    replay_rollback_witness: Mapping[str, Any],
    witness_set_id: str = DEFAULT_CONNECTOR_LEASE_WITNESS_SET_ID,
) -> dict[str, Any]:
    """Build no-effect connector/lease witness evidence from replay witness."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(witness_set_id, "witness_set_id", _WITNESS_SET_ID_PATTERN)
    replay_envelope = _require_mapping(replay_rollback_witness, "replay_rollback_witness")
    _scan_private_or_secret_payload(replay_envelope, path="replay_rollback_witness")
    _assert_replay_rollback_boundary(replay_envelope)
    source_witness_set_id = _require_non_empty_text(replay_envelope.get("witness_set_id"), "witness_set_id")

    witnesses: list[dict[str, Any]] = []
    witness_ids: list[str] = []
    source_witness_ids: list[str] = []
    receipt_ids: list[str] = []
    source_witnesses = replay_envelope.get("witnesses")
    if isinstance(source_witnesses, (str, bytes)) or not isinstance(source_witnesses, Sequence):
        raise PersonalAssistantInvariantError("replay_rollback_witness.witnesses must be a sequence")
    for source_witness in source_witnesses:
        if not isinstance(source_witness, Mapping):
            raise PersonalAssistantInvariantError("replay/rollback witness item must be a mapping")
        witness = _witness_item(source_witness_set_id, source_witness, timestamp=timestamp)
        if witness["witness_id"] in witness_ids:
            raise PersonalAssistantInvariantError(f"duplicate witness_id {witness['witness_id']}")
        witness_ids.append(witness["witness_id"])
        source_witness_ids.append(witness["source_witness_id"])
        receipt_ids.append(witness["receipt"]["receipt_id"])
        witnesses.append(witness)
    if not witnesses:
        raise PersonalAssistantInvariantError("connector/lease witness requires at least one replay/rollback witness")

    envelope = {
        "witness_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "replay_rollback_witness",
        "source_replay_rollback_witness_set_id": source_witness_set_id,
        "witness_count": len(witnesses),
        "witness_ids": witness_ids,
        "source_witness_ids": source_witness_ids,
        "receipt_ids": receipt_ids,
        "witnesses": witnesses,
        "effect_boundary": dict(_FALSE_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_connector_lease_witness_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "replay_rollback_witness_required",
                "connector_witness_ref_bound",
                "connector_scope_ref_bound",
                "connector_revocation_path_recorded",
                "dispatch_lease_ref_bound",
                "dispatch_lease_candidate_inactive",
                "live_connector_receipt_still_absent",
                "operator_reapproval_still_required",
                "no_execution_worker_admission",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "live_connector_receipt_absent",
                "dispatch_lease_inactive",
                "operator_reapproval_required",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect live connector receipt under approval, activate bounded dispatch lease, then request operator reapproval before execution-worker admission",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "connector_lease_witness_evidence_only",
            "runtime_boundary": "witness_records_connector_and_inactive_lease_refs_without_dispatch",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _witness_item(source_witness_set_id: str, source_witness: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_witness_id = _require_non_empty_text(source_witness.get("witness_id"), "source_witness_id")
    approval_id = _require_non_empty_text(source_witness.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_witness.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_witness.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_witness.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_witness.get("risk_level"), "risk_level")
    source_receipt = _require_mapping(source_witness.get("receipt"), "source_witness.receipt")
    dispatch_blockers = _require_mapping(source_witness.get("dispatch_blockers"), "source_witness.dispatch_blockers")
    replay_plan = _require_mapping(source_witness.get("replay_plan_witness"), "source_witness.replay_plan_witness")
    rollback_plan = _require_mapping(source_witness.get("rollback_plan_witness"), "source_witness.rollback_plan_witness")
    idempotency = _require_mapping(source_witness.get("idempotency_witness"), "source_witness.idempotency_witness")
    _assert_replay_rollback_item_boundary(source_witness_id, source_receipt, dispatch_blockers, replay_plan, rollback_plan, idempotency)
    suffix = approval_id.removeprefix("pa_approval_")
    witness_id = _require_pattern(
        f"pa_connector_lease_witness_item_{suffix}",
        "witness_id",
        _WITNESS_ID_PATTERN,
    )
    connector_family = "gmail" if skill_id.startswith("email.") else "none"
    connector_ref_digest = _digest_for("connector", approval_id, request_id, plan_id, skill_id)
    lease_digest = _digest_for("dispatch-lease", approval_id, request_id, plan_id, skill_id)
    return {
        "witness_id": witness_id,
        "source_witness_id": source_witness_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "replay_rollback_witness_ref": {
            "source_witness_set_id": source_witness_set_id,
            "source_receipt_id": str(source_receipt.get("receipt_id", "")),
            "source_receipt_state": "deferred",
            "replay_plan_bound": True,
            "rollback_plan_bound": True,
            "idempotency_ref_bound": True,
            "payload_digest_only": True,
        },
        "connector_witness": {
            "connector_family": connector_family,
            "connector_required": connector_family != "none",
            "connector_ref": f"connector://personal-assistant/{connector_family}/{approval_id}",
            "connector_ref_digest": connector_ref_digest,
            "connector_scope_ref": f"scope://personal-assistant/connector/{connector_family}/approval-bound/{approval_id}",
            "connector_tenant_ref": f"tenant://personal-assistant/operator-local/{approval_id}",
            "connector_tenant_bound": True,
            "connector_revocation_path_ref": f"recovery://personal-assistant/connector-revocation/{approval_id}",
            "connector_revocation_path_recorded": True,
            "live_connector_witness_required": connector_family != "none",
            "live_connector_witness_ref_bound": True,
            "live_connector_witness_state": "ref_bound_live_receipt_awaiting_evidence",
            "live_connector_receipt_present": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
        },
        "dispatch_lease_witness": {
            "dispatch_lease_required": True,
            "dispatch_lease_ref": f"lease://personal-assistant/dispatch/{approval_id}",
            "dispatch_lease_digest": lease_digest,
            "dispatch_lease_ref_bound": True,
            "dispatch_lease_state": "candidate_inactive",
            "dispatch_lease_active": False,
            "dispatch_lease_scope": "single_approval_projection",
            "dispatch_lease_expiry_ref": f"temporal://personal-assistant/dispatch-lease-expiry/{approval_id}",
            "dispatch_allowed": False,
            "execution_worker_admission_allowed": False,
        },
        "operator_reapproval_gate": {
            "operator_reapproval_required": True,
            "operator_reapproval_present": False,
            "approval_ref": approval_id,
            "approval_state": "required_after_connector_lease_binding",
            "execution_allowed_after_reapproval_only": True,
            "execution_worker_admission_allowed": False,
        },
        "receipt": _witness_receipt(
            receipt_id=f"pa_receipt_connector_lease_witness_{suffix}",
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
        "inputs_used": ["replay_rollback_witness", "connector_lease_witness_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "connector_witness_ref_recorded",
            "connector_scope_ref_recorded",
            "connector_revocation_path_recorded",
            "dispatch_lease_ref_recorded",
            "operator_reapproval_gate_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "live_connector_receipt_not_collected",
            "dispatch_lease_not_activated",
            "execution_worker_not_admitted",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": ["connector_refs_only", "lease_payload_digest_only", "private_connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/connector-lease-witness/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/connector-lease-witness/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "connector_lease_witness_is_execution": False,
            "connector_witness_ref_bound": True,
            "dispatch_lease_ref_bound": True,
            "dispatch_lease_active": False,
            "operator_reapproval_present": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_receipt_present": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _assert_replay_rollback_boundary(replay_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(replay_envelope.get("effect_boundary"), "effect_boundary")
    if effect_boundary.get("replay_rollback_witness_allowed") is not True:
        raise PersonalAssistantInvariantError("replay/rollback witness must be allowed")
    for field_name in (
        "worker_binding_allowed",
        "dispatch_lease_binding_allowed",
        "replay_execution_allowed",
        "rollback_execution_allowed",
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"replay/rollback witness effect_boundary.{field_name} must be false")


def _assert_replay_rollback_item_boundary(
    source_witness_id: str,
    source_receipt: Mapping[str, Any],
    dispatch_blockers: Mapping[str, Any],
    replay_plan: Mapping[str, Any],
    rollback_plan: Mapping[str, Any],
    idempotency: Mapping[str, Any],
) -> None:
    if source_receipt.get("decision") != "deferred":
        raise PersonalAssistantInvariantError(f"{source_witness_id}: replay/rollback receipt must be deferred")
    if replay_plan.get("replay_plan_validated") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: replay plan must be validated")
    if rollback_plan.get("rollback_plan_validated") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: rollback plan must be validated")
    if idempotency.get("idempotency_key_present") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: idempotency ref must be present")
    if idempotency.get("idempotency_key_serialized") is not False:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: idempotency key must not be serialized")
    for field_name in ("execution_worker_bound", "live_connector_witness_present", "dispatch_lease_present", "execution_allowed"):
        if dispatch_blockers.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_witness_id}: dispatch_blockers.{field_name} must be false")
    if dispatch_blockers.get("operator_reapproval_required") is not True:
        raise PersonalAssistantInvariantError(f"{source_witness_id}: operator reapproval must remain required")


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
