"""Purpose: runtime intake-chain read model for the personal assistant.
Governance scope: request intake, symbolic interpretation proposal binding,
WHQR clarification, preview planning, approval boundary, receipts, memory
boundary, and no-effect evidence projection.
Dependencies: personal-assistant intake, planner, WHQR bridge, and contracts.
Invariants:
  - Building the read model never calls connectors or mutates external state.
  - Approval remains a boundary record and does not execute actions.
  - Raw private payloads, secret-like values, memory writes, and readiness
    overclaims are rejected or forced false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import ConnectorProofRef, GovernedIntent, RequestInterface, interpret_user_request
from .planner import PersonalAssistantPlanningEnvelope, build_personal_assistant_preview_plan
from .whqr_bridge import PersonalAssistantClarificationBundle, build_clarification_requests


_DEFAULT_GENERATED_AT = "2026-06-25T00:00:00Z"
_DEFAULT_REQUEST_TEXT = "Check important inbox items and prepare response drafts only."
_DEFAULT_REQUEST_ID = "pa_request_inbox_summary_001"
_DEFAULT_PLAN_ID = "pa_plan_inbox_summary_chain_001"
_DEFAULT_GATEWAY_REQUEST_ID = "interpreted-request-2222222222222222"
_DEFAULT_PROPOSAL_ID = "symbolic-interpretation-proposal-1111111111111111"
_DEFAULT_CONNECTOR_REF = ConnectorProofRef(
    connector_id="connector:gmail:operator",
    connector_name="gmail",
    proof_state="Pass",
    private_data_allowed=True,
    scopes=("gmail.readonly",),
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
    }
)
_EFFECT_BOUNDARY = {
    "execution_allowed": False,
    "live_connector_execution_allowed": False,
    "connector_mutation_allowed": False,
    "mailbox_read_allowed": False,
    "mailbox_mutation_allowed": False,
    "external_send_allowed": False,
    "calendar_write_allowed": False,
    "task_write_allowed": False,
    "memory_write_allowed": False,
    "deployment_mutation_allowed": False,
    "customer_readiness_claim_allowed": False,
    "money_legal_public_action_allowed": False,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "connector_payload_projection": "digest_only",
    "body_projection": "operator_visible_draft",
}
_SOURCE_ARTIFACTS = (
    {
        "source_kind": "request",
        "source_ref": "examples/personal_assistant_request_inbox_summary.json",
        "schema_ref": "schemas/personal_assistant_request.schema.json",
        "payload_digest_only": True,
        "solver_outcome": "SolvedVerified",
    },
    {
        "source_kind": "symbolic_interpretation_proposal",
        "source_ref": "examples/symbolic_interpretation_proposal.foundation.json",
        "schema_ref": "schemas/symbolic_interpretation_proposal.schema.json",
        "payload_digest_only": True,
        "solver_outcome": "SolvedVerified",
    },
    {
        "source_kind": "clarification_request",
        "source_ref": "examples/clarification_request.foundation.json",
        "schema_ref": "schemas/clarification_request.schema.json",
        "payload_digest_only": True,
        "solver_outcome": "SolvedVerified",
    },
    {
        "source_kind": "approval_packet",
        "source_ref": "examples/personal_assistant_approval_packet.json",
        "schema_ref": "schemas/personal_assistant_approval.schema.json",
        "payload_digest_only": True,
        "solver_outcome": "SolvedVerified",
    },
    {
        "source_kind": "draft_receipt",
        "source_ref": "examples/personal_assistant_receipt_draft_only.json",
        "schema_ref": "schemas/personal_assistant_receipt.schema.json",
        "payload_digest_only": True,
        "solver_outcome": "SolvedVerified",
    },
)


def build_personal_assistant_intake_chain_read_model(
    *,
    generated_at: str = _DEFAULT_GENERATED_AT,
    intent: GovernedIntent | None = None,
    planning_envelope: PersonalAssistantPlanningEnvelope | None = None,
    clarification_bundle: PersonalAssistantClarificationBundle | None = None,
    interpretation_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Foundation Mode intake-chain read model.

    Input contract: callers may pass an already governed intent plus optional
    plan, clarification, and interpretation projections.
    Output contract: returns a JSON-ready no-effect read model.
    Error contract: raises PersonalAssistantInvariantError for missing
    timestamps, id drift, raw private fields, secret-like values, or execution
    authority drift.
    """

    timestamp = _require_text(generated_at, "generated_at")
    governed_intent = intent or _default_intent(timestamp)
    envelope = planning_envelope or build_personal_assistant_preview_plan(
        governed_intent,
        plan_id=_DEFAULT_PLAN_ID if governed_intent.request_id == _DEFAULT_REQUEST_ID else _plan_id(governed_intent),
        created_at=timestamp,
    )
    if envelope.plan["request_id"] != governed_intent.request_id:
        raise PersonalAssistantInvariantError("planning_envelope request_id must match intent.request_id")
    clarification = clarification_bundle or build_clarification_requests(
        governed_intent,
        thread_id=f"thread:{governed_intent.request_id}",
        requested_from_id="operator:local",
        requested_at=timestamp,
    )
    if clarification.request_id != governed_intent.request_id:
        raise PersonalAssistantInvariantError("clarification_bundle request_id must match intent.request_id")

    interpretation = _interpretation_summary(governed_intent, interpretation_summary)
    questions = [request.question for request in clarification.clarifications]
    reason_codes = [binding.reason_code for binding in governed_intent.missing_bindings]
    receipt_refs = _receipt_refs(envelope)
    evidence_refs = _evidence_refs(envelope)
    source_artifacts = [dict(artifact) for artifact in _SOURCE_ARTIFACTS]
    plan_steps = _list(envelope.plan.get("steps"))
    read_model = {
        "read_model_id": _read_model_id(governed_intent),
        "read_model_version": "personal_assistant_intake_chain_read_model.v1",
        "generated_at": timestamp,
        "foundation_only": True,
        "solver_outcome": "AwaitingEvidence" if governed_intent.has_missing_bindings else "SolvedVerified",
        "request": {
            "request_id": governed_intent.request_id,
            "interface": governed_intent.interface.value,
            "risk_level": governed_intent.risk_level.value,
            "execution_mode": governed_intent.execution_mode.value,
            "requires_approval": governed_intent.requires_approval,
            "requested_skill_ids": list(governed_intent.requested_skill_ids),
            "missing_binding_count": len(governed_intent.missing_bindings),
            "source_ref": "examples/personal_assistant_request_inbox_summary.json",
        },
        "interpretation": interpretation,
        "clarification": {
            "required": bool(governed_intent.missing_bindings),
            "missing_binding_count": len(governed_intent.missing_bindings),
            "reason_codes": reason_codes,
            "questions": questions,
            "safe_default": "no_execution",
            "source_ref": "examples/clarification_request.foundation.json",
        },
        "plan_preview": {
            "plan": dict(envelope.plan),
            "step_count": len(plan_steps),
            "actions_not_authorized": list(envelope.plan["actions_not_authorized"]),
            "source_ref": "examples/personal_assistant_dry_run_packet.json",
        },
        "approval_boundary": {
            "approval_required_for_p4_p5": True,
            "approval_id": "pa_approval_email_send_001",
            "approval_state": "requested",
            "approval_is_execution": False,
            "execution_allowed": False,
            "external_send_allowed": False,
            "source_ref": "examples/personal_assistant_approval_packet.json",
        },
        "receipt_boundary": {
            "receipt_required": True,
            "receipt_count": len(receipt_refs),
            "actions_taken_recorded": True,
            "actions_not_taken_recorded": True,
            "success_claim_allowed": False,
            "source_ref": "examples/personal_assistant_receipt_draft_only.json",
        },
        "memory_boundary": {
            "memory_observation_allowed": True,
            "memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "raw_chat_log_storage_allowed": False,
        },
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "source_artifacts": source_artifacts,
        "evidence_refs": evidence_refs,
        "receipt_refs": receipt_refs,
        "lineage": _lineage(),
        "contract_summary": {
            "source_artifact_count": len(source_artifacts),
            "evidence_ref_count": len(evidence_refs),
            "receipt_ref_count": len(receipt_refs),
            "missing_binding_count": len(governed_intent.missing_bindings),
            "plan_step_count": len(plan_steps),
            "read_model_projection_closed": True,
            "customer_readiness_claim_allowed": False,
            "deployment_mutation_allowed": False,
        },
    }
    _assert_no_private_or_secret_payload(read_model)
    _assert_no_effect_authority(read_model)
    return read_model


