"""Scheduler endpoints — manage and execute governed background jobs.

Provides HTTP interface to schedule, execute, list, and manage
governed background jobs. Every job goes through the guard chain.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


def _scheduler_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


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
def schedule_job(req: ScheduleJobRequest):
    """Schedule a new governed background job."""
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
def execute_job(req: ExecuteJobRequest):
    """Execute a scheduled job immediately through the governed pipeline."""
    deps.metrics.inc("requests_governed")
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
def list_jobs():
    """List all scheduled jobs."""
    deps.metrics.inc("requests_governed")
    jobs = deps.scheduler.list_jobs()
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
def disable_job(job_id: str):
    """Disable a scheduled job."""
    deps.metrics.inc("requests_governed")
    if not deps.scheduler.disable(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "enabled": False, "governed": True}


@router.post("/api/v1/scheduler/jobs/{job_id}/enable")
def enable_job(job_id: str):
    """Enable a previously disabled job."""
    deps.metrics.inc("requests_governed")
    if not deps.scheduler.enable(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "enabled": True, "governed": True}


@router.delete("/api/v1/scheduler/jobs/{job_id}")
def unschedule_job(job_id: str):
    """Remove a scheduled job."""
    deps.metrics.inc("requests_governed")
    if not deps.scheduler.unschedule(job_id):
        raise HTTPException(404, detail=_scheduler_error_detail("job not found", "job_not_found"))
    return {"job_id": job_id, "removed": True, "governed": True}


@router.get("/api/v1/scheduler/history")
def job_history(limit: int = 50):
    """Recent job execution history."""
    deps.metrics.inc("requests_governed")
    executions = deps.scheduler.recent_executions(limit=limit)
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
