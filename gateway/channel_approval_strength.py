"""Channel approval strength policy.

Purpose: decide whether an approval response is strong enough for the
requested channel, actor, tenant, request, and action risk.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: Python standard library.
Invariants:
  - Casual approvals never satisfy request-bound actions.
  - Cross-channel approvals require an explicit channel-binding witness.
  - High and critical approvals require operator authority stronger than a
    normal external-channel message.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChannelTrust(StrEnum):
    """Trust class assigned to a source channel before approval evaluation."""

    TRUSTED_CONTROL = "trusted_control"
    VERIFIED_EXTERNAL = "verified_external"
    WEAK_EXTERNAL = "weak_external"
    UNTRUSTED = "untrusted"


class ApprovalRisk(StrEnum):
    """Risk tier used by channel approval-strength policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStrength(StrEnum):
    """Observed approval strength after binding checks are applied."""

    NONE = "none"
    CONTEXTUAL = "contextual"
    REQUEST_BOUND = "request_bound"
    OPERATOR_BOUND = "operator_bound"
    DUAL_CONTROL = "dual_control"


class ApprovalStrengthDecision(StrEnum):
    """Admission decision for one approval response."""

    ALLOW = "allow"
    BLOCK = "block"


_CHANNEL_TRUST: dict[str, ChannelTrust] = {
    "operator_goal_intake": ChannelTrust.TRUSTED_CONTROL,
    "operator_console": ChannelTrust.TRUSTED_CONTROL,
    "test": ChannelTrust.TRUSTED_CONTROL,
    "web": ChannelTrust.TRUSTED_CONTROL,
    "slack": ChannelTrust.VERIFIED_EXTERNAL,
    "teams": ChannelTrust.VERIFIED_EXTERNAL,
    "whatsapp": ChannelTrust.WEAK_EXTERNAL,
    "telegram": ChannelTrust.WEAK_EXTERNAL,
    "sms": ChannelTrust.WEAK_EXTERNAL,
    "phone": ChannelTrust.WEAK_EXTERNAL,
    "email": ChannelTrust.WEAK_EXTERNAL,
    "discord": ChannelTrust.WEAK_EXTERNAL,
}

_STRENGTH_ORDER: dict[ApprovalStrength, int] = {
    ApprovalStrength.NONE: 0,
    ApprovalStrength.CONTEXTUAL: 1,
    ApprovalStrength.REQUEST_BOUND: 2,
    ApprovalStrength.OPERATOR_BOUND: 3,
    ApprovalStrength.DUAL_CONTROL: 4,
}

_REQUIRED_STRENGTH_BY_RISK: dict[ApprovalRisk, ApprovalStrength] = {
    ApprovalRisk.LOW: ApprovalStrength.CONTEXTUAL,
    ApprovalRisk.MEDIUM: ApprovalStrength.REQUEST_BOUND,
    ApprovalRisk.HIGH: ApprovalStrength.OPERATOR_BOUND,
    ApprovalRisk.CRITICAL: ApprovalStrength.DUAL_CONTROL,
}


@dataclass(frozen=True, slots=True)
class ChannelApprovalStrengthRequest:
    """Inputs needed to evaluate one approval response.

    Input contract:
      - request_channel and response_channel identify the original approval
        request and the channel that sent the response.
      - tenant_id_matches, identity_id_matches, and request_id_matches are
        caller-provided binding checks.
      - channel_binding_present proves an allowed cross-channel handoff.
    Output contract:
      - evaluate_channel_approval_strength returns a deterministic decision
        with explicit reasons and required controls.
    Error contract:
      - unknown channels are treated as untrusted rather than raising.
    """

    request_channel: str
    response_channel: str
    risk_tier: ApprovalRisk
    tenant_id_matches: bool
    identity_id_matches: bool
    request_id_matches: bool
    approval_not_expired: bool
    actor_has_approval_authority: bool
    channel_binding_present: bool = False
    operator_session_present: bool = False
    second_approval_present: bool = False


@dataclass(frozen=True, slots=True)
class ChannelApprovalStrengthResult:
    """Deterministic channel approval-strength decision."""

    decision: ApprovalStrengthDecision
    observed_strength: ApprovalStrength
    required_strength: ApprovalStrength
    request_channel_trust: ChannelTrust
    response_channel_trust: ChannelTrust
    cross_channel: bool
    reasons: tuple[str, ...]
    required_controls: tuple[str, ...]


