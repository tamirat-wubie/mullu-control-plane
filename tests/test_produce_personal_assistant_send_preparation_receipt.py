"""Tests for Personal Assistant send-preparation receipt production.

Purpose: prove approved Personal Assistant decisions compose into redacted
send-preparation receipts without draft, send, mailbox write, provider mutation,
memory write, or system-of-record effects.
Governance scope: Personal Assistant send preparation, approval carry-forward,
queue precondition binding, no-effect producer claims, and AwaitingEvidence
defaults.
Dependencies: scripts.produce_personal_assistant_send_preparation_receipt.
Invariants:
  - Ready send preparation requires approved decision evidence and redacted refs.
  - Rejected decisions block preparation.
  - Prepared send evidence still requires a separate send-execution receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_personal_assistant_send_preparation_receipt import (
    DEFAULT_APPROVAL_DECISION,
    main,
    produce_personal_assistant_send_preparation_receipt,
    write_personal_assistant_send_preparation_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_send_preparation_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_personal_assistant_send_preparation_requires_preparation_evidence() -> None:
    receipt = produce_personal_assistant_send_preparation_receipt(
        approval_decision_path=DEFAULT_APPROVAL_DECISION,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.approval_decision_valid is True
    assert receipt.approval_decision_ready is True
    assert receipt.decision == "approved"
    assert receipt.receipt_decision == "deferred"
    assert receipt.source_queue_state == "requested"
    assert receipt.send_preparation_ready is False
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.external_message_sent is False
    assert receipt.connector_mutation_performed is False
    assert receipt.blocked_until == ("send_preparation_evidence_missing",)


def test_personal_assistant_send_preparation_accepts_approved_packet() -> None:
    receipt = produce_personal_assistant_send_preparation_receipt(
        approval_decision_path=DEFAULT_APPROVAL_DECISION,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
        evidence_refs=("send-packet:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.approval_id == "pa_approval_decision_approved_001"
    assert receipt.queue_precondition_sha256
    assert receipt.source_queue_receipt_id.endswith("_request")
    assert receipt.send_preparation_state == "prepared"
    assert receipt.send_preparation_ready is True
    assert receipt.send_preparation_authorized_by_decision is True
    assert receipt.external_send_authorized_by_decision is False
    assert receipt.requires_separate_send_execution_receipt is True
    assert receipt.draft_created_by_producer is False
    assert receipt.external_message_sent is False
    assert receipt.memory_write_performed is False
    assert receipt.blocked_until == ()


def test_personal_assistant_send_preparation_blocks_rejected_decision() -> None:
    receipt = produce_personal_assistant_send_preparation_receipt(
        approval_decision_path=DEFAULT_APPROVAL_DECISION,
        schema_path=SCHEMA_PATH,
        approval_id="pa_approval_decision_rejected_002",
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.approval_decision_ready is False
    assert receipt.decision == ""
    assert receipt.send_preparation_state == "not_authorized"
    assert receipt.send_preparation_ready is False
    assert receipt.external_message_sent is False
    assert receipt.blocked_until == ("approval_decision_not_approved",)


def test_personal_assistant_send_preparation_rejects_secret_marker_ref() -> None:
    try:
        produce_personal_assistant_send_preparation_receipt(
            approval_decision_path=DEFAULT_APPROVAL_DECISION,
            schema_path=SCHEMA_PATH,
            prepared_at="2026-06-14T00:00:00+00:00",
            send_preparation_ref="client_secret=must-not-serialize",
            prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
            recipient_hash=HEX_A,
            prepared_message_hash=HEX_B,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret-like value" in message
    assert "must-not-serialize" not in message


def test_personal_assistant_send_preparation_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "personal_assistant_send_preparation_receipt.json"
    receipt = produce_personal_assistant_send_preparation_receipt(
        approval_decision_path=DEFAULT_APPROVAL_DECISION,
        schema_path=SCHEMA_PATH,
        prepared_at="2026-06-14T00:00:00+00:00",
        send_preparation_ref="send-preparation:aaaaaaaaaaaaaaaa",
        prepared_message_ref="prepared-message:aaaaaaaaaaaaaaaa",
        recipient_hash=HEX_A,
        prepared_message_hash=HEX_B,
    )

    written = write_personal_assistant_send_preparation_receipt(receipt, output_path)
    exit_code = main(
        [
            "--approval-decision",
            str(DEFAULT_APPROVAL_DECISION),
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
    assert payload["external_message_sent"] is False
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""
