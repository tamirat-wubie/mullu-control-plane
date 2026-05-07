"""Session Persistence Tests — Checkpoint, restore, and store backends."""

import json

import pytest
import mcoi_runtime.persistence.session_store as session_store_module
from mcoi_runtime.persistence.session_store import (
    FileSessionStore,
    InMemorySessionStore,
    SessionCheckpoint,
    SessionStore,
)


# ── SessionCheckpoint serialization ────────────────────────────

class TestSessionCheckpoint:
    def _checkpoint(self, **overrides) -> SessionCheckpoint:
        defaults = dict(
            session_id="gs-abc123",
            identity_id="user1",
            tenant_id="t1",
            operations=5,
            llm_calls=3,
            total_cost=0.12,
            context_messages=(
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ),
            compaction_count=1,
            checkpoint_at="2026-04-07T12:00:00Z",
        )
        defaults.update(overrides)
        return SessionCheckpoint(**defaults)

    def test_to_dict_roundtrip(self):
        cp = self._checkpoint()
        data = cp.to_dict()
        restored = SessionCheckpoint.from_dict(data)
        assert restored is not None
        assert restored.session_id == cp.session_id
        assert restored.identity_id == cp.identity_id
        assert restored.tenant_id == cp.tenant_id
        assert restored.operations == cp.operations
        assert restored.llm_calls == cp.llm_calls
        assert restored.total_cost == cp.total_cost
        assert restored.compaction_count == cp.compaction_count
        assert len(restored.context_messages) == 2

    def test_from_dict_does_not_mutate_input_payload(self):
        cp = self._checkpoint()
        data = cp.to_dict()
        original = dict(data)

        restored = SessionCheckpoint.from_dict(data)

        assert restored is not None
        assert data == original
        assert "checkpoint_hash" in data

    def test_hash_integrity(self):
        cp = self._checkpoint()
        data = cp.to_dict()
        assert "checkpoint_hash" in data
        assert len(data["checkpoint_hash"]) == 16

    def test_tampered_data_rejected(self):
        cp = self._checkpoint()
        data = cp.to_dict()
        data["operations"] = 999  # Tamper
        restored = SessionCheckpoint.from_dict(data)
        assert restored is None

    def test_missing_hash_allowed(self):
        """Checkpoints without hash (e.g., manual creation) are accepted."""
        cp = self._checkpoint()
        data = cp.to_dict()
        data.pop("checkpoint_hash")
        restored = SessionCheckpoint.from_dict(data)
        assert restored is not None

    def test_missing_required_field_rejected(self):
        data = {"session_id": "gs-x", "identity_id": "u1"}  # Missing fields
        assert SessionCheckpoint.from_dict(data) is None

    def test_context_messages_preserved(self):
        msgs = (
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "Thanks"},
        )
        cp = self._checkpoint(context_messages=msgs)
        data = cp.to_dict()
        restored = SessionCheckpoint.from_dict(data)
        assert restored is not None
        assert len(restored.context_messages) == 3
        assert restored.context_messages[1]["content"] == "4"

    def test_empty_context(self):
        cp = self._checkpoint(context_messages=())
        data = cp.to_dict()
        restored = SessionCheckpoint.from_dict(data)
        assert restored is not None
        assert restored.context_messages == ()


# ── InMemorySessionStore ───────────────────────────────────────

