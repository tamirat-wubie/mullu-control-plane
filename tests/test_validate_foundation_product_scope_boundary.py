"""Tests for the Foundation Mode product-scope boundary validator.

Purpose: prove the selected local learning lane does not become a pilot,
customer, market, launch, deployment, or legal-readiness claim.
Governance scope: Foundation Mode, product scope, local learning lane,
platform non-restriction, pilot blocking, customer blocking, and launch blocking.
Dependencies: scripts.validate_foundation_product_scope_boundary.
Invariants: the witness keeps the selected lane local, leaves long-term product
scope unrestricted, and rejects readiness-promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_product_scope_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_LANES,
    EXPECTED_SELECTED_LEARNING_LANE,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_product_scope_boundary,
    validate_packet,
)


def test_foundation_product_scope_boundary_artifacts_pass() -> None:
    assert validate_foundation_product_scope_boundary() == []


def test_product_scope_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert payload["selected_learning_lane"] == EXPECTED_SELECTED_LEARNING_LANE
    assert tuple((lane["lane_id"], lane["lane_type"], lane["state"]) for lane in payload["learning_lanes"]) == EXPECTED_LANES
    assert payload["long_term_platform_restricted"] is False
    assert payload["pilot_access_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["market_validation_claimed"] is False
    assert payload["deployment_dependency_allowed"] is False


def test_witness_rejects_platform_restriction() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")
    candidate = deepcopy(payload)
    candidate["long_term_platform_restricted"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "product_scope_root_value_invalid" for finding in findings)


def test_witness_rejects_pilot_access_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")
    candidate = deepcopy(payload)
    candidate["pilot_access_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "product_scope_root_value_invalid" for finding in findings)


def test_witness_rejects_selected_lane_replacement() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")
    candidate = deepcopy(payload)
    candidate["selected_learning_lane"] = "finance_approval_simulation"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "product_scope_root_value_invalid" for finding in findings)


def test_witness_rejects_lane_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")
    candidate = deepcopy(payload)
    candidate["learning_lanes"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "product_scope_lane_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "product_scope_lane_state_invalid" for finding in findings)


def test_witness_rejects_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "product-scope witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "This lane is pilot-ready."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "product_scope_forbidden_promotion_phrase" for finding in findings)
