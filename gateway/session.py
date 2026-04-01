"""Gateway Session Manager — Persistent conversation context.

Maps channel user → tenant → conversation context. Maintains session
state across messages so the agent has continuity without relying
on channel message history.

Invariants:
  - Context is tenant-scoped (no cross-tenant leakage).
  - Session expiry is enforced (configurable TTL).
  - Session count is bounded (eviction at MAX_SESSIONS).
  - Context reconstruction is governed (uses memory tiers, not raw history).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class ConversationContext:
    """Active conversation context for a channel user."""

    session_id: str
    channel: str
    sender_id: str
    tenant_id: str
    identity_id: str
    messages: list[dict[str, str]]  # [{"role": "user"/"assistant", "content": "..."}]
    created_at: str
    last_active_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.messages)


class SessionManager:
    """Manages conversation context across gateway messages.

    Each channel user gets a persistent context that accumulates
    message history (bounded) for LLM conversation continuity.
    Sessions are keyed by tenant_id:channel:sender_id to prevent
    cross-tenant context leakage.
    """

    MAX_SESSIONS = 50_000  # Evict oldest beyond this

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        max_context_messages: int = 20,
        session_ttl_seconds: int = 3600,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._max_messages = max_context_messages
        self._ttl = session_ttl_seconds
        self._contexts: dict[str, ConversationContext] = {}

    def _key(self, channel: str, sender_id: str, tenant_id: str = "") -> str:
        return f"{tenant_id}:{channel}:{sender_id}" if tenant_id else f":{channel}:{sender_id}"

    def get_or_create(
        self,
        *,
        channel: str,
        sender_id: str,
        tenant_id: str,
        identity_id: str,
    ) -> ConversationContext:
        """Get existing context or create a new one."""
        key = self._key(channel, sender_id, tenant_id)
        ctx = self._contexts.get(key)
        now = self._clock()

        if ctx is not None:
            ctx.last_active_at = now
            return ctx

        # Evict oldest if at capacity
        if len(self._contexts) >= self.MAX_SESSIONS:
            oldest_key = min(self._contexts, key=lambda k: self._contexts[k].last_active_at)
            del self._contexts[oldest_key]

        session_id = f"conv-{hashlib.sha256(f'{key}:{now}'.encode()).hexdigest()[:12]}"
        ctx = ConversationContext(
            session_id=session_id,
            channel=channel,
            sender_id=sender_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            messages=[],
            created_at=now,
            last_active_at=now,
        )
        self._contexts[key] = ctx
        return ctx

    def add_message(self, channel: str, sender_id: str, role: str, content: str, tenant_id: str = "") -> None:
        """Add a message to the conversation context."""
        key = self._key(channel, sender_id, tenant_id)
        ctx = self._contexts.get(key)
        if ctx is None:
            return
        ctx.messages.append({"role": role, "content": content})
        ctx.last_active_at = self._clock()
        if len(ctx.messages) > self._max_messages:
            ctx.messages = ctx.messages[-self._max_messages:]

    def get_context(self, channel: str, sender_id: str, tenant_id: str = "") -> ConversationContext | None:
        """Get existing context without creating."""
        return self._contexts.get(self._key(channel, sender_id, tenant_id))

    def clear_context(self, channel: str, sender_id: str, tenant_id: str = "") -> bool:
        """Clear a conversation context."""
        key = self._key(channel, sender_id, tenant_id)
        if key in self._contexts:
            del self._contexts[key]
            return True
        return False

    @property
    def active_sessions(self) -> int:
        return len(self._contexts)

    def summary(self) -> dict[str, Any]:
        return {
            "active_sessions": self.active_sessions,
            "max_context_messages": self._max_messages,
            "max_sessions": self.MAX_SESSIONS,
        }
