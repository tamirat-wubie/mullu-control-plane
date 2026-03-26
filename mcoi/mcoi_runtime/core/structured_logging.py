"""Phase 224A — Structured Logging (JSON format).

Purpose: Governed structured logging with JSON output, log levels,
    context propagation, and audit-safe formatting.
Dependencies: None (stdlib only).
Invariants:
  - All log entries are valid JSON.
  - Every entry includes timestamp, level, message, and trace context.
  - Log buffer is bounded (oldest entries evicted).
  - Sensitive fields are redacted.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


SENSITIVE_KEYS = frozenset({
    "password", "secret", "token", "api_key", "authorization",
    "credit_card", "ssn", "private_key",
})


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from log context."""
    return {
        k: "***REDACTED***" if k.lower() in SENSITIVE_KEYS else v
        for k, v in data.items()
    }


@dataclass
class LogEntry:
    """Single structured log entry."""
    timestamp: float
    level: LogLevel
    message: str
    logger: str = "mullu"
    trace_id: str = ""
    span_id: str = ""
    tenant_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp,
            "level": self.level.name,
            "logger": self.logger,
            "message": self.message,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "tenant_id": self.tenant_id,
            "context": _redact(self.context),
        }, default=str)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level.name,
            "message": self.message,
            "logger": self.logger,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
        }


class StructuredLogger:
    """Governed structured logger with JSON output and bounded buffer."""

    def __init__(self, name: str = "mullu", max_entries: int = 10_000,
                 min_level: LogLevel = LogLevel.INFO,
                 sink: Callable[[str], None] | None = None):
        self._name = name
        self._max_entries = max_entries
        self._min_level = min_level
        self._sink = sink
        self._entries: list[LogEntry] = []
        self._counts: dict[str, int] = {level.name: 0 for level in LogLevel}

    def log(self, level: LogLevel, message: str,
            trace_id: str = "", span_id: str = "",
            tenant_id: str = "", **context: Any) -> LogEntry | None:
        if level < self._min_level:
            return None

        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            logger=self._name,
            trace_id=trace_id,
            span_id=span_id,
            tenant_id=tenant_id,
            context=context,
        )

        self._entries.append(entry)
        self._counts[level.name] = self._counts.get(level.name, 0) + 1

        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        if self._sink:
            self._sink(entry.to_json())

        return entry

    def debug(self, message: str, **kw: Any) -> LogEntry | None:
        return self.log(LogLevel.DEBUG, message, **kw)

    def info(self, message: str, **kw: Any) -> LogEntry | None:
        return self.log(LogLevel.INFO, message, **kw)

    def warning(self, message: str, **kw: Any) -> LogEntry | None:
        return self.log(LogLevel.WARNING, message, **kw)

    def error(self, message: str, **kw: Any) -> LogEntry | None:
        return self.log(LogLevel.ERROR, message, **kw)

    def critical(self, message: str, **kw: Any) -> LogEntry | None:
        return self.log(LogLevel.CRITICAL, message, **kw)

    def recent(self, count: int = 50, min_level: LogLevel = LogLevel.DEBUG) -> list[LogEntry]:
        filtered = [e for e in self._entries if e.level >= min_level]
        return filtered[-count:]

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        return {
            "logger": self._name,
            "total_entries": self.entry_count,
            "min_level": self._min_level.name,
            "counts": dict(self._counts),
        }
