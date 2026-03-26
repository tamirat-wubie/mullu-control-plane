"""Phase 208B — Traced Workflow Engine.

Purpose: Wraps AgentWorkflowEngine with automatic replay trace recording.
    Every workflow execution produces a ReplayTrace for deterministic
    re-execution and audit verification.
Governance scope: trace recording only — delegates all logic to workflow engine.
Dependencies: agent_workflow, execution_replay.
Invariants:
  - Every workflow step generates a replay frame.
  - Traces are completed even on failure.
  - Trace recording adds no observable side effects to workflow logic.
"""

from __future__ import annotations

from typing import Any, Callable

from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine, WorkflowResult
from mcoi_runtime.core.execution_replay import ReplayRecorder, ReplayTrace


class TracedWorkflowEngine:
    """Workflow engine with automatic replay trace recording."""

    def __init__(
        self,
        *,
        workflow_engine: AgentWorkflowEngine,
        replay_recorder: ReplayRecorder,
    ) -> None:
        self._engine = workflow_engine
        self._recorder = replay_recorder

    def execute(
        self,
        *,
        task_id: str,
        description: str,
        capability: AgentCapability,
        payload: dict[str, Any],
        tenant_id: str = "",
        budget_id: str = "default",
    ) -> tuple[WorkflowResult, ReplayTrace | None]:
        """Execute a workflow with automatic trace recording.

        Returns (workflow_result, replay_trace).
        Trace may be None if recording fails (non-fatal).
        """
        trace_id = f"trace-{task_id}"
        trace: ReplayTrace | None = None

        try:
            self._recorder.start_trace(trace_id)
        except Exception:
            # Trace start failed — run workflow without tracing
            result = self._engine.execute(
                task_id=task_id, description=description,
                capability=capability, payload=payload,
                tenant_id=tenant_id, budget_id=budget_id,
            )
            return result, None

        # Record input frame
        self._recorder.record_frame(
            trace_id, "workflow.input",
            input_data={
                "task_id": task_id,
                "description": description,
                "capability": capability.value,
                "tenant_id": tenant_id,
                "budget_id": budget_id,
            },
            output_data={"status": "submitted"},
        )

        # Execute workflow
        result = self._engine.execute(
            task_id=task_id, description=description,
            capability=capability, payload=payload,
            tenant_id=tenant_id, budget_id=budget_id,
        )

        # Record each step as a frame
        for step in result.steps:
            self._recorder.record_frame(
                trace_id, f"workflow.step.{step.step_name}",
                input_data={"step_name": step.step_name},
                output_data={"status": step.status, "detail": step.detail},
            )

        # Record output frame
        self._recorder.record_frame(
            trace_id, "workflow.output",
            input_data={"task_id": task_id},
            output_data={
                "status": result.status,
                "agent_id": result.agent_id,
                "workflow_id": result.workflow_id,
                "has_output": bool(result.output),
                "error": result.error,
            },
        )

        # Complete trace
        try:
            trace = self._recorder.complete_trace(trace_id)
        except Exception:
            pass

        return result, trace

    @property
    def workflow_engine(self) -> AgentWorkflowEngine:
        return self._engine

    @property
    def replay_recorder(self) -> ReplayRecorder:
        return self._recorder
