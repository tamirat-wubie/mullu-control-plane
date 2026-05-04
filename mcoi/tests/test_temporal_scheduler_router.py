"""Purpose: verify temporal scheduler HTTP endpoints.
Governance scope: API creation, listing, cancellation, worker tick, and default
    router mounting.
Dependencies: FastAPI TestClient, temporal scheduler router, proof bridge.
Invariants:
  - API-created schedules are persisted.
  - Worker tick dispatches only due allowed schedules.
  - Cancel emits a terminal cancellation receipt and proof.
  - Default router mounting includes the temporal scheduler API.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.temporal_scheduler import router
from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.proof_bridge import ProofBridge
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import TemporalSchedulerEngine
from mcoi_runtime.persistence.temporal_scheduler_store import TemporalSchedulerStore


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


def _install_deps(clock: MutableClock, handlers=None) -> MetricsStub:
    metrics = MetricsStub()
    temporal_runtime = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    temporal_scheduler = TemporalSchedulerEngine(temporal_runtime, clock=clock)
    deps.set("clock", clock)
    deps.set("metrics", metrics)
    deps.set("temporal_runtime", temporal_runtime)
    deps.set("temporal_scheduler", temporal_scheduler)
    deps.set("temporal_scheduler_store", TemporalSchedulerStore())
    deps.set("temporal_action_handlers", dict(handlers or {}))
    deps.set("proof_bridge", ProofBridge(clock=clock))
    return metrics


def _client(clock: MutableClock, handlers=None) -> TestClient:
    _install_deps(clock, handlers=handlers)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _request(schedule_id: str = "sched-1") -> dict[str, object]:
    return {
        "schedule_id": schedule_id,
        "action_id": f"act-{schedule_id}",
        "tenant_id": "tenant-a",
        "actor_id": "user-a",
        "action_type": "reminder",
        "execute_at": "2026-05-04T14:00:00+00:00",
        "handler_name": "reminder",
    }


def test_create_list_and_get_temporal_schedule() -> None:
    client = _client(MutableClock("2026-05-04T13:00:00+00:00"))

    created = client.post("/api/v1/temporal/schedules", json=_request())
    listed = client.get("/api/v1/temporal/schedules", params={"tenant_id": "tenant-a"})
    fetched = client.get("/api/v1/temporal/schedules/sched-1")

    assert created.status_code == 200
    assert created.json()["schedule"]["state"] == "pending"
    assert listed.json()["count"] == 1
    assert listed.json()["schedules"][0]["schedule_id"] == "sched-1"
    assert fetched.json()["receipt_count"] == 0
    assert fetched.json()["governed"] is True


def test_worker_tick_runs_due_schedule_and_returns_proofs() -> None:
    calls: list[str] = []
    client = _client(
        MutableClock("2026-05-04T14:00:00+00:00"),
        handlers={"reminder": lambda action: calls.append(action.schedule_id) or {}},
    )
    client.post("/api/v1/temporal/schedules", json=_request())

    response = client.post(
        "/api/v1/temporal/worker/tick",
        json={"worker_id": "worker-a", "limit": 5, "certify_proofs": True},
    )
    body = response.json()

    assert response.status_code == 200
    assert calls == ["sched-1"]
    assert body["count"] == 1
    assert body["results"][0]["evaluation_receipt"]["verdict"] == "due"
    assert body["results"][0]["closure_receipt"]["verdict"] == "completed"
    assert len(body["results"][0]["proof_receipt_ids"]) == 2


def test_cancel_temporal_schedule_records_terminal_receipt() -> None:
    client = _client(MutableClock("2026-05-04T13:30:00+00:00"))
    client.post("/api/v1/temporal/schedules", json=_request())

    cancelled = client.post("/api/v1/temporal/schedules/sched-1/cancel", params={"worker_id": "operator-a"})
    fetched = client.get("/api/v1/temporal/schedules/sched-1")

    assert cancelled.status_code == 200
    assert cancelled.json()["schedule"]["state"] == "cancelled"
    assert cancelled.json()["receipt"]["reason"] == "cancelled"
    assert cancelled.json()["proof_receipt_id"].startswith("rcpt-")
    assert fetched.json()["receipt_count"] == 1
    assert fetched.json()["receipts"][0]["verdict"] == "blocked"


def test_invalid_risk_and_missing_schedule_fail_closed() -> None:
    client = _client(MutableClock("2026-05-04T13:00:00+00:00"))
    invalid = _request()
    invalid["risk"] = "unknown-risk"

    created = client.post("/api/v1/temporal/schedules", json=invalid)
    missing = client.post("/api/v1/temporal/schedules/missing/cancel")

    assert created.status_code == 400
    assert created.json()["detail"]["error_code"] == "invalid_risk"
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "schedule_not_found"


def test_default_routers_include_temporal_scheduler_summary() -> None:
    _install_deps(MutableClock("2026-05-04T13:00:00+00:00"))
    app = FastAPI()
    include_default_routers(app)
    paths = {route.path for route in app.routes}

    assert "/api/v1/temporal/summary" in paths
    assert "/api/v1/temporal/schedules" in paths
    assert "/api/v1/temporal/worker/tick" in paths
