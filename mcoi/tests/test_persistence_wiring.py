"""Tests for persistence wiring — state save/restore across restarts."""
from __future__ import annotations

import os
import tempfile

from mcoi_runtime.persistence.state_persistence import StatePersistence


class TestStatePersistenceRoundTrip:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = StatePersistence(clock=lambda: "2026-01-01T00:00:00Z", base_dir=tmpdir)
            data = {"tenant_a": {"spent": 42.5, "calls_made": 10}}
            snap = sp.save("budgets", data)
            assert snap.state_type == "budgets"
            assert snap.state_hash

            loaded = sp.load("budgets")
            assert loaded is not None
            assert loaded.data == data

    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = StatePersistence(clock=lambda: "2026-01-01T00:00:00Z", base_dir=tmpdir)
            assert sp.load("nonexistent") is None

    def test_atomic_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = StatePersistence(clock=lambda: "2026-01-01T00:00:00Z", base_dir=tmpdir)
            sp.save("test", {"key": "val1"})
            sp.save("test", {"key": "val2"})
            loaded = sp.load("test")
            assert loaded.data["key"] == "val2"

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = StatePersistence(clock=lambda: "2026-01-01T00:00:00Z", base_dir=tmpdir)
            sp.save("test", {"a": 1})
            assert sp.delete("test")
            assert sp.load("test") is None

    def test_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = StatePersistence(clock=lambda: "2026-01-01T00:00:00Z", base_dir=tmpdir)
            assert not sp.exists("test")
            sp.save("test", {})
            assert sp.exists("test")


class TestServerPersistenceWiring:
    """Verify state_persistence is wired into server."""

    def test_state_persistence_exists(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import state_persistence
        assert state_persistence is not None

    def test_shutdown_saves_state(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import _flush_state_on_shutdown
        result = _flush_state_on_shutdown()
        assert result["flushed"] is True
