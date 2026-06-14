"""Purpose: verify temporal scheduler HTTP endpoints.
Governance scope: API creation, listing, cancellation, missed closure, worker
    tick, and default router mounting.
Dependencies: FastAPI TestClient, temporal scheduler router, proof bridge.
Invariants:
  - API-created schedules are persisted.
  - Worker tick dispatches only due allowed schedules.
  - Cancel and missed closure emit terminal receipts and proofs.
  - Default router mounting includes the temporal scheduler API.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.temporal_scheduler import router
from mcoi_runtime.app.server_http import include_default_routers, iter_effective_app_routes
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


class DisabledBackground:
    def summary(self) -> dict[str, object]:
        return {"running": False, "enabled": False, "governed": True}


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
    deps.set("temporal_scheduler_background", DisabledBackground())
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


def test_missed_temporal_schedule_records_terminal_receipt() -> None:
    client = _client(MutableClock("2026-05-04T14:30:00+00:00"))
    client.post("/api/v1/temporal/schedules", json=_request())

    missed = client.post("/api/v1/temporal/schedules/sched-1/missed", params={"worker_id": "operator-a"})
    fetched = client.get("/api/v1/temporal/schedules/sched-1")
    worker = client.post(
        "/api/v1/temporal/worker/tick",
        json={"worker_id": "worker-a", "limit": 5, "certify_proofs": True},
    )

    assert missed.status_code == 200
    assert missed.json()["schedule"]["state"] == "missed"
    assert missed.json()["receipt"]["reason"] == "missed_run"
    assert missed.json()["receipt"]["worker_id"] == "operator-a"
    assert missed.json()["proof_receipt_id"].startswith("rcpt-")
    assert fetched.json()["receipt_count"] == 1
    assert fetched.json()["receipts"][0]["verdict"] == "blocked"
    assert worker.json()["count"] == 0


def test_reclaim_expired_temporal_lease_records_repair_receipt() -> None:
    calls: list[str] = []
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    client = _client(clock, handlers={"reminder": lambda action: calls.append(action.schedule_id) or {}})
    client.post("/api/v1/temporal/schedules", json=_request())
    lease = deps.temporal_scheduler.acquire_lease("sched-1", "worker-a", lease_seconds=60)
    deps.temporal_scheduler_store.save_action(deps.temporal_scheduler.get("sched-1"))
    clock.now = "2026-05-04T14:02:00+00:00"

    reclaimed = client.post("/api/v1/temporal/schedules/sched-1/lease/reclaim", params={"worker_id": "operator-a"})
    fetched = client.get("/api/v1/temporal/schedules/sched-1")
    worker = client.post(
        "/api/v1/temporal/worker/tick",
        json={"worker_id": "worker-b", "limit": 5, "certify_proofs": True},
    )

    assert lease is not None
    assert reclaimed.status_code == 200
    assert reclaimed.json()["schedule"]["state"] == "pending"
    assert reclaimed.json()["receipt"]["reason"] == "lease_reclaimed"
    assert reclaimed.json()["receipt"]["verdict"] == "not_due"
    assert reclaimed.json()["proof_receipt_id"].startswith("rcpt-")
    assert fetched.json()["receipt_count"] == 1
    assert fetched.json()["receipts"][0]["reason"] == "lease_reclaimed"
    assert worker.json()["count"] == 1
    assert calls == ["sched-1"]


def test_reclaim_active_temporal_lease_fails_closed() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    client = _client(clock)
    client.post("/api/v1/temporal/schedules", json=_request())
    lease = deps.temporal_scheduler.acquire_lease("sched-1", "worker-a", lease_seconds=120)
    deps.temporal_scheduler_store.save_action(deps.temporal_scheduler.get("sched-1"))

    reclaimed = client.post("/api/v1/temporal/schedules/sched-1/lease/reclaim", params={"worker_id": "operator-a"})
    fetched = client.get("/api/v1/temporal/schedules/sched-1")

    assert lease is not None
    assert reclaimed.status_code == 409
    assert reclaimed.json()["detail"]["error_code"] == "lease_not_reclaimable"
    assert fetched.json()["schedule"]["state"] == "running"
    assert fetched.json()["receipt_count"] == 0


def test_invalid_risk_and_missing_schedule_fail_closed() -> None:
    client = _client(MutableClock("2026-05-04T13:00:00+00:00"))
    invalid = _request()
    invalid["risk"] = "unknown-risk"

    created = client.post("/api/v1/temporal/schedules", json=invalid)
    missing_cancel = client.post("/api/v1/temporal/schedules/missing/cancel")
    missing_missed = client.post("/api/v1/temporal/schedules/missing/missed")

    assert created.status_code == 400
    assert created.json()["detail"]["error_code"] == "invalid_risk"
    assert missing_cancel.status_code == 404
    assert missing_cancel.json()["detail"]["error_code"] == "schedule_not_found"
    assert missing_missed.status_code == 404
    assert missing_missed.json()["detail"]["error_code"] == "schedule_not_found"


def test_create_temporal_schedule_error_detail_is_bounded() -> None:
    client = _client(MutableClock("2026-05-04T13:00:00+00:00"))

    class LeakyScheduler:
        def register(self, *args: object, **kwargs: object) -> object:
            raise ValueError("secret-token-from-scheduler")

    deps.set("temporal_scheduler", LeakyScheduler())

    response = client.post("/api/v1/temporal/schedules", json=_request())
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["error"] == "invalid temporal schedule"
    assert detail["error_code"] == "invalid_temporal_schedule"
    assert detail["governed"] is True
    assert "secret-token-from-scheduler" not in response.text


def test_default_routers_include_temporal_scheduler_summary() -> None:
    _install_deps(MutableClock("2026-05-04T13:00:00+00:00"))
    app = FastAPI()
    include_default_routers(app)
    paths = {route.path for route in iter_effective_app_routes(app)}

    assert "/api/v1/temporal/monitor" in paths
    assert "/api/v1/temporal/summary" in paths
    assert "/api/v1/temporal/schedules" in paths
    assert "/api/v1/temporal/schedules/{schedule_id}/lease/reclaim" in paths
    assert "/api/v1/temporal/schedules/{schedule_id}/missed" in paths
    assert "/api/v1/temporal/worker/tick" in paths


def test_temporal_monitor_reports_due_lease_and_expiry_without_mutation() -> None:
    client = _client(MutableClock("2026-05-04T14:00:00+00:00"))
    client.post("/api/v1/temporal/schedules", json=_request("sched-due"))
    future = _request("sched-future")
    future["execute_at"] = "2026-05-04T14:30:00+00:00"
    client.post("/api/v1/temporal/schedules", json=future)
    expired = _request("sched-expired")
    expired["execute_at"] = "2026-05-04T13:00:00+00:00"
    expired["expires_at"] = "2026-05-04T13:30:00+00:00"
    client.post("/api/v1/temporal/schedules", json=expired)
    client.post("/api/v1/temporal/schedules", json=_request("sched-leased"))
    lease = deps.temporal_scheduler.acquire_lease("sched-leased", "worker-a", lease_seconds=120)
    deps.temporal_scheduler_store.save_action(deps.temporal_scheduler.get("sched-leased"))

    response = client.get("/api/v1/temporal/monitor")
    body = response.json()
    audits = {item["schedule_id"]: item for item in body["audits"]}

    assert response.status_code == 200
    assert lease is not None
    assert body["count"] == 4
    assert audits["sched-due"]["verdict"] == "due"
    assert audits["sched-future"]["verdict"] == "not_due"
    assert audits["sched-expired"]["reason"] == "command_expired_candidate"
    assert audits["sched-leased"]["verdict"] == "leased"
    assert audits["sched-leased"]["lease_worker_id"] == "worker-a"
    assert body["counts"]["by_verdict"] == {"due": 1, "expired": 1, "leased": 1, "not_due": 1}
    assert body["store"]["receipt_count"] == 0
    assert deps.temporal_scheduler.get("sched-expired").state.value == "pending"
    assert deps.temporal_scheduler.get("sched-leased").state.value == "running"


def test_temporal_monitor_filters_by_tenant() -> None:
    client = _client(MutableClock("2026-05-04T14:00:00+00:00"))
    client.post("/api/v1/temporal/schedules", json=_request("sched-a"))
    other = _request("sched-b")
    other["tenant_id"] = "tenant-b"
    client.post("/api/v1/temporal/schedules", json=other)

    response = client.get("/api/v1/temporal/monitor", params={"tenant_id": "tenant-b"})
    body = response.json()

    assert response.status_code == 200
    assert body["count"] == 1
    assert body["audits"][0]["tenant_id"] == "tenant-b"
    assert body["audits"][0]["schedule_id"] == "sched-b"
    assert body["counts"]["by_verdict"] == {"due": 1}
    assert body["governed"] is True


def test_temporal_summary_reports_background_disabled() -> None:
    client = _client(MutableClock("2026-05-04T13:00:00+00:00"))

    response = client.get("/api/v1/temporal/summary")
    body = response.json()

    assert response.status_code == 200
    assert body["background"]["enabled"] is False
    assert body["background"]["running"] is False
    assert body["runtime"]["actions"] == 0
    assert body["governed"] is True