class TestInMemorySessionStore:
    def _store(self) -> InMemorySessionStore:
        return InMemorySessionStore()

    def _checkpoint(self, session_id: str = "gs-abc", **kw) -> SessionCheckpoint:
        return SessionCheckpoint(
            session_id=session_id,
            identity_id=kw.get("identity_id", "user1"),
            tenant_id=kw.get("tenant_id", "t1"),
            operations=kw.get("operations", 0),
            llm_calls=kw.get("llm_calls", 0),
            total_cost=kw.get("total_cost", 0.0),
            context_messages=kw.get("context_messages", ()),
            compaction_count=0,
            checkpoint_at=kw.get("checkpoint_at", "2026-04-07T12:00:00Z"),
        )

    def test_save_and_load(self):
        store = self._store()
        cp = self._checkpoint()
        assert store.save(cp) is True
        loaded = store.load("gs-abc")
        assert loaded is not None
        assert loaded.session_id == "gs-abc"

    def test_load_not_found(self):
        store = self._store()
        assert store.load("nonexistent") is None

    def test_delete(self):
        store = self._store()
        store.save(self._checkpoint())
        assert store.delete("gs-abc") is True
        assert store.load("gs-abc") is None

    def test_delete_not_found(self):
        store = self._store()
        assert store.delete("nonexistent") is False

    def test_list_sessions(self):
        store = self._store()
        store.save(self._checkpoint("gs-1", tenant_id="t1"))
        store.save(self._checkpoint("gs-2", tenant_id="t1"))
        store.save(self._checkpoint("gs-3", tenant_id="t2"))
        assert len(store.list_sessions()) == 3
        assert len(store.list_sessions(tenant_id="t1")) == 2
        assert len(store.list_sessions(tenant_id="t2")) == 1

    def test_overwrite(self):
        store = self._store()
        store.save(self._checkpoint("gs-1", operations=5))
        store.save(self._checkpoint("gs-1", operations=10))
        loaded = store.load("gs-1")
        assert loaded is not None
        assert loaded.operations == 10

    def test_bounded(self):
        store = self._store()
        for i in range(store.MAX_SESSIONS + 100):
            store.save(self._checkpoint(f"gs-{i}"))
        assert store.session_count <= store.MAX_SESSIONS

    def test_session_count(self):
        store = self._store()
        store.save(self._checkpoint("gs-1"))
        store.save(self._checkpoint("gs-2"))
        assert store.session_count == 2


# ── FileSessionStore ───────────────────────────────────────────

