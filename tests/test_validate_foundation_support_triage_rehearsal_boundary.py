"""Tests for the Foundation Mode support triage rehearsal boundary validator.

Purpose: prove support triage rehearsal stays local and does not authorize
support opening, inbound messages, tickets, inbox routing, customer data,
personal data, response commitments, support tooling, paid support, or
deployment claims.
Governance scope: Foundation Mode, support triage rehearsal planning, local
sample categorization, public-safe issue-shape notes, inbox/routing exclusion,
customer-data exclusion, response-commitment blocking, support-tool blocking,
onboarding blocking, paid-support blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_support_triage_rehearsal_boundary.
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

from scripts.validate_foundation_support_triage_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_support_triage_rehearsal_boundary,
    validate_packet,
)


def test_foundation_support_triage_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_support_triage_rehearsal_boundary() == []


def test_support_triage_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["support_triage_executed"] is False
    assert payload["customer_support_open"] is False
    assert payload["inbound_message_acceptance_allowed"] is False
    assert payload["support_ticket_creation_allowed"] is False
    assert payload["customer_data_handling_allowed"] is False
    assert payload["support_sla_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_support_open_and_inbound_messages() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_support_open"] = True
    candidate["inbound_message_acceptance_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_ticket_and_inbox_routing() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["support_ticket_creation_allowed"] = True
    candidate["inbox_routing_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_and_personal_data_handling() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_data_handling_allowed"] = True
    candidate["personal_data_handling_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_response_sla_and_incident_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["response_time_promise_claimed"] = True
    candidate["support_sla_claimed"] = True
    candidate["incident_response_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_tool_onboarding_paid_support_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["support_tool_activation_allowed"] = True
    candidate["onboarding_allowed"] = True
    candidate["paid_support_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "support_triage_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_ticket_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][2]["public_safe_note"] = "ticket_id=private-ticket"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_support_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support triage rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "support triage is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_triage_rehearsal_forbidden_promotion_phrase" for finding in findings)
