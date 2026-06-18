"""Tests for Personal Assistant TeamOps projection validation.

Purpose: prove TeamOps shared-inbox planning evidence remains schema-backed
and no-effect.
Governance scope: no Gmail call, no shared-inbox read, no draft/send, no
provider mutation, no raw payload storage, no secret serialization, and receipt
continuity.
Dependencies: personal-assistant TeamOps projection validator and fixture.
Invariants:
  - TeamOps plan projections are not live provider probes.
  - Ready evidence does not execute a live probe.
  - Receipts must record actions taken and actions not taken.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_teamops_projection import (
    build_runtime_teamops_projection_evidence,
    validate_personal_assistant_teamops_projection,
)
from mcoi_runtime.personal_assistant import build_teamops_gmail_live_probe_readiness


def test_personal_assistant_teamops_projection_fixture_validates() -> None:
    result = validate_personal_assistant_teamops_projection()

    assert result.valid is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.runtime_validated is True
    assert result.assurance_outcome == "AwaitingEvidence"
    assert result.errors == ()


def test_runtime_teamops_projection_blocks_effect_boundaries() -> None:
    envelope = build_runtime_teamops_projection_evidence()
    effect_boundary = envelope["effect_boundary"]
    ready_projection = envelope["projections"][1]
    ready_gate = ready_projection["plan"]["live_probe_gate"]
    ready_receipt = ready_projection["receipt"]

    assert effect_boundary["teamops_plan_records_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["live_connector_execution_allowed"] is False
    assert effect_boundary["live_probe_execution_allowed"] is False
    assert effect_boundary["mailbox_read_allowed"] is False
    assert effect_boundary["external_send_allowed"] is False
    assert ready_gate["ready_for_live_probe"] is True
    assert ready_gate["live_probe_executed"] is False
    assert ready_gate["external_provider_call_performed"] is False
    assert "gmail_not_called" in ready_receipt["actions_not_taken"]
    assert "shared_inbox_not_read" in ready_receipt["actions_not_taken"]


def test_teamops_gmail_live_probe_readiness_blocks_without_oauth_evidence() -> None:
    receipt = build_teamops_gmail_live_probe_readiness(
        generated_at="2026-06-18T12:00:00+00:00",
        environment={},
    )

    assert receipt["status"] == "blocked"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["effect_boundary"]["readiness_probe_performed"] is True
    assert receipt["effect_boundary"]["external_provider_call_performed"] is False
    assert receipt["effect_boundary"]["mailbox_read_performed"] is False
    assert receipt["effect_boundary"]["provider_mutation_performed"] is False
    assert "read_full_mailbox" in receipt["blocked_actions"]
    assert "gmail_provider_not_called" in receipt["actions_not_taken"]


def test_teamops_gmail_live_probe_readiness_accepts_presence_only_ready_env() -> None:
    receipt = build_teamops_gmail_live_probe_readiness(
        generated_at="2026-06-18T12:00:00+00:00",
        environment={
            "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
            "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
            "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
            "GMAIL_SCOPE_ID": "gmail.readonly",
            "GMAIL_OAUTH_CLIENT_ID": "client-id-secret-shaped-value",
            "GMAIL_OAUTH_CLIENT_SECRET": "client_secret=must-not-leak",
            "GMAIL_REFRESH_TOKEN": "refresh_token=must-not-leak",
            "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
            "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
            "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
            "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
            "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation-recovery",
        },
    )
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "passed"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert receipt["connector_readiness"]["ready_for_live_probe"] is True
    assert receipt["durable_oauth_presence"]["all_present"] is True
    assert receipt["mailbox_access_boundary"]["least_privilege_satisfied"] is True
    assert receipt["mailbox_access_boundary"]["mailbox_read_allowed"] is False
    assert receipt["effect_boundary"]["external_provider_call_performed"] is False
    assert "client_secret=must-not-leak" not in serialized
    assert "refresh_token=must-not-leak" not in serialized
    assert "client-id-secret-shaped-value" not in serialized


def test_teamops_projection_validator_rejects_live_execution_authority(tmp_path: Path) -> None:
    candidate = build_runtime_teamops_projection_evidence()
    candidate["effect_boundary"]["execution_allowed"] = True
    candidate["effect_boundary"]["live_probe_execution_allowed"] = True
    candidate["projections"][0]["plan"]["live_probe_executed"] = True
    candidate["projections"][0]["plan"]["live_probe_gate"]["external_provider_call_performed"] = True
    candidate_path = tmp_path / "teamops_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_teamops_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("execution_allowed" in error for error in result.errors)
    assert any("live_probe_execution_allowed" in error for error in result.errors)
    assert any("live_probe_executed" in error for error in result.errors)
    assert any("external_provider_call_performed" in error for error in result.errors)


def test_teamops_projection_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    candidate = build_runtime_teamops_projection_evidence()
    receipt = candidate["projections"][0]["receipt"]
    receipt["actions_not_taken"].remove("gmail_not_called")
    receipt["metadata"]["live_connector_execution_allowed"] = True
    candidate["receipt_ids"] = ["pa_receipt_wrong"]
    candidate_path = tmp_path / "teamops_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_teamops_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("gmail_not_called" in error for error in result.errors)
    assert any("live_connector_execution_allowed" in error for error in result.errors)
    assert any("receipt_ids must match" in error for error in result.errors)


def test_teamops_projection_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    candidate = build_runtime_teamops_projection_evidence()
    candidate["projections"][0]["plan"]["raw_connector_payload"] = "private mailbox body"
    candidate["projections"][1]["plan"]["handoff"]["operator_approval_ref"] = "Bearer secret-token-value"
    candidate_path = tmp_path / "teamops_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_teamops_projection(projection_path=candidate_path)
    serialized_errors = "\n".join(result.errors)

    assert result.valid is False
    assert "raw_connector_payload" in serialized_errors
    assert "secret-like value" in serialized_errors
    assert "private mailbox body" not in serialized_errors


def test_teamops_projection_validator_requires_ready_and_blocked_handoffs(tmp_path: Path) -> None:
    candidate = build_runtime_teamops_projection_evidence()
    ready_only = copy.deepcopy(candidate)
    ready_only["projections"] = [candidate["projections"][1]]
    ready_only["projection_count"] = 1
    ready_only["projection_ids"] = [candidate["projection_ids"][1]]
    ready_only["receipt_ids"] = [candidate["receipt_ids"][1]]
    candidate_path = tmp_path / "teamops_projection.json"
    candidate_path.write_text(json.dumps(ready_only), encoding="utf-8")

    result = validate_personal_assistant_teamops_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("blocked handoff" in error for error in result.errors)
    assert not any("ready-evidence handoff" in error for error in result.errors)
