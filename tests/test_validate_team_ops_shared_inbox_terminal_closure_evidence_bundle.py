"""Tests for TeamOps terminal closure evidence bundle validation.

Purpose: prove signed TeamOps trust-ledger bundles reject HMAC drift,
certificate mismatch, raw fields, production claims, and missing evidence.
Governance scope: TeamOps bundle verification, source-certificate binding,
proof-ref enforcement, redaction, and no-effect/no-production-claim checks.
Dependencies: scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.
Invariants:
  - A ready bundle verifies against the signing secret and source certificate.
  - Wrong secrets or source-certificate drift fail closed.
  - Raw fields, secret markers, and production claims are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (
    mint_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    produce_team_ops_shared_inbox_terminal_closure_evidence_bundle,
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    main,
    validate_team_ops_shared_inbox_terminal_closure_evidence_bundle,
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle_validation,
)


ROOT = Path(__file__).resolve().parent.parent
CERTIFICATE_SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
SIGNING_SECRET = "teamops-bundle-test-secret"


def test_team_ops_terminal_closure_evidence_bundle_validator_accepts_ready_bundle(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.command_id == "team_ops.shared_inbox_triage"
    assert validation.terminal_certificate_id.startswith("teamops-shared-inbox-terminal-closure-certificate-")
    assert validation.evidence_ref_count >= 9
    assert validation.signature_key_id == "teamops-local-trust-ledger-key"
    assert validation.next_action == "prepare TeamOps terminal closure evidence bundle for external anchor preflight"


def test_team_ops_terminal_closure_evidence_bundle_validator_rejects_wrong_secret(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret="wrong-secret",
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "trust ledger verification failed: signature_mismatch" in validation.errors
    assert SIGNING_SECRET not in json.dumps(validation.as_dict(), sort_keys=True)


def test_team_ops_terminal_closure_evidence_bundle_validator_rejects_certificate_drift(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["certificate_id"] = "teamops-shared-inbox-terminal-closure-certificate-bbbbbbbbbbbbbbbb"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "terminal_certificate_id must match source certificate id" in validation.errors
    assert any(error.startswith("evidence_refs must include proof://teamops/terminal-certificate/") for error in validation.errors)


def test_team_ops_terminal_closure_evidence_bundle_validator_rejects_raw_field(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["metadata"]["provider_message_id"] = "raw-provider-id"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "bundle must not serialize raw field: provider_message_id" in validation.errors
    assert "trust ledger verification failed: bundle_hash_mismatch" in validation.errors


def test_team_ops_terminal_closure_evidence_bundle_validator_rejects_production_claim(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["metadata"]["production_ready_claimed"] = True
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "metadata.production_ready_claimed must be false" in validation.errors
    assert "trust ledger verification failed: bundle_hash_mismatch" in validation.errors


def test_team_ops_terminal_closure_evidence_bundle_validator_rejects_secret_marker(tmp_path: Path) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["metadata"]["source_review_packet_id"] = "client_secret=blocked"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "bundle must not serialize secret marker: client_secret=" in validation.errors
    assert "client_secret=blocked" not in json.dumps(validation.as_dict(), sort_keys=True)


def test_team_ops_terminal_closure_evidence_bundle_validator_missing_path_is_bounded(tmp_path: Path) -> None:
    review_path, certificate_path, _bundle_path = _write_ready_bundle(tmp_path)
    missing_bundle_path = tmp_path / "missing_team_ops_terminal_closure_evidence_bundle.json"

    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=missing_bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "TeamOps terminal closure evidence bundle file missing" in validation.errors
    assert validation.next_action == "regenerate TeamOps terminal closure evidence bundle from ready certificate"


def test_team_ops_terminal_closure_evidence_bundle_validator_cli_writes_validation(tmp_path: Path, capsys) -> None:
    review_path, certificate_path, bundle_path = _write_ready_bundle(tmp_path)
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_evidence_bundle_validation.json"
    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    written = write_team_ops_shared_inbox_terminal_closure_evidence_bundle_validation(validation, output_path)
    exit_code = main(
        [
            "--bundle",
            str(bundle_path),
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--signing-secret",
            SIGNING_SECRET,
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
    assert stdout_payload["bundle_id"] == file_payload["bundle_id"]
    assert SIGNING_SECRET not in json.dumps(file_payload, sort_keys=True)
    assert captured.err == ""


def _write_ready_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    bundle_path = tmp_path / "team_ops_shared_inbox_terminal_closure_evidence_bundle.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = mint_team_ops_shared_inbox_terminal_closure_certificate(
        review_packet_path=review_path,
        schema_path=CERTIFICATE_SCHEMA_PATH,
        closed_at="2026-06-14T00:00:00+00:00",
    )
    write_team_ops_shared_inbox_terminal_closure_certificate(certificate, certificate_path)
    bundle = produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=BUNDLE_SCHEMA_PATH,
        signing_secret=SIGNING_SECRET,
        commit_sha="c8e772e5d",
        issued_at="2026-06-14T00:00:00+00:00",
    )
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle(bundle, bundle_path)
    return review_path, certificate_path, bundle_path


def _ready_review_packet() -> dict[str, object]:
    evidence_refs = [
        ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
        ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
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
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
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
