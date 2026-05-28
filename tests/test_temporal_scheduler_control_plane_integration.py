"""Tests for temporal-scheduler control-plane integration.

Purpose: verify the temporal subsystem helpers — store selection,
scheduler engine bootstrap with restore, and conditional background-worker
startup — pick the right shape from the runtime environment and validate
any hosted persistence path before construction.
Governance scope: file-vs-in-memory store selection, scheduler restore
ordering, optional worker lifecycle gating, and hosted-store path
validation.
Dependencies: temporal_scheduler_integration helpers, the temporal
runtime/engine/worker chain, and the in-memory and file-backed stores.
Invariants: unset store env yields the in-memory store; set env validates
the path and yields the file store; restore is called exactly once before
publication; the worker is only started when the explicit flag is enabled.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcoi_runtime.app.temporal_scheduler_integration import (
    TEMPORAL_SCHEDULER_STORE_PATH_ENV,
    TEMPORAL_WORKER_ENABLED_ENV,
    TEMPORAL_WORKER_ID_ENV,
    TEMPORAL_WORKER_INTERVAL_SECONDS_ENV,
    TEMPORAL_WORKER_LEASE_SECONDS_ENV,
    TEMPORAL_WORKER_LIMIT_ENV,
    TemporalSchedulerBootstrap,
    TemporalSchedulerStoreBootstrap,
    TemporalWorkerBootstrap,
    bootstrap_temporal_scheduler,
    maybe_start_temporal_worker,
    select_temporal_scheduler_store,
    validate_temporal_scheduler_store_path,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import TemporalSchedulerEngine
from mcoi_runtime.persistence.temporal_scheduler_store import (
    FileTemporalSchedulerStore,
    TemporalSchedulerStore,
)


def _frozen_clock() -> str:
    return datetime(2026, 5, 28, 0, 0, 0, tzinfo=timezone.utc).isoformat()


class _FakeBackgroundLoop:
    """Capture background-loop construction without touching threads."""

    def __init__(self, *, worker: object, interval_seconds: float, limit: int) -> None:
        self.worker = worker
        self.interval_seconds = interval_seconds
        self.limit = limit
        self.start_calls = 0

    def start(self) -> bool:
        self.start_calls += 1
        return True

    def stop(self) -> dict[str, object]:
        return {"stopped": True}


class _FakeWorker:
    """Capture worker constructor kwargs without touching real worker state."""

    def __init__(
        self,
        *,
        scheduler: object,
        store: object,
        worker_id: str,
        handlers: object,
        proof_bridge: object,
        lease_seconds: int,
    ) -> None:
        self.scheduler = scheduler
        self.store = store
        self.worker_id = worker_id
        self.handlers = handlers
        self.proof_bridge = proof_bridge
        self.lease_seconds = lease_seconds


def test_select_returns_in_memory_store_when_env_unset() -> None:
    bootstrap = select_temporal_scheduler_store({})

    assert isinstance(bootstrap, TemporalSchedulerStoreBootstrap)
    assert isinstance(bootstrap.store, TemporalSchedulerStore)
    assert not isinstance(bootstrap.store, FileTemporalSchedulerStore)
    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_in_memory_store_when_env_blank() -> None:
    bootstrap = select_temporal_scheduler_store(
        {TEMPORAL_SCHEDULER_STORE_PATH_ENV: "   "}
    )

    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_file_store_when_env_points_to_json(tmp_path: Path) -> None:
    target = tmp_path / "temporal-scheduler.json"

    bootstrap = select_temporal_scheduler_store(
        {TEMPORAL_SCHEDULER_STORE_PATH_ENV: str(target)}
    )

    assert isinstance(bootstrap.store, FileTemporalSchedulerStore)
    assert bootstrap.persistent is True
    assert bootstrap.path == str(target.expanduser())


def test_bootstrap_builds_engine_chain_and_restores_zero_actions() -> None:
    store = TemporalSchedulerStore()

    bootstrap = bootstrap_temporal_scheduler(store, clock=_frozen_clock)

    assert isinstance(bootstrap, TemporalSchedulerBootstrap)
    assert isinstance(bootstrap.event_spine, EventSpineEngine)
    assert isinstance(bootstrap.runtime, TemporalRuntimeEngine)
    assert isinstance(bootstrap.scheduler, TemporalSchedulerEngine)
    assert bootstrap.action_handlers == {}
    assert bootstrap.restored_action_count == 0


def test_maybe_start_worker_is_disabled_without_flag() -> None:
    store = TemporalSchedulerStore()
    chain = bootstrap_temporal_scheduler(store, clock=_frozen_clock)

    worker_bootstrap = maybe_start_temporal_worker(
        {},
        scheduler=chain.scheduler,
        store=store,
        action_handlers=chain.action_handlers,
        proof_bridge=object(),
    )

    assert isinstance(worker_bootstrap, TemporalWorkerBootstrap)
    assert worker_bootstrap.background is None
    assert worker_bootstrap.started is False


def test_maybe_start_worker_starts_when_flag_enabled() -> None:
    store = TemporalSchedulerStore()
    chain = bootstrap_temporal_scheduler(store, clock=_frozen_clock)
    proof_bridge_sentinel = object()
    constructed_workers: list[_FakeWorker] = []
    constructed_loops: list[_FakeBackgroundLoop] = []

    def _worker_factory(**kwargs: object) -> _FakeWorker:
        worker = _FakeWorker(**kwargs)  # type: ignore[arg-type]
        constructed_workers.append(worker)
        return worker

    def _loop_factory(**kwargs: object) -> _FakeBackgroundLoop:
        loop = _FakeBackgroundLoop(**kwargs)  # type: ignore[arg-type]
        constructed_loops.append(loop)
        return loop

    worker_bootstrap = maybe_start_temporal_worker(
        {
            TEMPORAL_WORKER_ENABLED_ENV: "true",
            TEMPORAL_WORKER_ID_ENV: "test-worker",
            TEMPORAL_WORKER_LEASE_SECONDS_ENV: "45",
            TEMPORAL_WORKER_INTERVAL_SECONDS_ENV: "15",
            TEMPORAL_WORKER_LIMIT_ENV: "5",
        },
        scheduler=chain.scheduler,
        store=store,
        action_handlers=chain.action_handlers,
        proof_bridge=proof_bridge_sentinel,
        background_loop_factory=_loop_factory,
        worker_factory=_worker_factory,
    )

    assert worker_bootstrap.started is True
    assert worker_bootstrap.background is constructed_loops[0]
    assert constructed_loops[0].start_calls == 1
    assert constructed_loops[0].interval_seconds == 15.0
    assert constructed_loops[0].limit == 5
    assert constructed_workers[0].worker_id == "test-worker"
    assert constructed_workers[0].lease_seconds == 45
    assert constructed_workers[0].proof_bridge is proof_bridge_sentinel
    assert constructed_workers[0].scheduler is chain.scheduler
    assert constructed_workers[0].store is store


def test_maybe_start_worker_uses_default_knobs_when_only_flag_set() -> None:
    store = TemporalSchedulerStore()
    chain = bootstrap_temporal_scheduler(store, clock=_frozen_clock)
    constructed_workers: list[_FakeWorker] = []
    constructed_loops: list[_FakeBackgroundLoop] = []

    def _worker_factory(**kwargs: object) -> _FakeWorker:
        worker = _FakeWorker(**kwargs)  # type: ignore[arg-type]
        constructed_workers.append(worker)
        return worker

    def _loop_factory(**kwargs: object) -> _FakeBackgroundLoop:
        loop = _FakeBackgroundLoop(**kwargs)  # type: ignore[arg-type]
        constructed_loops.append(loop)
        return loop

    maybe_start_temporal_worker(
        {TEMPORAL_WORKER_ENABLED_ENV: "1"},
        scheduler=chain.scheduler,
        store=store,
        action_handlers=chain.action_handlers,
        proof_bridge=object(),
        background_loop_factory=_loop_factory,
        worker_factory=_worker_factory,
    )

    assert constructed_workers[0].worker_id == "temporal-worker"
    assert constructed_workers[0].lease_seconds == 60
    assert constructed_loops[0].interval_seconds == 30.0
    assert constructed_loops[0].limit == 10


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_temporal_scheduler_store_path("relative/scheduler.json")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_temporal_scheduler_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".json file extension"):
        validate_temporal_scheduler_store_path(tmp_path / "scheduler.log")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "scheduler.json"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_temporal_scheduler_store_path(missing_parent)

    assert not missing_parent.parent.exists()