def _default_intent(generated_at: str) -> GovernedIntent:
    return interpret_user_request(
        _DEFAULT_REQUEST_TEXT,
        request_id=_DEFAULT_REQUEST_ID,
        submitted_at=generated_at,
        interface=RequestInterface.OPERATOR_CONSOLE,
        connector_refs=(_DEFAULT_CONNECTOR_REF,),
    )


def _interpretation_summary(
    intent: GovernedIntent,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if payload is None:
        summary: dict[str, Any] = {
            "proposal_id": _DEFAULT_PROPOSAL_ID,
            "personal_assistant_request_id": intent.request_id,
            "gateway_request_id": _DEFAULT_GATEWAY_REQUEST_ID,
            "comparison_result": "matches_deterministic",
            "validation_status": "accepted_as_proposal",
            "authority_level": "proposal_only",
            "deterministic_override_allowed": False,
            "action_authority_granted": False,
            "execution_allowed": False,
            "private_payload_included": False,
            "secret_values_serialized": False,
            "source_ref": "examples/symbolic_interpretation_proposal.foundation.json",
        }
    elif not isinstance(payload, Mapping):
        raise PersonalAssistantInvariantError("interpretation_summary must be a mapping")
    else:
        summary = dict(payload)
        summary.setdefault("personal_assistant_request_id", intent.request_id)
        summary.setdefault("source_ref", "examples/symbolic_interpretation_proposal.foundation.json")
    if summary.get("personal_assistant_request_id") != intent.request_id:
        raise PersonalAssistantInvariantError("interpretation request_id must match intent.request_id")
    for field_name in (
        "deterministic_override_allowed",
        "action_authority_granted",
        "execution_allowed",
        "private_payload_included",
        "secret_values_serialized",
    ):
        if summary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"interpretation.{field_name} must be false")
    return summary


