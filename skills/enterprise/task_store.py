"""Task Store — Persistent backend for TaskScheduler.

Purpose: Persist scheduled task definitions and execution history
    so they survive process restarts.  The scheduler loads tasks
    on startup and writes through on every mutation.
Governance scope: persistence only — no scheduling logic.
Dependencies: none (pure JSON file I/O).
Invariants:
  - Writes are atomic (tempfile + rename).
  - Load never corrupts scheduler state on failure (returns empty).
  - Task definitions and execution history are separate files.
  - Store is optional — scheduler works without it (in-memory only).
  - Thread-safe — concurrent save/load are safe.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from skills.enterprise.task_scheduler import (
    ScheduledTask,
    ScheduleInterval,
    TaskExecution,
    TaskStatus,
)


class TaskStore:
    """Protocol for task persistence backends."""

    def save_tasks(self, tasks: list[ScheduledTask]) -> bool:
        return False

    def load_tasks(self) -> list[ScheduledTask]:
        return []

    def save_executions(self, executions: list[TaskExecution], *, limit: int = 1000) -> bool:
        return False

    def load_executions(self) -> list[TaskExecution]:
        return []


class InMemoryTaskStore(TaskStore):
    """In-memory task store for testing."""

    def __init__(self) -> None:
        self._tasks: list[dict[str, Any]] = []
        self._executions: list[dict[str, Any]] = []

    def save_tasks(self, tasks: list[ScheduledTask]) -> bool:
        self._tasks = [_task_to_dict(t) for t in tasks]
        return True

    def load_tasks(self) -> list[ScheduledTask]:
        return [_task_from_dict(d) for d in self._tasks]

    def save_executions(self, executions: list[TaskExecution], *, limit: int = 1000) -> bool:
        self._executions = [_exec_to_dict(e) for e in executions[-limit:]]
        return True

    def load_executions(self) -> list[TaskExecution]:
        return [_exec_from_dict(d) for d in self._executions]


class FileTaskStore(TaskStore):
    """File-based task store with atomic writes.

    Stores tasks and executions as separate JSON files:
    - {base_dir}/scheduled_tasks.json
    - {base_dir}/task_executions.json
    """

    def __init__(self, *, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _tasks_path(self) -> Path:
        return self._base_dir / "scheduled_tasks.json"

    def _executions_path(self) -> Path:
        return self._base_dir / "task_executions.json"

    def _atomic_write(self, path: Path, data: Any) -> bool:
        try:
            content = json.dumps(data, sort_keys=True, default=str, indent=2)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._base_dir), suffix=".tmp", prefix="task_",
            )
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    f.write(content)
                os.replace(tmp_path, str(path))
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return False
            return True
        except (OSError, TypeError):
            return False

    def _atomic_read(self, path: Path) -> Any | None:
        try:
            if not path.exists():
                return None
            with path.open("r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def save_tasks(self, tasks: list[ScheduledTask]) -> bool:
        with self._lock:
            data = [_task_to_dict(t) for t in tasks]
            return self._atomic_write(self._tasks_path(), data)

    def load_tasks(self) -> list[ScheduledTask]:
        with self._lock:
            data = self._atomic_read(self._tasks_path())
            if not isinstance(data, list):
                return []
            result = []
            for d in data:
                try:
                    result.append(_task_from_dict(d))
                except (KeyError, TypeError, ValueError):
                    continue
            return result

    def save_executions(self, executions: list[TaskExecution], *, limit: int = 1000) -> bool:
        with self._lock:
            data = [_exec_to_dict(e) for e in executions[-limit:]]
            return self._atomic_write(self._executions_path(), data)

    def load_executions(self) -> list[TaskExecution]:
        with self._lock:
            data = self._atomic_read(self._executions_path())
            if not isinstance(data, list):
                return []
            result = []
            for d in data:
                try:
                    result.append(_exec_from_dict(d))
                except (KeyError, TypeError, ValueError):
                    continue
            return result

    def summary(self) -> dict[str, Any]:
        return {
            "base_dir": str(self._base_dir),
            "tasks_file_exists": self._tasks_path().exists(),
            "executions_file_exists": self._executions_path().exists(),
        }


# ── Serialization helpers ──────────────────────────────────────

def _task_to_dict(task: ScheduledTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "tenant_id": task.tenant_id,
        "name": task.name,
        "description": task.description,
        "interval": task.interval.value,
        "action": task.action,
        "action_params": task.action_params,
        "enabled": task.enabled,
        "created_at": task.created_at,
        "last_run_at": task.last_run_at,
        "next_run_at": task.next_run_at,
        "run_count": task.run_count,
        "fail_count": task.fail_count,
    }


def _task_from_dict(d: dict[str, Any]) -> ScheduledTask:
    return ScheduledTask(
        task_id=d["task_id"],
        tenant_id=d["tenant_id"],
        name=d["name"],
        description=d.get("description", ""),
        interval=ScheduleInterval(d.get("interval", "daily")),
        action=d["action"],
        action_params=d.get("action_params", {}),
        enabled=d.get("enabled", True),
        created_at=d.get("created_at", ""),
        last_run_at=d.get("last_run_at", ""),
        next_run_at=d.get("next_run_at", ""),
        run_count=int(d.get("run_count", 0)),
        fail_count=int(d.get("fail_count", 0)),
    )


def _exec_to_dict(ex: TaskExecution) -> dict[str, Any]:
    return {
        "execution_id": ex.execution_id,
        "task_id": ex.task_id,
        "tenant_id": ex.tenant_id,
        "status": ex.status.value,
        "started_at": ex.started_at,
        "completed_at": ex.completed_at,
        "result": ex.result,
        "error": ex.error,
        "duration_ms": ex.duration_ms,
    }


def _exec_from_dict(d: dict[str, Any]) -> TaskExecution:
    return TaskExecution(
        execution_id=d["execution_id"],
        task_id=d["task_id"],
        tenant_id=d["tenant_id"],
        status=TaskStatus(d.get("status", "completed")),
        started_at=d.get("started_at", ""),
        completed_at=d.get("completed_at", ""),
        result=d.get("result", {}),
        error=d.get("error", ""),
        duration_ms=float(d.get("duration_ms", 0.0)),
    )
