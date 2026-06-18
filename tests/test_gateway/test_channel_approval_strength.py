"""Channel approval-strength policy tests.

Purpose: verify approval responses are admitted only when channel, actor,
tenant, request, and risk-strength constraints are satisfied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: gateway.channel_approval_strength.
Invariants: casual approvals cannot satisfy request-bound actions; high and
critical risks require operator-bound authority.
"""

from __future__ import annotations

from gateway.channel_approval_strength import (
    ApprovalRisk,
    ApprovalStrength,
    ApprovalStrengthDecision,
    ChannelApprovalStrengthRequest,
    ChannelTrust,
    channel_trust,
    evaluate_channel_approval_strength,
    required_approval_strength,
)


def test_casual_yes_without_request_id_is_blocked() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="slack",
            response_channel="slack",
            risk_tier=ApprovalRisk.MEDIUM,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=False,
            approval_not_expired=True,
            actor_has_approval_authority=True,
        )
    )

    assert result.decision == ApprovalStrengthDecision.BLOCK
    assert result.observed_strength == ApprovalStrength.NONE
    assert "request_id_missing_or_mismatch" in result.reasons
    assert "request_id_binding_required" in result.required_controls


def test_bound_same_channel_medium_approval_is_allowed() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="slack",
            response_channel="slack",
            risk_tier=ApprovalRisk.MEDIUM,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
        )
    )

    assert result.decision == ApprovalStrengthDecision.ALLOW
    assert result.observed_strength == ApprovalStrength.REQUEST_BOUND
    assert result.required_strength == ApprovalStrength.REQUEST_BOUND
    assert result.reasons == ()


def test_cross_channel_approval_requires_binding_witness() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="web",
            response_channel="slack",
            risk_tier=ApprovalRisk.MEDIUM,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            channel_binding_present=False,
        )
    )

    assert result.decision == ApprovalStrengthDecision.BLOCK
    assert result.cross_channel is True
    assert "cross_channel_binding_missing" in result.reasons
    assert "cross_channel_binding_witness_required" in result.required_controls


def test_cross_channel_bound_medium_approval_is_allowed() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="web",
            response_channel="slack",
            risk_tier=ApprovalRisk.MEDIUM,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            channel_binding_present=True,
        )
    )

    assert result.decision == ApprovalStrengthDecision.ALLOW
    assert result.cross_channel is True
    assert result.observed_strength == ApprovalStrength.REQUEST_BOUND
    assert result.response_channel_trust == ChannelTrust.VERIFIED_EXTERNAL


def test_high_risk_external_message_without_operator_session_is_blocked() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="slack",
            response_channel="slack",
            risk_tier=ApprovalRisk.HIGH,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            operator_session_present=False,
        )
    )

    assert result.decision == ApprovalStrengthDecision.BLOCK
    assert result.required_strength == ApprovalStrength.OPERATOR_BOUND
    assert "operator_session_missing" in result.reasons
    assert "operator_bound_approval_required" in result.required_controls


def test_high_risk_operator_bound_approval_is_allowed() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="web",
            response_channel="web",
            risk_tier=ApprovalRisk.HIGH,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            operator_session_present=True,
        )
    )

    assert result.decision == ApprovalStrengthDecision.ALLOW
    assert result.observed_strength == ApprovalStrength.OPERATOR_BOUND
    assert result.request_channel_trust == ChannelTrust.TRUSTED_CONTROL
    assert result.reasons == ()


def test_critical_risk_requires_second_approval() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="operator_console",
            response_channel="operator_console",
            risk_tier=ApprovalRisk.CRITICAL,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            operator_session_present=True,
            second_approval_present=False,
        )
    )

    assert result.decision == ApprovalStrengthDecision.BLOCK
    assert result.required_strength == ApprovalStrength.DUAL_CONTROL
    assert "second_approval_missing" in result.reasons
    assert "dual_control_required" in result.required_controls


def test_critical_dual_control_approval_is_allowed() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="operator_console",
            response_channel="operator_console",
            risk_tier=ApprovalRisk.CRITICAL,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            operator_session_present=True,
            second_approval_present=True,
        )
    )

    assert result.decision == ApprovalStrengthDecision.ALLOW
    assert result.observed_strength == ApprovalStrength.DUAL_CONTROL
    assert result.required_strength == ApprovalStrength.DUAL_CONTROL
    assert result.reasons == ()


def test_unknown_channel_is_untrusted_and_blocks() -> None:
    result = evaluate_channel_approval_strength(
        ChannelApprovalStrengthRequest(
            request_channel="web",
            response_channel="unknown-chat",
            risk_tier=ApprovalRisk.LOW,
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            approval_not_expired=True,
            actor_has_approval_authority=True,
            channel_binding_present=True,
        )
    )

    assert channel_trust("unknown-chat") == ChannelTrust.UNTRUSTED
    assert required_approval_strength(ApprovalRisk.LOW) == ApprovalStrength.CONTEXTUAL
    assert result.decision == ApprovalStrengthDecision.BLOCK
    assert "response_channel_untrusted" in result.reasons
