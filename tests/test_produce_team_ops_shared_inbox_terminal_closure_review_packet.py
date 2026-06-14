"""Tests for TeamOps terminal closure review packet production.

Purpose: prove TeamOps sent-message observation evidence composes into a
redacted terminal closure review packet without minting terminal closure.
Governance scope: TeamOps closure review, evidence binding, replay binding,
duplicate-action protection, and no-effect/no-production-claim constraints.
Dependencies: scripts.produce_team_ops_shared_inbox_terminal_closure_review_packet.
Invariants:
  - Blocked sent-message observation keeps terminal review blocked.
  - Ready terminal review requires complete redacted evidence refs and hashes.
  - The producer never performs provider effects or mints a closure certificate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_terminal_closure_review_packet import (
    main,
    produce_team_ops_shared_inbox_terminal_closure_review_packet,
    write_team_ops_shared_inbox_terminal_closure_review_packet,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_review_packet.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_terminal_closure_review_blocks_without_observation_ready(tmp_path: Path) -> None:
    observation_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    observation_path.write_text(json.dumps(_blocked_observation_receipt()), encoding="utf-8")

    packet = produce_team_ops_shared_inbox_terminal_closure_review_packet(
        sent_message_observation_receipt_path=observation_path,
        schema_path=SCHEMA_PATH,
        reviewed_at="2026-06-14T00:00:00+00:00",
    )

    assert packet.status == "blocked"
    assert packet.solver_outcome == "AwaitingEvidence"
    assert packet.proof_state == "Unknown"
    assert packet.sent_message_observation_receipt_valid is True
    assert packet.sent_message_observation_receipt_ready is False
    assert packet.closure_review_ready is False
    assert packet.terminal_closure_candidate_ready is False
    assert packet.terminal_closure_certificate_required is True
    assert packet.terminal_closure_certificate_minted_by_producer is False
    assert packet.production_ready_claimed is False
    assert packet.blocked_until == ("sent_message_observation_receipt_not_ready",)


def test_team_ops_terminal_closure_review_accepts_ready_observation(tmp_path: Path) -> None:
    observation_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    observation_path.write_text(json.dumps(_ready_observation_receipt()), encoding="utf-8")

    packet = produce_team_ops_shared_inbox_terminal_closure_review_packet(
        sent_message_observation_receipt_path=observation_path,
        schema_path=SCHEMA_PATH,
        reviewed_at="2026-06-14T00:00:00+00:00",
    )

    assert packet.status == "passed"
    assert packet.solver_outcome == "SolvedVerified"
    assert packet.proof_state == "Pass"
    assert packet.closure_review_state == "assembled"
    assert packet.closure_review_ready is True
    assert packet.terminal_closure_candidate_ready is True
    assert packet.review_packet_ref.startswith("teamops-terminal-closure-review:")
    assert len(packet.review_packet_hash) == 64
    assert len(packet.required_terminal_evidence_refs) >= 8
    assert packet.approval_chain_reviewed is True
    assert packet.sent_message_observation_reviewed is True
    assert packet.report_is_not_terminal_closure is True
    assert packet.blocked_until == ()


def test_team_ops_terminal_closure_review_rejects_secret_marker_ref(tmp_path: Path) -> None:
    observation_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    observation_path.write_text(json.dumps(_ready_observation_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_terminal_closure_review_packet(
            sent_message_observation_receipt_path=observation_path,
            schema_path=SCHEMA_PATH,
            reviewed_at="2026-06-14T00:00:00+00:00",
            evidence_refs=("client_secret=must-not-serialize",),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_terminal_closure_review_cli_writes_packet(tmp_path: Path, capsys) -> None:
    observation_path = tmp_path / "team_ops_shared_inbox_sent_message_observation_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    observation_path.write_text(json.dumps(_ready_observation_receipt()), encoding="utf-8")
    packet = produce_team_ops_shared_inbox_terminal_closure_review_packet(
        sent_message_observation_receipt_path=observation_path,
        schema_path=SCHEMA_PATH,
        reviewed_at="2026-06-14T00:00:00+00:00",
    )

    written = write_team_ops_shared_inbox_terminal_closure_review_packet(packet, output_path)
    exit_code = main(
        [
            "--sent-message-observation-receipt",
            str(observation_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--reviewed-at",
            "2026-06-14T00:00:00+00:00",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["terminal_closure_candidate_ready"] is True
    assert payload["terminal_closure_certificate_minted_by_producer"] is False
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_observation_receipt() -> dict[str, object]:
    return _base_observation_receipt() | {
        "send_execution_receipt_valid": True,
        "send_execution_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "send_execution_ref": "",
        "dispatch_receipt_ref": "",
        "provider_message_ref": "",
        "provider_message_hash": "",
        "sent_message_observation_state": "missing",
        "sent_message_observation_ready": False,
        "first_observation_ref": "",
        "first_observation_hash": "",
        "second_observation_ref": "",
        "second_observation_hash": "",
        "observation_count": 0,
        "provider_state_consistent": False,
        "provider_message_hash_matches_execution": False,
        "duplicate_absence_observed": False,
        "replay_ref": "",
        "replay_hash": "",
        "deterministic_replay_observed": False,
        "workflow_closure_ready": False,
        "evidence_refs": [],
        "blocked_until": ["send_execution_receipt_not_ready"],
        "recovery_actions": ["record ready TeamOps send-execution evidence before observing sent-message closure"],
    }


def _ready_observation_receipt() -> dict[str, object]:
    return _base_observation_receipt() | {
        "send_execution_receipt_valid": True,
        "send_execution_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "send_execution_ref": "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_ref": "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider_message_ref": "provider-message:aaaaaaaaaaaaaaaa",
        "provider_message_hash": HEX_A,
        "sent_message_observation_state": "observed",
        "sent_message_observation_ready": True,
        "first_observation_ref": "sent-observation:first",
        "first_observation_hash": HEX_A,
        "second_observation_ref": "sent-observation:second",
        "second_observation_hash": HEX_A,
        "observation_count": 2,
        "provider_state_consistent": True,
        "provider_message_hash_matches_execution": True,
        "duplicate_absence_observed": True,
        "replay_ref": "sent-message-replay:aaaaaaaaaaaaaaaa",
        "replay_hash": HEX_B,
        "deterministic_replay_observed": True,
        "workflow_closure_ready": True,
        "evidence_refs": [
            "sent-observation:first",
            "sent-observation:second",
            "sent-message-replay:aaaaaaaaaaaaaaaa",
            "duplicate-check:aaaaaaaaaaaaaaaa",
        ],
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_observation_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-sent-message-observation-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_send_execution_receipt_ref": ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
        "source_send_execution_receipt_id": "teamops-shared-inbox-send-execution-receipt-aaaaaaaaaaaaaaaa",
        "observed_at": "2026-06-14T00:00:00+00:00",
        "observation_performed_by_producer": False,
        "external_message_sent_by_producer": False,
        "external_mailbox_write_performed_by_producer": False,
        "provider_mutation_performed_by_producer": False,
        "provider_call_performed_by_producer": False,
        "draft_created_by_producer": False,
        "raw_message_content_serialized": False,
        "raw_recipient_serialized": False,
        "raw_subject_serialized": False,
        "raw_body_serialized": False,
        "raw_provider_payload_serialized": False,
        "no_secret_values_serialized": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
