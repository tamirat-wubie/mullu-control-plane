"""Optional governed note-memory router integration for the control-plane app.

Purpose: mount the governed note-memory router only when explicitly enabled by
environment configuration.
Governance scope: feature flag boundary, append-only store path requirement,
and fail-closed optional HTTP adapter loading.
Dependencies: app router mounting and mcoi_runtime.core.note_memory_* modules.
Invariants: disabled means no route mount; enabled requires an explicit store
path and loadable note-memory runtime/router factories.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    store_path = str(runtime_env.get("MULLU_NOTE_MEMORY_STORE_PATH", "")).strip()
    if not store_path:
        raise RuntimeError("MULLU_NOTE_MEMORY_STORE_PATH is required when note memory is enabled")

    if runtime_factory is None or router_factory is None:
        try:
            from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime
            from mcoi_runtime.core.note_memory_fastapi_router import create_note_memory_fastapi_router
        except ImportError as exc:
            raise RuntimeError("governed note-memory package is required when MULLU_NOTE_MEMORY_ENABLED is true") from exc
        runtime_factory = runtime_factory or NoteMemoryRuntime.from_path
        router_factory = router_factory or create_note_memory_fastapi_router

    runtime = runtime_factory(Path(store_path))
    router = router_factory(runtime)
    if include_router_fn is None:
        app.include_router(router)
    else:
        include_router_fn(router)
    return NoteMemoryBootstrap(
        enabled=True,
        mounted=True,
        store_path=store_path,
        reason="mounted",
    )
