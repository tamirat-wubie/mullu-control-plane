"""Tests for persistence wiring — state save/restore across restarts."""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

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
        assert result["warnings"] == ()

    def test_shutdown_partial_flush_is_bounded(self, monkeypatch):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server as server

        logged: list[str] = []

        def fake_log(level, message):
            logged.append(str(message))

        def fake_save(state_type, data):
            if state_type == "budgets":
                raise RuntimeError("shutdown secret detail")
            return SimpleNamespace(state_type=state_type, data=data)

        monkeypatch.setattr(server.platform_logger, "log", fake_log)
        monkeypatch.setattr(server.state_persistence, "save", fake_save)

        result = server._flush_state_on_shutdown()

        assert result["flushed"] is False
        assert result["audit_sequence"] >= 0
        assert result["cost_analytics"] is True
        assert result["warnings"] == ("shutdown budgets flush failed (RuntimeError)",)
        assert "shutdown secret detail" not in str(result)
        assert all("shutdown secret detail" not in message for message in logged)

    def test_startup_restore_skips_invalid_budget_with_bounded_warning(self, monkeypatch):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server as server

        logged: list[str] = []

        def fake_log(level, message):
            logged.append(str(message))

        def fake_load(state_type):
            if state_type == "budgets":
                return SimpleNamespace(data={"tenant-a": {"spent": 7.5}})
            if state_type == "audit_summary":
                return SimpleNamespace(data={"sequence": 9})
            return None

        def fake_record_spend(*args, **kwargs):
            raise ValueError("restore secret detail")

        monkeypatch.setattr(server.platform_logger, "log", fake_log)
        monkeypatch.setattr(server.state_persistence, "load", fake_load)
        monkeypatch.setattr(server.tenant_budget_mgr, "ensure_budget", lambda tenant_id: None)
        monkeypatch.setattr(server.tenant_budget_mgr, "record_spend", fake_record_spend)

        result = server._restore_state_on_startup()

        assert result["budgets"] == 1
        assert result["budget_restore_skipped"] == 1
        assert result["audit_sequence"] == 9
        assert result["warnings"] == ("startup budget restore failed (ValueError)",)
        assert "restore secret detail" not in str(result)
        assert all("restore secret detail" not in message for message in logged)

    def test_close_governance_stores_reports_bounded_warnings(self, monkeypatch):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server as server

        logged: list[str] = []

        class BrokenGovStores:
            def close(self):
                raise RuntimeError("governance close secret")

        class BrokenStore:
            def close(self):
                raise ValueError("primary store secret")

        def fake_log(level, message):
            logged.append(str(message))

        monkeypatch.setattr(server.platform_logger, "log", fake_log)
        monkeypatch.setattr(server, "_gov_stores", BrokenGovStores())
        monkeypatch.setattr(server, "store", BrokenStore())

        result = server._close_governance_stores()

        assert result["closed"] is False
        assert result["governance_stores_closed"] is False
        assert result["store_closed"] is False
        assert result["warnings"] == (
            "shutdown governance store close failed (RuntimeError)",
            "shutdown primary store close failed (ValueError)",
        )
        assert "governance close secret" not in str(result)
        assert "primary store secret" not in str(result)
        assert all("secret" not in message for message in logged)
