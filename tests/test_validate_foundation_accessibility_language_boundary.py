"""Tests for the Foundation Mode accessibility/language boundary validator.

Purpose: prove accessibility/language preparation stays local and does not
authorize accessibility compliance, WCAG conformance, screen-reader
verification, keyboard-navigation verification, mobile accessibility, contrast
compliance, translation readiness, localization readiness, Mfidel support,
Amharic support, user testing, personal-data collection, customer access,
publication, or deployment claims.
Governance scope: Foundation Mode, public-safe accessibility/language posture,
Mfidel atomicity, private-value exclusion, customer-access blocking,
publication blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_accessibility_language_boundary.
Invariants: accessibility/language surfaces remain AwaitingEvidence and reject
compliance, language-readiness, user-testing, publication, or private-value
drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_accessibility_language_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_accessibility_language_boundary,
    validate_packet,
)


def test_foundation_accessibility_language_boundary_artifacts_pass() -> None:
    assert validate_foundation_accessibility_language_boundary() == []


def test_accessibility_language_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["accessibility_language_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["accessibility_compliance_claimed"] is False
    assert payload["wcag_conformance_claimed"] is False
    assert payload["screen_reader_verified"] is False
    assert payload["keyboard_navigation_verified"] is False
    assert payload["translation_readiness_claimed"] is False
    assert payload["localization_readiness_claimed"] is False
    assert payload["mfidel_support_claimed"] is False
    assert payload["amharic_support_claimed"] is False
    assert payload["external_user_testing_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_accessibility_compliance_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["accessibility_compliance_claimed"] = True
    candidate["wcag_conformance_claimed"] = True
    candidate["contrast_compliance_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_root_value_invalid" for finding in findings)
    assert not any(finding.rule_id == "accessibility_language_surface_state_invalid" for finding in findings)


def test_witness_rejects_language_support_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["translation_readiness_claimed"] = True
    candidate["localization_readiness_claimed"] = True
    candidate["mfidel_support_claimed"] = True
    candidate["amharic_support_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_root_value_invalid" for finding in findings)
    assert candidate["mfidel_support_claimed"] is True


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["accessibility_language_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "accessibility_language_surface_state_invalid" for finding in findings)


def test_witness_rejects_accessibility_or_user_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["accessibility_language_surfaces"][3]["public_safe_note"] = "screen_reader_status=passed"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_forbidden_private_value_pattern" for finding in findings)
    assert not any(finding.rule_id == "accessibility_language_root_value_invalid" for finding in findings)


def test_witness_rejects_translation_or_locale_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["accessibility_language_surfaces"][6]["public_safe_note"] = "translation_text=example"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_forbidden_private_value_pattern" for finding in findings)
    assert len(findings) >= 1


def test_witness_rejects_accessibility_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "accessibility/language witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "accessibility is compliant after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "accessibility_language_forbidden_promotion_phrase" for finding in findings)
    assert any(finding.rule_id == "accessibility_language_next_action_invalid" for finding in findings)
