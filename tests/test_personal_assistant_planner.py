"""Tests for schema-backed personal-assistant preview planning.

Purpose: prove governed intents compile into plan and receipt projections.
Governance scope: WHQR blocked plans, no-execution preview, schema validation,
and receipt evidence preservation.
Dependencies: mcoi_runtime.personal_assistant planner and schema validators.
Invariants: planner output never authorizes connector calls, external sends,
memory writes, deployment mutation, or system-of-record writes.
"""

from __future__ import annotations

from pathlib import Path

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    build_personal_assistant_preview_plan,
    interpret_user_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
PLAN_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_plan.schema.json"
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
