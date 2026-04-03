"""Phase 203A — Agent Protocol Contracts.

Purpose: Typed protocol for task delegation between agents.
    Enables governed multi-agent coordination with result collection,
    capability advertisement, and task lifecycle tracking.
Governance scope: agent protocol contracts only.
Dependencies: none (pure contracts + state machine).
Invariants:
  - Tasks have explicit lifecycle: pending → assigned → running → completed/failed.
  - Results are immutable once submitted.
  - Agents declare capabilities — tasks are matched against them.
  - Delegation requires explicit capability match.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import threading
from typing import Any, Callable


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(StrEnum):
    LLM_COMPLETION = "llm.completion"
    CODE_EXECUTION = "code.execution"
    FILE_OPERATIONS = "file.operations"
    WEB_SEARCH = "web.search"
    DATA_ANALYSIS = "data.analysis"
    TOOL_USE = "tool.use"


@dataclass(frozen=True, slots=True)
class AgentDescriptor:
    """Describes an agent's identity and capabilities."""

    agent_id: str
    name: str
    capabilities: tuple[AgentCapability, ...]
    max_concurrent_tasks: int = 5
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """Specification for a task to be delegated to an agent."""

    task_id: str
    description: str
    required_capability: AgentCapability
    payload: dict[str, Any]
    priority: int = 0  # Higher = more important
    timeout_seconds: float = 300.0
    tenant_id: str = ""
    parent_task_id: str = ""  # For sub-task chains


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Immutable result of a completed/failed task."""

    task_id: str
    agent_id: str
    status: TaskStatus
    output: dict[str, Any]
    error: str = ""
    duration_ms: float = 0.0
    result_hash: str = ""


class AgentRegistry:
    """Registry of available agents and their capabilities."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}
        self._lock = threading.RLock()

    def register(self, agent: AgentDescriptor) -> None:
        with self._lock:
            if agent.agent_id in self._agents:
                raise ValueError(f"agent already registered: {agent.agent_id}")
            self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> bool:
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> AgentDescriptor | None:
        with self._lock:
            return self._agents.get(agent_id)

    def find_capable(self, capability: AgentCapability) -> list[AgentDescriptor]:
        """Find all agents with a given capability."""
        with self._lock:
            return [
                a for a in self._agents.values()
                if a.enabled and capability in a.capabilities
            ]

    def list_agents(self) -> list[AgentDescriptor]:
        with self._lock:
            return sorted(self._agents.values(), key=lambda a: a.agent_id)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._agents)


class TaskManager:
    """Manages task lifecycle — delegation, assignment, result collection."""

    def __init__(self, *, clock: Callable[[], str], registry: AgentRegistry) -> None:
        self._clock = clock
        self._registry = registry
        self._tasks: dict[str, TaskSpec] = {}
        self._assignments: dict[str, str] = {}  # task_id -> agent_id
        self._statuses: dict[str, TaskStatus] = {}
        self._results: dict[str, TaskResult] = {}
        self._lock = threading.RLock()

    def _assign_locked(self, task_id: str, agent_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")

        agent = self._registry.get(agent_id)
        if agent is None:
            raise ValueError(f"agent not found: {agent_id}")

        if not agent.enabled:
            raise ValueError(f"agent disabled: {agent_id}")

        if task.required_capability not in agent.capabilities:
            raise ValueError(
                f"agent {agent_id} lacks capability {task.required_capability}"
            )

        self._assignments[task_id] = agent_id
        self._statuses[task_id] = TaskStatus.ASSIGNED
        return True

    def submit(self, spec: TaskSpec) -> TaskSpec:
        """Submit a task for delegation."""
        with self._lock:
            if spec.task_id in self._tasks:
                raise ValueError(f"task already exists: {spec.task_id}")
            self._tasks[spec.task_id] = spec
            self._statuses[spec.task_id] = TaskStatus.PENDING
            return spec

    def assign(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to a specific agent.

        Validates that the agent has the required capability.
        """
        with self._lock:
            return self._assign_locked(task_id, agent_id)

    def auto_assign(self, task_id: str) -> str | None:
        """Auto-assign a task to a capable agent."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            candidates = self._registry.find_capable(task.required_capability)
            if not candidates:
                return None

            # Simple: pick the first capable agent
            agent = candidates[0]
            self._assign_locked(task_id, agent.agent_id)
            return agent.agent_id

    def start(self, task_id: str) -> bool:
        """Mark a task as running."""
        with self._lock:
            if self._statuses.get(task_id) != TaskStatus.ASSIGNED:
                return False
            self._statuses[task_id] = TaskStatus.RUNNING
            return True

    def complete(self, task_id: str, output: dict[str, Any], duration_ms: float = 0.0) -> TaskResult:
        """Record task completion."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise ValueError(f"task not found: {task_id}")

            agent_id = self._assignments.get(task_id, "unknown")
            result_hash = sha256(
                json.dumps(output, sort_keys=True, default=str).encode()
            ).hexdigest()

            result = TaskResult(
                task_id=task_id,
                agent_id=agent_id,
                status=TaskStatus.COMPLETED,
                output=output,
                duration_ms=duration_ms,
                result_hash=result_hash,
            )
            self._results[task_id] = result
            self._statuses[task_id] = TaskStatus.COMPLETED
            return result

    def fail(self, task_id: str, error: str) -> TaskResult:
        """Record task failure."""
        with self._lock:
            agent_id = self._assignments.get(task_id, "unknown")
            result = TaskResult(
                task_id=task_id,
                agent_id=agent_id,
                status=TaskStatus.FAILED,
                output={},
                error=error,
            )
            self._results[task_id] = result
            self._statuses[task_id] = TaskStatus.FAILED
            return result

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or assigned task."""
        with self._lock:
            status = self._statuses.get(task_id)
            if status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
                return False
            self._statuses[task_id] = TaskStatus.CANCELLED
            return True

    def get_result(self, task_id: str) -> TaskResult | None:
        with self._lock:
            return self._results.get(task_id)

    def get_status(self, task_id: str) -> TaskStatus | None:
        with self._lock:
            return self._statuses.get(task_id)

    def pending_tasks(self) -> list[TaskSpec]:
        with self._lock:
            return [
                self._tasks[tid] for tid, status in self._statuses.items()
                if status == TaskStatus.PENDING
            ]

    def running_tasks(self) -> list[TaskSpec]:
        with self._lock:
            return [
                self._tasks[tid] for tid, status in self._statuses.items()
                if status == TaskStatus.RUNNING
            ]

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    @property
    def completed_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._statuses.values() if s == TaskStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._statuses.values() if s == TaskStatus.FAILED)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            status_counts: dict[str, int] = {}
            for status in self._statuses.values():
                status_counts[status.value] = status_counts.get(status.value, 0) + 1
            return {
                "total_tasks": len(self._tasks),
                "status_counts": status_counts,
                "agents": self._registry.count,
            }
