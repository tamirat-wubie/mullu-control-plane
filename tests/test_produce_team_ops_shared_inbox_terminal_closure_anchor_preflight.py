"""Tests for TeamOps terminal closure anchor preflight production.

Purpose: prove TeamOps terminal closure evidence bundles can be checked for a
later trust-ledger anchor without creating an anchor receipt or remote effect.
Governance scope: TeamOps terminal closure anchor readiness, artifact
projection, operator authority, secret-presence checks, and no-effect metadata.
Dependencies: scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight.
Invariants:
  - Ready preflight binds a signed TeamOps terminal closure evidence bundle.
  - Missing operator authority or anchor secret blocks readiness.
  - Preflight never serializes secret values or claims provider effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.mint_team_ops_shared_inbox_terminal_closure_certificate import (
    mint_team_ops_shared_inbox_terminal_closure_certificate,
    write_team_ops_shared_inbox_terminal_closure_certificate,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_preflight import (
    main,
    produce_team_ops_shared_inbox_terminal_closure_anchor_preflight,
    write_team_ops_shared_inbox_terminal_closure_anchor_preflight,
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


def test_team_ops_terminal_closure_anchor_preflight_accepts_ready_bundle(tmp_path: Path) -> None:
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
    payload = preflight.as_dict()
    output_path = tmp_path / "team_ops_anchor_preflight.json"
    write_team_ops_shared_inbox_terminal_closure_anchor_preflight(preflight, output_path)

    assert preflight.ready is True
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["proof_state"] == "Pass"
    assert payload["artifact_count"] >= 4
    assert {"command", "execution_receipt", "verification_result", "terminal_certificate"}.issubset(
        {artifact["artifact_type"] for artifact in payload["artifacts"] if artifact["required"]}
    )
    assert payload["metadata"]["anchor_receipt_created"] is False
    assert payload["metadata"]["remote_submit_executed"] is False
    assert payload["metadata"]["ledger_append_executed"] is False
    assert payload["metadata"]["production_ready_claimed"] is False
    assert ANCHOR_SECRET not in json.dumps(payload, sort_keys=True)
    assert not payload["bundle_path"].startswith(str(tmp_path))
    assert output_path.exists()


def test_team_ops_terminal_closure_anchor_preflight_blocks_missing_anchor_secret(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path = _write_ready_bundle(tmp_path)

    preflight = produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret="",
        operator_authority_ref=AUTHORITY_REF,
        checked_at="2026-06-14T00:00:00+00:00",
    )
    payload = preflight.as_dict()

    assert preflight.ready is False
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["proof_state"] == "Unknown"
    assert payload["blockers"] == ["anchor_signing_secret"]
    assert payload["anchor_signing_secret_present"] is False
    assert payload["metadata"]["anchor_receipt_created"] is False


def test_team_ops_terminal_closure_anchor_preflight_blocks_missing_authority(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path = _write_ready_bundle(tmp_path)

    preflight = produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        operator_authority_ref="",
        checked_at="2026-06-14T00:00:00+00:00",
    )
    payload = preflight.as_dict()

    assert preflight.ready is False
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["proof_state"] == "Unknown"
    assert payload["blockers"] == ["operator_authority"]
    assert payload["operator_authority_ref"] == ""
    assert payload["metadata"]["provider_call_performed"] is False


def test_team_ops_terminal_closure_anchor_preflight_blocks_invalid_target(tmp_path: Path) -> None:
    bundle_path, certificate_path, review_path = _write_ready_bundle(tmp_path)

    preflight = produce_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        operator_authority_ref=AUTHORITY_REF,
        anchor_target="unknown_anchor",
        checked_at="2026-06-14T00:00:00+00:00",
    )
    payload = preflight.as_dict()

    assert preflight.ready is False
    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert payload["proof_state"] == "Fail"
    assert "anchor_target" in payload["blockers"]
    assert payload["metadata"]["remote_submit_executed"] is False
    assert payload["planned_external_anchor_status"] == "pending"


def test_team_ops_terminal_closure_anchor_preflight_cli_writes_blocked_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_path, certificate_path, review_path = _write_ready_bundle(tmp_path)
    output_path = tmp_path / "team_ops_anchor_preflight.json"

    exit_code = main(
        [
            "--bundle",
            str(bundle_path),
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--bundle-signing-secret",
            SIGNING_SECRET,
            "--anchor-signing-secret",
            "",
            "--operator-authority-ref",
            AUTHORITY_REF,
            "--checked-at",
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

    assert exit_code == 2
    assert file_payload["ready"] is False
    assert stdout_payload["blockers"] == ["anchor_signing_secret"]
    assert file_payload["metadata"]["anchor_receipt_created"] is False
    assert file_payload["metadata"]["external_message_sent"] is False
    assert captured.err == ""


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
