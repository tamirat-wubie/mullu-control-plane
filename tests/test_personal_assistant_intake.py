"""Tests for personal-assistant governed request intake.

Purpose: prove request text becomes schema-ready governed intent and WHQR
clarification requests without connector or external effects.
Governance scope: request interpretation, connector proof admission, missing
binding detection, approval boundaries, and clarification projection.
Dependencies: mcoi_runtime.personal_assistant intake and WHQR bridge modules.
Invariants:
  - Intake never executes a connector.
  - Missing hard bindings block execution mode.
  - Ambiguous external communication requires recipient, artifact, and approval clarification.
  - Schema-ready request output preserves blocked actions and receipt evidence refs.
"""

from __future__ import annotations

from pathlib import Path

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    RequestExecutionMode,
    SkillRiskLevel,
    build_clarification_requests,
    interpret_user_request,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_request.schema.json"
SUBMITTED_AT = "2026-06-14T00:00:00+00:00"


def test_inbox_request_with_connector_proof_compiles_to_read_and_draft_intent() -> None:
    intent = interpret_user_request(
        "Check important inbox items and prepare response drafts only.",
        request_id="pa_request_runtime_inbox_001",
        submitted_at=SUBMITTED_AT,
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:gmail:operator",
                connector_name="gmail",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("gmail.readonly",),
            ),
        ),
    )
    request_payload = intent.as_request_dict()

    assert _validate_schema_instance(_load_schema(REQUEST_SCHEMA_PATH), request_payload) == []
    assert intent.risk_level is SkillRiskLevel.P2
    assert intent.execution_mode is RequestExecutionMode.READ_AND_DRAFT_ONLY
    assert intent.missing_bindings == ()
    assert intent.requested_skill_ids == ("email.inbox.summarize", "email.response.draft")
    assert "send" in intent.blocked_actions
    assert request_payload["metadata"]["live_connector_execution_allowed"] is False


def test_missing_private_connector_proof_blocks_inbox_intake() -> None:
    intent = interpret_user_request(
        "Check my inbox and draft replies.",
        request_id="pa_request_runtime_missing_connector_001",
        submitted_at=SUBMITTED_AT,
    )
    missing = tuple(binding.as_dict() for binding in intent.missing_bindings)

    assert intent.execution_mode is RequestExecutionMode.BLOCKED
    assert len(missing) == 1
    assert missing[0]["binding_id"] == "connector:gmail"
    assert missing[0]["binding_type"] == "connector"
    assert missing[0]["reason_code"] == "missing_connector_proof"
    assert "email.response.draft" in intent.requested_skill_ids


def test_ambiguous_send_request_emits_whqr_clarifications() -> None:
    intent = interpret_user_request(
        "Send it to Daniel.",
        request_id="pa_request_runtime_send_daniel_001",
        submitted_at=SUBMITTED_AT,
        connector_refs=(
            {
                "connector_id": "connector:gmail:operator",
                "connector_name": "gmail",
                "proof_state": "Pass",
                "private_data_allowed": True,
                "scopes": ["gmail.send"],
            },
        ),
    )
    bundle = build_clarification_requests(
        intent,
        thread_id="thread-personal-assistant-001",
        requested_from_id="operator",
    )
    questions = tuple(request.question for request in bundle.clarifications)

    assert intent.risk_level is SkillRiskLevel.P4
    assert intent.requires_approval is True
    assert intent.execution_mode is RequestExecutionMode.BLOCKED
    assert intent.requested_skill_ids == ("email.send.with_approval",)
    assert len(bundle.clarifications) == 3
    assert "Which Daniel should receive the message?" in questions
    assert all("pa_request_runtime_send_daniel_001" in request.context for request in bundle.clarifications)


def test_math_request_preserves_planning_only_boundary() -> None:
    intent = interpret_user_request(
        "Compare two cost scenarios and check the assumptions.",
        request_id="pa_request_runtime_math_001",
        submitted_at=SUBMITTED_AT,
    )
    payload = intent.as_request_dict()

    assert _validate_schema_instance(_load_schema(REQUEST_SCHEMA_PATH), payload) == []
    assert intent.requested_skill_ids == ("math.reasoning.plan",)
    assert intent.connector_refs == ()
    assert intent.risk_level is SkillRiskLevel.P2
    assert intent.execution_mode is RequestExecutionMode.PREVIEW
    assert "pay_invoice" in intent.blocked_actions
    assert payload["metadata"]["system_of_record_write_allowed"] is False


def test_unknown_request_blocks_on_action_boundary_clarification() -> None:
    intent = interpret_user_request(
        "Handle this for me.",
        request_id="pa_request_runtime_unknown_001",
        submitted_at=SUBMITTED_AT,
    )
    bundle = build_clarification_requests(
        intent,
        thread_id="thread-personal-assistant-unknown",
        requested_from_id="operator",
        requested_at=SUBMITTED_AT,
    )
    clarification = bundle.clarifications[0]

    assert intent.requested_skill_ids == ()
    assert intent.execution_mode is RequestExecutionMode.BLOCKED
    assert intent.missing_bindings[0].binding_type == "action_boundary"
    assert len(bundle.clarifications) == 1
    assert clarification.request_id.endswith("action_boundary_unknown")
    assert "missing_skill_boundary" in clarification.context
    assert clarification.requested_at == SUBMITTED_AT