class TestFileSessionStore:
    def _store(self, tmp_path: str) -> FileSessionStore:
        return FileSessionStore(base_dir=tmp_path)

    def _checkpoint(self, session_id: str = "gs-abc", **kw) -> SessionCheckpoint:
        return SessionCheckpoint(
            session_id=session_id,
            identity_id=kw.get("identity_id", "user1"),
            tenant_id=kw.get("tenant_id", "t1"),
            operations=kw.get("operations", 0),
            llm_calls=kw.get("llm_calls", 0),
            total_cost=kw.get("total_cost", 0.0),
            context_messages=kw.get("context_messages", ()),
            compaction_count=0,
            checkpoint_at=kw.get("checkpoint_at", "2026-04-07T12:00:00Z"),
        )

    def test_save_and_load(self, tmp_path):
        store = self._store(str(tmp_path))
        cp = self._checkpoint()
        assert store.save(cp) is True
        loaded = store.load("gs-abc")
        assert loaded is not None
        assert loaded.session_id == "gs-abc"
        assert loaded.identity_id == "user1"

    def test_file_created(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint())
        files = list(tmp_path.iterdir())
        assert any("session_gs-abc.json" in f.name for f in files)

    def test_load_not_found(self, tmp_path):
        store = self._store(str(tmp_path))
        assert store.load("nonexistent") is None

    def test_delete(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint())
        assert store.delete("gs-abc") is True
        assert store.load("gs-abc") is None

    def test_list_sessions(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint("gs-1", tenant_id="t1"))
        store.save(self._checkpoint("gs-2", tenant_id="t2"))
        all_sessions = store.list_sessions()
        assert len(all_sessions) == 2

    def test_corrupted_file_returns_none(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint())
        # Corrupt the file
        path = tmp_path / "session_gs-abc.json"
        path.write_text("not json{{{")
        assert store.load("gs-abc") is None

    def test_tampered_file_returns_none(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint())
        path = tmp_path / "session_gs-abc.json"
        data = json.loads(path.read_text())
        data["operations"] = 999
        path.write_text(json.dumps(data))
        assert store.load("gs-abc") is None

    def test_path_traversal_blocked(self, tmp_path):
        store = self._store(str(tmp_path))
        # save() catches ValueError internally and returns False
        assert store.save(self._checkpoint("../../etc/passwd")) is False

    def test_null_byte_blocked(self, tmp_path):
        store = self._store(str(tmp_path))
        assert store.save(self._checkpoint("gs-\x00evil")) is False

    def test_save_failure_logs_bounded_warning_and_cleans_temp(
        self,
        tmp_path,
        monkeypatch,
    ):
        warnings = []

        def _capture_warning(message, failure_class):
            warnings.append(message % failure_class)

        def _raise_replace(source, target):
            raise RuntimeError("secret session write failure")

        monkeypatch.setattr(session_store_module._log, "warning", _capture_warning)
        monkeypatch.setattr(session_store_module.os, "replace", _raise_replace)

        store = self._store(str(tmp_path))
        saved = store.save(self._checkpoint("gs-secret"))

        assert saved is False
        assert warnings == ["session checkpoint save failed (RuntimeError)"]
        assert "secret session write failure" not in warnings[0]
        assert not list(tmp_path.glob("session_*.tmp"))

    def test_invalid_session_id_logs_bounded_warning(self, tmp_path, monkeypatch):
        warnings = []

        def _capture_warning(message, failure_class):
            warnings.append(message % failure_class)

        monkeypatch.setattr(session_store_module._log, "warning", _capture_warning)

        store = self._store(str(tmp_path))
        saved = store.save(self._checkpoint("../../secret-session"))

        assert saved is False
        assert warnings == ["session checkpoint save failed (ValueError)"]
        assert "secret-session" not in warnings[0]

    def test_summary(self, tmp_path):
        store = self._store(str(tmp_path))
        store.save(self._checkpoint("gs-1"))
        summary = store.summary()
        assert summary["session_count"] == 1
        assert str(tmp_path) in summary["base_dir"]


# ── GovernedSession checkpoint/restore ─────────────────────────

