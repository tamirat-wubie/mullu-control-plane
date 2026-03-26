"""Tests for Phase 224A — Structured Logging."""
from __future__ import annotations

import json
import pytest

from mcoi_runtime.core.structured_logging import (
    LogEntry,
    LogLevel,
    StructuredLogger,
)


class TestLogEntry:
    def test_to_json_valid(self):
        entry = LogEntry(timestamp=1700000000.0, level=LogLevel.INFO, message="test")
        j = entry.to_json()
        parsed = json.loads(j)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "test"

    def test_redacts_sensitive_fields(self):
        entry = LogEntry(
            timestamp=1.0, level=LogLevel.INFO, message="login",
            context={"password": "secret123", "username": "bob"},
        )
        j = entry.to_json()
        parsed = json.loads(j)
        assert parsed["context"]["password"] == "***REDACTED***"
        assert parsed["context"]["username"] == "bob"

    def test_to_dict(self):
        entry = LogEntry(timestamp=1.0, level=LogLevel.ERROR, message="fail", logger="test")
        d = entry.to_dict()
        assert d["level"] == "ERROR"
        assert d["logger"] == "test"


class TestStructuredLogger:
    def test_info_log(self):
        logger = StructuredLogger()
        entry = logger.info("hello")
        assert entry is not None
        assert entry.level == LogLevel.INFO
        assert logger.entry_count == 1

    def test_min_level_filtering(self):
        logger = StructuredLogger(min_level=LogLevel.WARNING)
        assert logger.debug("ignored") is None
        assert logger.info("ignored") is None
        assert logger.warning("kept") is not None
        assert logger.entry_count == 1

    def test_all_log_levels(self):
        logger = StructuredLogger(min_level=LogLevel.DEBUG)
        logger.debug("d")
        logger.info("i")
        logger.warning("w")
        logger.error("e")
        logger.critical("c")
        assert logger.entry_count == 5

    def test_context_propagation(self):
        logger = StructuredLogger()
        entry = logger.info("req", trace_id="t1", span_id="s1", tenant_id="tenant-a")
        assert entry.trace_id == "t1"
        assert entry.span_id == "s1"
        assert entry.tenant_id == "tenant-a"

    def test_custom_context(self):
        logger = StructuredLogger()
        entry = logger.info("event", user_id="u1", action="login")
        assert entry.context["user_id"] == "u1"

    def test_buffer_eviction(self):
        logger = StructuredLogger(max_entries=5)
        for i in range(10):
            logger.info(f"msg-{i}")
        assert logger.entry_count == 5

    def test_recent_with_level_filter(self):
        logger = StructuredLogger(min_level=LogLevel.DEBUG)
        logger.debug("d")
        logger.info("i")
        logger.error("e")
        recent = logger.recent(count=10, min_level=LogLevel.ERROR)
        assert len(recent) == 1
        assert recent[0].level == LogLevel.ERROR

    def test_sink_callback(self):
        captured = []
        logger = StructuredLogger(sink=lambda s: captured.append(s))
        logger.info("test")
        assert len(captured) == 1
        parsed = json.loads(captured[0])
        assert parsed["message"] == "test"

    def test_summary(self):
        logger = StructuredLogger(name="test-logger")
        logger.info("a")
        logger.error("b")
        s = logger.summary()
        assert s["logger"] == "test-logger"
        assert s["total_entries"] == 2
        assert s["counts"]["INFO"] == 1
        assert s["counts"]["ERROR"] == 1
