"""Tests for TeamOps terminal closure evidence bundle production.

Purpose: prove TeamOps terminal closure certificates can be signed into
canonical trust-ledger bundles without external anchoring or production claims.
Governance scope: TeamOps terminal closure evidence bundles, HMAC signing,
certificate binding, proof-ref canonicalization, and no-secret serialization.
Dependencies: scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle.
Invariants:
  - A missing signing secret blocks bundle production.
  - A ready terminal certificate produces a schema-valid signed bundle.
  - The bundle carries proof:// refs and no provider/mailbox/send effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (
    mint_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    main,
    produce_team_ops_shared_inbox_terminal_closure_evidence_bundle,
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    validate_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)


ROOT = Path(__file__).resolve().parent.parent
CERTIFICATE_SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
SIGNING_SECRET = "teamops-bundle-test-secret"


def test_team_ops_terminal_closure_evidence_bundle_blocks_missing_secret(tmp_path: Path) -> None:
    review_path, certificate_path = _write_ready_review_and_certificate(tmp_path)

    try:
        produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
            certificate_path=certificate_path,
            source_review_packet_path=review_path,
            schema_path=BUNDLE_SCHEMA_PATH,
            signing_secret="",
            issued_at="2026-06-14T00:00:00+00:00",
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "signing secret is required" in message
    assert SIGNING_SECRET not in message
    assert "client_secret" not in message


def test_team_ops_terminal_closure_evidence_bundle_signs_ready_certificate(tmp_path: Path) -> None:
    review_path, certificate_path = _write_ready_review_and_certificate(tmp_path)

    bundle = produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        schema_path=BUNDLE_SCHEMA_PATH,
        signing_secret=SIGNING_SECRET,
        commit_sha="c8e772e5d",
        issued_at="2026-06-14T00:00:00+00:00",
    )
    bundle_path = tmp_path / "team_ops_shared_inbox_terminal_closure_evidence_bundle.json"
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle(bundle, bundle_path)
    validation = validate_team_ops_shared_inbox_terminal_closure_evidence_bundle(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert bundle["bundle_id"].startswith("trust-bundle-")
    assert bundle["command_id"] == "team_ops.shared_inbox_triage"
    assert bundle["external_anchor_status"] == "not_requested"
    assert bundle["external_anchor_ref"] == ""
    assert bundle["metadata"]["team_ops_terminal_closure_bundle"] is True
    assert (
        bundle["metadata"]["provider_observation_receipt_id"]
        == "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa"
    )
    assert (
        bundle["metadata"]["provider_observation_receipt_ref"]
        == ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json"
    )
    assert bundle["metadata"]["provider_observation_receipt_valid"] is True
    assert bundle["metadata"]["provider_call_performed_by_producer"] is False
    assert bundle["metadata"]["production_ready_claimed"] is False
    assert (
        "proof://teamops/provider-observation/teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa"
        in bundle["evidence_refs"]
    )
    assert all(ref.startswith("proof://") for ref in bundle["evidence_refs"])
    assert len(bundle["evidence_refs"]) >= 9
    assert SIGNING_SECRET not in json.dumps(bundle, sort_keys=True)
    assert validation.valid is True
    assert validation.ready is True


def test_team_ops_terminal_closure_evidence_bundle_rejects_unready_certificate(tmp_path: Path) -> None:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = mint_team_ops_shared_inbox_terminal_closure_certificate(
        review_packet_path=review_path,
        schema_path=CERTIFICATE_SCHEMA_PATH,
        closed_at="2026-06-14T00:00:00+00:00",
    )
    certificate["metadata"]["production_ready_claimed"] = True
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_terminal_closure_evidence_bundle(
            certificate_path=certificate_path,
            source_review_packet_path=review_path,
            schema_path=BUNDLE_SCHEMA_PATH,
            signing_secret=SIGNING_SECRET,
            issued_at="2026-06-14T00:00:00+00:00",
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        message = ""

    assert "certificate not ready" in message
    assert "production_ready_claimed" not in message
    assert SIGNING_SECRET not in message


def test_team_ops_terminal_closure_evidence_bundle_cli_writes_bundle(tmp_path: Path, capsys) -> None:
    review_path, certificate_path = _write_ready_review_and_certificate(tmp_path)
    output_path = tmp_path / "team_ops_shared_inbox_terminal_closure_evidence_bundle.json"

    exit_code = main(
        [
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--schema",
            str(BUNDLE_SCHEMA_PATH),
            "--output",
            str(output_path),
            "--signing-secret",
            SIGNING_SECRET,
            "--commit-sha",
            "c8e772e5d",
            "--issued-at",
            "2026-06-14T00:00:00+00:00",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert file_payload["bundle_id"] == stdout_payload["bundle_id"]
    assert file_payload["signature"].startswith("hmac-sha256:")
    assert file_payload["metadata"]["provider_observation_receipt_valid"] is True
    assert file_payload["metadata"]["external_anchor_requested_by_producer"] is False
    assert captured.err == ""


def _write_ready_review_and_certificate(tmp_path: Path) -> tuple[Path, Path]:
    review_path = tmp_path / "team_ops_shared_inbox_terminal_closure_review_packet.json"
    certificate_path = tmp_path / "team_ops_shared_inbox_terminal_closure_certificate.json"
    review_path.write_text(json.dumps(_ready_review_packet()), encoding="utf-8")
    certificate = mint_team_ops_shared_inbox_terminal_closure_certificate(
        review_packet_path=review_path,
        schema_path=CERTIFICATE_SCHEMA_PATH,
        closed_at="2026-06-14T00:00:00+00:00",
    )
    write_team_ops_shared_inbox_terminal_closure_certificate(certificate, certificate_path)
    return review_path, certificate_path


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
