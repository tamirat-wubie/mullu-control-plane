"""Tests for the Foundation Mode customer-access policy rehearsal validator.

Purpose: prove customer-access policy rehearsal stays local and does not
authorize access approval, invitations, accounts, tenants, login routes,
support commitments, terms/privacy readiness, personal-data collection, paid
access, pilot/beta/waitlist access, external publication, or deployment.
Governance scope: Foundation Mode, customer-access policy rehearsal planning,
local eligibility and denial criteria, invitation exclusion, account and tenant
exclusion, login route exclusion, support-duty blocking, terms/privacy
blocking, personal-data exclusion, paid-access blocking, pilot/beta/waitlist
blocking, external-publication restraint, and deployment blocking.
Dependencies: scripts.validate_foundation_customer_access_policy_rehearsal_boundary.
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

from scripts.validate_foundation_customer_access_policy_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_customer_access_policy_rehearsal_boundary,
    validate_packet,
)


def test_foundation_customer_access_policy_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_customer_access_policy_rehearsal_boundary() == []


def test_customer_access_policy_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["access_policy_rehearsal_executed"] is False
    assert payload["access_policy_approved"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["account_creation_allowed"] is False
    assert payload["tenant_provisioning_allowed"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_access_policy_and_customer_access_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["access_policy_rehearsal_executed"] = True
    candidate["access_policy_approved"] = True
    candidate["customer_access_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_invitation_account_tenant_and_login_route() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_invitation_allowed"] = True
    candidate["account_creation_allowed"] = True
    candidate["tenant_provisioning_allowed"] = True
    candidate["login_route_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_support_terms_privacy_and_personal_data_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["support_commitment_allowed"] = True
    candidate["terms_privacy_ready_claimed"] = True
    candidate["personal_data_collection_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_paid_access_publication_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["paid_access_allowed"] = True
    candidate["pilot_beta_waitlist_access_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "customer_access_policy_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_account_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][3]["public_safe_note"] = "account_id=private-account"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_customer_access_open_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access policy rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "customer access is open after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_policy_rehearsal_forbidden_promotion_phrase" for finding in findings)
