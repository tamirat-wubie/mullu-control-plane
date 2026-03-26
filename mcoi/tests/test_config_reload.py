"""Phase 203D — Configuration hot-reload tests."""

import pytest
from mcoi_runtime.core.config_reload import ConfigManager, ConfigChangeResult

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestConfigManager:
    def test_initial_empty(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        assert mgr.version == 0
        assert mgr.get_all() == {}

    def test_initial_with_config(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {"model": "claude"}})
        assert mgr.version == 1
        assert mgr.get("llm")["model"] == "claude"

    def test_update(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        result = mgr.update({"llm": {"model": "gpt-4o"}}, applied_by="admin")
        assert result.success is True
        assert mgr.get("llm")["model"] == "gpt-4o"

    def test_update_increments_version(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        mgr.update({"llm": {"model": "v1"}})
        mgr.update({"llm": {"model": "v2"}})
        assert mgr.version == 2

    def test_get_missing_section(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        assert mgr.get("nonexistent") is None
        assert mgr.get("nonexistent", "default") == "default"

    def test_validation_pass(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        mgr.register_validator("rate_limits", lambda v: isinstance(v, dict))
        result = mgr.update({"rate_limits": {"max_tokens": 60}})
        assert result.success is True

    def test_validation_fail(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        mgr.register_validator("rate_limits", lambda v: isinstance(v, dict) and "max_tokens" in v)
        result = mgr.update({"rate_limits": "invalid"})
        assert result.success is False
        assert "validation failed" in result.error

    def test_atomic_update(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {"model": "original"}})
        mgr.register_validator("rate_limits", lambda v: False)  # Always fails
        result = mgr.update({"rate_limits": "x", "llm": {"model": "new"}})
        assert result.success is False
        # LLM should NOT have been updated (atomic)
        # NOTE: Our current impl updates dict then validates. Let me fix the test expectation:
        # Actually our impl validates first, then applies. So llm stays original.
        assert mgr.get("llm")["model"] == "original"

    def test_rollback(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {"model": "v1"}})
        mgr.update({"llm": {"model": "v2"}})
        result = mgr.rollback(1, applied_by="admin")
        assert result.success is True
        assert mgr.get("llm")["model"] == "v1"

    def test_rollback_invalid_version(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        result = mgr.rollback(999)
        assert result.success is False
        assert "not found" in result.error

    def test_history(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1})
        mgr.update({"a": 2})
        mgr.update({"a": 3})
        history = mgr.history()
        assert len(history) == 3
        assert history[0].version == 1
        assert history[-1].version == 3

    def test_diff(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1, "b": 2})
        mgr.update({"a": 10, "c": 3})
        diff = mgr.diff(1, 2)
        assert "a" in diff["changed"]
        assert "c" in diff["added"]

    def test_config_hash(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1})
        assert mgr.config_hash  # Non-empty

    def test_summary(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {}, "features": {}})
        summary = mgr.summary()
        assert summary["version"] == 1
        assert "llm" in summary["sections"]
        assert summary["history_size"] == 1
