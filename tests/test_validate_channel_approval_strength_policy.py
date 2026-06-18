"""Tests for the channel approval-strength policy validator.

Purpose: prove the Foundation Mode approval policy remains default-block,
request-bound, and high-risk operator-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: scripts.validate_channel_approval_strength_policy.
Invariants: casual approval, unbound cross-channel approval, and under-strength
approval paths remain rejected.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.validate_channel_approval_strength_policy import (
    EXAMPLE_PATH,
    REQUIRED_PROOF_OBLIGATIONS,
    load_json_payload,
    validate_channel_approval_strength_policy,
)


def test_channel_approval_strength_policy_example_passes() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    errors = validate_channel_approval_strength_policy(payload)

    assert errors == []
    assert payload["default_decision"] == "block"
    assert payload["cross_channel_rules"]["binding_witness_required"] is True
    assert "casual_yes_without_request_id" in payload["blocked_patterns"]


def test_channel_approval_strength_policy_rejects_default_allow() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["default_decision"] = "allow"

    errors = validate_channel_approval_strength_policy(mutated_payload)

    assert errors
    assert any("default_decision" in error for error in errors)
    assert mutated_payload["foundation_mode_only"] is True
    assert "request_id_bound" in mutated_payload["proof_obligations"]


def test_channel_approval_strength_policy_rejects_missing_cross_channel_binding() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["cross_channel_rules"]["binding_witness_required"] = False

    errors = validate_channel_approval_strength_policy(mutated_payload)

    assert errors
    assert any("binding_witness_required" in error for error in errors)
    assert mutated_payload["cross_channel_rules"]["same_identity_required"] is True
    assert mutated_payload["cross_channel_rules"]["same_request_id_required"] is True


def test_channel_approval_strength_policy_rejects_high_risk_downgrade() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    for entry in mutated_payload["risk_strength_matrix"]:
        if entry["risk_tier"] == "high":
            entry["required_strength"] = "request_bound"

    errors = validate_channel_approval_strength_policy(mutated_payload)

    assert errors
    assert any("high risk must require operator_bound" in error for error in errors)
    assert "high_risk_operator_bound" in mutated_payload["proof_obligations"]
    assert "critical_dual_control" in mutated_payload["proof_obligations"]


def test_channel_approval_strength_policy_rejects_missing_casual_text_obligation() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["proof_obligations"] = [
        obligation
        for obligation in REQUIRED_PROOF_OBLIGATIONS
        if obligation != "no_casual_text_approval"
    ]

    errors = validate_channel_approval_strength_policy(mutated_payload)

    assert errors
    assert any("no_casual_text_approval" in error for error in errors)
    assert mutated_payload["default_decision"] == "block"
    assert "casual_yes_without_request_id" in mutated_payload["blocked_patterns"]
