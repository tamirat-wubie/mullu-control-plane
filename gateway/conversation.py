"""Conversation State Management — Threads, topics, and context windows.

Purpose: Enhanced conversation state tracking for multi-turn gateway
    interactions.  Supports thread isolation, topic change detection,
    context summarization, and conversation export.
Governance scope: conversation context only — no LLM calls.
Dependencies: none (pure algorithm).
Invariants:
  - Threads are isolated within a session (no cross-thread leakage).
  - Context summarization preserves key information while reducing tokens.
  - Topic detection uses keyword overlap heuristic (no LLM dependency).
  - Conversations are bounded (max messages, max threads per session).
  - Thread-safe — concurrent message additions are safe.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ConversationMessage:
    """A single message in a conversation thread."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationThread:
    """An isolated conversation thread within a session.

    Threads allow parallel conversations (e.g., Slack threads)
    without context contamination.
    """

    thread_id: str
    topic: str = ""
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: str = ""
    last_active_at: str = ""
    summarized_context: str = ""  # Compressed history from older messages

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "topic": self.topic,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "has_summary": bool(self.summarized_context),
        }


@dataclass
class ConversationSession:
    """A conversation session with multiple threads."""

    session_id: str
    channel: str
    sender_id: str
    tenant_id: str
    identity_id: str
    threads: dict[str, ConversationThread] = field(default_factory=dict)
    active_thread_id: str = ""
    created_at: str = ""
    last_active_at: str = ""
    topic_changes: int = 0

    @property
    def thread_count(self) -> int:
        return len(self.threads)

    @property
    def total_messages(self) -> int:
        return sum(t.message_count for t in self.threads.values())

    def active_thread(self) -> ConversationThread | None:
        return self.threads.get(self.active_thread_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "channel": self.channel,
            "sender_id": self.sender_id,
            "tenant_id": self.tenant_id,
            "thread_count": self.thread_count,
            "total_messages": self.total_messages,
            "active_thread_id": self.active_thread_id,
            "topic_changes": self.topic_changes,
            "threads": [t.to_dict() for t in self.threads.values()],
        }


