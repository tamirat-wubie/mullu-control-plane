"""Purpose: verify TrustedCaptureEvidencePacket validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_trusted_capture_evidence_packet and SDLC validator.
Invariants:
  - Capture evidence remains digest-only.
  - Foundation Mode does not grant live capture, media recording, camera,
    microphone, sensor, connector, write, publication, or terminal authority.
  - Raw surfaces, media, audio, sensor payloads, source bodies, and secrets are
    not stored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_trusted_capture_evidence_packet as validator


def test_trusted_capture_evidence_packet_passes() -> None:
    errors = validator.validate_trusted_capture_evidence_packet()
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "TrustedCaptureEvidencePacket")

    assert errors == []
    assert packet["packet_version"] == validator.EXPECTED_PACKET_VERSION
    assert packet["capture_scope"]["surface_redaction_policy"] == "digest_only_no_raw_surface"
    assert packet["capture_scope"]["capture_mode"] == "dry_run_operator_supplied_digest"
    assert packet["capture_scope"]["consent_scope"] == "operator_local_explicit"
    assert packet["authority_boundary"]["live_capture_performed"] is False
    assert packet["authority_boundary"]["media_recording_performed"] is False
    assert packet["authority_boundary"]["sensor_read_performed"] is False
    assert packet["privacy_guard"]["raw_media_stored"] is False
    assert validator.validate_trusted_capture_evidence_packet_record(packet) == []


def test_trusted_capture_evidence_packet_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_trusted_capture_evidence_packet(
        authority_boundary__live_capture_performed=True,
        authority_boundary__media_recording_performed=True,
        authority_boundary__screen_recording_performed=True,
        authority_boundary__microphone_capture_performed=True,
        authority_boundary__camera_capture_performed=True,
        authority_boundary__sensor_read_performed=True,
        authority_boundary__file_write_performed=True,
        authority_boundary__connector_call_performed=True,
        authority_boundary__external_write_performed=True,
        authority_boundary__publication_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_trusted_capture_evidence_packet_record(mutated)

    assert any("authority_boundary.live_capture_performed" in error for error in errors)
    assert any("authority_boundary.media_recording_performed" in error for error in errors)
    assert any("authority_boundary.screen_recording_performed" in error for error in errors)
    assert any("authority_boundary.microphone_capture_performed" in error for error in errors)
    assert any("authority_boundary.camera_capture_performed" in error for error in errors)
    assert any("authority_boundary.sensor_read_performed" in error for error in errors)
    assert any("authority_boundary.connector_call_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_trusted_capture_evidence_packet_rejects_raw_media_retention() -> None:
    mutated = validator.build_mutated_trusted_capture_evidence_packet(
        authority_boundary__raw_media_stored=True,
        authority_boundary__raw_source_body_stored=True,
        authority_boundary__raw_secret_value_stored=True,
        privacy_guard__raw_surface_stored=True,
        privacy_guard__raw_media_stored=True,
        privacy_guard__raw_audio_stored=True,
        privacy_guard__raw_sensor_payload_stored=True,
        privacy_guard__raw_secret_value_stored=True,
        privacy_guard__private_payload_redacted=False,
        privacy_guard__operator_review_required=False,
        privacy_guard__retention_policy_ref="",
    )

    errors = validator.validate_trusted_capture_evidence_packet_record(mutated)

    assert any("authority_boundary.raw_media_stored" in error for error in errors)
    assert any("authority_boundary.raw_source_body_stored" in error for error in errors)
    assert any("authority_boundary.raw_secret_value_stored" in error for error in errors)
    assert any("privacy_guard.raw_surface_stored" in error for error in errors)
    assert any("privacy_guard.raw_audio_stored" in error for error in errors)
    assert any("privacy_guard.raw_sensor_payload_stored" in error for error in errors)
    assert any("private_payload_redacted" in error for error in errors)
    assert any("operator_review_required" in error for error in errors)


def test_trusted_capture_evidence_packet_rejects_digest_and_scope_drift() -> None:
    mutated = validator.build_mutated_trusted_capture_evidence_packet(
        capture_scope__source_surface_hash="https://example.com/raw-capture",
        capture_artifacts__surface_digest_ref="surface://raw",
        capture_artifacts__frame_digest_ref="file://frame.png",
        capture_artifacts__media_digest_ref="https://example.com/video.mp4",
        capture_artifacts__transcript_digest_ref="transcript://raw",
        capture_artifacts__sensor_digest_ref="sensor://raw",
        capture_artifacts__artifact_manifest_ref="manifest://raw",
        capture_scope__surface_redaction_policy="operator_redacted_surface_ref",
        capture_scope__capture_mode="manual_capture_digest",
        capture_scope__consent_scope="sandbox_only_observation",
    )

    errors = validator.validate_trusted_capture_evidence_packet_record(mutated)

    assert any("source_surface_hash must use hash://sha256/" in error for error in errors)
    assert any("source_surface_hash must not store raw capture URL" in error for error in errors)
    assert any("surface_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("frame_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("media_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("transcript_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("sensor_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("artifact_manifest_ref must use hash://sha256/" in error for error in errors)
    assert any("surface_redaction_policy" in error for error in errors)
    assert any("capture_mode" in error for error in errors)


def test_trusted_capture_evidence_packet_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_trusted_capture_evidence_packet(
        receipt_refs__trusted_capture_evidence_packet_schema="schemas/other.schema.json",
        receipt_refs__capture_policy_decision_ledger_schema="schemas/other_capture.schema.json",
        receipt_refs__browser_observation_receipt_schema="schemas/other_browser.schema.json",
        capture_scope__capture_policy_ref="schemas/other_capture.schema.json",
        capture_scope__evidence_classification_ref="schemas/other_evidence.schema.json",
        capture_artifacts__browser_observation_ref="schemas/other_browser.schema.json",
        contract_summary__digest_only=False,
        contract_summary__capture_authority_denied=False,
        contract_summary__authority_denial_count=1,
        contract_summary__privacy_guard_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/trusted_capture_evidence_packet.schema.json"],
    )

    errors = validator.validate_trusted_capture_evidence_packet_record(mutated)

    assert any("receipt_refs.trusted_capture_evidence_packet_schema" in error for error in errors)
    assert any("receipt_refs.capture_policy_decision_ledger_schema" in error for error in errors)
    assert any("receipt_refs.browser_observation_receipt_schema" in error for error in errors)
    assert any("capture_scope.capture_policy_ref" in error for error in errors)
    assert any("capture_scope.evidence_classification_ref" in error for error in errors)
    assert any("capture_artifacts.browser_observation_ref" in error for error in errors)
    assert any("contract_summary.capture_authority_denied" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/trusted_capture_evidence_packet.schema.json",
            "--packet",
            "examples/trusted_capture_evidence_packet.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/trusted_capture_evidence_packet.schema.json"
    assert Path(payload["packet_path"]).as_posix() == "examples/trusted_capture_evidence_packet.foundation.json"
    assert payload["errors"] == []


def test_malformed_trusted_capture_evidence_packet_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_trusted_capture_evidence_packet_record(None, schema)
    list_errors = validator.validate_trusted_capture_evidence_packet_record([], schema)

    assert any("trusted capture evidence packet must be a JSON object" in error for error in none_errors)
    assert any("trusted capture evidence packet must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_trusted_capture_evidence_packet() -> None:
    requirement_path = Path("examples/sdlc/requirement_trusted_capture_evidence_packet_20260616.json")
    design_path = Path("examples/sdlc/design_trusted_capture_evidence_packet_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "trusted capture evidence packet requirement")
    design = sdlc_validator.load_json_object(design_path, "trusted capture evidence packet design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/trusted_capture_evidence_packet.schema.json" in requirement["affected_surfaces"]
    assert "schemas/trusted_capture_evidence_packet.schema.json" in design["schema_changes"]
    assert "scripts/validate_trusted_capture_evidence_packet.py" in design["validator_changes"]
    assert "tests/test_validate_trusted_capture_evidence_packet.py" in design["validator_changes"]
    assert "no live capture" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
