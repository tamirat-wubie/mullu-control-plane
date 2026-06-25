"""Policy denial response composer tests.

Purpose: verify denial templates produce user-facing text and redaction
metadata without leaking internal exception detail.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: gateway.denial_response.
Invariants: denial bodies are plain text; internal reasons remain metadata-only
and bounded by explicit redaction flags.
"""

from __future__ import annotations

from gateway.denial_response import (
    DenialResponseKind,
    compose_policy_denial_response,
)


def test_tenant_denial_template_is_user_facing_and_redacted() -> None:
    denial = compose_policy_denial_response(DenialResponseKind.TENANT_NOT_FOUND)

    assert "don't recognize" in denial.body
    assert "traceback" not in denial.body.lower()
    assert denial.metadata["denial_kind"] == "tenant_not_found"
    assert denial.metadata["denial_user_facing"] is True
    assert denial.metadata["denial_redacted"] is True
    assert denial.metadata["denial_internal_reason_exposed"] is False


def test_approval_strength_denial_preserves_controls_without_raw_detail() -> None:
    denial = compose_policy_denial_response(
        "approval_strength_denied",
        request_id="req-123",
        required_controls=("operator_bound_approval_required", "operator_bound_approval_required"),
        evidence_refs=("receipt://approval/req-123",),
    )

    assert "approval-strength policy" in denial.body
    assert "operator_bound_approval_required" not in denial.body
    assert denial.metadata["request_id"] == "req-123"
    assert denial.metadata["denial_required_controls"] == ("operator_bound_approval_required",)
    assert denial.metadata["denial_evidence_refs"] == ("receipt://approval/req-123",)
    assert denial.metadata["denial_next_action"] == "provide_bound_approval_evidence"


def test_approval_denied_template_is_receipt_oriented() -> None:
    denial = compose_policy_denial_response(
        DenialResponseKind.APPROVAL_DENIED,
        request_id="req-deny-1",
        evidence_refs=("approval-request://req-deny-1",),
    )

    assert "will not execute" in denial.body
    assert denial.metadata["denial_kind"] == "approval_denied"
    assert denial.metadata["request_id"] == "req-deny-1"
    assert denial.metadata["denial_next_action"] == "inspect_denial_or_block_receipts"
    assert denial.metadata["denial_evidence_refs"] == ("approval-request://req-deny-1",)


def test_unknown_denial_kind_degrades_to_policy_denied() -> None:
    denial = compose_policy_denial_response("new_internal_block_reason")

    assert denial.kind == DenialResponseKind.POLICY_DENIED
    assert "governed policy check" in denial.body
    assert denial.metadata["denial_kind"] == "policy_denied"
    assert denial.metadata["denial_internal_reason_exposed"] is False
