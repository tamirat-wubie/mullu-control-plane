"""Phase 211D — State persistence tests."""

import os
import tempfile
import pytest
from mcoi_runtime.persistence.state_persistence import StatePersistence

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestStatePersistence:
    def _persistence(self):
        tmp_dir = tempfile.mkdtemp()
        return StatePersistence(clock=FIXED_CLOCK, base_dir=tmp_dir), tmp_dir

    def test_save(self):
        sp, _ = self._persistence()
        snap = sp.save("config", {"llm": {"model": "claude"}, "version": 1})
        assert snap.state_type == "config"
        assert snap.state_hash
        assert snap.saved_at

    def test_save_and_load(self):
        sp, _ = self._persistence()
        sp.save("config", {"key": "value"})
        loaded = sp.load("config")
        assert loaded is not None
        assert loaded.data["key"] == "value"

    def test_load_missing(self):
        sp, _ = self._persistence()
        assert sp.load("nonexistent") is None

    def test_exists(self):
        sp, _ = self._persistence()
        assert sp.exists("config") is False
        sp.save("config", {})
        assert sp.exists("config") is True

    def test_delete(self):
        sp, _ = self._persistence()
        sp.save("config", {"x": 1})
        assert sp.delete("config") is True
        assert sp.exists("config") is False
        assert sp.delete("config") is False  # Already deleted

    def test_list_states(self):
        sp, _ = self._persistence()
        sp.save("config", {})
        sp.save("conversations", {})
        states = sp.list_states()
        assert "config" in states
        assert "conversations" in states

    def test_overwrite(self):
        sp, _ = self._persistence()
        sp.save("config", {"v": 1})
        sp.save("config", {"v": 2})
        loaded = sp.load("config")
        assert loaded.data["v"] == 2

    def test_state_hash_changes(self):
        sp, _ = self._persistence()
        s1 = sp.save("config", {"v": 1})
        s2 = sp.save("config", {"v": 2})
        assert s1.state_hash != s2.state_hash

    def test_complex_data(self):
        sp, _ = self._persistence()
        data = {
            "conversations": [
                {"id": "c1", "messages": [{"role": "user", "content": "hi"}]},
            ],
            "count": 1,
            "nested": {"deep": {"value": True}},
        }
        sp.save("complex", data)
        loaded = sp.load("complex")
        assert loaded.data["nested"]["deep"]["value"] is True

    def test_summary(self):
        sp, _ = self._persistence()
        sp.save("config", {})
        s = sp.summary()
        assert s["saved_states"] == 1

    def test_atomic_write(self):
        """Verify no partial files are left on disk."""
        sp, tmp_dir = self._persistence()
        sp.save("atomic_test", {"safe": True})
        files = os.listdir(tmp_dir)
        # Should only have the final file, no .tmp files
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0