class TestSessionCheckpointRestore:
    def _platform(self, **kw):
        from mcoi_runtime.core.governed_session import Platform
        return Platform(
            clock=lambda: "2026-04-07T12:00:00Z",
            **kw,
        )

    def test_checkpoint_returns_dict(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()
        assert isinstance(data, dict)
        assert data["session_id"].startswith("gs-")
        assert data["identity_id"] == "user1"
        assert data["tenant_id"] == "t1"
        assert data["operations"] == 0

    def test_checkpoint_after_operations(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        # Manually increment (no LLM bridge, so simulate state)
        session._operations = 5
        session._llm_calls = 3
        session._total_cost = 0.15
        session._context_messages = [{"role": "user", "content": "test"}]
        data = session.checkpoint()
        assert data["operations"] == 5
        assert data["llm_calls"] == 3
        assert data["total_cost"] == 0.15
        assert len(data["context_messages"]) == 1

    def test_checkpoint_on_closed_session_raises(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        session.close()
        with pytest.raises(RuntimeError, match="closed"):
            session.checkpoint()

    def test_resume_restores_state(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        session._operations = 7
        session._llm_calls = 4
        session._total_cost = 0.25
        session._context_messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        data = session.checkpoint()
        sid = session._session_id

        # Resume on a "new" platform (simulating restart)
        p2 = self._platform()
        resumed = p2.resume(
            session_id=sid,
            identity_id="user1",
            tenant_id="t1",
            checkpoint_data=data,
        )
        assert resumed._operations == 7
        assert resumed._llm_calls == 4
        assert resumed._total_cost == 0.25
        assert len(resumed._context_messages) == 2
        assert resumed._context_messages[0]["content"] == "hello"

    def test_resume_identity_mismatch_raises(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()
        sid = session._session_id

        with pytest.raises(ValueError, match="identity_id"):
            p.resume(
                session_id=sid,
                identity_id="user2",  # Mismatch!
                tenant_id="t1",
                checkpoint_data=data,
            )

    def test_resume_tenant_mismatch_raises(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()
        sid = session._session_id

        with pytest.raises(ValueError, match="tenant_id"):
            p.resume(
                session_id=sid,
                identity_id="user1",
                tenant_id="t2",  # Mismatch!
                checkpoint_data=data,
            )

    def test_resume_session_id_mismatch_raises(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()

        with pytest.raises(ValueError, match="session_id"):
            p.resume(
                session_id="gs-wrong",
                identity_id="user1",
                tenant_id="t1",
                checkpoint_data=data,
            )

    def test_resumed_session_is_open(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()
        sid = session._session_id

        resumed = p.resume(
            session_id=sid,
            identity_id="user1",
            tenant_id="t1",
            checkpoint_data=data,
        )
        # Session should be open and operational
        assert resumed._closed is False
        # Should be able to close it
        report = resumed.close()
        assert report.session_id == sid

    def test_resumed_session_increments_platform_count(self):
        p = self._platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        data = session.checkpoint()
        sid = session._session_id

        assert p.session_count == 1
        p.resume(session_id=sid, identity_id="user1", tenant_id="t1", checkpoint_data=data)
        assert p.session_count == 2


# ── End-to-end: checkpoint → store → restore ───────────────────

class TestEndToEndPersistence:
    def _platform(self):
        from mcoi_runtime.core.governed_session import Platform
        return Platform(clock=lambda: "2026-04-07T12:00:00Z")

    def test_inmemory_store_roundtrip(self):
        store = InMemorySessionStore()
        p = self._platform()

        # Create session, do some work, checkpoint
        session = p.connect(identity_id="user1", tenant_id="t1")
        session._operations = 3
        session._context_messages = [{"role": "user", "content": "save me"}]
        data = session.checkpoint()
        sid = session._session_id

        # Save to store
        cp = SessionCheckpoint.from_dict(dict(data))
        assert cp is not None
        store.save(cp)

        # "Restart" — new platform, load from store
        p2 = self._platform()
        loaded = store.load(sid)
        assert loaded is not None
        resumed = p2.resume(
            session_id=loaded.session_id,
            identity_id=loaded.identity_id,
            tenant_id=loaded.tenant_id,
            checkpoint_data=loaded.to_dict(),
        )
        assert resumed._operations == 3
        assert resumed._context_messages[0]["content"] == "save me"

    def test_file_store_roundtrip(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        p = self._platform()

        session = p.connect(identity_id="user1", tenant_id="t1")
        session._operations = 10
        session._total_cost = 0.50
        data = session.checkpoint()
        sid = session._session_id

        cp = SessionCheckpoint.from_dict(dict(data))
        assert cp is not None
        store.save(cp)

        # "Restart"
        p2 = self._platform()
        loaded = store.load(sid)
        assert loaded is not None
        resumed = p2.resume(
            session_id=loaded.session_id,
            identity_id=loaded.identity_id,
            tenant_id=loaded.tenant_id,
            checkpoint_data=loaded.to_dict(),
        )
        assert resumed._operations == 10
        assert resumed._total_cost == 0.50
        report = resumed.close()
        assert report.operations == 10


# ── Base SessionStore (no-op) ──────────────────────────────────

class TestBaseSessionStore:
    def test_base_store_returns_defaults(self):
        store = SessionStore()
        assert store.save(SessionCheckpoint(
            session_id="x", identity_id="u", tenant_id="t",
            operations=0, llm_calls=0, total_cost=0.0,
            context_messages=(), compaction_count=0, checkpoint_at="",
        )) is False
        assert store.load("x") is None
        assert store.delete("x") is False
        assert store.list_sessions() == []
        assert store.prune() == 0
