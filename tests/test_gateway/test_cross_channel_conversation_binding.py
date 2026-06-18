"""Cross-channel conversation-binding policy tests.

Purpose: verify conversation handoffs are admitted only when channel, tenant,
identity, request, and binding-witness constraints are satisfied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: gateway.cross_channel_conversation_binding.
Invariants: ambiguous cross-channel replies are blocked; audit receipts expose
hashes and policy facts, not raw message text.
"""

from __future__ import annotations

from gateway.channel_approval_strength import ChannelTrust
from gateway.cross_channel_conversation_binding import (
    ConversationBindingDecision,
    ConversationBindingScope,
    CrossChannelConversationBindingRequest,
    build_cross_channel_conversation_binding_receipt,
    evaluate_cross_channel_conversation_binding,
)


def test_same_channel_same_conversation_is_allowed() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="slack",
            response_channel="slack",
            source_conversation_id="thread-7",
            response_conversation_id="thread-7",
            tenant_id_matches=True,
            identity_id_matches=True,
        )
    )

    assert result.decision == ConversationBindingDecision.ALLOW
    assert result.scope == ConversationBindingScope.SAME_CHANNEL
    assert result.same_conversation is True
    assert result.binding_ref is not None
    assert result.reasons == ()


def test_same_channel_different_conversation_without_binding_is_blocked() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="slack",
            response_channel="slack",
            source_conversation_id="thread-7",
            response_conversation_id="thread-8",
            tenant_id_matches=True,
            identity_id_matches=True,
        )
    )

    assert result.decision == ConversationBindingDecision.BLOCK
    assert result.scope == ConversationBindingScope.SAME_CHANNEL
    assert result.binding_ref is None
    assert "same_channel_conversation_binding_missing" in result.reasons
    assert "same_channel_conversation_binding_required" in result.required_controls


def test_cross_channel_reply_without_witness_is_blocked() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="web",
            response_channel="slack",
            source_conversation_id="web-conversation-1",
            response_conversation_id="slack-thread-1",
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            actor_authorized_for_cross_channel=True,
            binding_witness_present=False,
        )
    )

    assert result.decision == ConversationBindingDecision.BLOCK
    assert result.scope == ConversationBindingScope.CROSS_CHANNEL
    assert result.response_channel_trust == ChannelTrust.VERIFIED_EXTERNAL
    assert "cross_channel_binding_witness_missing" in result.reasons
    assert "cross_channel_binding_witness_required" in result.required_controls


def test_cross_channel_bound_request_reply_is_allowed() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="web",
            response_channel="slack",
            source_conversation_id="web-conversation-1",
            response_conversation_id="slack-thread-1",
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            binding_witness_present=True,
            binding_not_expired=True,
            actor_authorized_for_cross_channel=True,
        )
    )

    assert result.decision == ConversationBindingDecision.ALLOW
    assert result.scope == ConversationBindingScope.CROSS_CHANNEL
    assert result.source_channel_trust == ChannelTrust.TRUSTED_CONTROL
    assert result.response_channel_trust == ChannelTrust.VERIFIED_EXTERNAL
    assert result.binding_ref is not None


def test_cross_channel_casual_reply_without_request_or_context_is_blocked() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="web",
            response_channel="whatsapp",
            source_conversation_id="web-conversation-1",
            response_conversation_id="whatsapp-chat-1",
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=False,
            conversation_binding_matches=False,
            binding_witness_present=True,
            actor_authorized_for_cross_channel=True,
        )
    )

    assert result.decision == ConversationBindingDecision.BLOCK
    assert result.response_channel_trust == ChannelTrust.WEAK_EXTERNAL
    assert "cross_channel_request_or_conversation_binding_missing" in result.reasons
    assert "request_or_conversation_binding_required" in result.required_controls
    assert result.binding_ref is None


def test_cross_channel_expired_binding_is_blocked() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="web",
            response_channel="slack",
            source_conversation_id="web-conversation-1",
            response_conversation_id="slack-thread-1",
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            binding_witness_present=True,
            binding_not_expired=False,
            actor_authorized_for_cross_channel=True,
        )
    )

    assert result.decision == ConversationBindingDecision.BLOCK
    assert "cross_channel_binding_expired" in result.reasons
    assert "fresh_cross_channel_binding_required" in result.required_controls
    assert result.binding_ref is None


def test_unknown_channel_blocks_with_explicit_reason() -> None:
    result = evaluate_cross_channel_conversation_binding(
        CrossChannelConversationBindingRequest(
            source_channel="web",
            response_channel="unknown-chat",
            source_conversation_id="web-conversation-1",
            response_conversation_id="external-thread-1",
            tenant_id_matches=True,
            identity_id_matches=True,
            request_id_matches=True,
            binding_witness_present=True,
            actor_authorized_for_cross_channel=True,
        )
    )

    assert result.decision == ConversationBindingDecision.BLOCK
    assert result.response_channel_trust == ChannelTrust.UNTRUSTED
    assert "response_channel_untrusted" in result.reasons
    assert "known_response_channel_required" in result.required_controls


def test_binding_receipt_hides_raw_message_and_is_stable() -> None:
    request = CrossChannelConversationBindingRequest(
        source_channel="web",
        response_channel="slack",
        source_conversation_id="web-conversation-1",
        response_conversation_id="slack-thread-1",
        tenant_id_matches=True,
        identity_id_matches=True,
        request_id_matches=True,
        binding_witness_present=True,
        actor_authorized_for_cross_channel=True,
    )
    result = evaluate_cross_channel_conversation_binding(request)

    receipt = build_cross_channel_conversation_binding_receipt(request, result)
    repeated_receipt = build_cross_channel_conversation_binding_receipt(request, result)

    assert receipt["receipt_type"] == "cross_channel_conversation_binding_receipt"
    assert receipt["decision"] == "allow"
    assert receipt["raw_message_exposed"] is False
    assert receipt["live_channel_promotion_claimed"] is False
    assert receipt["source_conversation_hash"] != request.source_conversation_id
    assert receipt["receipt_hash"] == repeated_receipt["receipt_hash"]
