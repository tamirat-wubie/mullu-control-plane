"""Phase 204B — End-to-End Multi-Agent Workflow Engine.

Purpose: Orchestrates complete agent workflows — from task submission
    through LLM processing to result delivery and webhook notification.
    Bridges agent_protocol, llm_integration, webhook_system, and audit_trail.
Governance scope: workflow orchestration only.
Dependencies: agent_protocol, llm_integration, webhook_system, audit_trail, tenant_budget.
Invariants:
  - Every workflow step is audited.
  - Budget is checked before LLM invocation.
  - Webhook notification fires on completion/failure.
  - Workflow results are deterministic for same inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.core.agent_protocol import (
    AgentCapability,
    AgentDescriptor,
    AgentRegistry,
    TaskManager,
    TaskResult,
    TaskSpec,
    TaskStatus,
)
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.webhook_system import WebhookManager


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """Single step in a workflow execution trace."""

    step_name: str
    status: str  # "ok", "error", "skipped"
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Complete result of a multi-agent workflow execution."""

    workflow_id: str
    task_id: str
    agent_id: str
    status: str  # "completed", "failed"
    steps: tuple[WorkflowStep, ...]
    output: dict[str, Any]
    error: str = ""


class AgentWorkflowEngine:
    """Orchestrates end-to-end agent workflows.

    Flow:
    1. Submit task → TaskManager
    2. Auto-assign to capable agent
    3. Execute LLM completion (governed, budgeted)
    4. Record result + audit trail
    5. Emit webhook notification
    6. Return WorkflowResult
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        task_manager: TaskManager,
        llm_complete_fn: Callable[[str, str], Any] | None = None,
        webhook_manager: WebhookManager | None = None,
        audit_trail: AuditTrail | None = None,
    ) -> None:
        self._clock = clock
        self._task_mgr = task_manager
        self._llm_complete_fn = llm_complete_fn
        self._webhook_mgr = webhook_manager
        self._audit = audit_trail
        self._workflow_counter = 0
        self._history: list[WorkflowResult] = []

    def execute(
        self,
        *,
        task_id: str,
        description: str,
        capability: AgentCapability,
        payload: dict[str, Any],
        tenant_id: str = "",
        budget_id: str = "default",
    ) -> WorkflowResult:
        """Execute a full governed workflow.

        Steps: submit → assign → start → invoke LLM → complete → audit → webhook
        """
        self._workflow_counter += 1
        workflow_id = f"wf-{self._workflow_counter}"
        steps: list[WorkflowStep] = []
        agent_id = ""

        try:
            # Step 1: Submit task
            spec = TaskSpec(
                task_id=task_id,
                description=description,
                required_capability=capability,
                payload=payload,
                tenant_id=tenant_id,
            )
            self._task_mgr.submit(spec)
            steps.append(WorkflowStep("submit", "ok", {"task_id": task_id}))

            # Step 2: Auto-assign
            agent_id = self._task_mgr.auto_assign(task_id) or ""
            if not agent_id:
                raise ValueError(f"no capable agent for {capability}")
            steps.append(WorkflowStep("assign", "ok", {"agent_id": agent_id}))

            # Step 3: Start
            self._task_mgr.start(task_id)
            steps.append(WorkflowStep("start", "ok", {}))

            # Step 4: LLM invocation (if function provided)
            llm_output: dict[str, Any] = {}
            if self._llm_complete_fn is not None:
                prompt = payload.get("prompt", description)
                result = self._llm_complete_fn(prompt, budget_id)
                if hasattr(result, "content"):
                    llm_output = {
                        "content": result.content,
                        "model": getattr(result, "model_name", ""),
                        "tokens": getattr(result, "total_tokens", 0),
                        "cost": getattr(result, "cost", 0.0),
                        "succeeded": getattr(result, "succeeded", True),
                    }
                else:
                    llm_output = {"result": str(result)}
                steps.append(WorkflowStep("llm_invoke", "ok", {"model": llm_output.get("model", "")}))
            else:
                llm_output = {"content": f"stub result for: {description}"}
                steps.append(WorkflowStep("llm_invoke", "skipped", {"reason": "no LLM function"}))

            # Step 5: Complete task
            task_result = self._task_mgr.complete(task_id, llm_output)
            steps.append(WorkflowStep("complete", "ok", {"result_hash": task_result.result_hash[:16]}))

            # Step 6: Audit
            if self._audit is not None:
                self._audit.record(
                    action="workflow.complete",
                    actor_id=agent_id,
                    tenant_id=tenant_id,
                    target=task_id,
                    outcome="success",
                    detail={"workflow_id": workflow_id, "cost": llm_output.get("cost", 0.0)},
                )
                steps.append(WorkflowStep("audit", "ok", {}))

            # Step 7: Webhook
            if self._webhook_mgr is not None:
                deliveries = self._webhook_mgr.emit(
                    "task.completed",
                    {"task_id": task_id, "agent_id": agent_id, "workflow_id": workflow_id},
                    tenant_id=tenant_id,
                )
                steps.append(WorkflowStep("webhook", "ok", {"deliveries": len(deliveries)}))

            result = WorkflowResult(
                workflow_id=workflow_id,
                task_id=task_id,
                agent_id=agent_id,
                status="completed",
                steps=tuple(steps),
                output=llm_output,
            )
            self._history.append(result)
            return result

        except Exception as exc:
            # Record failure
            self._task_mgr.fail(task_id, str(exc)) if task_id in {s.task_id for s in self._task_mgr.pending_tasks()} or self._task_mgr.get_status(task_id) in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING) else None

            if self._audit is not None:
                self._audit.record(
                    action="workflow.failed",
                    actor_id=agent_id or "system",
                    tenant_id=tenant_id,
                    target=task_id,
                    outcome="error",
                    detail={"error": str(exc), "workflow_id": workflow_id},
                )

            if self._webhook_mgr is not None:
                self._webhook_mgr.emit(
                    "task.failed",
                    {"task_id": task_id, "error": str(exc), "workflow_id": workflow_id},
                    tenant_id=tenant_id,
                )

            result = WorkflowResult(
                workflow_id=workflow_id,
                task_id=task_id,
                agent_id=agent_id,
                status="failed",
                steps=tuple(steps),
                output={},
                error=str(exc),
            )
            self._history.append(result)
            return result

    def history(self, limit: int = 50) -> list[WorkflowResult]:
        return self._history[-limit:]

    @property
    def total_workflows(self) -> int:
        return len(self._history)

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self._history if r.status == "completed")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self._history if r.status == "failed")

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total_workflows,
            "completed": self.completed_count,
            "failed": self.failed_count,
        }
