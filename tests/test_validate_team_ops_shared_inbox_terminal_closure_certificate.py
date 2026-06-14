"""Tests for TeamOps terminal closure certificate validation.

Purpose: prove TeamOps terminal certificates reject generic, drifted, raw,
production-claiming, or unbound closure artifacts.
Governance scope: TeamOps terminal closure, source-review binding, evidence
completeness, redaction, and no-effect/no-production-claim constraints.
Dependencies: scripts.validate_team_ops_shared_inbox_terminal_closure_certificate.
Invariants:
  - A valid TeamOps certificate binds the ready review packet.
  - Generic terminal certificates are insufficient for TeamOps closure.
  - Raw fields, secret markers, and production claims are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_team_ops_shared_inbox_terminal_closure_certificate import (
    main,
    validate_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64


def test_team_ops_terminal_closure_certificate_validator_accepts_ready_certificate(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate_path.write_text(json.dumps(_ready_certificate()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.disposition == "committed"
    assert validation.certificate_id == "teamops-shared-inbox-terminal-closure-certificate-aaaaaaaaaaaaaaaa"
    assert validation.source_review_packet_id == "teamops-shared-inbox-terminal-closure-review-packet-aaaaaaaaaaaaaaaa"
    assert validation.evidence_ref_count >= 9
    assert validation.next_action == "bind TeamOps terminal closure certificate into signed evidence bundle"


def test_team_ops_terminal_closure_certificate_validator_rejects_generic_certificate(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate_path.write_text(
        json.dumps(
            {
                "certificate_id": "terminal-closure-example-1",
                "command_id": "command-example-1",
                "execution_id": "execution-example-1",
                "disposition": "committed",
                "verification_result_id": "verification-example-1",
                "effect_reconciliation_id": "reconciliation-example-1",
                "evidence_refs": ["proof://verification/example", "proof://reconciliation/example"],
                "closed_at": "2026-06-14T00:00:00+00:00",
                "response_closure_ref": "proof://response/example",
                "metadata": {"source": "public-schema-example", "terminal_proof": True},
            }
        ),
        encoding="utf-8",
    )

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "certificate_id must match TeamOps terminal closure certificate pattern" in validation.errors
    assert "command_id must bind TeamOps shared inbox workflow" in validation.errors
    assert "TeamOps terminal closure certificate requires at least nine evidence refs" in validation.errors


def test_team_ops_terminal_closure_certificate_validator_rejects_review_hash_drift(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet() | {"review_packet_hash": "c" * 64}), encoding="utf-8")
    certificate_path.write_text(json.dumps(_ready_certificate()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "metadata.source_review_packet_hash must match review packet hash" in validation.errors
    assert "effect_reconciliation_id must derive from review packet hash" in validation.errors


def test_team_ops_terminal_closure_certificate_validator_rejects_raw_field(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = _ready_certificate()
    certificate["metadata"]["provider_message_id"] = "raw-provider-id"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "certificate must not serialize raw field: provider_message_id" in validation.errors


def test_team_ops_terminal_closure_certificate_validator_rejects_production_claim(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = _ready_certificate()
    certificate["metadata"]["production_ready_claimed"] = True
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "metadata.production_ready_claimed must be false" in validation.errors


def test_team_ops_terminal_closure_certificate_validator_rejects_secret_marker(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = _ready_certificate()
    certificate["metadata"]["source_review_packet_ref"] = "client_secret=blocked"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "certificate must not serialize secret marker: client_secret=" in validation.errors
    assert "client_secret=blocked" not in json.dumps(validation.as_dict(), sort_keys=True)


def test_team_ops_terminal_closure_certificate_validator_missing_path_is_bounded(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "missing_team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps terminal closure certificate file missing" in validation.errors
    assert validation.next_action == "regenerate TeamOps terminal closure certificate from ready review packet"


def test_team_ops_terminal_closure_certificate_validator_cli_writes_validation(tmp_path: Path, capsys) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate_validation.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate_path.write_text(json.dumps(_ready_certificate()), encoding="utf-8")
    validation = validate_team_ops_shared_inbox_terminal_closure_certificate(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=SCHEMA_PATH,
        require_ready=True,
    )

    written = write_team_ops_shared_inbox_terminal_closure_certificate_validation(validation, output_path)
    exit_code = main(
        [
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert file_payload["valid"] is True
    assert file_payload["ready"] is True
    assert stdout_payload["certificate_id"] == file_payload["certificate_id"]
    assert captured.err == ""


def _ready_certificate() -> dict[str, object]:
    evidence_refs = [
        "team_ops_shared_inbox_terminal_closure_review_packet.json",
        "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa",
        ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json",
        ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
        "send-execution:aaaaaaaaaaaaaaaa",
        "dispatch-receipt:aaaaaaaaaaaaaaaa",
        "provider-message:aaaaaaaaaaaaaaaa",
        "sent-observation:first",
        "sent-observation:second",
        "sent-message-replay:aaaaaaaaaaaaaaaa",
        "duplicate-check:aaaaaaaaaaaaaaaa",
    ]
    return {
        "certificate_id": "teamops-shared-inbox-terminal-closure-certificate-aaaaaaaaaaaaaaaa",
        "command_id": "team_ops.shared_inbox_triage",
        "execution_id": "teamops-shared-inbox-terminal-closure-review-packet-aaaaaaaaaaaaaaaa",
        "disposition": "committed",
        "verification_result_id": "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa",
        "effect_reconciliation_id": "teamops-effect-reconciliation:" + HEX_B[:16],
        "evidence_refs": evidence_refs,
        "closed_at": "2026-06-14T00:00:00+00:00",
        "response_closure_ref": "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa",
        "memory_entry_id": None,
        "compensation_outcome_id": None,
        "accepted_risk_id": None,
        "case_id": None,
        "graph_refs": [
            "workflow:team_ops.shared_inbox_triage",
            "review_packet:teamops-shared-inbox-terminal-closure-review-packet-aaaaaaaaaaaaaaaa",
            "send_execution:send-execution:aaaaaaaaaaaaaaaa",
            "dispatch_receipt:dispatch-receipt:aaaaaaaaaaaaaaaa",
            "provider_message:provider-message:aaaaaaaaaaaaaaaa",
            "first_observation:sent-observation:first",
            "second_observation:sent-observation:second",
            "replay:sent-message-replay:aaaaaaaaaaaaaaaa",
        ],
        "metadata": {
            "source": "team_ops_shared_inbox_terminal_closure_certificate",
            "terminal_proof": True,
            "team_ops_terminal_closure": True,
            "source_review_packet_id": "teamops-shared-inbox-terminal-closure-review-packet-aaaaaaaaaaaaaaaa",
            "source_review_packet_ref": "teamops-terminal-closure-review:aaaaaaaaaaaaaaaa",
            "source_review_packet_hash": HEX_B,
            "source_review_packet_path": "team_ops_shared_inbox_terminal_closure_review_packet.json",
            "source_sent_message_observation_receipt_id": (
                "teamops-shared-inbox-sent-message-observation-receipt-aaaaaaaaaaaaaaaa"
            ),
            "source_sent_message_observation_receipt_ref": (
                ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json"
            ),
            "approval_chain_reviewed": True,
            "send_execution_reviewed": True,
            "sent_message_observation_reviewed": True,
            "duplicate_absence_reviewed": True,
            "deterministic_replay_reviewed": True,
            "duplicate_absence_observed": True,
            "deterministic_replay_observed": True,
            "external_message_sent_by_minting_producer": False,
            "external_mailbox_write_performed_by_minting_producer": False,
            "provider_mutation_performed_by_minting_producer": False,
            "provider_call_performed_by_minting_producer": False,
            "draft_created_by_minting_producer": False,
            "raw_message_content_serialized": False,
            "raw_provider_payload_serialized": False,
            "no_secret_values_serialized": True,
            "production_ready_claimed": False,
            "terminal_certificate_schema_id": "urn:mullusi:schema:terminal-closure-certificate:1",
        },
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
        "sent_message_observation_receipt_valid": True,
        "sent_message_observation_receipt_ready": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "reviewed_at": "2026-06-14T00:00:00+00:00",
        "closure_review_state": "assembled",
        "closure_review_ready": True,
        "terminal_closure_candidate_ready": True,
        "terminal_closure_certificate_required": True,
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
        "evidence_refs": evidence_refs,
        "blocked_until": [],
        "recovery_actions": [],
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