def _extract_keywords(text: str) -> set[str]:
    """Extract significant keywords from text for topic comparison."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "it", "its", "this", "that", "these", "those", "i", "you",
        "he", "she", "we", "they", "me", "him", "her", "us", "them",
        "my", "your", "his", "our", "their", "what", "which", "who",
        "when", "where", "why", "how", "not", "no", "yes", "and",
        "or", "but", "if", "then", "so", "just", "also", "very",
        "please", "thanks", "thank", "ok", "okay", "hi", "hello",
    }
    words = set()
    for word in text.lower().split():
        cleaned = "".join(c for c in word if c.isalnum())
        if cleaned and len(cleaned) > 2 and cleaned not in stop_words:
            words.add(cleaned)
    return words


def detect_topic_change(
    recent_messages: list[ConversationMessage],
    new_message: str,
    *,
    threshold: float = 0.15,
) -> bool:
    """Detect if a new message represents a topic change.

    Uses keyword overlap between recent conversation context and
    the new message.  Low overlap suggests a topic change.

    Returns True if topic change is detected.
    """
    if not recent_messages:
        return False  # First message is never a topic change

    # Build context keywords from recent messages
    context_text = " ".join(m.content for m in recent_messages[-5:])
    context_keywords = _extract_keywords(context_text)
    new_keywords = _extract_keywords(new_message)

    if not context_keywords or not new_keywords:
        return False

    overlap = len(context_keywords & new_keywords)
    total = len(context_keywords | new_keywords)
    similarity = overlap / total if total > 0 else 0.0

    return similarity < threshold


def summarize_messages(messages: list[ConversationMessage], max_chars: int = 500) -> str:
    """Summarize a list of messages into a compact context string.

    Uses a simple extractive approach — takes key user questions
    and assistant conclusions. No LLM dependency.
    """
    if not messages:
        return ""

    parts: list[str] = []
    char_count = 0

    for msg in messages:
        prefix = "Q" if msg.role == "user" else "A"
        truncated = msg.content[:150]
        line = f"[{prefix}]: {truncated}"
        if char_count + len(line) > max_chars:
            break
        parts.append(line)
        char_count += len(line)

    return "\n".join(parts)


class ConversationManager:
    """Manages conversation sessions with thread isolation and topic tracking.

    Usage:
        mgr = ConversationManager(clock=lambda: "2026-04-07T12:00:00Z")

        # Add message (auto-creates session and thread)
        mgr.add_message(
            channel="whatsapp", sender_id="+1234", tenant_id="t1",
            identity_id="user1", role="user", content="What is my balance?",
        )

        # Get context for LLM
        context = mgr.get_context_messages("whatsapp", "+1234", "t1")

        # Start a new thread (e.g., Slack thread)
        mgr.start_thread("whatsapp", "+1234", "t1", thread_id="thread-123")
    """

    MAX_SESSIONS = 50_000
    MAX_THREADS_PER_SESSION = 20
    MAX_MESSAGES_PER_THREAD = 50

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_messages_per_thread: int = MAX_MESSAGES_PER_THREAD,
        auto_detect_topics: bool = True,
    ) -> None:
        self._clock = clock
        self._max_messages = max_messages_per_thread
        self._auto_detect_topics = auto_detect_topics
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = threading.Lock()

    def _key(self, channel: str, sender_id: str, tenant_id: str) -> str:
        return f"{tenant_id}:{channel}:{sender_id}"

    def _get_or_create_session(
        self, channel: str, sender_id: str, tenant_id: str, identity_id: str,
    ) -> ConversationSession:
        key = self._key(channel, sender_id, tenant_id)
        session = self._sessions.get(key)
        if session is not None:
            session.last_active_at = self._clock()
            return session

        # Evict oldest if at capacity
        if len(self._sessions) >= self.MAX_SESSIONS:
            oldest_key = min(self._sessions, key=lambda k: self._sessions[k].last_active_at)
            del self._sessions[oldest_key]

        now = self._clock()
        session_id = f"conv-{hashlib.sha256(f'{key}:{now}'.encode()).hexdigest()[:12]}"
        session = ConversationSession(
            session_id=session_id,
            channel=channel,
            sender_id=sender_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            created_at=now,
            last_active_at=now,
        )
        self._sessions[key] = session
        return session

    def _ensure_thread(self, session: ConversationSession, thread_id: str = "") -> ConversationThread:
        tid = thread_id or "main"
        thread = session.threads.get(tid)
        if thread is not None:
            thread.last_active_at = self._clock()
            return thread

        # Evict oldest thread if at capacity
        if len(session.threads) >= self.MAX_THREADS_PER_SESSION:
            oldest_tid = min(session.threads, key=lambda t: session.threads[t].last_active_at)
            del session.threads[oldest_tid]

        now = self._clock()
        thread = ConversationThread(
            thread_id=tid, created_at=now, last_active_at=now,
        )
        session.threads[tid] = thread
        session.active_thread_id = tid
        return thread

    def add_message(
        self,
        channel: str,
        sender_id: str,
        tenant_id: str,
        identity_id: str,
        *,
        role: str,
        content: str,
        thread_id: str = "",
    ) -> ConversationThread:
        """Add a message to the conversation. Returns the active thread."""
        with self._lock:
            session = self._get_or_create_session(channel, sender_id, tenant_id, identity_id)
            thread = self._ensure_thread(session, thread_id)

            # Topic change detection
            if self._auto_detect_topics and role == "user" and thread.messages:
                if detect_topic_change(thread.messages, content):
                    session.topic_changes += 1
                    # Summarize old context before topic shift
                    if thread.messages:
                        thread.summarized_context = summarize_messages(thread.messages)

            msg = ConversationMessage(
                role=role, content=content, timestamp=self._clock(),
            )
            thread.messages.append(msg)

            # Compact if over limit
            if len(thread.messages) > self._max_messages:
                old_msgs = thread.messages[:-self._max_messages]
                thread.summarized_context = summarize_messages(old_msgs)
                thread.messages = thread.messages[-self._max_messages:]

            return thread

    def get_context_messages(
        self, channel: str, sender_id: str, tenant_id: str,
        *, thread_id: str = "",
    ) -> list[dict[str, str]]:
        """Get conversation context for LLM input.

        Returns messages as [{"role": "...", "content": "..."}].
        If a summary exists, it's prepended as a system message.
        """
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            session = self._sessions.get(key)
            if session is None:
                return []
            tid = thread_id or session.active_thread_id or "main"
            thread = session.threads.get(tid)
            if thread is None:
                return []

            result: list[dict[str, str]] = []
            if thread.summarized_context:
                result.append({
                    "role": "system",
                    "content": f"Previous conversation summary:\n{thread.summarized_context}",
                })
            for msg in thread.messages:
                result.append({"role": msg.role, "content": msg.content})
            return result

    def start_thread(
        self, channel: str, sender_id: str, tenant_id: str,
        *, thread_id: str, topic: str = "",
    ) -> ConversationThread | None:
        """Start a new conversation thread within an existing session."""
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            session = self._sessions.get(key)
            if session is None:
                return None
            thread = self._ensure_thread(session, thread_id)
            if topic:
                thread.topic = topic
            session.active_thread_id = thread_id
            return thread

    def get_session(self, channel: str, sender_id: str, tenant_id: str) -> ConversationSession | None:
        with self._lock:
            return self._sessions.get(self._key(channel, sender_id, tenant_id))

    def clear_session(self, channel: str, sender_id: str, tenant_id: str) -> bool:
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            if key in self._sessions:
                del self._sessions[key]
                return True
            return False

    def export_session(self, channel: str, sender_id: str, tenant_id: str) -> dict[str, Any] | None:
        """Export a full conversation session for review or handoff."""
        with self._lock:
            key = self._key(channel, sender_id, tenant_id)
            session = self._sessions.get(key)
            if session is None:
                return None
            data = session.to_dict()
            # Include full messages per thread
            data["thread_messages"] = {}
            for tid, thread in session.threads.items():
                data["thread_messages"][tid] = [
                    {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                    for m in thread.messages
                ]
            return data

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def summary(self) -> dict[str, Any]:
        total_threads = sum(s.thread_count for s in self._sessions.values())
        total_messages = sum(s.total_messages for s in self._sessions.values())
        return {
            "active_sessions": len(self._sessions),
            "total_threads": total_threads,
            "total_messages": total_messages,
            "max_messages_per_thread": self._max_messages,
            "auto_detect_topics": self._auto_detect_topics,
        }
