"""Cross-channel conversation binding policy.

Purpose: decide whether a response from one communication channel may be
bound to a conversation that began on another channel.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: Python standard library; gateway.channel_approval_strength.
Invariants:
  - Same-channel replies require a matching conversation or binding record.
  - Cross-channel replies require an explicit channel-binding witness.
  - Tenant and identity bindings must match before any conversation handoff is
    allowed.
  - Audit receipts expose hashes and policy facts, not raw message text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from gateway.channel_approval_strength import ChannelTrust, channel_trust


class ConversationBindingDecision(StrEnum):
    """Admission decision for one conversation-binding attempt."""

    ALLOW = "allow"
    BLOCK = "block"


class ConversationBindingScope(StrEnum):
    """Relationship between the original and response channels."""

    SAME_CHANNEL = "same_channel"
    CROSS_CHANNEL = "cross_channel"


@dataclass(frozen=True, slots=True)
class CrossChannelConversationBindingRequest:
    """Inputs needed to evaluate one conversation handoff.

    Input contract:
      - source_channel and response_channel identify where the conversation
        began and where the reply arrived.
      - source_conversation_id and response_conversation_id are opaque channel
        conversation identifiers.
      - tenant_id_matches, identity_id_matches, request_id_matches, and
        conversation_binding_matches are caller-provided binding checks.
      - binding_witness_present proves an allowed cross-channel handoff.
    Output contract:
      - evaluate_cross_channel_conversation_binding returns a deterministic
        decision with explicit reasons, controls, and a stable binding ref.
    Error contract:
      - unknown or blank channels and conversations are treated as blocked
        policy facts rather than raising.
    """

    source_channel: str
    response_channel: str
    source_conversation_id: str
    response_conversation_id: str
    tenant_id_matches: bool
    identity_id_matches: bool
    request_id_matches: bool = False
    conversation_binding_matches: bool = False
    binding_witness_present: bool = False
    binding_not_expired: bool = True
    actor_authorized_for_cross_channel: bool = False


@dataclass(frozen=True, slots=True)
class CrossChannelConversationBindingResult:
    """Deterministic conversation-binding decision."""

    decision: ConversationBindingDecision
    scope: ConversationBindingScope
    source_channel_trust: ChannelTrust
    response_channel_trust: ChannelTrust
    same_conversation: bool
    binding_ref: str | None
    reasons: tuple[str, ...]
    required_controls: tuple[str, ...]


def evaluate_cross_channel_conversation_binding(
    request: CrossChannelConversationBindingRequest,
) -> CrossChannelConversationBindingResult:
    """Evaluate whether a reply can bind to an existing conversation."""

    source_channel = _normalize(request.source_channel)
    response_channel = _normalize(request.response_channel)
    source_conversation_id = request.source_conversation_id.strip()
    response_conversation_id = request.response_conversation_id.strip()
    source_trust = channel_trust(source_channel)
    response_trust = channel_trust(response_channel)
    scope = (
        ConversationBindingScope.SAME_CHANNEL
        if source_channel == response_channel
        else ConversationBindingScope.CROSS_CHANNEL
    )
    same_conversation = (
        bool(source_conversation_id)
        and bool(response_conversation_id)
        and source_conversation_id == response_conversation_id
    )
    has_conversation_evidence = same_conversation or request.conversation_binding_matches
    has_request_or_conversation_evidence = has_conversation_evidence or request.request_id_matches
    reasons: list[str] = []
    required_controls: list[str] = []

    if source_trust == ChannelTrust.UNTRUSTED:
        reasons.append("source_channel_untrusted")
        required_controls.append("known_source_channel_required")
    if response_trust == ChannelTrust.UNTRUSTED:
        reasons.append("response_channel_untrusted")
        required_controls.append("known_response_channel_required")
    if not source_conversation_id:
        reasons.append("source_conversation_id_missing")
        required_controls.append("source_conversation_id_required")
    if not response_conversation_id:
        reasons.append("response_conversation_id_missing")
        required_controls.append("response_conversation_id_required")
    if not request.tenant_id_matches:
        reasons.append("tenant_id_mismatch")
        required_controls.append("tenant_binding_required")
    if not request.identity_id_matches:
        reasons.append("identity_id_mismatch")
        required_controls.append("identity_binding_required")

    if scope == ConversationBindingScope.SAME_CHANNEL and not has_conversation_evidence:
        reasons.append("same_channel_conversation_binding_missing")
        required_controls.append("same_channel_conversation_binding_required")

    if scope == ConversationBindingScope.CROSS_CHANNEL:
        if not request.binding_witness_present:
            reasons.append("cross_channel_binding_witness_missing")
            required_controls.append("cross_channel_binding_witness_required")
        if not request.binding_not_expired:
            reasons.append("cross_channel_binding_expired")
            required_controls.append("fresh_cross_channel_binding_required")
        if not request.actor_authorized_for_cross_channel:
            reasons.append("cross_channel_actor_authority_missing")
            required_controls.append("cross_channel_actor_authority_required")
        if not has_request_or_conversation_evidence:
            reasons.append("cross_channel_request_or_conversation_binding_missing")
            required_controls.append("request_or_conversation_binding_required")

    decision = ConversationBindingDecision.BLOCK if reasons else ConversationBindingDecision.ALLOW
    binding_ref = None
    if decision == ConversationBindingDecision.ALLOW:
        binding_ref = "conversation-binding:" + _stable_digest(
            source_channel,
            response_channel,
            source_conversation_id,
            response_conversation_id,
            str(request.request_id_matches),
            str(request.conversation_binding_matches),
        )

    return CrossChannelConversationBindingResult(
        decision=decision,
        scope=scope,
        source_channel_trust=source_trust,
        response_channel_trust=response_trust,
        same_conversation=same_conversation,
        binding_ref=binding_ref,
        reasons=tuple(dict.fromkeys(reasons)),
        required_controls=tuple(dict.fromkeys(required_controls)),
    )


def build_cross_channel_conversation_binding_receipt(
    request: CrossChannelConversationBindingRequest,
    result: CrossChannelConversationBindingResult,
) -> dict[str, Any]:
    """Build an audit receipt for a conversation-binding decision."""

    receipt: dict[str, Any] = {
        "receipt_type": "cross_channel_conversation_binding_receipt",
        "decision": result.decision.value,
        "scope": result.scope.value,
        "source_channel": _normalize(request.source_channel),
        "response_channel": _normalize(request.response_channel),
        "source_channel_trust": result.source_channel_trust.value,
        "response_channel_trust": result.response_channel_trust.value,
        "source_conversation_hash": _stable_digest(request.source_conversation_id.strip()),
        "response_conversation_hash": _stable_digest(request.response_conversation_id.strip()),
        "same_conversation": result.same_conversation,
        "tenant_id_matches": request.tenant_id_matches,
        "identity_id_matches": request.identity_id_matches,
        "request_id_matches": request.request_id_matches,
        "conversation_binding_matches": request.conversation_binding_matches,
        "binding_witness_present": request.binding_witness_present,
        "binding_not_expired": request.binding_not_expired,
        "actor_authorized_for_cross_channel": request.actor_authorized_for_cross_channel,
        "binding_ref": result.binding_ref,
        "reasons": list(result.reasons),
        "required_controls": list(result.required_controls),
        "raw_message_exposed": False,
        "live_channel_promotion_claimed": False,
    }
    receipt["receipt_hash"] = _stable_digest(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return receipt


def _normalize(value: str) -> str:
    return value.strip().lower()


def _stable_digest(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
