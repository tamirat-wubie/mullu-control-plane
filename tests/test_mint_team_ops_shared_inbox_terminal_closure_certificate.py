"""Tests for TeamOps terminal closure certificate minting.

Purpose: prove TeamOps terminal certificates are minted only from ready review
packets and remain canonical terminal-closure schema artifacts.
Governance scope: TeamOps terminal closure, evidence binding, replay binding,
duplicate-action protection, redaction, and no-production-claim constraints.
Dependencies: scripts.mint_team_ops_shared_inbox_terminal_closure_certificate.
Invariants:
  - A blocked review packet mints no certificate.
  - A ready review packet mints a schema-valid committed certificate.
  - The minting producer records no provider, mailbox, draft, or send effect.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (
    main,
    mint_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_certificate import (
    validate_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.validate_terminal_closure_certificate import validate_terminal_closure_certificate


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_terminal_closure_certificate_blocks_unready_review(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    review_path.write_text(json.dumps(_blocked_review_packet()), encoding="utf-8")

    try:
        mint_team_ops_shared_inbox_terminal_closure_certificate(
            review_packet_path=review_path,
            schema_path=SCHEMA_PATH,
            closed_at="2026-06-14T00:00:00+00:00",
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        message = ""

    assert "not ready" in message
    assert "certificate" in message
    assert "secret" not in message


def test_team_ops_terminal_closure_certificate_mints_ready_review(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")

    certificate = mint_team_ops_shared_inbox_terminal_closure_certificate(
        review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
        closed_at="2026-06-14T00:00:00+00:00",
    )
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    write_team_ops_shared_inbox_terminal_closure_certificate(certificate, certificate_path)
    generic_validation = validate_terminal_closure_certificate(certificate_path=certificate_path)
    teamops_validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert certificate["certificate_id"].startswith("teamops-shared-inbox-terminal-closure-certificate-")
    assert certificate["command_id"] == "team_ops.shared_inbox_triage"
    assert certificate["disposition"] == "committed"
    assert certificate["verification_result_id"] == "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa"
    assert certificate["effect_reconciliation_id"] == "teamops-effect-reconciliation:" + HEX_B[:16]
    assert certificate["metadata"]["terminal_proof"] is True
    assert certificate["metadata"]["provider_call_performed_by_minting_producer"] is False
    assert certificate["metadata"]["production_ready_claimed"] is False
    assert len(certificate["evidence_refs"]) >= 9
    assert generic_validation.valid is True
    assert teamops_validation.valid is True
    assert teamops_validation.ready is True


def test_team_ops_terminal_closure_certificate_rejects_secret_marker_review(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    review_path.write_text(
        json.dumps(_ready_review_packet() | {"review_packet_ref": "client_secret=must-not-serialize"}),
        encoding="utf-8",
    )

    try:
        mint_team_ops_shared_inbox_terminal_closure_certificate(
            review_packet_path=review_path,
            schema_path=SCHEMA_PATH,
            closed_at="2026-06-14T00:00:00+00:00",
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        message = ""

    assert "not ready" in message
    assert "client_secret=must-not-serialize" not in message
    assert "certificate" in message


def test_team_ops_terminal_closure_certificate_cli_writes_certificate(tmp_path: Path, capsys) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")

    exit_code = main(
        [
            "--review-packet",
            str(review_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--closed-at",
            "2026-06-14T00:00:00+00:00",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert file_payload["certificate_id"] == stdout_payload["certificate_id"]
    assert file_payload["disposition"] == "committed"
    assert file_payload["metadata"]["team_ops_terminal_closure"] is True
    assert file_payload["metadata"]["external_message_sent_by_minting_producer"] is False
    assert captured.err == ""


def _blocked_review_packet() -> dict[str, object]:
    return _base_review_packet() | {
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


def _ready_review_packet() -> dict[str, object]:
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
    return _base_review_packet() | {
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


def _base_review_packet() -> dict[str, object]:
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
