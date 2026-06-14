"""Tests for personal-assistant TeamOps shared-inbox planning.

Purpose: prove PR8 TeamOps shared-inbox planning composes existing handoff
contracts without mailbox reads, external sends, provider mutation, or secrets.
Governance scope: TeamOps intake routing, operator handoff projection,
live-probe gate summary, connector proof gating, receipt emission, and
secret/raw-payload denial.
Dependencies: mcoi_runtime.personal_assistant TeamOps helpers and TeamOps
handoff scripts.
Invariants:
  - TeamOps plans remain preview-only and non-mutating.
  - Live-probe readiness is evidence state, not execution.
  - Secret values and raw connector payloads are never serialized.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    PersonalAssistantInvariantError,
    RequestExecutionMode,
    plan_teamops_shared_inbox,
    interpret_user_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
HANDOFF_SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_operator_handoff.schema.json"
SUBMITTED_AT = "2026-06-14T00:00:00+00:00"
GENERATED_AT = "2026-06-14T00:05:00+00:00"


def test_teamops_shared_inbox_plan_emits_blocked_handoff_without_provider_call() -> None:
    intent = _teamops_intent()
    projection = plan_teamops_shared_inbox(
        intent,
        generated_at=GENERATED_AT,
        environment={},
        github_secret_names=set(),
    )
    plan = dict(projection.plan)
    receipt = dict(projection.receipt)
    serialized = json.dumps(projection.as_dict(), sort_keys=True)

    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert _validate_schema_instance(_load_schema(HANDOFF_SCHEMA_PATH), plan["handoff"]) == []
    assert projection.skill_id == "teamops.shared_inbox.plan"
    assert plan["execution_allowed"] is False
    assert plan["live_probe_gate"]["ready_for_live_probe"] is False
    assert plan["live_probe_gate"]["live_probe_executed"] is False
    assert "operator_approval_ref" in plan["handoff"]["blocked_until"]
    assert "gmail_not_called" in receipt["actions_not_taken"]
    assert receipt["metadata"]["live_probe_executed"] is False
    assert "secret-token-value" not in serialized


def test_teamops_shared_inbox_plan_accepts_ready_evidence_but_does_not_execute_probe() -> None:
    intent = _teamops_intent(request_id="pa_request_teamops_ready_001")
    projection = plan_teamops_shared_inbox(
        intent,
        generated_at=GENERATED_AT,
        environment=_ready_environment(),
        github_secret_names=_ready_secret_names(),
        operator_approval_ref="approval:teamops-shared-inbox-provider-setup-20260614",
    )
    handoff = projection.plan["handoff"]
    gate = projection.plan["live_probe_gate"]
    receipt = projection.receipt

    assert handoff["ready_for_live_probe"] is True
    assert handoff["solver_outcome"] == "SolvedVerified"
    assert gate["ready_for_live_probe"] is True
    assert gate["approval_binding_required"] is True
    assert gate["authority_receipt_required"] is True
    assert gate["live_probe_executed"] is False
    assert receipt["metadata"]["ready_for_live_probe"] is True
    assert receipt["metadata"]["live_connector_execution_allowed"] is False
    assert "live_probe_not_executed" in receipt["actions_not_taken"]


def test_teamops_intake_routes_before_generic_inbox() -> None:
    intent = _teamops_intent()

    assert intent.requested_skill_ids == ("teamops.shared_inbox.plan",)
    assert intent.execution_mode is RequestExecutionMode.PREVIEW
    assert intent.risk_level.value == "P2"
    assert intent.connector_refs[0].connector_name == "gmail"
    assert "email.inbox.summarize" not in intent.requested_skill_ids


def test_teamops_plan_requires_passing_gmail_connector_proof() -> None:
    missing_connector_intent = interpret_user_request(
        "Prepare a TeamOps shared inbox handoff.",
        request_id="pa_request_teamops_missing_connector_001",
        submitted_at=SUBMITTED_AT,
    )
    failing_connector_intent = interpret_user_request(
        "Prepare a TeamOps shared inbox handoff.",
        request_id="pa_request_teamops_failing_connector_001",
        submitted_at=SUBMITTED_AT,
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:gmail:operator",
                connector_name="gmail",
                proof_state="Unknown",
                private_data_allowed=True,
            ),
        ),
    )

    with pytest.raises(PersonalAssistantInvariantError) as missing_exc:
        plan_teamops_shared_inbox(missing_connector_intent, generated_at=GENERATED_AT)

    with pytest.raises(PersonalAssistantInvariantError) as failing_exc:
        plan_teamops_shared_inbox(failing_connector_intent, generated_at=GENERATED_AT)

    assert missing_connector_intent.execution_mode is RequestExecutionMode.BLOCKED
    assert "missing bindings block TeamOps plan" in str(missing_exc.value)
    assert failing_connector_intent.execution_mode is RequestExecutionMode.BLOCKED
    assert "missing bindings block TeamOps plan" in str(failing_exc.value)


def test_teamops_plan_rejects_raw_payload_fields_and_secret_like_values() -> None:
    intent = _teamops_intent(request_id="pa_request_teamops_secret_001")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        plan_teamops_shared_inbox(
            intent,
            generated_at=GENERATED_AT,
            environment={"raw_connector_payload": "private message"},
        )

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        plan_teamops_shared_inbox(
            intent,
            generated_at=GENERATED_AT,
            environment={"MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER": "Bearer secret-token-value"},
        )

    assert "raw_connector_payload" in str(raw_exc.value)
    assert "private message" not in str(raw_exc.value)
    assert "secret-like value" in str(secret_exc.value)


def _teamops_intent(*, request_id: str = "pa_request_teamops_shared_inbox_001"):
    return interpret_user_request(
        "Prepare a TeamOps shared inbox handoff.",
        request_id=request_id,
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


def _ready_environment() -> dict[str, str]:
    return {
        "MULLU_TEAM_OPS_ASSISTANT_PROFILE": "team_ops.default",
        "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER": "gmail",
        "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE": "shared_inbox_triage",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY": "approval_required",
        "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF": "witness:teamops-tenant-scope",
        "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF": "witness:teamops-shared-inbox",
        "MULLU_TEAM_OPS_DIRECTORY_WITNESS_REF": "witness:teamops-directory",
        "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF": "witness:teamops-owner-queue",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF": "policy:teamops-external-send-approval",
        "MULLU_TEAM_OPS_IDEMPOTENCY_POLICY_REF": "policy:teamops-idempotency",
        "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:teamops-revocation-recovery",
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_and_send_with_approval",
        "GMAIL_SCOPE_ID": (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send"
        ),
        "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID": (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send"
        ),
        "GMAIL_OAUTH_CLIENT_ID": "present",
        "GMAIL_OAUTH_CLIENT_SECRET": "present",
        "GMAIL_REFRESH_TOKEN": "present",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-token-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation",
        "MULLU_GMAIL_CONNECTOR_TENANT_WITNESS_REF": "witness:gmail-tenant",
    }


def _ready_secret_names() -> set[str]:
    return {
        "GMAIL_OAUTH_CLIENT_ID",
        "GMAIL_OAUTH_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
        "MULLU_GMAIL_CONNECTOR_TENANT_WITNESS_REF",
        "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF",
        "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF",
        "MULLU_TEAM_OPS_DIRECTORY_WITNESS_REF",
        "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF",
        "MULLU_TEAM_OPS_IDEMPOTENCY_POLICY_REF",
        "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF",
    }
