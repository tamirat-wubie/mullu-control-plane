"""Scheduler endpoints — manage and execute governed background jobs.

Provides HTTP interface to schedule, execute, list, and manage
governed background jobs. Every job goes through the guard chain.
"""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()
_MAX_SCHEDULER_HISTORY_READ_LIMIT = 500


def _scheduler_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_scheduler_validation_error(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_scheduler_error_detail(
            "invalid scheduler history request",
            "scheduler_history_invalid_request",
        ),
    ) from error


def _coerce_scheduler_history_limit(limit: object) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if isinstance(limit, int):
        value = limit
    elif isinstance(limit, str):
        normalized = limit.strip()
        if not normalized.isdecimal():
            raise ValueError("limit must be an integer")
        value = int(normalized)
    else:
        raise ValueError("limit must be an integer")
    if value < 0 or value > _MAX_SCHEDULER_HISTORY_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


def _enforce_job_tenant(request: Request, job_id: str) -> None:
    """Reject access to a scheduled job owned by another tenant.

    Jobs are addressed by job_id (not a tenant_id parameter), so the linter
    cannot see these handlers; the owning tenant is read off the job. A no-op for
    operators (wildcard scope) and unauthenticated dev requests.
    """
    job = deps.scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    enforce_tenant_scope(request, job.tenant_id)


class ScheduleJobRequest(BaseModel):
    job_id: str
    name: str
    schedule_type: str = "once"  # "once", "interval", "cron"
    interval_seconds: int = 0
    cron_expression: str = ""
    handler_name: str = ""
    tenant_id: str = ""
    budget_id: str = ""
    mission_id: str = ""
    goal_id: str = ""
    max_retries: int = 3
    timeout_seconds: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecuteJobRequest(BaseModel):
    job_id: str


@router.post("/api/v1/scheduler/jobs")
def schedule_job(req: ScheduleJobRequest, request: Request):
    """Schedule a new governed background job."""
    enforce_tenant_scope(request, req.tenant_id)
    from mcoi_runtime.core.scheduler import JobSchedule, ScheduledJob
    deps.metrics.inc("requests_governed")
    try:
        schedule_type = JobSchedule(req.schedule_type)
    except ValueError:
        raise HTTPException(400, detail=_scheduler_error_detail("invalid schedule type", "invalid_schedule_type"))
    job = ScheduledJob(
        job_id=req.job_id,
        name=req.name,
        schedule_type=schedule_type,
        interval_seconds=req.interval_seconds,
        cron_expression=req.cron_expression,
        handler_name=req.handler_name,
        tenant_id=req.tenant_id,
        budget_id=req.budget_id,
        mission_id=req.mission_id,
        goal_id=req.goal_id,
        max_retries=req.max_retries,
        timeout_seconds=req.timeout_seconds,
    )
    deps.scheduler.schedule(job)
    return {
        "job_id": job.job_id,
        "name": job.name,
        "schedule_type": job.schedule_type.value,
        "enabled": job.enabled,
        "governed": True,
    }


@router.post("/api/v1/scheduler/execute")
def execute_job(req: ExecuteJobRequest, request: Request):
    """Execute a scheduled job immediately through the governed pipeline."""
    deps.metrics.inc("requests_governed")
    _enforce_job_tenant(request, req.job_id)
    try:
        execution = deps.scheduler.execute_job(req.job_id)
    except ValueError:
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {
        "execution_id": execution.execution_id,
        "job_id": execution.job_id,
        "status": execution.status.value,
        "error": execution.error,
        "governed": True,
    }


@router.get("/api/v1/scheduler/jobs")
def list_jobs(request: Request):
    """List all scheduled jobs."""
    deps.metrics.inc("requests_governed")
    scoped = scoped_listing_tenant(request, None)
    jobs = deps.scheduler.list_jobs()
    if scoped is not None:
        jobs = [job for job in jobs if job.tenant_id == scoped]
    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "name": j.name,
                "schedule_type": j.schedule_type.value,
                "handler_name": j.handler_name,
                "enabled": j.enabled,
                "tenant_id": j.tenant_id,
            }
            for j in jobs
        ],
        "count": len(jobs),
        "governed": True,
    }


@router.post("/api/v1/scheduler/jobs/{job_id}/disable")
def disable_job(job_id: str, request: Request):
    """Disable a scheduled job."""
    deps.metrics.inc("requests_governed")
    _enforce_job_tenant(request, job_id)
    if not deps.scheduler.disable(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "enabled": False, "governed": True}


@router.post("/api/v1/scheduler/jobs/{job_id}/enable")
def enable_job(job_id: str, request: Request):
    """Enable a previously disabled job."""
    deps.metrics.inc("requests_governed")
    _enforce_job_tenant(request, job_id)
    if not deps.scheduler.enable(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "enabled": True, "governed": True}


@router.delete("/api/v1/scheduler/jobs/{job_id}")
def unschedule_job(job_id: str, request: Request):
    """Remove a scheduled job."""
    deps.metrics.inc("requests_governed")
    _enforce_job_tenant(request, job_id)
    if not deps.scheduler.unschedule(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "removed": True, "governed": True}


@router.get("/api/v1/scheduler/history")
def job_history(limit: str = "50"):
    """Recent job execution history."""
    deps.metrics.inc("requests_governed")
    try:
        read_limit = _coerce_scheduler_history_limit(limit)
    except ValueError as error:
        _raise_scheduler_validation_error(error)
    executions = deps.scheduler.recent_executions(limit=read_limit)
    return {
        "executions": [
            {
                "execution_id": e.execution_id,
                "job_id": e.job_id,
                "status": e.status.value,
                "started_at": e.started_at,
                "error": e.error,
            }
            for e in executions
        ],
        "count": len(executions),
        "governed": True,
    }


@router.get("/api/v1/scheduler/summary")
def scheduler_summary():
    """Scheduler status summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.scheduler.summary(), "governed": True}
