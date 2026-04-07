"""Streaming Response Bridge — Forward LLM chunks to gateway channels.

Purpose: Bridges LLM streaming output to channel adapters so users see
    progressive responses instead of waiting for full completion.
    Supports chunked delivery, final assembly, and timeout protection.
Governance scope: delivery only — no content modification.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Chunks are delivered in order (no reordering).
  - Final assembled response matches concatenation of all chunks.
  - Timeout protection: incomplete streams auto-finalize.
  - Channel adapters that don't support streaming get final response only.
  - Thread-safe — concurrent streams to different channels are safe.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class StreamChunk:
    """A single chunk of a streaming LLM response."""

    index: int
    content: str
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamSession:
    """Tracks a streaming response being delivered to a channel."""

    stream_id: str
    channel: str
    recipient_id: str
    tenant_id: str
    chunks: list[StreamChunk] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0
    total_chars: int = 0
    finalized: bool = False
    error: str = ""

    @property
    def assembled_content(self) -> str:
        return "".join(c.content for c in self.chunks)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "channel": self.channel,
            "recipient_id": self.recipient_id,
            "chunk_count": self.chunk_count,
            "total_chars": self.total_chars,
            "finalized": self.finalized,
            "error": self.error,
        }


class StreamingBridge:
    """Bridges LLM streaming output to gateway channel adapters.

    Usage:
        bridge = StreamingBridge(clock=time.monotonic)

        # Start a stream
        stream_id = bridge.start_stream("whatsapp", "+1234", "t1")

        # Feed chunks as they arrive from LLM
        bridge.push_chunk(stream_id, "The answer ")
        bridge.push_chunk(stream_id, "is 42.")
        bridge.finalize(stream_id)

        # Get assembled response
        content = bridge.get_assembled(stream_id)

        # Or register a channel callback for real-time delivery
        bridge.set_chunk_callback(stream_id, lambda chunk: send_to_channel(chunk))
    """

    MAX_STREAMS = 10_000
    DEFAULT_TIMEOUT = 60.0  # seconds

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        stream_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._clock = clock or time.monotonic
        self._timeout = stream_timeout
        self._streams: dict[str, StreamSession] = {}
        self._callbacks: dict[str, Callable[[StreamChunk], None]] = {}
        self._lock = threading.Lock()
        self._sequence = 0
        self._completed_count = 0
        self._timed_out_count = 0

    def start_stream(
        self,
        channel: str,
        recipient_id: str,
        tenant_id: str,
    ) -> str:
        """Start a new streaming session. Returns stream_id."""
        with self._lock:
            self._sequence += 1
            stream_id = f"stream-{self._sequence}"

            # Capacity enforcement
            if len(self._streams) >= self.MAX_STREAMS:
                self._evict_oldest()

            self._streams[stream_id] = StreamSession(
                stream_id=stream_id,
                channel=channel,
                recipient_id=recipient_id,
                tenant_id=tenant_id,
                started_at=self._clock(),
            )
            return stream_id

    def _evict_oldest(self) -> None:
        """Evict oldest finalized stream, or oldest overall."""
        finalized = [
            (sid, s) for sid, s in self._streams.items() if s.finalized
        ]
        if finalized:
            oldest = min(finalized, key=lambda x: x[1].started_at)[0]
            del self._streams[oldest]
            self._callbacks.pop(oldest, None)
            return
        if self._streams:
            oldest = min(self._streams, key=lambda k: self._streams[k].started_at)
            del self._streams[oldest]
            self._callbacks.pop(oldest, None)

    def set_chunk_callback(
        self,
        stream_id: str,
        callback: Callable[[StreamChunk], None],
    ) -> bool:
        """Register a callback for real-time chunk delivery."""
        with self._lock:
            if stream_id not in self._streams:
                return False
            self._callbacks[stream_id] = callback
            return True

    def push_chunk(self, stream_id: str, content: str) -> bool:
        """Push a content chunk to the stream. Returns False if stream not found."""
        with self._lock:
            session = self._streams.get(stream_id)
            if session is None or session.finalized:
                return False

            # Timeout check
            if (self._clock() - session.started_at) > self._timeout:
                session.finalized = True
                session.error = "stream timed out"
                session.completed_at = self._clock()
                self._timed_out_count += 1
                return False

            chunk = StreamChunk(
                index=session.chunk_count,
                content=content,
            )
            session.chunks.append(chunk)
            session.total_chars += len(content)

            callback = self._callbacks.get(stream_id)

        # Call callback outside lock to avoid deadlock
        if callback is not None:
            try:
                callback(chunk)
            except Exception:
                pass  # Callback failure doesn't fail the stream

        return True

    def finalize(self, stream_id: str) -> StreamSession | None:
        """Mark a stream as complete. Returns the session."""
        with self._lock:
            session = self._streams.get(stream_id)
            if session is None:
                return None
            if session.finalized:
                return session

            session.finalized = True
            session.completed_at = self._clock()
            self._completed_count += 1

            # Send final chunk notification
            callback = self._callbacks.get(stream_id)

        if callback is not None:
            try:
                callback(StreamChunk(
                    index=session.chunk_count,
                    content="",
                    is_final=True,
                ))
            except Exception:
                pass

        return session

    def get_assembled(self, stream_id: str) -> str | None:
        """Get the fully assembled response content."""
        with self._lock:
            session = self._streams.get(stream_id)
            if session is None:
                return None
            return session.assembled_content

    def get_session(self, stream_id: str) -> StreamSession | None:
        with self._lock:
            return self._streams.get(stream_id)

    def is_active(self, stream_id: str) -> bool:
        with self._lock:
            session = self._streams.get(stream_id)
            if session is None:
                return False
            return not session.finalized

    def cleanup_finalized(self) -> int:
        """Remove all finalized streams. Returns count removed."""
        with self._lock:
            to_remove = [sid for sid, s in self._streams.items() if s.finalized]
            for sid in to_remove:
                del self._streams[sid]
                self._callbacks.pop(sid, None)
            return len(to_remove)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._streams.values() if not s.finalized)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            active = sum(1 for s in self._streams.values() if not s.finalized)
            return {
                "total_streams": len(self._streams),
                "active_streams": active,
                "completed": self._completed_count,
                "timed_out": self._timed_out_count,
                "stream_timeout": self._timeout,
            }
