"""Tests for the Foundation Mode next-action boundary validator.

Purpose: prove continuation preparation stays local, atomic, and public-safe
without authorizing external action, deployment, publication, spending,
customer action, legal/business action, claim promotion, secret use, credential
use, service activation, source-control publication, roadmap commitment, or
deadline promise.
Governance scope: Foundation Mode, continuation triage, smallest prerequisite
selection, dependency checks, local edit scope, verification planning, stop
rules, receipt planning, handoff summaries, private-value exclusion, and
external-action blocking.
Dependencies: scripts.validate_foundation_next_action_boundary.
Invariants: next-action surfaces remain AwaitingEvidence and reject promotion
or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_next_action_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_next_action_boundary,
    validate_packet,
)


def test_foundation_next_action_boundary_artifacts_pass() -> None:
    assert validate_foundation_next_action_boundary() == []


def test_next_action_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["next_action_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["broad_continuation_execution_allowed"] is False
    assert payload["external_action_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["spending_allowed"] is False
    assert payload["customer_action_allowed"] is False
    assert payload["source_control_publication_allowed"] is False
    assert payload["deadline_promise_claimed"] is False


def test_witness_rejects_broad_continuation_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["broad_continuation_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_root_value_invalid" for finding in findings)


def test_witness_rejects_external_action_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["external_action_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_root_value_invalid" for finding in findings)


def test_witness_rejects_spending_and_customer_action() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["spending_allowed"] = True
    candidate["customer_action_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["next_action_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "next_action_surface_state_invalid" for finding in findings)


def test_witness_rejects_secret_or_provider_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["next_action_surfaces"][0]["public_safe_note"] = "provider_id=private-account api_key=secret"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_continue_authorized_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "next-action witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "continue is authorized and deadline is promised"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "next_action_forbidden_promotion_phrase" for finding in findings)
