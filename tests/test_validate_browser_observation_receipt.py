"""Purpose: verify BrowserObservationReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_browser_observation_receipt and SDLC validator.
Invariants:
  - Browser observation remains digest-only.
  - Foundation Mode does not grant browser navigation, click, submit, cookie,
    connector, publication, or terminal authority.
  - Raw URLs, DOM, screenshots, and secret values are not stored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_browser_observation_receipt as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_browser_observation_receipt_passes() -> None:
    errors = validator.validate_browser_observation_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "BrowserObservationReceipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["observation_scope"]["url_redaction_policy"] == "hash_only_no_raw_url"
    assert receipt["observation_scope"]["consent_scope"] == "operator_local_explicit"
    assert receipt["authority_boundary"]["navigation_performed"] is False
    assert receipt["authority_boundary"]["click_performed"] is False
    assert receipt["authority_boundary"]["form_submit_performed"] is False
    assert receipt["privacy_guard"]["raw_dom_stored"] is False
    assert validator.validate_browser_observation_receipt_record(receipt) == []


def test_browser_observation_receipt_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_browser_observation_receipt(
        authority_boundary__navigation_performed=True,
        authority_boundary__click_performed=True,
        authority_boundary__form_submit_performed=True,
        authority_boundary__keystroke_injection_performed=True,
        authority_boundary__cookie_or_session_read=True,
        authority_boundary__external_write_performed=True,
        authority_boundary__connector_call_performed=True,
        authority_boundary__publication_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_browser_observation_receipt_record(mutated)

    assert any("authority_boundary.navigation_performed" in error for error in errors)
    assert any("authority_boundary.click_performed" in error for error in errors)
    assert any("authority_boundary.form_submit_performed" in error for error in errors)
    assert any("authority_boundary.keystroke_injection_performed" in error for error in errors)
    assert any("authority_boundary.cookie_or_session_read" in error for error in errors)
    assert any("authority_boundary.connector_call_performed" in error for error in errors)
    assert any("authority_boundary.publication_allowed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_browser_observation_receipt_rejects_raw_storage_drift() -> None:
    mutated = validator.build_mutated_browser_observation_receipt(
        privacy_guard__raw_url_stored=True,
        privacy_guard__raw_dom_stored=True,
        privacy_guard__raw_screenshot_stored=True,
        privacy_guard__raw_secret_value_stored=True,
        privacy_guard__private_payload_redacted=False,
        privacy_guard__operator_review_required=False,
        privacy_guard__retention_policy_ref="",
    )

    errors = validator.validate_browser_observation_receipt_record(mutated)

    assert any("privacy_guard.raw_url_stored" in error for error in errors)
    assert any("privacy_guard.raw_dom_stored" in error for error in errors)
    assert any("privacy_guard.raw_screenshot_stored" in error for error in errors)
    assert any("privacy_guard.raw_secret_value_stored" in error for error in errors)
    assert any("private_payload_redacted" in error for error in errors)
    assert any("operator_review_required" in error for error in errors)
    assert any("retention_policy_ref" in error for error in errors)


def test_browser_observation_receipt_rejects_raw_url_and_digest_drift() -> None:
    mutated = validator.build_mutated_browser_observation_receipt(
        observation_scope__source_url_hash="https://example.com/private",
        observation_artifacts__dom_digest_ref="dom://raw-fragment",
        observation_artifacts__screenshot_digest_ref="file://raw-screenshot.png",
        observation_artifacts__title_digest_ref="title://raw-title",
        observation_scope__url_redaction_policy="operator_redacted_url_ref",
        observation_scope__observation_mode="manual_screenshot_digest",
        observation_scope__consent_scope="public_page_observation",
    )

    errors = validator.validate_browser_observation_receipt_record(mutated)

    assert any("source_url_hash must use hash://sha256/" in error for error in errors)
    assert any("source_url_hash must not store a raw URL" in error for error in errors)
    assert any("dom_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("screenshot_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("title_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("url_redaction_policy" in error for error in errors)
    assert any("observation_mode" in error for error in errors)
    assert any("consent_scope" in error for error in errors)


def test_browser_observation_receipt_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_browser_observation_receipt(
        receipt_refs__browser_observation_receipt_schema="schemas/other.schema.json",
        receipt_refs__capture_policy_decision_ledger_schema="schemas/other_capture.schema.json",
        observation_artifacts__capture_policy_ref="schemas/other_capture.schema.json",
        observation_artifacts__evidence_classification_ref="schemas/other_evidence.schema.json",
        contract_summary__digest_only=False,
        contract_summary__authority_denied=False,
        contract_summary__authority_denial_count=1,
        contract_summary__privacy_guard_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/browser_observation_receipt.schema.json"],
    )

    errors = validator.validate_browser_observation_receipt_record(mutated)

    assert any("receipt_refs.browser_observation_receipt_schema" in error for error in errors)
    assert any("receipt_refs.capture_policy_decision_ledger_schema" in error for error in errors)
    assert any("observation_artifacts.capture_policy_ref" in error for error in errors)
    assert any("observation_artifacts.evidence_classification_ref" in error for error in errors)
    assert any("contract_summary.digest_only" in error for error in errors)
    assert any("contract_summary.authority_denied" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/browser_observation_receipt.schema.json",
            "--receipt",
            "examples/browser_observation_receipt.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/browser_observation_receipt.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/browser_observation_receipt.foundation.json"
    assert payload["errors"] == []


def test_malformed_browser_observation_receipt_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_browser_observation_receipt_record(None, schema)
    list_errors = validator.validate_browser_observation_receipt_record([], schema)

    assert any("browser observation receipt must be a JSON object" in error for error in none_errors)
    assert any("browser observation receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_browser_observation_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_browser_observation_receipt_20260616.json")
    design_path = Path("examples/sdlc/design_browser_observation_receipt_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "browser observation receipt requirement")
    design = sdlc_validator.load_json_object(design_path, "browser observation receipt design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/browser_observation_receipt.schema.json" in requirement["affected_surfaces"]
    assert "schemas/browser_observation_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_browser_observation_receipt.py" in design["validator_changes"]
    assert "tests/test_validate_browser_observation_receipt.py" in design["validator_changes"]
    assert "no browser navigation authority" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
