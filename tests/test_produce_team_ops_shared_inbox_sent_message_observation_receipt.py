"""Tests for TeamOps sent-message observation receipt production.

Purpose: prove TeamOps send-execution evidence composes into redacted
sent-message observation and replay receipts without local provider calls.
Governance scope: TeamOps send closure, two-observation safety, replay binding,
duplicate-action protection, and no-local-provider mutation claims.
Dependencies: scripts.produce_team_ops_shared_inbox_sent_message_observation_receipt.
Invariants:
  - Blocked send-execution evidence keeps observation blocked.
  - Ready observation requires two matching provider observations and replay.
  - The receipt producer never performs provider reads, writes, or sends.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_sent_message_observation_receipt import (
    main,
    produce_team_ops_shared_inbox_sent_message_observation_receipt,
    write_team_ops_shared_inbox_sent_message_observation_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_sent_message_observation_receipt.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def test_team_ops_sent_message_observation_blocks_without_send_execution_ready(
    tmp_path: Path,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    execution_path.write_text(json.dumps(_blocked_send_execution_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
        send_execution_receipt_path=execution_path,
        schema_path=SCHEMA_PATH,
        observed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.send_execution_receipt_valid is True
    assert receipt.send_execution_receipt_ready is False
    assert receipt.sent_message_observation_ready is False
    assert receipt.workflow_closure_ready is False
    assert receipt.provider_call_performed_by_producer is False
    assert receipt.provider_mutation_performed_by_producer is False
    assert receipt.blocked_until == ("send_execution_receipt_not_ready",)


def test_team_ops_sent_message_observation_requires_observation_and_replay_evidence(
    tmp_path: Path,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    execution_path.write_text(json.dumps(_ready_send_execution_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
        send_execution_receipt_path=execution_path,
        schema_path=SCHEMA_PATH,
        observed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.send_execution_receipt_ready is True
    assert receipt.send_execution_ref == "send-execution:aaaaaaaaaaaaaaaa"
    assert receipt.provider_message_hash == HEX_A
    assert receipt.sent_message_observation_state == "missing"
    assert receipt.sent_message_observation_ready is False
    assert receipt.observation_count == 0
    assert receipt.workflow_closure_ready is False
    assert receipt.blocked_until == ("sent_message_observation_or_replay_evidence_missing",)


def test_team_ops_sent_message_observation_accepts_two_observations_and_replay(
    tmp_path: Path,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    execution_path.write_text(json.dumps(_ready_send_execution_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
        send_execution_receipt_path=execution_path,
        schema_path=SCHEMA_PATH,
        observed_at="2026-06-14T00:00:00+00:00",
        first_observation_ref="sent-observation:first",
        first_observation_hash=HEX_A,
        second_observation_ref="sent-observation:second",
        second_observation_hash=HEX_A,
        duplicate_absence_observed=True,
        replay_ref="sent-message-replay:aaaaaaaaaaaaaaaa",
        replay_hash=HEX_B,
        deterministic_replay_observed=True,
        evidence_refs=("duplicate-check:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.sent_message_observation_state == "observed"
    assert receipt.sent_message_observation_ready is True
    assert receipt.observation_count == 2
    assert receipt.provider_state_consistent is True
    assert receipt.provider_message_hash_matches_execution is True
    assert receipt.duplicate_absence_observed is True
    assert receipt.deterministic_replay_observed is True
    assert receipt.workflow_closure_ready is True
    assert receipt.observation_performed_by_producer is False
    assert receipt.blocked_until == ()


def test_team_ops_sent_message_observation_blocks_hash_mismatch(
    tmp_path: Path,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    execution_path.write_text(json.dumps(_ready_send_execution_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
        send_execution_receipt_path=execution_path,
        schema_path=SCHEMA_PATH,
        observed_at="2026-06-14T00:00:00+00:00",
        first_observation_ref="sent-observation:first",
        first_observation_hash=HEX_A,
        second_observation_ref="sent-observation:second",
        second_observation_hash=HEX_C,
        duplicate_absence_observed=True,
        replay_ref="sent-message-replay:aaaaaaaaaaaaaaaa",
        replay_hash=HEX_B,
        deterministic_replay_observed=True,
        evidence_refs=("duplicate-check:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "failed"
    assert receipt.solver_outcome == "GovernanceBlocked"
    assert receipt.proof_state == "Fail"
    assert receipt.sent_message_observation_state == "inconsistent"
    assert receipt.workflow_closure_ready is False
    assert receipt.blocked_until == ("sent_message_observation_hash_mismatch",)


def test_team_ops_sent_message_observation_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    execution_path.write_text(json.dumps(_ready_send_execution_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_sent_message_observation_receipt(
            send_execution_receipt_path=execution_path,
            schema_path=SCHEMA_PATH,
            observed_at="2026-06-14T00:00:00+00:00",
            first_observation_ref="client_secret=must-not-serialize",
            first_observation_hash=HEX_A,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_sent_message_observation_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    execution_path = tmp_path / "team_ops_shared_inbox_send_execution_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    execution_path.write_text(json.dumps(_ready_send_execution_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
        send_execution_receipt_path=execution_path,
        schema_path=SCHEMA_PATH,
        observed_at="2026-06-14T00:00:00+00:00",
        first_observation_ref="sent-observation:first",
        first_observation_hash=HEX_A,
        second_observation_ref="sent-observation:second",
        second_observation_hash=HEX_A,
        duplicate_absence_observed=True,
        replay_ref="sent-message-replay:aaaaaaaaaaaaaaaa",
        replay_hash=HEX_B,
        deterministic_replay_observed=True,
    )

    written = write_team_ops_shared_inbox_sent_message_observation_receipt(receipt, output_path)
    exit_code = main(
        [
            "--send-execution-receipt",
            str(execution_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--observed-at",
            "2026-06-14T00:00:00+00:00",
            "--first-observation-ref",
            "sent-observation:first",
            "--first-observation-hash",
            HEX_A,
            "--second-observation-ref",
            "sent-observation:second",
            "--second-observation-hash",
            HEX_A,
            "--duplicate-absence-observed",
            "--replay-ref",
            "sent-message-replay:aaaaaaaaaaaaaaaa",
            "--replay-hash",
            HEX_B,
            "--deterministic-replay-observed",
            "--evidence-ref",
            "duplicate-check:aaaaaaaaaaaaaaaa",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["workflow_closure_ready"] is True
    assert payload["provider_call_performed_by_producer"] is False
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_send_execution_receipt() -> dict[str, object]:
    return _base_send_execution_receipt() | {
        "send_preparation_receipt_valid": True,
        "send_preparation_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "send_execution_state": "missing",
        "send_execution_ready": False,
        "send_execution_ref": "",
        "dispatch_receipt_ref": "",
        "provider_message_ref": "",
        "provider_message_hash": "",
        "dispatch_receipt_hash": "",
        "send_execution_observed": False,
        "external_message_sent": False,
        "evidence_refs": [],
        "blocked_until": ["send_preparation_receipt_not_ready"],
        "recovery_actions": ["record ready TeamOps send-preparation evidence before admitting send execution evidence"],
    }


def _ready_send_execution_receipt() -> dict[str, object]:
    return _base_send_execution_receipt() | {
        "send_preparation_receipt_valid": True,
        "send_preparation_receipt_ready": True,
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "send_execution_state": "sent",
        "send_execution_ready": True,
        "send_execution_ref": "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_ref": "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider_message_ref": "provider-message:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_hash": HEX_B,
        "provider_message_hash": HEX_A,
        "send_execution_observed": True,
        "external_message_sent": True,
        "evidence_refs": [
            "send-execution:aaaaaaaaaaaaaaaa",
            "dispatch-receipt:aaaaaaaaaaaaaaaa",
            "provider-message:aaaaaaaaaaaaaaaa",
        ],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_send_execution_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-send-execution-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_send_preparation_receipt_ref": ".change_assurance/team_ops_shared_inbox_send_preparation_receipt.json",
        "source_send_preparation_receipt_id": "teamops-shared-inbox-send-preparation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "executed_at": "2026-06-14T00:00:00+00:00",
        "approval_queue_id": "team_ops.external_send_approval",
        "approval_request_ref": "approval-request:teamops-123",
        "approval_decision_ref": "approval-decision:aaaaaaaaaaaaaaaa",
        "approver_ref": "principal:team-ops-owner",
        "decision": "approved",
        "approval_state": "approved",
        "external_send_authorized_by_decision": True,
        "send_preparation_ref": "send-preparation:aaaaaaaaaaaaaaaa",
        "prepared_message_ref": "prepared-message:aaaaaaaaaaaaaaaa",
        "thread_ref": "thread:teamops-123",
        "recipient_hash": HEX_A,
        "prepared_message_hash": HEX_B,
        "send_execution_performed_by_producer": False,
        "external_message_sent_by_producer": False,
        "external_mailbox_write_performed_by_producer": False,
        "provider_mutation_performed_by_producer": False,
        "provider_call_performed_by_producer": False,
        "draft_created_by_producer": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "no_secret_values_serialized": True,
        "requires_sent_message_observation_receipt": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_send_execution_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
