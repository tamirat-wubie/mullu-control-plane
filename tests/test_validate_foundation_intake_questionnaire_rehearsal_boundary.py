"""Tests for the Foundation Mode intake questionnaire rehearsal validator.

Purpose: prove intake questionnaire rehearsal stays local and does not
authorize form publication, waitlists, pilot signups, personal-data collection,
CRM import, outreach, onboarding, customer access, payment, legal/privacy
readiness, or deployment claims.
Governance scope: Foundation Mode, intake questionnaire rehearsal planning,
fictional local field categories, collection exclusion, CRM exclusion,
outreach exclusion, customer-access blocking, payment blocking, and deployment
blocking.
Dependencies: scripts.validate_foundation_intake_questionnaire_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject private
value drift, execution drift, and readiness promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_intake_questionnaire_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_intake_questionnaire_rehearsal_boundary,
    validate_packet,
)


def test_foundation_intake_questionnaire_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_intake_questionnaire_rehearsal_boundary() == []


def test_intake_questionnaire_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["questionnaire_rehearsal_executed"] is False
    assert payload["active_intake_form_exists"] is False
    assert payload["form_publication_allowed"] is False
    assert payload["waitlist_open"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_questionnaire_execution_and_form_publication() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["questionnaire_rehearsal_executed"] = True
    candidate["active_intake_form_exists"] = True
    candidate["form_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_waitlist_and_pilot_signup() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["waitlist_open"] = True
    candidate["pilot_signup_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_personal_data_crm_and_outreach() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["personal_data_collection_allowed"] = True
    candidate["crm_import_allowed"] = True
    candidate["outreach_campaign_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_onboarding_customer_access_payment_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_onboarding_allowed"] = True
    candidate["customer_access_allowed"] = True
    candidate["payment_collection_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_legal_privacy_readiness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["legal_privacy_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_form_link_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "form_url=private-form"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_questionnaire_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake questionnaire rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "questionnaire is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_questionnaire_rehearsal_forbidden_promotion_phrase" for finding in findings)
