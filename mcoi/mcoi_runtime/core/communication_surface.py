"""Purpose: omni-channel communication surface engine.
Governance scope: message ingestion, outbound dispatch, delivery tracking,
    call session lifecycle, transcript management, communication policy
    evaluation, contact/escalation preference routing.
Dependencies: communication_surface contracts, core invariants.
Invariants:
  - All mutations are construct-then-commit (atomic append).
  - Public getters return frozen snapshots.
  - IDs are unique per collection; duplicates raise RuntimeCoreInvariantError.
  - Communication policy is fail-closed: no policy → DENY.
  - Outbound rate tracking is per-channel, per-hour window.
  - Call sessions follow a defined lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.communication_surface import (
    CallSession,
    CallSessionState,
    CallTranscript,
    ChannelCapabilityManifest,
    ChannelIdentity,
    ChannelType,
    CommunicationPolicy,
    CommunicationPolicyDecision,
    CommunicationPolicyEffect,
    ContactPreference,
    ConversationHandle,
    DeliveryReceipt,
    DeliveryStatus,
    EscalationPreference,
    InboundMessage,
    OutboundMessage,
    TranscriptSegment,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommunicationSurfaceEngine:
    """Omni-channel communication substrate.

    Normalizes channel-specific communication into canonical contracts,
    tracks delivery, manages call sessions, and enforces communication policy.
    """

    def __init__(self) -> None:
        self._identities: dict[str, ChannelIdentity] = {}
        self._conversations: dict[str, ConversationHandle] = {}
        self._inbound: dict[str, InboundMessage] = {}
        self._outbound: dict[str, OutboundMessage] = {}
        self._receipts: dict[str, DeliveryReceipt] = {}
        self._contact_prefs: dict[str, ContactPreference] = {}
        self._escalation_prefs: dict[str, EscalationPreference] = {}
        self._call_sessions: dict[str, CallSession] = {}
        self._transcripts: dict[str, CallTranscript] = {}
        self._policies: dict[str, CommunicationPolicy] = {}
        self._policy_decisions: list[CommunicationPolicyDecision] = []
        self._channel_manifests: dict[ChannelType, ChannelCapabilityManifest] = {}
        # Rate tracking: channel_type -> list of send timestamps
        self._outbound_timestamps: dict[ChannelType, list[datetime]] = {}

    # ------------------------------------------------------------------
    # Channel identities
    # ------------------------------------------------------------------

    def register_identity(self, identity: ChannelIdentity) -> ChannelIdentity:
        """Register a contact's channel identity."""
        if not isinstance(identity, ChannelIdentity):
            raise RuntimeCoreInvariantError("identity must be a ChannelIdentity")
        if identity.identity_id in self._identities:
            raise RuntimeCoreInvariantError(f"duplicate identity_id: {identity.identity_id}")
        self._identities[identity.identity_id] = identity
        return identity

    def get_identity(self, identity_id: str) -> ChannelIdentity | None:
        return self._identities.get(identity_id)

    def get_identities_for_contact(self, contact_id: str) -> tuple[ChannelIdentity, ...]:
        return tuple(i for i in self._identities.values() if i.contact_id == contact_id)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(self, handle: ConversationHandle) -> ConversationHandle:
        """Create or register a conversation handle."""
        if not isinstance(handle, ConversationHandle):
            raise RuntimeCoreInvariantError("handle must be a ConversationHandle")
        if handle.conversation_id in self._conversations:
            raise RuntimeCoreInvariantError(f"duplicate conversation_id: {handle.conversation_id}")
        self._conversations[handle.conversation_id] = handle
        return handle

    def get_conversation(self, conversation_id: str) -> ConversationHandle | None:
        return self._conversations.get(conversation_id)

    # ------------------------------------------------------------------
    # Inbound messages
    # ------------------------------------------------------------------

    def ingest_inbound(self, message: InboundMessage) -> InboundMessage:
        """Ingest a normalized inbound message."""
        if not isinstance(message, InboundMessage):
            raise RuntimeCoreInvariantError("message must be an InboundMessage")
        if message.message_id in self._inbound:
            raise RuntimeCoreInvariantError(f"duplicate inbound message_id: {message.message_id}")
        self._inbound[message.message_id] = message
        return message

    def get_inbound(self, message_id: str) -> InboundMessage | None:
        return self._inbound.get(message_id)

    def list_inbound_for_conversation(self, conversation_id: str) -> tuple[InboundMessage, ...]:
        return tuple(m for m in self._inbound.values() if m.conversation_id == conversation_id)

    # ------------------------------------------------------------------
    # Outbound messages
    # ------------------------------------------------------------------

    def send_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """Record an outbound message for dispatch."""
        if not isinstance(message, OutboundMessage):
            raise RuntimeCoreInvariantError("message must be an OutboundMessage")
        if message.message_id in self._outbound:
            raise RuntimeCoreInvariantError(f"duplicate outbound message_id: {message.message_id}")
        self._outbound[message.message_id] = message
        # Track timestamp for rate limiting
        ts_list = self._outbound_timestamps.setdefault(message.channel_type, [])
        ts_list.append(datetime.now(timezone.utc))
        return message

    def get_outbound(self, message_id: str) -> OutboundMessage | None:
        return self._outbound.get(message_id)

    def list_outbound_for_conversation(self, conversation_id: str) -> tuple[OutboundMessage, ...]:
        return tuple(m for m in self._outbound.values() if m.conversation_id == conversation_id)

    # ------------------------------------------------------------------
    # Delivery receipts
    # ------------------------------------------------------------------

    def record_receipt(self, receipt: DeliveryReceipt) -> DeliveryReceipt:
        """Record a delivery receipt for an outbound message."""
        if not isinstance(receipt, DeliveryReceipt):
            raise RuntimeCoreInvariantError("receipt must be a DeliveryReceipt")
        if receipt.message_id not in self._outbound:
            raise RuntimeCoreInvariantError(f"outbound message_id not found: {receipt.message_id}")
        if receipt.receipt_id in self._receipts:
            raise RuntimeCoreInvariantError(f"duplicate receipt_id: {receipt.receipt_id}")
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipts_for_message(self, message_id: str) -> tuple[DeliveryReceipt, ...]:
        return tuple(r for r in self._receipts.values() if r.message_id == message_id)

    # ------------------------------------------------------------------
    # Contact / escalation preferences
    # ------------------------------------------------------------------

    def set_contact_preference(self, pref: ContactPreference) -> ContactPreference:
        """Set or replace a contact's communication preferences."""
        if not isinstance(pref, ContactPreference):
            raise RuntimeCoreInvariantError("pref must be a ContactPreference")
        self._contact_prefs[pref.preference_id] = pref
        return pref

    def get_contact_preference(self, contact_id: str) -> ContactPreference | None:
        for p in self._contact_prefs.values():
            if p.contact_id == contact_id:
                return p
        return None

    def set_escalation_preference(self, pref: EscalationPreference) -> EscalationPreference:
        """Set or replace an escalation preference."""
        if not isinstance(pref, EscalationPreference):
            raise RuntimeCoreInvariantError("pref must be an EscalationPreference")
        self._escalation_prefs[pref.preference_id] = pref
        return pref

    def get_escalation_preference(self, contact_id: str) -> EscalationPreference | None:
        for p in self._escalation_prefs.values():
            if p.contact_id == contact_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Call sessions and transcripts
    # ------------------------------------------------------------------

    def start_call_session(self, session: CallSession) -> CallSession:
        """Start a new call session."""
        if not isinstance(session, CallSession):
            raise RuntimeCoreInvariantError("session must be a CallSession")
        if session.session_id in self._call_sessions:
            raise RuntimeCoreInvariantError(f"duplicate session_id: {session.session_id}")
        self._call_sessions[session.session_id] = session
        return session

    def complete_call_session(
        self,
        session_id: str,
        state: CallSessionState,
        ended_at: str,
        duration_seconds: int,
    ) -> CallSession:
        """Complete a call session with final state."""
        existing = self._call_sessions.get(session_id)
        if existing is None:
            raise RuntimeCoreInvariantError(f"session_id not found: {session_id}")
        if existing.state in (CallSessionState.COMPLETED, CallSessionState.FAILED, CallSessionState.MISSED):
            raise RuntimeCoreInvariantError(f"session already terminal: {existing.state}")
        completed = CallSession(
            session_id=existing.session_id,
            conversation_id=existing.conversation_id,
            channel_type=existing.channel_type,
            participant_ids=existing.participant_ids,
            state=state,
            started_at=existing.started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            metadata=dict(existing.metadata),
        )
        self._call_sessions[session_id] = completed
        return completed

    def get_call_session(self, session_id: str) -> CallSession | None:
        return self._call_sessions.get(session_id)

    def add_transcript(self, transcript: CallTranscript) -> CallTranscript:
        """Add a transcript for a call session."""
        if not isinstance(transcript, CallTranscript):
            raise RuntimeCoreInvariantError("transcript must be a CallTranscript")
        if transcript.session_id not in self._call_sessions:
            raise RuntimeCoreInvariantError(f"session_id not found: {transcript.session_id}")
        if transcript.transcript_id in self._transcripts:
            raise RuntimeCoreInvariantError(f"duplicate transcript_id: {transcript.transcript_id}")
        self._transcripts[transcript.transcript_id] = transcript
        return transcript

    def get_transcript(self, transcript_id: str) -> CallTranscript | None:
        return self._transcripts.get(transcript_id)

    def get_transcripts_for_session(self, session_id: str) -> tuple[CallTranscript, ...]:
        return tuple(t for t in self._transcripts.values() if t.session_id == session_id)

    # ------------------------------------------------------------------
    # Communication policy
    # ------------------------------------------------------------------

    def register_policy(self, policy: CommunicationPolicy) -> CommunicationPolicy:
        """Register a communication policy."""
        if not isinstance(policy, CommunicationPolicy):
            raise RuntimeCoreInvariantError("policy must be a CommunicationPolicy")
        self._policies[policy.policy_id] = policy
        return policy

    def evaluate_policy(
        self,
        policy_id: str,
        channel_type: ChannelType,
    ) -> CommunicationPolicyDecision:
        """Evaluate whether a channel is allowed under a policy. Fail-closed."""
        policy = self._policies.get(policy_id)
        if policy is None:
            # Fail-closed: no policy → deny
            decision = CommunicationPolicyDecision(
                decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type}),
                policy_id=policy_id,
                channel_type=channel_type,
                effect=CommunicationPolicyEffect.DENY,
                reason="No policy found — fail-closed deny",
                evaluated_at=_now_iso(),
            )
            self._policy_decisions.append(decision)
            return decision

        now = _now_iso()

        # Check denied first
        if channel_type in policy.denied_channels:
            decision = CommunicationPolicyDecision(
                decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type, "ts": now}),
                policy_id=policy_id,
                channel_type=channel_type,
                effect=CommunicationPolicyEffect.DENY,
                reason=f"Channel {channel_type} is denied by policy {policy.name}",
                evaluated_at=now,
            )
            self._policy_decisions.append(decision)
            return decision

        # Check require-approval
        if channel_type in policy.require_approval_channels:
            decision = CommunicationPolicyDecision(
                decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type, "ts": now}),
                policy_id=policy_id,
                channel_type=channel_type,
                effect=CommunicationPolicyEffect.REQUIRE_APPROVAL,
                reason=f"Channel {channel_type} requires approval under policy {policy.name}",
                evaluated_at=now,
            )
            self._policy_decisions.append(decision)
            return decision

        # Check rate limits
        if policy.max_outbound_per_hour is not None:
            cutoff = datetime.now(timezone.utc).replace(microsecond=0)
            from datetime import timedelta
            hour_ago = cutoff - timedelta(hours=1)
            recent = [
                ts for ts in self._outbound_timestamps.get(channel_type, [])
                if ts >= hour_ago
            ]
            if len(recent) >= policy.max_outbound_per_hour:
                decision = CommunicationPolicyDecision(
                    decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type, "ts": now}),
                    policy_id=policy_id,
                    channel_type=channel_type,
                    effect=CommunicationPolicyEffect.RATE_LIMITED,
                    reason=f"Rate limit exceeded: {len(recent)}/{policy.max_outbound_per_hour} per hour",
                    evaluated_at=now,
                )
                self._policy_decisions.append(decision)
                return decision

        # Check allowed
        if channel_type in policy.allowed_channels:
            decision = CommunicationPolicyDecision(
                decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type, "ts": now}),
                policy_id=policy_id,
                channel_type=channel_type,
                effect=CommunicationPolicyEffect.ALLOW,
                reason=f"Channel {channel_type} is allowed by policy {policy.name}",
                evaluated_at=now,
            )
            self._policy_decisions.append(decision)
            return decision

        # Fail-closed: not explicitly allowed → deny
        decision = CommunicationPolicyDecision(
            decision_id=stable_identifier("cpd", {"policy_id": policy_id, "channel": channel_type, "ts": now}),
            policy_id=policy_id,
            channel_type=channel_type,
            effect=CommunicationPolicyEffect.DENY,
            reason=f"Channel {channel_type} not in allowed list — fail-closed deny",
            evaluated_at=now,
        )
        self._policy_decisions.append(decision)
        return decision

    # ------------------------------------------------------------------
    # Channel capability manifests
    # ------------------------------------------------------------------

    def register_channel_manifest(self, manifest: ChannelCapabilityManifest) -> ChannelCapabilityManifest:
        """Register capabilities for a channel type."""
        if not isinstance(manifest, ChannelCapabilityManifest):
            raise RuntimeCoreInvariantError("manifest must be a ChannelCapabilityManifest")
        self._channel_manifests[manifest.channel_type] = manifest
        return manifest

    def get_channel_manifest(self, channel_type: ChannelType) -> ChannelCapabilityManifest | None:
        return self._channel_manifests.get(channel_type)

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------

    def route_for_contact(self, contact_id: str) -> ChannelType | None:
        """Return the contact's preferred channel, or None."""
        pref = self.get_contact_preference(contact_id)
        if pref is None or not pref.preferred_channels:
            return None
        return pref.preferred_channels[0]

    def route_for_escalation(self, contact_id: str) -> tuple[ChannelType, ...]:
        """Return the escalation chain for a contact."""
        pref = self.get_escalation_preference(contact_id)
        if pref is None:
            return ()
        return pref.escalation_chain

    # ------------------------------------------------------------------
    # Counts and state hash
    # ------------------------------------------------------------------

    @property
    def identity_count(self) -> int:
        return len(self._identities)

    @property
    def conversation_count(self) -> int:
        return len(self._conversations)

    @property
    def inbound_count(self) -> int:
        return len(self._inbound)

    @property
    def outbound_count(self) -> int:
        return len(self._outbound)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def call_session_count(self) -> int:
        return len(self._call_sessions)

    @property
    def transcript_count(self) -> int:
        return len(self._transcripts)

    def state_hash(self) -> str:
        """Deterministic hash over all ordered records."""
        parts: list[str] = []
        for k in sorted(self._identities):
            parts.append(f"ident:{k}")
        for k in sorted(self._conversations):
            parts.append(f"conv:{k}")
        for k in sorted(self._inbound):
            parts.append(f"in:{k}")
        for k in sorted(self._outbound):
            parts.append(f"out:{k}")
        for k in sorted(self._receipts):
            parts.append(f"rcpt:{k}")
        for k in sorted(self._call_sessions):
            parts.append(f"call:{k}")
        for k in sorted(self._transcripts):
            parts.append(f"txn:{k}")
        payload = "|".join(parts)
        return sha256(payload.encode()).hexdigest()
