"""Tests for TeamOps terminal closure review packet validation.

Purpose: prove the TeamOps terminal closure review validator rejects raw
payloads, local effect claims, malformed hashes, production overclaims, and
certificate-minting claims.
Governance scope: TeamOps terminal closure review, replay evidence,
duplicate-action protection, redaction, and no-terminal-closure-overclaim.
Dependencies: scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet.
Invariants:
  - Ready review packets require complete sent-message observation evidence.
  - Review readiness is not terminal certificate minting.
  - Raw message/provider fields and producer effect claims are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (
    main,
    validate_team_ops_shared_inbox_terminal_closure_review_packet,
    write_team_ops_shared_inbox_terminal_closure_review_packet_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_review_packet.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_terminal_closure_review_validator_accepts_blocked_packet(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet_path.write_text(json.dumps(_blocked_packet()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is True
    assert validation.ready is False
    assert validation.status == "blocked"
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.proof_state == "Unknown"
    assert validation.terminal_closure_certificate_required is True
    assert validation.blocked_until == ("sent_message_observation_receipt_not_ready",)
    assert validation.errors == ()


def test_team_ops_terminal_closure_review_validator_require_ready_rejects_blocked(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet_path.write_text(json.dumps(_blocked_packet()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.status == "blocked"
    assert "TeamOps terminal closure review packet ready must be true" in validation.errors
    assert validation.next_action == "record ready TeamOps sent-message observation evidence before terminal closure review"


def test_team_ops_terminal_closure_review_validator_accepts_ready_packet(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet_path.write_text(json.dumps(_ready_packet()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.status == "passed"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.proof_state == "Pass"
    assert validation.required_terminal_evidence_count == 8
    assert validation.closure_review_ready is True
    assert validation.terminal_closure_candidate_ready is True
    assert validation.next_action == "mint TeamOps terminal closure certificate from reviewed packet"


def test_team_ops_terminal_closure_review_validator_rejects_certificate_mint_claim(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet = _ready_packet() | {"terminal_closure_certificate_minted_by_producer": True}
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "terminal_closure_certificate_minted_by_producer must be false" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_terminal_closure_review_validator_rejects_raw_provider_field(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet = _ready_packet() | {"provider_message_id": "raw-provider-id"}
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "packet must not serialize raw field: provider_message_id" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_terminal_closure_review_validator_rejects_bad_review_hash(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet = _ready_packet() | {"review_packet_hash": "not-a-sha"}
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "passed packet requires review_packet_hash sha256 hex" in validation.errors
    assert len(validation.errors) >= 1


def test_team_ops_terminal_closure_review_validator_rejects_secret_marker(tmp_path: Path) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    packet = _ready_packet() | {"review_packet_ref": "client_secret=blocked"}
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "packet must not serialize secret marker: client_secret=" in validation.errors
    assert "client_secret=blocked" not in json.dumps(validation.as_dict(), sort_keys=True)


def test_team_ops_terminal_closure_review_validator_cli_writes_validation(tmp_path: Path, capsys) -> None:
    packet_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet_validation.json"
    packet_path.write_text(json.dumps(_ready_packet()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    written = write_team_ops_shared_inbox_terminal_closure_review_packet_validation(validation, output_path)
    exit_code = main(
        [
            "--packet",
            str(packet_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def test_team_ops_terminal_closure_review_validator_missing_path_is_bounded(tmp_path: Path) -> None:
    packet_path = tmp_path / "missing_team_ops_shared_inbox_terminal_closure_review_packet.json"

    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.receipt_id == ""
    assert validation.errors == ("TeamOps terminal closure review packet file missing",)
    assert validation.next_action == "regenerate TeamOps terminal closure review packet"


def _blocked_packet() -> dict[str, object]:
    return _base_packet() | {
        "sent_message_observation_receipt_valid": True,
        "sent_message_observation_receipt_ready": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "closure_review_state": "missing",
        "closure_review_ready": False,
        "terminal_closure_candidate_ready": False,
        "review_packet_ref": "",
        "review_packet_hash": "",
        "send_execution_ref": "",
        "dispatch_receipt_ref": "",
        "provider_message_ref": "",
        "provider_message_hash": "",
        "first_observation_ref": "",
        "first_observation_hash": "",
        "second_observation_ref": "",
        "second_observation_hash": "",
        "duplicate_absence_observed": False,
        "replay_ref": "",
        "replay_hash": "",
        "deterministic_replay_observed": False,
        "required_terminal_evidence_refs": [],
        "approval_chain_reviewed": False,
        "send_execution_reviewed": False,
        "sent_message_observation_reviewed": False,
        "duplicate_absence_reviewed": False,
        "deterministic_replay_reviewed": False,
        "evidence_refs": [],
        "blocked_until": ["sent_message_observation_receipt_not_ready"],
        "recovery_actions": ["record ready TeamOps sent-message observation evidence before terminal closure review"],
    }


def _ready_packet() -> dict[str, object]:
    evidence_refs = [
        ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
        "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider-message:aaaaaaaaaaaaaaaa",
        "sent-observation:first",
        "sent-observation:second",
        "sent-message-replay:aaaaaaaaaaaaaaaa",
        "duplicate-check:aaaaaaaaaaaaaaaa",
    ]
    return _base_packet() | {
        "sent_message_observation_receipt_valid": True,
        "sent_message_observation_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "closure_review_state": "assembled",
        "closure_review_ready": True,
        "terminal_closure_candidate_ready": True,
        "review_packet_ref": "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa",
        "review_packet_hash": HEX_B,
        "send_execution_ref": "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch_receipt_ref": "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider_message_ref": "provider-message:aaaaaaaaaaaaaaaa",
        "provider_message_hash": HEX_A,
        "first_observation_ref": "sent-observation:first",
        "first_observation_hash": HEX_A,
        "second_observation_ref": "sent-observation:second",
        "second_observation_hash": HEX_A,
        "duplicate_absence_observed": True,
        "replay_ref": "sent-message-replay:aaaaaaaaaaaaaaaa",
        "replay_hash": HEX_B,
        "deterministic_replay_observed": True,
        "required_terminal_evidence_refs": evidence_refs,
        "approval_chain_reviewed": True,
        "send_execution_reviewed": True,
        "sent_message_observation_reviewed": True,
        "duplicate_absence_reviewed": True,
        "deterministic_replay_reviewed": True,
        "evidence_refs": evidence_refs,
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_packet() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-terminal-closure-review-packet-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_sent_message_observation_receipt_ref": (
            ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json"
        ),
        "source_sent_message_observation_receipt_id": (
            "teamops-shared-inbox-sent-message-observation-receipt-aaaaaaaaaaaaaaaa"
        ),
        "reviewed_at": "2026-06-14T00:00:00+00:00",
        "terminal_closure_certificate_required": True,
        "review_performed_by_producer": False,
        "terminal_closure_certificate_minted_by_producer": False,
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
        "production_ready_claimed": False,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
