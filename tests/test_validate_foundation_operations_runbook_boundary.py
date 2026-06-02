"""Tests for the Foundation Mode operations/runbook boundary validator.

Purpose: prove operations/runbook preparation stays local and does not
authorize runbook execution, incident response, monitoring, alerting, on-call,
SLO, recovery, customer-support operations, publication, or deployment claims.
Governance scope: Foundation Mode, public-safe operations/runbook posture,
private-value exclusion, customer-support blocking, publication blocking, and
deployment blocking.
Dependencies: scripts.validate_foundation_operations_runbook_boundary.
Invariants: operations/runbook surfaces remain AwaitingEvidence and reject
operational-readiness, customer-support, publication, deployment, or
private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_operations_runbook_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_operations_runbook_boundary,
    validate_packet,
)


def test_foundation_operations_runbook_boundary_artifacts_pass() -> None:
    assert validate_foundation_operations_runbook_boundary() == []


def test_operations_runbook_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["operations_runbook_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["operations_runbook_claimed"] is False
    assert payload["runbook_execution_allowed"] is False
    assert payload["incident_response_ready"] is False
    assert payload["monitoring_ready"] is False
    assert payload["alerting_ready"] is False
    assert payload["on_call_ready"] is False
    assert payload["slo_claimed"] is False
    assert payload["recovery_ready"] is False
    assert payload["customer_support_operations_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_operations_readiness_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")
    candidate = deepcopy(payload)
    candidate["runbook_execution_allowed"] = True
    candidate["incident_response_ready"] = True
    candidate["monitoring_ready"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operations_runbook_root_value_invalid" for finding in findings)
    assert not any(finding.rule_id == "operations_runbook_surface_state_invalid" for finding in findings)


def test_witness_rejects_recovery_and_slo_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")
    candidate = deepcopy(payload)
    candidate["slo_claimed"] = True
    candidate["recovery_ready"] = True
    candidate["operational_graph_complete"] = True
    candidate["mil_runbook_admission_ready"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operations_runbook_root_value_invalid" for finding in findings)
    assert candidate["mil_runbook_admission_ready"] is True


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")
    candidate = deepcopy(payload)
    candidate["operations_runbook_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operations_runbook_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "operations_runbook_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_operations_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")
    candidate = deepcopy(payload)
    candidate["operations_runbook_surfaces"][3]["public_safe_note"] = "alert_route=prod-pager"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operations_runbook_forbidden_private_value_pattern" for finding in findings)
    assert not any(finding.rule_id == "operations_runbook_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_support_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operations/runbook witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "customer-support operations are ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operations_runbook_forbidden_promotion_phrase" for finding in findings)
    assert any(finding.rule_id == "operations_runbook_next_action_invalid" for finding in findings)
