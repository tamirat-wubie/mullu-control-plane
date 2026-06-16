"""Tests for TeamOps shared inbox send-execution receipt production.

Purpose: prove ready TeamOps send-preparation receipts compose into redacted
send-execution evidence receipts without local provider calls.
Governance scope: TeamOps send execution, preparation carry-forward, no-local
provider mutation claims, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_send_execution_receipt.
Invariants:
  - Blocked send-preparation evidence keeps send execution blocked.
  - Ready send execution requires redacted provider dispatch evidence.
  - The receipt producer never performs the provider send itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_send_execution_receipt import (
    main,
    produce_team_ops_shared_inbox_send_execution_receipt,
    write_team_ops_shared_inbox_send_execution_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_send_execution_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64


def test_team_ops_shared_inbox_send_execution_blocks_without_preparation_ready(
    tmp_path: Path,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    preparation_path.write_text(json.dumps(_blocked_preparation_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_execution_receipt(
        send_preparation_receipt_path=preparation_path,
        schema_path=SCHEMA_PATH,
        executed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.send_preparation_receipt_valid is True
    assert receipt.send_preparation_receipt_ready is False
    assert receipt.send_execution_ready is False
    assert receipt.external_message_sent is False
    assert receipt.send_execution_performed_by_producer is False
    assert receipt.provider_call_performed_by_producer is False
    assert receipt.provider_mutation_performed_by_producer is False
    assert receipt.blocked_until == ("send_preparation_receipt_not_ready",)


def test_team_ops_shared_inbox_send_execution_requires_execution_evidence(
    tmp_path: Path,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    preparation_path.write_text(json.dumps(_ready_preparation_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_execution_receipt(
        send_preparation_receipt_path=preparation_path,
        schema_path=SCHEMA_PATH,
        executed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.send_preparation_receipt_ready is True
    assert receipt.decision == "approved"
    assert receipt.external_send_authorized_by_decision is True
    assert receipt.send_preparation_ref == "send-preparation:aaaaaaaaaaaaaaaa"
    assert receipt.send_execution_state == "missing"
    assert receipt.send_execution_ready is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ("send_execution_evidence_missing",)


def test_team_ops_shared_inbox_send_execution_accepts_provider_receipt(
    tmp_path: Path,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    preparation_path.write_text(json.dumps(_ready_preparation_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_execution_receipt(
        send_preparation_receipt_path=preparation_path,
        schema_path=SCHEMA_PATH,
        executed_at="2026-06-14T00:00:00+00:00",
        send_execution_ref="send-execution:aaaaaaaaaaaaaaaa",
        dispatch_receipt_ref="dispatch-receipt:aaaaaaaaaaaaaaaa",
        provider_message_ref="provider-message:aaaaaaaaaaaaaaaa",
        dispatch_receipt_hash=HEX_C,
        provider_message_hash=HEX_D,
        evidence_refs=("provider-send-receipt:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.send_preparation_receipt_ready is True
    assert receipt.send_execution_state == "sent"
    assert receipt.send_execution_ready is True
    assert receipt.send_execution_observed is True
    assert receipt.external_message_sent is True
    assert receipt.external_message_sent_by_producer is False
    assert receipt.provider_call_performed_by_producer is False
    assert receipt.requires_sent_message_observation_receipt is True
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_send_execution_blocks_preparation_drift(
    tmp_path: Path,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    preparation_path.write_text(json.dumps(_denied_preparation_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_execution_receipt(
        send_preparation_receipt_path=preparation_path,
        schema_path=SCHEMA_PATH,
        executed_at="2026-06-14T00:00:00+00:00",
        send_execution_ref="send-execution:aaaaaaaaaaaaaaaa",
        dispatch_receipt_ref="dispatch-receipt:aaaaaaaaaaaaaaaa",
        provider_message_ref="provider-message:aaaaaaaaaaaaaaaa",
        dispatch_receipt_hash=HEX_C,
        provider_message_hash=HEX_D,
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.send_preparation_receipt_valid is False
    assert receipt.send_execution_state == "not_authorized"
    assert receipt.send_execution_ready is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ("send_preparation_receipt_invalid",)


def test_team_ops_shared_inbox_send_execution_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    preparation_path.write_text(json.dumps(_ready_preparation_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_send_execution_receipt(
            send_preparation_receipt_path=preparation_path,
            schema_path=SCHEMA_PATH,
            executed_at="2026-06-14T00:00:00+00:00",
            send_execution_ref="client_secret=must-not-serialize",
            dispatch_receipt_ref="dispatch-receipt:aaaaaaaaaaaaaaaa",
            provider_message_ref="provider-message:aaaaaaaaaaaaaaaa",
            dispatch_receipt_hash=HEX_C,
            provider_message_hash=HEX_D,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_send_execution_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    preparation_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    preparation_path.write_text(json.dumps(_ready_preparation_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_send_execution_receipt(
        send_preparation_receipt_path=preparation_path,
        schema_path=SCHEMA_PATH,
        executed_at="2026-06-14T00:00:00+00:00",
        send_execution_ref="send-execution:aaaaaaaaaaaaaaaa",
        dispatch_receipt_ref="dispatch-receipt:aaaaaaaaaaaaaaaa",
        provider_message_ref="provider-message:aaaaaaaaaaaaaaaa",
        dispatch_receipt_hash=HEX_C,
        provider_message_hash=HEX_D,
    )

    written = write_team_ops_shared_inbox_send_execution_receipt(receipt, output_path)
    exit_code = main(
        [
            "--send-preparation-receipt",
            str(preparation_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--executed-at",
            "2026-06-14T00:00:00+00:00",
            "--send-execution-ref",
            "send-execution:aaaaaaaaaaaaaaaa",
            "--dispatch-receipt-ref",
            "dispatch-receipt:aaaaaaaaaaaaaaaa",
            "--provider-message-ref",
            "provider-message:aaaaaaaaaaaaaaaa",
            "--dispatch-receipt-hash",
            HEX_C,
            "--provider-message-hash",
            HEX_D,
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["send_execution_ready"] is True
    assert payload["provider_call_performed_by_producer"] is False
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_preparation_receipt() -> dict[str, object]:
    return _base_preparation_receipt() | {
        "approval_decision_receipt_valid": True,
        "approval_decision_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "approval_queue_id": "",
        "approval_request_ref": "",
        "approval_decision_ref": "",
        "approver_ref": "",
        "decision": "",
        "approval_state": "missing",
        "external_send_authorized_by_decision": False,
        "send_preparation_state": "missing",
        "send_preparation_ready": False,
        "send_preparation_ref": "",
        "prepared_message_ref": "",
        "thread_ref": "",
        "recipient_hash": "",
        "prepared_message_hash": "",
        "evidence_refs": [],
        "blocked_until": ["approval_decision_receipt_not_ready"],
        "recovery_actions": ["record an approved TeamOps approval decision before preparing send evidence"],
    }


def _ready_preparation_receipt() -> dict[str, object]:
    return _base_preparation_receipt() | {
        "approval_decision_receipt_valid": True,
        "approval_decision_receipt_ready": True,
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "approval_decision_ref": "approval-decision:aaaaaaaaaaaaaaaa",
        "approver_ref": "principal:team-ops-owner",
        "decision": "approved",
        "approval_state": "approved",
        "external_send_authorized_by_decision": True,
        "send_preparation_state": "prepared",
        "send_preparation_ready": True,
        "send_preparation_ref": "send-preparation:aaaaaaaaaaaaaaaa",
        "prepared_message_ref": "prepared-message:aaaaaaaaaaaaaaaa",
        "thread_ref": "thread:teamops-123",
        "recipient_hash": HEX_A,
        "prepared_message_hash": HEX_B,
        "evidence_refs": ["send-preparation:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _denied_preparation_receipt() -> dict[str, object]:
    return _ready_preparation_receipt() | {
        "decision": "denied",
        "approval_state": "denied",
        "external_send_authorized_by_decision": False,
    }


def _base_preparation_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-send-preparation-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_approval_decision_receipt_ref": ".change_assurance/team_ops_shared_inbox_approval_decision_receipt.json",
        "source_approval_decision_receipt_id": "teamops-shared-inbox-approval-decision-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "prepared_at": "2026-06-14T00:00:00+00:00",
        "send_execution_performed_by_producer": False,
        "requires_separate_send_execution_receipt": True,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
