"""Tests for the Foundation Mode secrets/credentials boundary validator.

Purpose: prove secrets/credentials preparation stays local and does not
authorize real secret storage, credential activation, provider binding, key
creation, environment-file commits, external calls, or deployment claims.
Governance scope: Foundation Mode, secrets posture, credential posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_secrets_credentials_boundary.
Invariants: secrets/credentials surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_secrets_credentials_boundary import (  # noqa: E402
    DEFAULT_APPLICATION_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_APPLICATION_ID,
    EXPECTED_APPLICATION_ITEMS,
    EXPECTED_SCREENING_CATEGORIES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_application,
    validate_foundation_secrets_credentials_boundary,
    validate_packet,
)


def test_foundation_secrets_credentials_boundary_artifacts_pass() -> None:
    assert validate_foundation_secrets_credentials_boundary() == []


def test_secrets_credentials_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["credential_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["real_secret_storage_allowed"] is False
    assert payload["credential_activation_allowed"] is False
    assert payload["provider_account_binding_allowed"] is False
    assert payload["api_key_creation_allowed"] is False
    assert payload["external_call_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_current_packet_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "secrets/credentials current-packet application")

    assert payload["application_id"] == EXPECTED_APPLICATION_ID
    assert tuple(payload["observed_screening_categories"]) == EXPECTED_SCREENING_CATEGORIES
    assert tuple((item["surface_id"], item["state"]) for item in payload["screening_items"]) == EXPECTED_APPLICATION_ITEMS
    assert payload["screening_context"]["changed_file_list_recorded"] is False
    assert payload["screening_context"]["private_values_recorded"] is False
    assert payload["screening_context"]["secret_value_recorded"] is False
    assert payload["screening_context"]["saved_preflight_receipt_available"] is True
    assert payload["screening_context"]["receipt_is_terminal_closure_claimed"] is False
    assert payload["real_secret_storage_allowed"] is False
    assert payload["credential_activation_allowed"] is False
    assert payload["provider_account_binding_allowed"] is False
    assert payload["api_key_creation_allowed"] is False
    assert payload["secret_scan_pass_claimed"] is False
    assert payload["external_call_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False


def test_witness_rejects_real_secret_storage_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["real_secret_storage_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_root_value_invalid" for finding in findings)


def test_witness_rejects_credential_activation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["credential_activation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_root_value_invalid" for finding in findings)


def test_witness_rejects_key_creation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["api_key_creation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["credential_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "secrets_credentials_surface_state_invalid" for finding in findings)


def test_witness_rejects_environment_assignment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["credential_surfaces"][0]["public_safe_note"] = "MULLU_SAMPLE_KEY=placeholder"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_credentials_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "secrets/credentials witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "credentials-ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_forbidden_promotion_phrase" for finding in findings)


def test_application_rejects_scan_pass_and_category_drift() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "secrets/credentials current-packet application")
    candidate = deepcopy(payload)
    candidate["secret_scan_pass_claimed"] = True
    candidate["observed_screening_categories"] = ["secret_value_pattern_guard"]

    findings = validate_application(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_application_root_value_invalid" for finding in findings)
    assert any(finding.rule_id == "secrets_credentials_application_categories_invalid" for finding in findings)


def test_application_rejects_screening_item_state_promotion() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "secrets/credentials current-packet application")
    candidate = deepcopy(payload)
    candidate["screening_items"][0]["state"] = "Ready"

    findings = validate_application(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_application_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "secrets_credentials_application_item_state_invalid" for finding in findings)


def test_application_rejects_private_value_and_readiness_phrase() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "secrets/credentials current-packet application")
    candidate = deepcopy(payload)
    candidate["screening_items"][0]["application_note"] = "MULLU_SAMPLE_KEY=placeholder"
    candidate["next_action"] = "credentials-ready after screening"

    findings = validate_application(candidate)

    assert findings
    assert any(finding.rule_id == "secrets_credentials_forbidden_private_value_pattern" for finding in findings)
    assert any(finding.rule_id == "secrets_credentials_forbidden_promotion_phrase" for finding in findings)
