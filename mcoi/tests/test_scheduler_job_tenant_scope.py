"""Cross-tenant scoping for scheduler job endpoints.

Scheduled jobs are tenant-owned (ScheduledJob.tenant_id) but were addressed by
job_id with no tenant check, so an authenticated caller for tenant A could
execute, disable, enable, or delete tenant B's jobs, and list_jobs returned every
tenant's jobs. The by-id handlers now enforce the job's tenant before mutating;
list_jobs filters to the caller's tenant (operators/dev see all).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import scheduler


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.write"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


class _SType:
    value = "once"


class _Job:
    def __init__(self, tenant_id, job_id="j"):
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.name = "n"
        self.enabled = True
        self.schedule_type = _SType()
        self.handler_name = "h"


class _Sched:
    def __init__(self, *, job=None, jobs=None):
        self._job = job
        self._jobs = jobs or []

    def get_job(self, job_id):
        return self._job

    def list_jobs(self):
        return list(self._jobs)


class _ExecBody:
    job_id = "j"


@pytest.fixture
def owned_by_b(monkeypatch):
    monkeypatch.setattr(scheduler.deps, "scheduler", _Sched(job=_Job("tenant-b")))


def test_execute_job_rejects_cross_tenant(owned_by_b):
    with pytest.raises(HTTPException) as exc:
        scheduler.execute_job(_ExecBody(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_disable_job_rejects_cross_tenant(owned_by_b):
    with pytest.raises(HTTPException) as exc:
        scheduler.disable_job("j", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_enable_job_rejects_cross_tenant(owned_by_b):
    with pytest.raises(HTTPException) as exc:
        scheduler.enable_job("j", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_unschedule_job_rejects_cross_tenant(owned_by_b):
    with pytest.raises(HTTPException) as exc:
        scheduler.unschedule_job("j", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_unschedule_missing_job_is_404(monkeypatch):
    monkeypatch.setattr(scheduler.deps, "scheduler", _Sched(job=None))
    with pytest.raises(HTTPException) as exc:
        scheduler.unschedule_job("missing", _authed("tenant-a"))
    assert exc.value.status_code == 404


def test_list_jobs_filters_to_own_tenant(monkeypatch):
    jobs = [_Job("tenant-a", "ja"), _Job("tenant-b", "jb")]
    monkeypatch.setattr(scheduler.deps, "scheduler", _Sched(jobs=jobs))
    result = scheduler.list_jobs(_authed("tenant-a"))
    assert result["count"] == 1
    assert [j["job_id"] for j in result["jobs"]] == ["ja"]


def test_list_jobs_operator_sees_all(monkeypatch):
    jobs = [_Job("tenant-a", "ja"), _Job("tenant-b", "jb")]
    monkeypatch.setattr(scheduler.deps, "scheduler", _Sched(jobs=jobs))
    result = scheduler.list_jobs(_authed("tenant-a", operator=True))
    assert result["count"] == 2
