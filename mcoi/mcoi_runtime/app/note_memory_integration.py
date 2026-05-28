"""Optional governed note-memory router integration for the control-plane app.

Purpose: mount the governed note-memory router only when explicitly enabled by
environment configuration.
Governance scope: feature flag boundary, append-only store path requirement,
hosted-store path validation, and fail-closed optional HTTP adapter loading.
Dependencies: app router mounting and mcoi_runtime.core.note_memory_* modules.
Invariants: disabled means no route mount; enabled requires an explicit store
path that resolves to an absolute directory root the control plane can write,
and loadable note-memory runtime/router factories.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class NoteMemoryBootstrap:
    """Startup posture for the governed note-memory router integration."""

    enabled: bool
    mounted: bool
    store_path: str
    reason: str


def env_flag(value: str | None) -> bool:
    """Return whether an environment flag is enabled."""

    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def mount_note_memory_router_from_env(
    *,
    app: Any,
    runtime_env: Mapping[str, str],
    include_router_fn: Callable[[Any], Any] | None = None,
    runtime_factory: Callable[[str | Path], Any] | None = None,
    router_factory: Callable[[Any], Any] | None = None,
) -> NoteMemoryBootstrap:
    """Mount the governed note-memory router when the explicit flag is enabled."""

    if not env_flag(runtime_env.get("MULLU_NOTE_MEMORY_ENABLED")):
        return NoteMemoryBootstrap(
            enabled=False,
            mounted=False,
            store_path="",
            reason="disabled",
        )

    store_path_text = str(runtime_env.get("MULLU_NOTE_MEMORY_STORE_PATH", "")).strip()
    if not store_path_text:
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH is required when note memory is enabled")
    store_path = validate_note_memory_store_path(store_path_text)

    if runtime_factory is None or router_factory is None:
        try:
            from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime
            from mcoi_runtime.core.note_memory_fastapi_router import create_note_memory_fastapi_router
        except ImportError as exc:
            raise RuntimeError("governed note-memory package is required when MULLU_NOTE_MEMORY_ENABLED is true") from exc
        runtime_factory = runtime_factory or NoteMemoryRuntime.from_path
        router_factory = router_factory or create_note_memory_fastapi_router

    runtime = runtime_factory(store_path)
    router = router_factory(runtime)
    if include_router_fn is None:
        app.include_router(router)
    else:
        include_router_fn(router)
    return NoteMemoryBootstrap(
        enabled=True,
        mounted=True,
        store_path=str(store_path),
        reason="mounted",
    )


def validate_note_memory_store_path(store_path: str | Path) -> Path:
    """Validate the hosted governed note-memory store path before mounting.

    The store root is a directory tree managed by NoteMemoryMesh (events/,
    anchors/, promotions/, rejected-deltas/, episodes/, write.lock). It is
    permitted to not yet exist — the mesh creates it on first write — but
    its parent must already exist and the target location must be writable.
    """

    path = Path(store_path).expanduser()
    if not path.is_absolute():
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH must be an absolute directory path")
    if path.exists() and path.is_file():
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH must point to a directory, not a regular file")
    parent = path.parent
    if not parent.exists():
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH parent directory must already exist")
    if not parent.is_dir():
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH parent must be a directory")
    if path.exists() and not path.is_dir():
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH must point to a directory")
    writable_target = path if path.exists() else parent
    if not os.access(writable_target, os.W_OK):
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH must be writable by the control-plane process")
    return path
