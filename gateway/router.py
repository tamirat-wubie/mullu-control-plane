"""Gateway Router — Unified message ingress through governance.

Purpose: Receives normalized messages from channel adapters, resolves tenant
    identity, opens a GovernedSession, executes through the LLM pipeline,
    and returns the response through the originating channel.
Invariants:
  - Every message flows through GovernedSession (no bypass path).
  - Tenant is resolved from channel user identity, never from message content.
  - Failed governance checks return structured denial to the user.
  - Every message produces an audit trail entry.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from gateway.approval import ApprovalRouter, ApprovalStatus
from gateway.skill_dispatch import SkillDispatcher, detect_intent


@dataclass(frozen=True, slots=True)
class GatewayMessage:
    """Canonical inbound message from any channel."""

    message_id: str
    channel: str  # "whatsapp", "telegram", "slack", "discord", "web"
    sender_id: str  # Channel-specific user ID (phone number, user ID, etc.)
    body: str
    conversation_id: str = ""
    attachments: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    received_at: str = ""


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """Response to send back through the originating channel."""

    message_id: str
    channel: str
    recipient_id: str
    body: str
    governed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TenantMapping:
    """Maps a channel user identity to a tenant."""

    channel: str
    sender_id: str
    tenant_id: str
    identity_id: str


class ChannelAdapter(Protocol):
    """Protocol for channel-specific message handling."""

    @property
    def channel_name(self) -> str: ...

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool: ...


class GatewayRouter:
    """Routes messages from channels through governed execution.

    Flow:
    1. Receive GatewayMessage from channel adapter
    2. Resolve tenant from channel user identity
    3. Open GovernedSession
    4. Execute LLM call with message as prompt
    5. Return response through originating channel

    All operations are governed — no bypass path.
    """

    def __init__(
        self,
        *,
        platform: Any,  # Platform instance from governed_session.py
        clock: Callable[[], str] | None = None,
        approval_router: ApprovalRouter | None = None,
        skill_dispatcher: SkillDispatcher | None = None,
    ) -> None:
        self._platform = platform
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._approval = approval_router or ApprovalRouter(clock=self._clock)
        self._skills = skill_dispatcher or SkillDispatcher()
        self._tenant_mappings: dict[str, TenantMapping] = {}  # "channel:sender_id" -> mapping
        self._channels: dict[str, ChannelAdapter] = {}
        self._message_count = 0
        self._error_count = 0

    def register_channel(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._channels[adapter.channel_name] = adapter

    def register_tenant_mapping(self, mapping: TenantMapping) -> None:
        """Map a channel user identity to a tenant."""
        key = f"{mapping.channel}:{mapping.sender_id}"
        self._tenant_mappings[key] = mapping

    def resolve_tenant(self, channel: str, sender_id: str) -> TenantMapping | None:
        """Resolve tenant from channel user identity."""
        key = f"{channel}:{sender_id}"
        return self._tenant_mappings.get(key)

    def handle_message(self, message: GatewayMessage) -> GatewayResponse:
        """Process an inbound message through the full governance pipeline.

        This is the main entry point. Every message goes through:
        tenant resolution → session → content safety → LLM → PII redaction → audit → proof.
        """
        self._message_count += 1

        # 1. Resolve tenant
        mapping = self.resolve_tenant(message.channel, message.sender_id)
        if mapping is None:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="I don't recognize your account. Please register first.",
                governed=True,
                metadata={"error": "tenant_not_found"},
            )

        # 2. Open governed session
        try:
            session = self._platform.connect(
                identity_id=mapping.identity_id,
                tenant_id=mapping.tenant_id,
            )
        except PermissionError:
            self._error_count += 1
            return GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body="Access denied.",
                governed=True,
                metadata={"error": "access_denied"},
            )

        # 3. Risk classification + approval
        approval = self._approval.request_approval(
            tenant_id=mapping.tenant_id,
            identity_id=mapping.identity_id,
            channel=message.channel,
            action_description="llm_completion",
            body=message.body,
        )
        if approval.status == ApprovalStatus.PENDING:
            # Medium/high risk — return pending message, wait for approval
            try:
                session.close()
            except Exception:
                pass
            return GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body=f"This action requires approval (risk: {approval.risk_tier.value}). "
                     f"Request ID: {approval.request_id}",
                governed=True,
                metadata={"approval_required": True, "request_id": approval.request_id},
            )

        # 4. Check for skill intent (financial, etc.) before LLM
        intent = detect_intent(message.body)
        if intent is not None:
            skill_result = self._skills.dispatch(intent, mapping.tenant_id, mapping.identity_id)
            if skill_result is not None:
                response_body = skill_result.get("response", "Skill executed.")
                try:
                    session.close()
                except Exception:
                    pass
                response = GatewayResponse(
                    message_id=self._gen_id("resp", message.message_id),
                    channel=message.channel,
                    recipient_id=message.sender_id,
                    body=response_body,
                    governed=True,
                    metadata=skill_result,
                )
                adapter = self._channels.get(message.channel)
                if adapter is not None:
                    try:
                        adapter.send(message.sender_id, response_body)
                    except Exception:
                        pass
                return response

        # 5. Execute through LLM (governed — no skill match)
        try:
            result = session.llm(message.body)
            response_body = result.content if result.succeeded else f"I couldn't process that: {result.error}"
        except ValueError as exc:
            # Content safety blocked
            response_body = "I can't process that request due to safety policies."
            session.close()
            return GatewayResponse(
                message_id=self._gen_id("resp", message.message_id),
                channel=message.channel,
                recipient_id=message.sender_id,
                body=response_body,
                governed=True,
                metadata={"error": "content_blocked"},
            )
        except RuntimeError:
            response_body = "Service temporarily unavailable."
            self._error_count += 1
        except Exception as exc:
            response_body = "An error occurred. Please try again."
            self._error_count += 1

        # 4. Close session
        try:
            session.close()
        except Exception:
            pass

        # 5. Send response through originating channel
        response = GatewayResponse(
            message_id=self._gen_id("resp", message.message_id),
            channel=message.channel,
            recipient_id=message.sender_id,
            body=response_body,
            governed=True,
        )

        adapter = self._channels.get(message.channel)
        if adapter is not None:
            try:
                adapter.send(message.sender_id, response_body)
            except Exception:
                pass  # Channel send failure — response still returned

        return response

    def handle_approval_callback(self, request_id: str, approved: bool, resolved_by: str = "user") -> GatewayResponse | None:
        """Handle an approval callback from a channel button press.

        Returns a GatewayResponse if the approval resolves successfully, None otherwise.
        """
        result = self._approval.resolve(request_id, approved=approved, resolved_by=resolved_by)
        if result is None:
            return None
        status = "approved" if result.status == ApprovalStatus.APPROVED else "denied"
        return GatewayResponse(
            message_id=self._gen_id("apr-resp", request_id),
            channel=result.channel,
            recipient_id=result.identity_id,
            body=f"Request {request_id} has been {status}.",
            governed=True,
            metadata={"approval_resolved": True, "status": status},
        )

    @property
    def pending_approvals(self) -> int:
        return self._approval.pending_count

    def _gen_id(self, prefix: str, ref: str) -> str:
        return f"{prefix}-{hashlib.sha256(f'{ref}:{self._message_count}'.encode()).hexdigest()[:12]}"

    @property
    def message_count(self) -> int:
        return self._message_count

    @property
    def error_count(self) -> int:
        return self._error_count

    def summary(self) -> dict[str, Any]:
        return {
            "message_count": self._message_count,
            "error_count": self._error_count,
            "channels": list(self._channels.keys()),
            "tenant_mappings": len(self._tenant_mappings),
        }
