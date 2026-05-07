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
import threading
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
        self._ttl_parse_failures = 0
        self._evicted_count = 0
        self._eviction_reasons: dict[str, int] = {}
        self._lock = threading.Lock()

    def _key(self, channel: str, sender_id: str, tenant_id: str = "") -> str:
        return f"{tenant_id}:{channel}:{sender_id}" if tenant_id else f":{channel}:{sender_id}"

    def _record_eviction(self, reason_code: str) -> None:
        """Record a bounded session-removal reason for operator summaries."""
        self._evicted_count += 1
        self._eviction_reasons[reason_code] = self._eviction_reasons.get(reason_code, 0) + 1

    def get_or_create(
        self,
        *,
        channel: str,
        sender_id: str,
        tenant_id: str,
        identity_id: str,
    ) -> ConversationContext:
        """Get existing context or create a new one."""
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            ctx = self._contexts.get(key)
            now = self._clock()

            if ctx is not None:
                # TTL enforcement: expire stale sessions
                if self._ttl > 0 and ctx.last_active_at and now:
                    try:
                        from datetime import datetime as _dt
                        last = _dt.fromisoformat(ctx.last_active_at.replace("Z", "+00:00"))
                        current = _dt.fromisoformat(now.replace("Z", "+00:00"))
                        if (current - last).total_seconds() > self._ttl:
                            del self._contexts[key]
                            self._record_eviction("ttl_expired")
                            ctx = None
                    except (AttributeError, TypeError, ValueError, OverflowError):
                        self._ttl_parse_failures += 1
                        self._contexts.pop(key, None)
                        self._record_eviction("invalid_ttl_timestamp")
                        ctx = None
                if ctx is not None:
                    ctx.last_active_at = now
                    return ctx

            # Evict oldest if at capacity
            if len(self._contexts) >= self.MAX_SESSIONS:
                oldest_key = min(self._contexts, key=lambda k: self._contexts[k].last_active_at)
                del self._contexts[oldest_key]
                self._record_eviction("capacity_pressure")

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
        with self._lock:
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
        with self._lock:
            return self._contexts.get(self._key(channel, sender_id, tenant_id))

    def clear_context(self, channel: str, sender_id: str, tenant_id: str = "") -> bool:
        """Clear a conversation context."""
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            if key in self._contexts:
                del self._contexts[key]
                return True
            return False

    @property
    def active_sessions(self) -> int:
        return len(self._contexts)

    @property
    def ttl_parse_failures(self) -> int:
        return self._ttl_parse_failures

    def summary(self) -> dict[str, Any]:
        return {
            "active_sessions": self.active_sessions,
            "max_context_messages": self._max_messages,
            "max_sessions": self.MAX_SESSIONS,
            "ttl_parse_failures": self._ttl_parse_failures,
            "total_evicted": self._evicted_count,
            "eviction_reasons": dict(sorted(self._eviction_reasons.items())),
        }
