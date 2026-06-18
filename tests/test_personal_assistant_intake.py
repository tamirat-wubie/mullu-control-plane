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

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    PersonalAssistantInvariantError,
    PersonalAssistantSkillRegistry,
    RequestExecutionMode,
    SkillRiskLevel,
    build_clarification_requests,
    interpret_user_request,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_request.schema.json"
REGISTRY_PATH = ROOT / "examples" / "personal_assistant_skill_registry.json"
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
    assert request_payload["metadata"]["capability_pack_binding_valid"] is True
    assert request_payload["metadata"]["local_capability_ref_count"] >= 1
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


def test_schedule_planning_request_preserves_preview_only_boundary() -> None:
    intent = interpret_user_request(
        "Plan my day with a capacity plan and time blocks.",
        request_id="pa_request_runtime_planning_001",
        submitted_at=SUBMITTED_AT,
    )
    payload = intent.as_request_dict()

    assert _validate_schema_instance(_load_schema(REQUEST_SCHEMA_PATH), payload) == []
    assert intent.requested_skill_ids == ("planning.optimize_schedule",)
    assert intent.connector_refs == ()
    assert intent.risk_level is SkillRiskLevel.P2
    assert intent.execution_mode is RequestExecutionMode.PREVIEW
    assert "create_event" in intent.blocked_actions
    assert "task.create_draft" not in intent.requested_skill_ids
    assert payload["metadata"]["system_of_record_write_allowed"] is False


def test_task_request_compiles_to_connector_free_draft_intent() -> None:
    intent = interpret_user_request(
        "Create a task draft for the release checklist.",
        request_id="pa_request_runtime_task_draft_001",
        submitted_at=SUBMITTED_AT,
    )
    payload = intent.as_request_dict()

    assert _validate_schema_instance(_load_schema(REQUEST_SCHEMA_PATH), payload) == []
    assert intent.requested_skill_ids == ("task.create_draft",)
    assert intent.connector_refs == ()
    assert intent.risk_level is SkillRiskLevel.P2
    assert intent.execution_mode is RequestExecutionMode.READ_AND_DRAFT_ONLY
    assert "system_of_record_write" in intent.blocked_actions
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


def test_intake_rejects_registry_with_unbound_local_capability_ref() -> None:
    registry_payload = _load_json(REGISTRY_PATH)
    mutated_skill = deepcopy(_skill_by_id(registry_payload, "email.inbox.summarize"))
    mutated_skill["skill_id"] = "email.inbox.unbound_local_ref"
    mutated_skill["capability_refs"] = ["personal_assistant.unbound_intake_ref"]
    registry_payload["skills"] = [mutated_skill]
    registry = PersonalAssistantSkillRegistry.from_mapping(registry_payload)

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        interpret_user_request(
            "Check important inbox items.",
            request_id="pa_request_runtime_unbound_capability_001",
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
            registry=registry,
        )

    assert "unbound local capability refs" in str(exc_info.value)
    assert "personal_assistant.unbound_intake_ref" in str(exc_info.value)
    assert "email.inbox.unbound_local_ref" not in str(exc_info.value)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_by_id(registry_payload: dict, skill_id: str) -> dict:
    for skill in registry_payload["skills"]:
        if skill["skill_id"] == skill_id:
            return skill
    raise AssertionError(f"missing skill {skill_id}")
