"""Temporal scheduler integration for the control-plane app.

Purpose: build the temporal subsystem (event spine + runtime + scheduler
engine + optional background worker) from runtime environment configuration
and validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory store selection, scheduler restore
ordering, optional background-worker lifecycle, and fail-closed
misconfiguration handling.
Dependencies: TemporalRuntimeEngine + TemporalSchedulerEngine +
TemporalSchedulerWorker + TemporalSchedulerBackgroundLoop runtime,
EventSpineEngine, and FileTemporalSchedulerStore persistence.
Invariants: no env path means a non-persistent in-memory scheduler store;
an env path must be absolute, must use a .json extension, must not be a
directory, and the parent directory must already exist and be writable;
``restore`` is called exactly once before the scheduler is published;
the background worker is only started when the explicit flag is enabled,
and its shutdown is registered with the supplied shutdown manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from mcoi_runtime.app._integration_paths import env_flag, validate_hosted_store_path
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import TemporalSchedulerEngine
from mcoi_runtime.core.temporal_scheduler_background import (
    TemporalSchedulerBackgroundLoop,
)
from mcoi_runtime.core.temporal_scheduler_worker import TemporalSchedulerWorker
from mcoi_runtime.persistence.temporal_scheduler_store import (
    FileTemporalSchedulerStore,
    TemporalSchedulerStore,
)


TEMPORAL_SCHEDULER_STORE_PATH_ENV = "MULLU_TEMPORAL_SCHEDULER_STORE_PATH"
TEMPORAL_WORKER_ENABLED_ENV = "MULLU_TEMPORAL_WORKER_ENABLED"
TEMPORAL_WORKER_ID_ENV = "MULLU_TEMPORAL_WORKER_ID"
TEMPORAL_WORKER_LEASE_SECONDS_ENV = "MULLU_TEMPORAL_WORKER_LEASE_SECONDS"
TEMPORAL_WORKER_INTERVAL_SECONDS_ENV = "MULLU_TEMPORAL_WORKER_INTERVAL_SECONDS"
TEMPORAL_WORKER_LIMIT_ENV = "MULLU_TEMPORAL_WORKER_LIMIT"


@dataclass(frozen=True)
class TemporalSchedulerStoreBootstrap:
    """Startup posture for the temporal scheduler store."""

    store: TemporalSchedulerStore
    path: str
    persistent: bool


@dataclass(frozen=True)
class TemporalSchedulerBootstrap:
    """Startup posture for the temporal scheduler engine chain."""

    event_spine: EventSpineEngine
    runtime: TemporalRuntimeEngine
    scheduler: TemporalSchedulerEngine
    action_handlers: dict[str, Any]
    restored_action_count: int


@dataclass(frozen=True)
class TemporalWorkerBootstrap:
    """Startup posture for the optional temporal background worker."""

    background: TemporalSchedulerBackgroundLoop | None
    started: bool


def select_temporal_scheduler_store(
    runtime_env: Mapping[str, str],
) -> TemporalSchedulerStoreBootstrap:
    """Return the scheduler store that matches the runtime environment.

    When the env path is unset, an in-memory ``TemporalSchedulerStore`` is
    used. When set, the path is validated and a ``FileTemporalSchedulerStore``
    is constructed (auto-loading any existing persisted state).
    """

    raw_value = runtime_env.get(TEMPORAL_SCHEDULER_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return TemporalSchedulerStoreBootstrap(
            store=TemporalSchedulerStore(),
            path="",
            persistent=False,
        )

    path = validate_temporal_scheduler_store_path(str(raw_value).strip())
    return TemporalSchedulerStoreBootstrap(
        store=FileTemporalSchedulerStore(path),
        path=str(path),
        persistent=True,
    )


def bootstrap_temporal_scheduler(
    store: TemporalSchedulerStore,
    *,
    clock: Callable[[], str],
) -> TemporalSchedulerBootstrap:
    """Build the temporal subsystem and restore actions from the store.

    Constructs the event spine + runtime + scheduler engine chain, restores
    persisted actions from ``store.list_actions()`` into the scheduler, and
    returns the assembled bootstrap with an empty action-handlers registry
    that callers populate via subsystem wiring.
    """

    event_spine = EventSpineEngine()
    runtime = TemporalRuntimeEngine(event_spine, clock=clock)
    scheduler = TemporalSchedulerEngine(runtime, clock=clock)
    restored_actions = store.list_actions()
    scheduler.restore(restored_actions)
    action_handlers: dict[str, Any] = {}
    return TemporalSchedulerBootstrap(
        event_spine=event_spine,
        runtime=runtime,
        scheduler=scheduler,
        action_handlers=action_handlers,
        restored_action_count=len(restored_actions),
    )


def maybe_start_temporal_worker(
    runtime_env: Mapping[str, str],
    *,
    scheduler: TemporalSchedulerEngine,
    store: TemporalSchedulerStore,
    action_handlers: Mapping[str, Any],
    proof_bridge: Any,
    background_loop_factory: Callable[..., TemporalSchedulerBackgroundLoop] | None = None,
    worker_factory: Callable[..., TemporalSchedulerWorker] | None = None,
) -> TemporalWorkerBootstrap:
    """Start the background temporal worker only when the explicit flag is set.

    Returns ``TemporalWorkerBootstrap(background=None, started=False)`` when
    the flag is unset. When enabled, constructs the worker + background loop
    using the env-driven knobs, starts the loop, and returns the started
    bootstrap. The caller is responsible for registering shutdown.
    """

    if not env_flag(runtime_env.get(TEMPORAL_WORKER_ENABLED_ENV)):
        return TemporalWorkerBootstrap(background=None, started=False)

    worker_factory = worker_factory or TemporalSchedulerWorker
    background_loop_factory = background_loop_factory or TemporalSchedulerBackgroundLoop

    worker = worker_factory(
        scheduler=scheduler,
        store=store,
        worker_id=runtime_env.get(TEMPORAL_WORKER_ID_ENV, "temporal-worker"),
        handlers=action_handlers,
        proof_bridge=proof_bridge,
        lease_seconds=int(runtime_env.get(TEMPORAL_WORKER_LEASE_SECONDS_ENV, "60")),
    )
    background = background_loop_factory(
        worker=worker,
        interval_seconds=float(runtime_env.get(TEMPORAL_WORKER_INTERVAL_SECONDS_ENV, "30")),
        limit=int(runtime_env.get(TEMPORAL_WORKER_LIMIT_ENV, "10")),
    )
    background.start()
    return TemporalWorkerBootstrap(background=background, started=True)


def validate_temporal_scheduler_store_path(store_path: str | Path) -> Path:
    """Validate the hosted temporal-scheduler store path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=TEMPORAL_SCHEDULER_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