def channel_trust(channel: str) -> ChannelTrust:
    """Return the configured trust class for a channel name."""

    normalized_channel = channel.strip().lower()
    return _CHANNEL_TRUST.get(normalized_channel, ChannelTrust.UNTRUSTED)


def required_approval_strength(risk_tier: ApprovalRisk) -> ApprovalStrength:
    """Return the minimum approval strength for an action risk tier."""

    return _REQUIRED_STRENGTH_BY_RISK[risk_tier]


def evaluate_channel_approval_strength(
    request: ChannelApprovalStrengthRequest,
) -> ChannelApprovalStrengthResult:
    """Evaluate whether one approval response satisfies channel policy."""

    required_strength = required_approval_strength(request.risk_tier)
    request_trust = channel_trust(request.request_channel)
    response_trust = channel_trust(request.response_channel)
    cross_channel = request.request_channel.strip().lower() != request.response_channel.strip().lower()
    reasons: list[str] = []
    required_controls: list[str] = []

    if response_trust == ChannelTrust.UNTRUSTED:
        reasons.append("response_channel_untrusted")
        required_controls.append("known_channel_required")
    if not request.tenant_id_matches:
        reasons.append("tenant_id_mismatch")
        required_controls.append("tenant_binding_required")
    if not request.identity_id_matches:
        reasons.append("identity_id_mismatch")
        required_controls.append("identity_binding_required")
    if not request.request_id_matches:
        reasons.append("request_id_missing_or_mismatch")
        required_controls.append("request_id_binding_required")
    if not request.approval_not_expired:
        reasons.append("approval_expired")
        required_controls.append("fresh_approval_required")
    if cross_channel and not request.channel_binding_present:
        reasons.append("cross_channel_binding_missing")
        required_controls.append("cross_channel_binding_witness_required")
    if not request.actor_has_approval_authority:
        reasons.append("actor_authority_missing")
        required_controls.append("actor_approval_authority_required")
    if request.risk_tier in {ApprovalRisk.HIGH, ApprovalRisk.CRITICAL} and not request.operator_session_present:
        reasons.append("operator_session_missing")
        required_controls.append("operator_bound_approval_required")
    if request.risk_tier == ApprovalRisk.CRITICAL and not request.second_approval_present:
        reasons.append("second_approval_missing")
        required_controls.append("dual_control_required")

    observed_strength = _observed_strength(request, cross_channel, reasons)
    if _STRENGTH_ORDER[observed_strength] < _STRENGTH_ORDER[required_strength]:
        reasons.append("approval_strength_insufficient")
        required_controls.append(f"{required_strength.value}_approval_required")

    decision = ApprovalStrengthDecision.BLOCK if reasons else ApprovalStrengthDecision.ALLOW
    return ChannelApprovalStrengthResult(
        decision=decision,
        observed_strength=observed_strength,
        required_strength=required_strength,
        request_channel_trust=request_trust,
        response_channel_trust=response_trust,
        cross_channel=cross_channel,
        reasons=tuple(dict.fromkeys(reasons)),
        required_controls=tuple(dict.fromkeys(required_controls)),
    )


def _observed_strength(
    request: ChannelApprovalStrengthRequest,
    cross_channel: bool,
    blocking_reasons: list[str],
) -> ApprovalStrength:
    """Derive the strongest admissible approval level from bound inputs."""

    if blocking_reasons:
        return ApprovalStrength.NONE

    if request.risk_tier == ApprovalRisk.CRITICAL and request.second_approval_present and request.operator_session_present:
        return ApprovalStrength.DUAL_CONTROL
    if request.actor_has_approval_authority and request.operator_session_present:
        return ApprovalStrength.OPERATOR_BOUND
    if (
        request.tenant_id_matches
        and request.identity_id_matches
        and request.request_id_matches
        and request.approval_not_expired
        and not (cross_channel and not request.channel_binding_present)
    ):
        return ApprovalStrength.REQUEST_BOUND
    if request.tenant_id_matches and request.identity_id_matches:
        return ApprovalStrength.CONTEXTUAL
    return ApprovalStrength.NONE
