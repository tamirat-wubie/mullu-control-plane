"""Tests for TeamOps terminal closure anchor receipt production.

Purpose: prove ready TeamOps anchor preflights can create a pending local
trust-ledger anchor receipt without remote submission.
Governance scope: TeamOps terminal closure anchor receipt creation, source
preflight binding, anchor signature verification, and no-effect metadata.
Dependencies: scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_receipt.
Invariants:
  - Ready receipts embed a pending trust-ledger anchor receipt.
  - Missing anchor secret blocks receipt production.
  - Production never serializes secret values or claims remote effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (
    mint_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight import (
    produce_team_ops_shared_inbox_terminal_closure_anchor_preflight,
    write_team_ops_shared_inbox_terminal_closure_anchor_preflight,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_receipt import (
    main,
    produce_team_ops_shared_inbox_terminal_closure_anchor_receipt,
    write_team_ops_shared_inbox_terminal_closure_anchor_receipt,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    produce_team_ops_shared_inbox_terminal_closure_evidence_bundle,
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)


ROOT = Path(__file__).resolve().parent.parent
CERTIFICATE_SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
SIGNING_SECRET = "teamops-bundle-test-secret"
ANCHOR_SECRET = "teamops-anchor-test-secret"
AUTHORITY_REF = "proof://teamops/operator-authority/test"


def test_team_ops_terminal_closure_anchor_receipt_accepts_ready_preflight(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)

    receipt = produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        created_at="2026-06-14T00:00:00+00:00",
    )
    payload = receipt.as_dict()
    output_path = tmp_path / "team_ops_anchor_receipt.json"
    write_team_ops_shared_inbox_terminal_closure_anchor_receipt(receipt, output_path)

    assert receipt.ready is True
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["proof_state"] == "Pass"
    assert payload["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert payload["anchor_receipt"]["external_anchor_status"] == "pending"
    assert payload["anchor_receipt"]["external_anchor_ref"] == ""
    assert payload["metadata"]["anchor_receipt_created"] is True
    assert payload["metadata"]["remote_submit_executed"] is False
    assert payload["metadata"]["ledger_append_executed"] is False
    assert payload["metadata"]["production_ready_claimed"] is False
    assert ANCHOR_SECRET not in json.dumps(payload, sort_keys=True)
    assert output_path.exists()


def test_team_ops_terminal_closure_anchor_receipt_blocks_missing_anchor_secret(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)

    receipt = produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret="",
        created_at="2026-06-14T00:00:00+00:00",
    )
    payload = receipt.as_dict()

    assert receipt.ready is False
    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert "anchor_receipt_signature" in payload["blockers"]
    assert "pending_boundary" in payload["blockers"]
    assert payload["metadata"]["anchor_receipt_created"] is False
    assert payload["metadata"]["remote_submit_executed"] is False


def test_team_ops_terminal_closure_anchor_receipt_blocks_not_ready_preflight(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["ready"] = False
    payload["proof_state"] = "Unknown"
    payload["blockers"] = ["operator_authority"]
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        created_at="2026-06-14T00:00:00+00:00",
    )
    payload = receipt.as_dict()

    assert receipt.ready is False
    assert "preflight_validation" in payload["blockers"]
    assert "preflight_ready" in payload["blockers"]
    assert payload["metadata"]["anchor_bundle_called"] is False
    assert payload["metadata"]["provider_call_performed"] is False


def test_team_ops_terminal_closure_anchor_receipt_cli_writes_ready_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    output_path = tmp_path / "team_ops_anchor_receipt.json"

    exit_code = main(
        [
            "--preflight",
            str(preflight_path),
            "--bundle",
            str(bundle_path),
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--bundle-signing-secret",
            SIGNING_SECRET,
            "--anchor-signing-secret",
            ANCHOR_SECRET,
            "--created-at",
            "2026-06-14T00:00:00+00:00",
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert file_payload["ready"] is True
    assert stdout_payload["anchor_receipt_id"].startswith("trust-anchor-receipt-")
    assert file_payload["metadata"]["requires_separate_remote_submission_preflight"] is True
    assert captured.err == ""


def _write_ready_preflight(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    bundle_path, certificate_path, review_path = _write_ready_bundle(tmp_path)
    preflight = produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        operator_authority_ref=AUTHORITY_REF,
        checked_at="2026-06-14T00:00:00+00:00",
    )
    preflight_path = tmp_path / "team_ops_shared_inbox_terminal_closure_anchor_preflight.json"
    write_team_ops_shared_inbox_terminal_closure_anchor_preflight(preflight, preflight_path)
    return bundle_path, certificate_path, review_path, preflight_path


def _write_ready_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
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
    return bundle_path, certificate_path, review_path


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
