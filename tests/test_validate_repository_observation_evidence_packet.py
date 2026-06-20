"""Tests for the RepositoryObservationEvidencePacket validator.

Purpose: prove repository observation evidence remains digest-only,
Foundation Mode safe, and blocked from hard-constraint planning until live
read-only evidence exists.
Governance scope: repository observation packet schema, Foundation example,
authority denial, privacy guards, proof-state admission, and receipt refs.
Dependencies: scripts.validate_repository_observation_evidence_packet.
Invariants: no live repository read claim, no filesystem write, no file-content
read, no secret read, no connector call, no terminal closure, no success claim.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_repository_observation_evidence_packet as validator


def test_repository_observation_evidence_packet_passes() -> None:
    errors = validator.validate_repository_observation_evidence_packet()
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "RepositoryObservationEvidencePacket")

    assert errors == []
    assert packet["packet_version"] == validator.EXPECTED_PACKET_VERSION
    assert packet["observation_scope"]["source_kind"] == "repository"
    assert packet["observed_state"]["freshness_state"] == "awaiting_live_observation"
    assert packet["evidence_admission"]["planning_admission"] == "defer"
    assert packet["evidence_admission"]["hard_constraint_planning_allowed"] is False
    assert packet["authority_boundary"]["live_repository_read_performed"] is False
    assert packet["authority_boundary"]["filesystem_write_performed"] is False
    assert validator.validate_repository_observation_evidence_packet_record(packet) == []


def test_repository_observation_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_repository_observation_evidence_packet(
        authority_boundary__live_repository_read_performed=True,
        authority_boundary__filesystem_write_performed=True,
        authority_boundary__file_content_read_performed=True,
        authority_boundary__secret_read_performed=True,
        authority_boundary__connector_call_performed=True,
        authority_boundary__external_write_performed=True,
        authority_boundary__runtime_dispatch_performed=True,
        authority_boundary__deployment_mutation_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_repository_observation_evidence_packet_record(mutated)

    assert any("authority_boundary.live_repository_read_performed" in error for error in errors)
    assert any("authority_boundary.filesystem_write_performed" in error for error in errors)
    assert any("authority_boundary.file_content_read_performed" in error for error in errors)
    assert any("authority_boundary.secret_read_performed" in error for error in errors)
    assert any("authority_boundary.connector_call_performed" in error for error in errors)
    assert any("authority_boundary.runtime_dispatch_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)
    assert any("authority_boundary.success_claim_allowed" in error for error in errors)


def test_repository_observation_rejects_privacy_and_digest_drift() -> None:
    mutated = validator.build_mutated_repository_observation_evidence_packet(
        privacy_guard__raw_git_status_stored=True,
        privacy_guard__raw_diff_stored=True,
        privacy_guard__raw_file_contents_stored=True,
        privacy_guard__raw_secret_value_stored=True,
        privacy_guard__private_payload_redacted=False,
        observed_state__git_status_digest_ref="status://raw-status",
        observed_state__diff_digest_ref="https://example.invalid/raw-diff",
    )

    errors = validator.validate_repository_observation_evidence_packet_record(mutated)

    assert any("privacy_guard.raw_git_status_stored" in error for error in errors)
    assert any("privacy_guard.raw_diff_stored" in error for error in errors)
    assert any("privacy_guard.raw_file_contents_stored" in error for error in errors)
    assert any("privacy_guard.raw_secret_value_stored" in error for error in errors)
    assert any("private_payload_redacted" in error for error in errors)
    assert any("git_status_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("diff_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("diff_digest_ref must not store a raw URL" in error for error in errors)


def test_repository_observation_rejects_hard_constraint_promotion() -> None:
    mutated = validator.build_mutated_repository_observation_evidence_packet(
        evidence_admission__planning_admission="admit",
        evidence_admission__proof_state="Pass",
        evidence_admission__solver_outcome="SolvedVerified",
        evidence_admission__hard_constraint_planning_allowed=True,
        evidence_admission__live_evidence_required=False,
        evidence_admission__live_evidence_state="SolvedVerified",
        observed_state__freshness_state="fresh",
    )

    errors = validator.validate_repository_observation_evidence_packet_record(mutated)

    assert any("evidence_admission.planning_admission" in error for error in errors)
    assert any("evidence_admission.proof_state" in error for error in errors)
    assert any("evidence_admission.solver_outcome" in error for error in errors)
    assert any("hard_constraint_planning_allowed" in error for error in errors)
    assert any("live_evidence_required" in error for error in errors)
    assert any("live_evidence_state" in error for error in errors)
    assert any("observed_state.freshness_state" in error for error in errors)


def test_repository_observation_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_repository_observation_evidence_packet(
        receipt_refs__repository_observation_evidence_packet_schema="schemas/other.schema.json",
        receipt_refs__observation_evidence_acquisition_architecture_doc="docs/other.md",
        contract_summary__digest_only=False,
        contract_summary__authority_denied=False,
        contract_summary__hard_constraint_blocked=False,
        contract_summary__authority_denial_count=1,
        contract_summary__privacy_guard_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/repository_observation_evidence_packet.schema.json"],
    )

    errors = validator.validate_repository_observation_evidence_packet_record(mutated)

    assert any("receipt_refs.repository_observation_evidence_packet_schema" in error for error in errors)
    assert any("receipt_refs.observation_evidence_acquisition_architecture_doc" in error for error in errors)
    assert any("contract_summary.digest_only" in error for error in errors)
    assert any("contract_summary.authority_denied" in error for error in errors)
    assert any("contract_summary.hard_constraint_blocked" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_repository_observation_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/repository_observation_evidence_packet.schema.json",
            "--packet",
            "examples/repository_observation_evidence_packet.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/repository_observation_evidence_packet.schema.json"
    assert Path(payload["packet_path"]).as_posix() == "examples/repository_observation_evidence_packet.foundation.json"
    assert payload["errors"] == []


def test_malformed_repository_observation_packet_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_repository_observation_evidence_packet_record(None, schema)
    list_errors = validator.validate_repository_observation_evidence_packet_record([], schema)

    assert any("repository observation evidence packet must be a JSON object" in error for error in none_errors)
    assert any("repository observation evidence packet must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)
