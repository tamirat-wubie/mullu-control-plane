"""Phase 211D - State persistence tests."""

import json
import os
import tempfile
from hashlib import sha256

import pytest

from mcoi_runtime.persistence import CorruptedDataError, PathTraversalError, PersistenceError
from mcoi_runtime.persistence.state_persistence import StatePersistence, _content_hash

def FIXED_CLOCK():
    return "2026-03-26T12:00:00Z"


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

    def test_content_hash_preserves_non_ascii_fidel_bytes(self):
        content = '{"fidel":"ሀ"}'
        digest = _content_hash(content)

        assert digest == sha256(content.encode("utf-8")).hexdigest()
        assert digest != sha256(content.encode("ascii", "ignore")).hexdigest()
        assert len(digest) == 64

    def test_save_rejects_non_dict_data(self):
        sp, _ = self._persistence()
        with pytest.raises(PersistenceError, match=r"^data must be a dict$"):
            sp.save("config", ["not", "a", "dict"])  # type: ignore[arg-type]

    def test_snapshot_data_is_defensive(self):
        sp, _ = self._persistence()
        data = {"nested": {"value": 1}, "items": [{"x": 2}]}
        snap = sp.save("config", data)

        data["nested"]["value"] = 99

        assert snap.data["nested"]["value"] == 1
        assert snap.data["items"][0]["x"] == 2
        with pytest.raises(TypeError):
            snap.data["new"] = True  # type: ignore[index]

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
        with pytest.raises(PathTraversalError) as excinfo:
            sp.save(bad_state_type, {"safe": True})
        expected = (
            "state_type contains null byte"
            if "\0" in bad_state_type
            else "state_type contains forbidden characters"
        )
        assert str(excinfo.value) == expected
        assert bad_state_type not in str(excinfo.value)

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
        with open(file_path, "r", encoding="utf-8") as f:
            wrapper = json.load(f)
        wrapper["data"]["key"] = "tampered"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(wrapper, f, sort_keys=True)
        with pytest.raises(CorruptedDataError, match=r"^state hash mismatch$"):
            sp.load("config")

    def test_load_rejects_malformed_json(self):
        sp, tmp_dir = self._persistence()
        file_path = os.path.join(tmp_dir, "mullu_state_config.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        with pytest.raises(CorruptedDataError, match=r"^malformed state file \(JSONDecodeError\)$"):
            sp.load("config")

    def test_list_states_rejects_invalid_filename(self):
        sp, tmp_dir = self._persistence()
        file_path = os.path.join(tmp_dir, "mullu_state_bad..name.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        with pytest.raises(CorruptedDataError, match=r"^state filename is invalid$"):
            sp.list_states()

    def test_list_states_missing_base_dir(self):
        missing_dir = os.path.join(tempfile.gettempdir(), "mullu-state-missing-dir")
        if os.path.isdir(missing_dir):
            os.rmdir(missing_dir)
        sp = StatePersistence(clock=FIXED_CLOCK, base_dir=missing_dir)
        assert sp.list_states() == []
