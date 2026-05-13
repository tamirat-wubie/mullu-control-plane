"""Phase 203D — Configuration hot-reload tests."""

import pytest
from mcoi_runtime.core.config_reload import ConfigManager


def FIXED_CLOCK():
    return "2026-03-26T12:00:00Z"


class TestConfigManager:
    def test_initial_empty(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        assert mgr.version == 0
        assert mgr.get_all() == {}

    def test_initial_with_config(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {"model": "claude"}})
        assert mgr.version == 1
        assert mgr.get("llm")["model"] == "claude"

    def test_initial_rejects_non_mapping_and_uncallable_clock(self):
        with pytest.raises(ValueError, match="clock"):
            ConfigManager(clock="bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="initial"):
            ConfigManager(clock=FIXED_CLOCK, initial="bad")  # type: ignore[arg-type]

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

    def test_update_rejects_non_mapping_blank_actor_and_bad_validator(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        with pytest.raises(ValueError, match="changes"):
            mgr.update("bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="applied_by"):
            mgr.update({"llm": {}}, applied_by="")
        with pytest.raises(ValueError, match="validator"):
            mgr.register_validator("llm", "bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="section"):
            mgr.register_validator("", lambda value: True)

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
        assert "999" not in result.error

    def test_rollback_rejects_bool_version(self):
        mgr = ConfigManager(clock=FIXED_CLOCK)
        with pytest.raises(ValueError, match="to_version"):
            mgr.rollback(True)  # type: ignore[arg-type]

    def test_history(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1})
        mgr.update({"a": 2})
        mgr.update({"a": 3})
        history = mgr.history()
        assert len(history) == 3
        assert history[0].version == 1
        assert history[-1].version == 3

    def test_history_and_current_reads_are_defensive(self):
        initial = {"llm": {"model": "v1"}}
        mgr = ConfigManager(clock=FIXED_CLOCK, initial=initial)
        initial["llm"]["model"] = "mutated"
        assert mgr.get("llm")["model"] == "v1"

        loaded = mgr.get("llm")
        loaded["model"] = "mutated-read"
        assert mgr.get("llm")["model"] == "v1"

        all_config = mgr.get_all()
        all_config["llm"]["model"] = "mutated-all"
        assert mgr.get("llm")["model"] == "v1"

        history = mgr.history()
        with pytest.raises(TypeError):
            history[0].config["llm"] = {}  # type: ignore[index]
        assert mgr.get("llm")["model"] == "v1"

    def test_diff(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1, "b": 2})
        mgr.update({"a": 10, "c": 3})
        diff = mgr.diff(1, 2)
        assert "a" in diff["changed"]
        assert "c" in diff["added"]

    def test_diff_rejects_missing_versions_and_bool_versions(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1})
        with pytest.raises(ValueError, match="version not found"):
            mgr.diff(1, 999)
        with pytest.raises(ValueError, match="from_version"):
            mgr.diff(True, 1)  # type: ignore[arg-type]

    def test_config_hash(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"a": 1})
        assert mgr.config_hash  # Non-empty

    def test_summary(self):
        mgr = ConfigManager(clock=FIXED_CLOCK, initial={"llm": {}, "features": {}})
        summary = mgr.summary()
        assert summary["version"] == 1
        assert "llm" in summary["sections"]
        assert summary["history_size"] == 1