def _receipt_refs(envelope: PersonalAssistantPlanningEnvelope) -> list[str]:
    refs = list(_text_list(envelope.plan.get("receipt_refs"), "plan.receipt_refs"))
    if envelope.receipt.get("receipt_id") not in refs:
        refs.append(_require_text(envelope.receipt.get("receipt_id"), "receipt.receipt_id"))
    if "pa_receipt_email_draft_001" not in refs:
        refs.append("pa_receipt_email_draft_001")
    return refs


def _evidence_refs(envelope: PersonalAssistantPlanningEnvelope) -> list[str]:
    refs = list(_text_list(envelope.plan.get("evidence_refs"), "plan.evidence_refs"))
    refs.extend(_text_list(envelope.receipt.get("evidence_refs"), "receipt.evidence_refs"))
    refs.extend(
        (
            "proof://personal-assistant/intake-chain/inbox-summary",
            "proof://personal-assistant/approval/email-send-001",
            "proof://personal-assistant/receipt/email-draft-001",
        )
    )
    return list(dict.fromkeys(refs))


def _lineage() -> dict[str, list[dict[str, Any]]]:
    return {
        "accepted_deltas": [
            {
                "delta_id": "intake_chain_runtime_projection_built",
                "logged_in_lineage": True,
                "reason": "Runtime builder may project the intake chain as a Foundation Mode read model.",
            }
        ],
        "rejected_deltas": [
            {
                "delta_id": "live_connector_execution",
                "logged_in_lineage": True,
                "reason": "Runtime intake-chain projection grants no connector execution authority.",
            },
            {
                "delta_id": "external_send",
                "logged_in_lineage": True,
                "reason": "External communication remains blocked without explicit approval and live evidence.",
            },
            {
                "delta_id": "memory_write",
                "logged_in_lineage": True,
                "reason": "Memory observation remains review-only; no live memory write is admitted.",
            },
        ],
    }


def _assert_no_effect_authority(payload: Mapping[str, Any]) -> None:
    for field_name, value in _flatten_mapping(payload):
        if field_name.endswith("execution_allowed") and value is True:
            raise PersonalAssistantInvariantError(f"{field_name} must be false")
        if field_name in {
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_send_allowed",
            "mailbox_read_allowed",
            "mailbox_mutation_allowed",
            "calendar_write_allowed",
            "task_write_allowed",
            "memory_write_allowed",
            "nested_mind_live_activation_allowed",
            "deployment_mutation_allowed",
            "customer_readiness_claim_allowed",
            "money_legal_public_action_allowed",
            "raw_private_payload_serialized",
            "secret_values_serialized",
        } and value is True:
            raise PersonalAssistantInvariantError(f"{field_name} must be false")


def _assert_no_private_or_secret_payload(payload: Any, *, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in _RAW_PRIVATE_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private field is forbidden")
            _assert_no_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _assert_no_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                raise PersonalAssistantInvariantError(f"{path}: secret-like value is forbidden")


def _flatten_mapping(payload: Any) -> tuple[tuple[str, Any], ...]:
    values: list[tuple[str, Any]] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            values.append((str(key), value))
            values.extend(_flatten_mapping(value))
    elif isinstance(payload, list):
        for value in payload:
            values.extend(_flatten_mapping(value))
    return tuple(values)


def _plan_id(intent: GovernedIntent) -> str:
    return f"pa_plan_{intent.request_id.removeprefix('pa_request_')}_intake_chain"


def _read_model_id(intent: GovernedIntent) -> str:
    return f"pa_intake_chain_{intent.request_id.removeprefix('pa_request_')}"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _text_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a non-empty string")
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
