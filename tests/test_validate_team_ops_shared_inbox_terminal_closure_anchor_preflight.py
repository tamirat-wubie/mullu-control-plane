"""Tests for TeamOps terminal closure anchor preflight validation.

Purpose: prove TeamOps anchor preflight receipts are schema-valid, bound to the
signed source bundle, and blocked from raw fields or effect claims.
Governance scope: TeamOps anchor preflight validation, deterministic artifact
projection, no-effect metadata, and no-secret serialization.
Dependencies: scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.
Invariants:
  - Validation rejects invalid source bundle signatures.
  - Validation rejects artifact projection drift.
  - Validation rejects effect claims and raw message/provider fields.
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
from scripts.produce_team_ops_shared_inbox_terminal_closure_evidence_bundle import (
    produce_team_ops_shared_inbox_terminal_closure_evidence_bundle,
    write_team_ops_shared_inbox_terminal_closure_evidence_bundle,
)
from scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_preflight import (
    main,
    validate_team_ops_shared_inbox_terminal_closure_anchor_preflight,
)


ROOT = Path(__file__).resolve().parent.parent
CERTIFICATE_SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_bundle.schema.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
SIGNING_SECRET = "teamops-bundle-test-secret"
ANCHOR_SECRET = "teamops-anchor-test-secret"
AUTHORITY_REF = "proof://teamops/operator-authority/test"


def test_team_ops_terminal_closure_anchor_preflight_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.errors == ()
    assert validation.artifact_count >= 4
    assert validation.bundle_id.startswith("trust-bundle-")
    assert validation.next_action.startswith("operator may create")


def test_team_ops_terminal_closure_anchor_preflight_validation_rejects_wrong_bundle_secret(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret="wrong-secret",
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "source TeamOps terminal closure evidence bundle must be ready" in validation.errors
    assert validation.receipt_id.startswith("teamops-shared-inbox-terminal-anchor-preflight-")
    assert validation.artifact_count >= 4


def test_team_ops_terminal_closure_anchor_preflight_validation_rejects_artifact_drift(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["artifact_hash"] = f"sha256:{'f' * 64}"
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "artifact_root_hash must match projected artifacts" in validation.errors
    assert "artifacts must match deterministic source-bundle projection" in validation.errors
    assert validation.artifact_root_hash == payload["artifact_root_hash"]


def test_team_ops_terminal_closure_anchor_preflight_validation_rejects_effect_claim(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["metadata"]["remote_submit_executed"] = True
    payload["metadata"]["anchor_receipt_created"] = True
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "metadata.remote_submit_executed must be false" in validation.errors
    assert "metadata.anchor_receipt_created must be false" in validation.errors
    assert validation.next_action.startswith("repair TeamOps")


def test_team_ops_terminal_closure_anchor_preflight_validation_rejects_raw_field(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["metadata"]["raw_subject"] = "do not serialize"
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_preflight(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "anchor preflight must not serialize raw field: raw_subject" in validation.errors
    assert "$.metadata: unexpected property 'raw_subject'" in validation.errors
    assert validation.receipt_id.startswith("teamops-shared-inbox-terminal-anchor-preflight-")


def test_team_ops_terminal_closure_anchor_preflight_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    output_path = tmp_path / "team_ops_anchor_preflight_validation.json"

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
            "--output",
            str(output_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert file_payload["valid"] is True
    assert stdout_payload["ready"] is True
    assert file_payload["errors"] == []
    assert file_payload["artifact_count"] >= 4
    assert captured.err == ""


def _write_ready_preflight(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
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
