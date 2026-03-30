"""Phase 211D - State persistence tests."""

import json
import os
import tempfile

import pytest

from mcoi_runtime.persistence import PathTraversalError
from mcoi_runtime.persistence.state_persistence import StatePersistence

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"
MALICIOUS_STATE_TYPES = [
    "../../etc/passwd",
    "foo/bar",
    "foo\\bar",
    "foo\0bar",
    "..\\..\\windows\\system32\\config\\sam",
]


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
        assert sp.delete("config") is False

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
        sp, tmp_dir = self._persistence()
        sp.save("atomic_test", {"safe": True})
        files = os.listdir(tmp_dir)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    @pytest.mark.parametrize("bad_state_type", MALICIOUS_STATE_TYPES)
    def test_save_rejects_path_traversal(self, bad_state_type):
        sp, _ = self._persistence()
        with pytest.raises(PathTraversalError):
            sp.save(bad_state_type, {"safe": True})

    @pytest.mark.parametrize("bad_state_type", MALICIOUS_STATE_TYPES)
    def test_load_rejects_path_traversal(self, bad_state_type):
        sp, _ = self._persistence()
        with pytest.raises(PathTraversalError):
            sp.load(bad_state_type)

    @pytest.mark.parametrize("bad_state_type", MALICIOUS_STATE_TYPES)
    def test_exists_rejects_path_traversal(self, bad_state_type):
        sp, _ = self._persistence()
        with pytest.raises(PathTraversalError):
            sp.exists(bad_state_type)

    @pytest.mark.parametrize("bad_state_type", MALICIOUS_STATE_TYPES)
    def test_delete_rejects_path_traversal(self, bad_state_type):
        sp, _ = self._persistence()
        with pytest.raises(PathTraversalError):
            sp.delete(bad_state_type)

    def test_load_rejects_hash_mismatch(self):
        sp, tmp_dir = self._persistence()
        sp.save("config", {"key": "value"})
        file_path = os.path.join(tmp_dir, "mullu_state_config.json")
        with open(file_path, "r") as f:
            wrapper = json.load(f)
        wrapper["data"]["key"] = "tampered"
        with open(file_path, "w") as f:
            json.dump(wrapper, f, sort_keys=True, default=str, indent=2)
        assert sp.load("config") is None

    def test_list_states_missing_base_dir(self):
        missing_dir = os.path.join(tempfile.gettempdir(), "mullu-state-missing-dir")
        if os.path.isdir(missing_dir):
            os.rmdir(missing_dir)
        sp = StatePersistence(clock=FIXED_CLOCK, base_dir=missing_dir)
        assert sp.list_states() == []
