"""Tests for TeamOps shared inbox send-preparation receipt production.

Purpose: prove approved TeamOps decisions compose into redacted send-preparation
receipts without draft, send, mailbox write, or provider mutation effects.
Governance scope: TeamOps send preparation, approval carry-forward, no-effect
producer claims, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_send_preparation_receipt.
Invariants:
  - Blocked approval-decision evidence keeps send-preparation blocked.
  - Ready send preparation requires an approved decision and redacted evidence.
  - Prepared send evidence still requires a separate send-execution receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_send_preparation_receipt import (
    main,
    produce_team_ops_shared_inbox_send_preparation_receipt,
    write_team_ops_shared_inbox_send_preparation_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_send_preparation_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_shared_inbox_send_preparation_blocks_without_decision_ready(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    decision_path.write_text(json.dumps(_blocked_decision_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
        approval_decision_receipt_path=decision_path,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.approval_decision_receipt_valid is True
    assert receipt.approval_decision_receipt_ready is False
    assert receipt.send_preparation_ready is False
    assert receipt.send_execution_performed_by_producer is False
    assert receipt.draft_created_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("approval_decision_receipt_not_ready",)


def test_team_ops_shared_inbox_send_preparation_requires_preparation_evidence(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    decision_path.write_text(json.dumps(_approved_decision_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
        approval_decision_receipt_path=decision_path,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.approval_decision_receipt_ready is True
    assert receipt.decision == "approved"
    assert receipt.external_send_authorized_by_decision is True
    assert receipt.send_preparation_state == "missing"
    assert receipt.send_preparation_ready is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ("send_preparation_evidence_missing",)


def test_team_ops_shared_inbox_send_preparation_accepts_approved_packet(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    decision_path.write_text(json.dumps(_approved_decision_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
        approval_decision_receipt_path=decision_path,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        thread_ref="thread:teamops-123",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
        evidence_refs=("send-packet:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.approval_state == "approved"
    assert receipt.send_preparation_state == "prepared"
    assert receipt.send_preparation_ready is True
    assert receipt.send_execution_performed_by_producer is False
    assert receipt.requires_separate_send_execution_receipt is True
    assert receipt.draft_created_by_producer is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_send_preparation_blocks_denied_decision(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    decision_path.write_text(json.dumps(_denied_decision_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
        approval_decision_receipt_path=decision_path,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        thread_ref="thread:teamops-123",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.decision == "denied"
    assert receipt.send_preparation_state == "not_authorized"
    assert receipt.send_preparation_ready is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ("approval_decision_not_approved",)


def test_team_ops_shared_inbox_send_preparation_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    decision_path.write_text(json.dumps(_approved_decision_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_send_preparation_receipt(
            approval_decision_receipt_path=decision_path,
            schema_path=SCHEMA_PATH,
            prepared_at="2026-06-14T00:00:00+00:00",
            send_preparation_ref="client_secret=must-not-serialize",
            prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
            thread_ref="thread:teamops-123",
            recipient_hash=HEX_A,
            prepared_message_hash=HEX_B,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_send_preparation_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    decision_path = tmp_path / "team_ops_shared_inbox_approval_decision_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_send_preparation_receipt.json"
    decision_path.write_text(json.dumps(_approved_decision_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
        approval_decision_receipt_path=decision_path,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        thread_ref="thread:teamops-123",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
    )

    written = write_team_ops_shared_inbox_send_preparation_receipt(receipt, output_path)
    exit_code = main(
        [
            "--approval-decision-receipt",
            str(decision_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--prepared-at",
            "2026-06-14T00:00:00+00:00",
            "--send-preparation-ref",
            "send-preparation:aaaaaaaaaaaaaaaa",
            "--prepared-message-ref",
            "prepared-message:aaaaaaaaaaaaaaaa",
            "--thread-ref",
            "thread:teamops-123",
            "--recipient-hash",
            HEX_A,
            "--prepared-message-hash",
            HEX_B,
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["send_preparation_ready"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_decision_receipt() -> dict[str, object]:
    return _base_decision_receipt() | {
        "approval_queue_receipt_valid": True,
        "approval_queue_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "approval_queue_id": "",
        "approval_request_ref": "",
        "required_approver_role": "",
        "approver_ref": "",
        "decision": "",
        "approval_state": "missing",
        "decision_evidence_ref": "",
        "operator_decision_evidence_recorded": False,
        "external_send_authorized_by_decision": False,
        "evidence_refs": [],
        "blocked_until": ["approval_queue_receipt_not_ready"],
        "recovery_actions": ["close TeamOps approval queue evidence before recording an approval decision"],
    }


def _approved_decision_receipt() -> dict[str, object]:
    return _base_decision_receipt() | {
        "approval_queue_receipt_valid": True,
        "approval_queue_receipt_ready": True,
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "required_approver_role": "team_ops_owner",
        "approver_ref": "principal:team-ops-owner",
        "approver_role": "team_ops_owner",
        "decision": "approved",
        "approval_state": "approved",
        "decision_evidence_ref": "approval-decision:aaaaaaaaaaaaaaaa",
        "operator_decision_evidence_recorded": True,
        "external_send_authorized_by_decision": True,
        "evidence_refs": ["approval-decision:aaaaaaaaaaaaaaaa"],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _denied_decision_receipt() -> dict[str, object]:
    return _approved_decision_receipt() | {
        "decision": "denied",
        "approval_state": "denied",
        "external_send_authorized_by_decision": False,
        "decision_evidence_ref": "approval-decision:bbbbbbbbbbbbbbbb",
        "evidence_refs": ["approval-decision:bbbbbbbbbbbbbbbb"],
    }


def _base_decision_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-approval-decision-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_approval_queue_receipt_ref": ".change_assurance/team_ops_shared_inbox_approval_queue_receipt.json",
        "source_approval_queue_receipt_id": "teamops-shared-inbox-approval-queue-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "decided_at": "2026-06-14T00:00:00+00:00",
        "approver_role": "team_ops_owner",
        "decision_reason_ref": "",
        "approval_decision_performed_by_producer": False,
        "requires_separate_send_receipt": True,
        "draft_created_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "raw_message_content_serialized": False,
        "raw_decision_text_serialized": False,
        "no_secret_values_serialized": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
