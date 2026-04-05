"""Purpose: verify governed background scheduler.
Governance scope: scheduler core + HTTP endpoint tests.
Dependencies: scheduler module, FastAPI test client.
Invariants: all jobs go through guard chain; history is bounded; thread-safe.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from mcoi_runtime.core.scheduler import (
    GovernedScheduler,
    JobSchedule,
    JobStatus,
    ScheduledJob,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_scheduler(**kwargs) -> GovernedScheduler:
    return GovernedScheduler(clock=lambda: _CLOCK, **kwargs)


def _sample_job(job_id: str = "job-1", handler_name: str = "test_handler") -> ScheduledJob:
    return ScheduledJob(
        job_id=job_id,
        name="Test Job",
        schedule_type=JobSchedule.ONCE,
        handler_name=handler_name,
    )


# --- Core Engine Tests ---


def test_schedule_and_list_jobs() -> None:
    s = _make_scheduler()
    s.schedule(_sample_job("j1"))
    s.schedule(_sample_job("j2"))
    jobs = s.list_jobs()
    assert len(jobs) == 2
    assert jobs[0].job_id == "j1"


def test_unschedule_job() -> None:
    s = _make_scheduler()
    s.schedule(_sample_job())
    assert s.unschedule("job-1") is True
    assert s.unschedule("job-1") is False
    assert len(s.list_jobs()) == 0


def test_disable_enable_job() -> None:
    s = _make_scheduler()
    s.schedule(_sample_job())
    assert s.disable("job-1") is True
    job = s.get_job("job-1")
    assert job is not None and not job.enabled
    assert s.enable("job-1") is True
    job = s.get_job("job-1")
    assert job is not None and job.enabled


def test_execute_job_succeeds() -> None:
    s = _make_scheduler()
    s.register_handler("test_handler", lambda job: {"result": "ok"})
    s.schedule(_sample_job())
    execution = s.execute_job("job-1")
    assert execution.status == JobStatus.SUCCEEDED
    assert execution.result == {"result": "ok"}


def test_execute_job_handler_not_found() -> None:
    s = _make_scheduler()
    s.schedule(_sample_job(handler_name="missing"))
    execution = s.execute_job("job-1")
    assert execution.status == JobStatus.FAILED
    assert execution.error == "handler not found"
    assert "missing" not in execution.error


def test_execute_disabled_job() -> None:
    s = _make_scheduler()
    s.register_handler("test_handler", lambda job: {"result": "ok"})
    s.schedule(_sample_job())
    s.disable("job-1")
    execution = s.execute_job("job-1")
    assert execution.status == JobStatus.DISABLED


def test_execute_job_handler_raises() -> None:
    def bad_handler(job):
        raise RuntimeError("boom")

    s = _make_scheduler()
    s.register_handler("test_handler", bad_handler)
    s.schedule(_sample_job())
    execution = s.execute_job("job-1")
    assert execution.status == JobStatus.FAILED
    assert execution.error == "handler error (RuntimeError)"


def test_execute_job_guard_denied_is_bounded() -> None:
    class GuardChain:
        def evaluate(self, ctx):
            return SimpleNamespace(allowed=False, reason="budget b1 denied for tenant t1")

    s = _make_scheduler(guard_chain=GuardChain())
    s.register_handler("test_handler", lambda job: {"result": "ok"})
    s.schedule(_sample_job())
    execution = s.execute_job("job-1")
    assert execution.status == JobStatus.FAILED
    assert execution.error == "job execution denied"
    assert "budget b1" not in execution.error
    assert "tenant t1" not in execution.error


def test_execute_nonexistent_job_raises() -> None:
    s = _make_scheduler()
    with pytest.raises(ValueError, match="job not found"):
        s.execute_job("nonexistent")


def test_execute_nonexistent_job_error_is_bounded() -> None:
    s = _make_scheduler()
    with pytest.raises(ValueError, match="job not found") as excinfo:
        s.execute_job("nonexistent")
    assert str(excinfo.value) == "job not found"
    assert "nonexistent" not in str(excinfo.value)


def test_history_bounded() -> None:
    s = _make_scheduler()
    s.register_handler("test_handler", lambda job: {})
    s.schedule(_sample_job())
    for _ in range(50):
        s.execute_job("job-1")
    assert len(s.recent_executions(limit=10)) == 10


def test_summary() -> None:
    s = _make_scheduler()
    s.register_handler("test_handler", lambda job: {})
    s.schedule(_sample_job())
    s.execute_job("job-1")
    summary = s.summary()
    assert summary["total_jobs"] == 1
    assert summary["enabled_jobs"] == 1
    assert summary["total_executions"] == 1


# --- HTTP Endpoint Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_schedule_job_endpoint(client) -> None:
    resp = client.post("/api/v1/scheduler/jobs", json={
        "job_id": "http-job-1",
        "name": "HTTP Test Job",
        "schedule_type": "once",
        "handler_name": "noop",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "http-job-1"
    assert data["governed"] is True


def test_list_jobs_endpoint(client) -> None:
    client.post("/api/v1/scheduler/jobs", json={
        "job_id": "list-job",
        "name": "List Test",
        "schedule_type": "once",
    })
    resp = client.get("/api/v1/scheduler/jobs")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_scheduler_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/scheduler/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_jobs" in data
    assert data["governed"] is True


def test_invalid_schedule_type_400(client) -> None:
    resp = client.post("/api/v1/scheduler/jobs", json={
        "job_id": "bad",
        "name": "Bad",
        "schedule_type": "invalid",
    })
    assert resp.status_code == 400
