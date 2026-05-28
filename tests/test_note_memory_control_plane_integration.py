"""Tests for optional governed note-memory control-plane integration.

Purpose: verify the note-memory router mounts only behind an explicit flag and
fails closed when required persistence configuration is absent.
Governance scope: feature flag, append-only store path, and router mount
boundary.
Dependencies: note_memory_integration helper.
Invariants: disabled startup mounts nothing, enabled startup requires explicit
store persistence, and mounted state is recorded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.note_memory_integration import (
    NoteMemoryBootstrap,
    env_flag,
    mount_note_memory_router_from_env,
    validate_note_memory_store_path,
)


class FakeApp:
    """Minimal app object with router collection."""

    def __init__(self) -> None:
        self.routers: list[object] = []

    def include_router(self, router: object) -> None:
        self.routers.append(router)


class FakeRuntime:
    """Runtime marker for router factory tests."""

    def __init__(self, path: Path) -> None:
        self.path = path


def test_env_flag_accepts_explicit_truthy_values_only() -> None:
    assert env_flag("true") is True
    assert env_flag("enabled") is True
    assert env_flag("1") is True
    assert env_flag("") is False
    assert env_flag("false") is False
    assert env_flag(None) is False


def test_note_memory_integration_stays_disabled_without_flag() -> None:
    app = FakeApp()

    bootstrap = mount_note_memory_router_from_env(app=app, runtime_env={})

    assert isinstance(bootstrap, NoteMemoryBootstrap)
    assert bootstrap.enabled is False
    assert bootstrap.mounted is False
    assert bootstrap.reason == "disabled"
    assert app.routers == []


def test_note_memory_integration_requires_store_path_when_enabled() -> None:
    app = FakeApp()

    with pytest.raises(RuntimeError, match="STORE_PATH"):
        mount_note_memory_router_from_env(
            app=app,
            runtime_env={"MULLU_NOTE_MEMORY_ENABLED": "true"},
        )

    assert app.routers == []


def test_note_memory_store_path_must_be_absolute() -> None:
    with pytest.raises(RuntimeError, match="absolute directory path"):
        validate_note_memory_store_path("relative/notes")


def test_note_memory_store_path_requires_existing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "notes"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_note_memory_store_path(missing_parent)

    assert not missing_parent.parent.exists()


def test_note_memory_store_path_rejects_regular_file(tmp_path: Path) -> None:
    target_file = tmp_path / "notes.txt"
    target_file.write_text("not a store root", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not a regular file"):
        validate_note_memory_store_path(target_file)

    assert target_file.is_file()


def test_note_memory_store_path_accepts_nonexistent_dir_under_existing_parent(
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "notes"

    resolved = validate_note_memory_store_path(target_dir)

    assert resolved == target_dir.expanduser()
    assert not target_dir.exists()


def test_note_memory_integration_rejects_relative_store_path_at_mount() -> None:
    app = FakeApp()

    with pytest.raises(RuntimeError, match="absolute directory path"):
        mount_note_memory_router_from_env(
            app=app,
            runtime_env={
                "MULLU_NOTE_MEMORY_ENABLED": "true",
                "MULLU_NOTE_MEMORY_STORE_PATH": "relative/notes",
            },
        )

    assert app.routers == []


def test_note_memory_integration_mounts_supplied_router_factory(tmp_path: Path) -> None:
    app = FakeApp()
    mounted_runtime: dict[str, FakeRuntime] = {}

    def runtime_factory(path: str | Path) -> FakeRuntime:
        runtime = FakeRuntime(Path(path))
        mounted_runtime["runtime"] = runtime
        return runtime

    def router_factory(runtime: FakeRuntime) -> dict[str, object]:
        return {"runtime_path": runtime.path}

    bootstrap = mount_note_memory_router_from_env(
        app=app,
        runtime_env={
            "MULLU_NOTE_MEMORY_ENABLED": "true",
            "MULLU_NOTE_MEMORY_STORE_PATH": str(tmp_path / "notes"),
        },
        runtime_factory=runtime_factory,
        router_factory=router_factory,
    )

    assert bootstrap.enabled is True
    assert bootstrap.mounted is True
    assert bootstrap.reason == "mounted"
    assert bootstrap.store_path.endswith("notes")
    assert app.routers == [{"runtime_path": mounted_runtime["runtime"].path}]


def test_enabled_note_memory_integration_mounts_real_router(tmp_path: Path) -> None:
    fastapi = pytest.importorskip("fastapi")
    testclient_module = pytest.importorskip("fastapi.testclient")
    app = fastapi.FastAPI()

    bootstrap = mount_note_memory_router_from_env(
        app=app,
        runtime_env={
            "MULLU_NOTE_MEMORY_ENABLED": "true",
            "MULLU_NOTE_MEMORY_STORE_PATH": str(tmp_path / "notes"),
        },
    )
    client = testclient_module.TestClient(app)
    response = client.post(
        "/api/v1/notes/events",
        json={
            "kind": "WorkingNote",
            "scope": "task",
            "content_summary": "control-plane note memory route",
            "source_ref": "test:control-plane-router",
            "proof_state": "Pass",
            "trust_zone": "workspace",
            "expires_at": "2026-06-02T00:00:00+00:00",
            "evidence_refs": ["test_note_memory_control_plane_integration"],
        },
    )

    assert bootstrap.enabled is True
    assert bootstrap.mounted is True
    assert response.status_code == 200
    assert response.json()["governed"] is True
    assert response.json()["ok"] is True
