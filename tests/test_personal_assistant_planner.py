"""Tests for schema-backed personal-assistant preview planning.

Purpose: prove governed intents compile into plan and receipt projections.
Governance scope: WHQR blocked plans, no-execution preview, schema validation,
and receipt evidence preservation.
Dependencies: mcoi_runtime.personal_assistant planner and schema validators.
Invariants: planner output never authorizes connector calls, external sends,
memory writes, deployment mutation, or system-of-record writes.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ApprovalScope,
    ConnectorProofRef,
    GovernedIntent,
    PersonalAssistantApprovalMatrix,
    PersonalAssistantInvariantError,
    RequestExecutionMode,
    RequestInterface,
    SkillRiskLevel,
    build_personal_assistant_preview_plan,
    interpret_user_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
PLAN_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_plan.schema.json"
MATRIX_PATH = ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
SUBMITTED_AT = "2026-06-14T00:00:00+00:00"


def test_preview_planner_emits_schema_valid_inbox_plan_and_receipt() -> None:
    intent = interpret_user_request(
        "Check important inbox items and prepare response drafts only.",
        request_id="pa_request_planner_inbox_001",
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
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_planner_inbox_001",
        created_at=SUBMITTED_AT,
    )

    assert _validate_schema_instance(_load_schema(PLAN_SCHEMA_PATH), envelope.plan) == []
    assert validate_personal_assistant_receipt_payload(envelope.receipt) == ()
    assert envelope.plan["execution_allowed"] is False
    assert envelope.plan["steps"][0]["skill_id"] == "email.inbox.summarize"
    assert envelope.receipt["decision"] == "allowed"
    assert "external_message_not_sent" in envelope.receipt["actions_not_taken"]


def test_preview_planner_blocks_unknown_request_with_clarification_skill() -> None:
    intent = interpret_user_request(
        "Handle this for me.",
        request_id="pa_request_planner_unknown_001",
        submitted_at=SUBMITTED_AT,
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_planner_unknown_001",
        created_at=SUBMITTED_AT,
    )

    assert _validate_schema_instance(_load_schema(PLAN_SCHEMA_PATH), envelope.plan) == []
    assert validate_personal_assistant_receipt_payload(envelope.receipt) == ()
    assert envelope.plan["mode"] == "blocked"
    assert envelope.plan["steps"][0]["skill_id"] == "personal_assistant.clarification.request"
    assert envelope.receipt["outcome"] == "AwaitingEvidence"
    assert "plan_execution_blocked_until_clarification" in envelope.plan["actions_not_authorized"]


def test_preview_planner_binds_approval_matrix_read_model_for_p4_action() -> None:
    intent = GovernedIntent(
        request_id="pa_request_planner_p4_matrix_001",
        submitted_at=SUBMITTED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/request/planner-p4-matrix-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_planner_p4_matrix_001",
        created_at=SUBMITTED_AT,
    )
    matrix_metadata = envelope.plan["metadata"]["approval_matrix"]

    assert _validate_schema_instance(_load_schema(PLAN_SCHEMA_PATH), envelope.plan) == []
    assert validate_personal_assistant_receipt_payload(envelope.receipt) == ()
    assert envelope.plan["mode"] == "execute_with_approval"
    assert envelope.plan["approval_gate"]["approval_level"] == "P4"
    assert matrix_metadata["matrix_id"] == "personal_assistant_approval_matrix.foundation.v1"
    assert matrix_metadata["risk_allowed_modes"] == ["execute_with_approval", "blocked"]
    assert matrix_metadata["execution_allowed_by_matrix"] is False
    assert envelope.receipt["metadata"]["approval_matrix_ref"] == matrix_metadata["matrix_id"]
    assert envelope.receipt["metadata"]["approval_matrix"]["approval_is_execution"] is False


def test_preview_planner_forces_p5_action_to_blocked_matrix_mode() -> None:
    intent = GovernedIntent(
        request_id="pa_request_planner_p5_matrix_001",
        submitted_at=SUBMITTED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Review deployment publication readiness without deploying.",
        requested_capabilities=("deployment.publish.review",),
        requested_skill_ids=("deployment.publish.review",),
        risk_level=SkillRiskLevel.P5,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_PLAN,
        blocked_actions=("deploy_service", "publish", "live_nested_mind_activation"),
        evidence_refs=("proof://personal-assistant/request/planner-p5-matrix-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_planner_p5_matrix_001",
        created_at=SUBMITTED_AT,
    )
    step = envelope.plan["steps"][0]
    matrix_metadata = envelope.plan["metadata"]["approval_matrix"]

    assert _validate_schema_instance(_load_schema(PLAN_SCHEMA_PATH), envelope.plan) == []
    assert envelope.plan["mode"] == "blocked"
    assert step["skill_id"] == "deployment.publish.review"
    assert step["mode"] == "blocked"
    assert matrix_metadata["risk_level"] == "P5"
    assert matrix_metadata["risk_allowed_modes"] == ["blocked"]
    assert envelope.receipt["decision"] == "approval_required"
    assert "deployment_not_started" in envelope.receipt["actions_not_taken"]


def test_preview_planner_rejects_approval_matrix_mode_drift() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    drifted = deepcopy(payload)
    for entry in drifted["risk_levels"]:
        if entry["level"] == "P4":
            entry["allowed_modes"] = ["blocked"]
    matrix = PersonalAssistantApprovalMatrix.from_mapping(drifted)
    intent = GovernedIntent(
        request_id="pa_request_planner_p4_drift_001",
        submitted_at=SUBMITTED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/request/planner-p4-drift-001",),
    )

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_preview_plan(
            intent,
            plan_id="pa_plan_planner_p4_drift_001",
            created_at=SUBMITTED_AT,
            approval_matrix=matrix,
        )

    assert "P4" in str(exc_info.value)
    assert "not allowed by approval matrix" in str(exc_info.value)
    assert "execute_with_approval" in str(exc_info.value)
