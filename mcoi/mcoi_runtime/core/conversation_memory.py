"""Phase 208C — Conversation Memory.

Purpose: Multi-turn governed chat with conversation history management.
    Maintains conversation state per tenant/session with configurable
    context window and message pruning.
Governance scope: conversation state management only.
Dependencies: llm contracts.
Invariants:
  - Conversations are tenant-scoped.
  - Message history is bounded (configurable max).
  - System messages are never pruned.
  - Conversation state is serializable for persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """Single message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str
    message_id: str = ""
    timestamp: str = ""


@dataclass(frozen=True, slots=True)
class ConversationConfig:
    """Configuration for conversation memory."""

    max_messages: int = 50
    max_tokens_estimate: int = 100000
    prune_strategy: str = "oldest_first"  # "oldest_first", "keep_system"


class Conversation:
    """Single conversation with history management."""

    def __init__(
        self,
        conversation_id: str,
        *,
        tenant_id: str = "",
        config: ConversationConfig | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.tenant_id = tenant_id
        self._config = config or ConversationConfig()
        self._clock = clock or (lambda: "")
        self._messages: list[ConversationMessage] = []
        self._message_counter = 0

    def add_message(self, role: str, content: str) -> ConversationMessage:
        """Add a message to the conversation."""
        self._message_counter += 1
        msg = ConversationMessage(
            role=role,
            content=content,
            message_id=f"msg-{self._message_counter}",
            timestamp=self._clock(),
        )
        self._messages.append(msg)
        self._prune()
        return msg

    def add_system(self, content: str) -> ConversationMessage:
        return self.add_message("system", content)

    def add_user(self, content: str) -> ConversationMessage:
        return self.add_message("user", content)

    def add_assistant(self, content: str) -> ConversationMessage:
        return self.add_message("assistant", content)

    def _prune(self) -> None:
        """Prune messages if over limit, keeping system messages."""
        if len(self._messages) <= self._config.max_messages:
            return

        if self._config.prune_strategy == "keep_system":
            system_msgs = [m for m in self._messages if m.role == "system"]
            non_system = [m for m in self._messages if m.role != "system"]
            keep = self._config.max_messages - len(system_msgs)
            self._messages = system_msgs + non_system[-max(keep, 0):]
        else:
            # oldest_first — but always keep system messages
            system_msgs = [m for m in self._messages if m.role == "system"]
            non_system = [m for m in self._messages if m.role != "system"]
            keep = self._config.max_messages - len(system_msgs)
            self._messages = system_msgs + non_system[-max(keep, 0):]

    @property
    def messages(self) -> list[ConversationMessage]:
        return list(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def to_chat_messages(self) -> list[dict[str, str]]:
        """Export as list of role/content dicts for LLM API."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def state_hash(self) -> str:
        content = json.dumps(
            [{"role": m.role, "content": m.content} for m in self._messages],
            sort_keys=True,
        ).encode()
        return sha256(content).hexdigest()

    def clear(self) -> None:
        """Clear all messages except system messages."""
        self._messages = [m for m in self._messages if m.role == "system"]

    def summary(self) -> dict[str, Any]:
        role_counts: dict[str, int] = {}
        for m in self._messages:
            role_counts[m.role] = role_counts.get(m.role, 0) + 1
        return {
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "message_count": self.message_count,
            "roles": role_counts,
            "state_hash": self.state_hash()[:16],
        }


class ConversationStore:
    """Manages multiple conversations with tenant scoping."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._conversations: dict[str, Conversation] = {}

    def get_or_create(
        self,
        conversation_id: str,
        *,
        tenant_id: str = "",
        config: ConversationConfig | None = None,
    ) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(
                conversation_id, tenant_id=tenant_id,
                config=config, clock=self._clock,
            )
        return self._conversations[conversation_id]

    def get(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def list_conversations(self, tenant_id: str | None = None) -> list[Conversation]:
        convs = list(self._conversations.values())
        if tenant_id is not None:
            convs = [c for c in convs if c.tenant_id == tenant_id]
        return sorted(convs, key=lambda c: c.conversation_id)

    def delete(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None

    @property
    def count(self) -> int:
        return len(self._conversations)

    def summary(self) -> dict[str, Any]:
        return {
            "conversations": self.count,
            "total_messages": sum(c.message_count for c in self._conversations.values()),
        }
