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

from typing import Any

from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine, WorkflowResult
from mcoi_runtime.core.execution_replay import ReplayRecorder, ReplayTrace


def _bounded_trace_recording_error(exc: Exception) -> str:
    """Return a stable trace-recording failure reason without raw detail."""
    return f"trace recording failed ({type(exc).__name__})"


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
        self._trace_recording_failures = 0
        self._last_trace_recording_error = ""

    @property
    def trace_recording_failures(self) -> int:
        """Return contained trace-recording failure count."""
        return self._trace_recording_failures

    @property
    def last_trace_recording_error(self) -> str:
        """Return the latest bounded trace-recording failure reason."""
        return self._last_trace_recording_error

    def _record_trace_failure(self, exc: Exception, *, trace_id: str = "") -> None:
        """Record a bounded trace failure and discard any partial trace."""
        self._trace_recording_failures += 1
        self._last_trace_recording_error = _bounded_trace_recording_error(exc)
        if trace_id:
            self._discard_trace(trace_id)

    def _discard_trace(self, trace_id: str) -> None:
        """Best-effort cleanup for partial traces after recording failure."""
        discard = getattr(self._recorder, "discard_trace", None)
        if callable(discard):
            try:
                discard(trace_id)
            except Exception as exc:
                self._trace_recording_failures += 1
                self._last_trace_recording_error = _bounded_trace_recording_error(exc)

    def _record_frame(
        self,
        trace_id: str,
        operation: str,
        *,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> bool:
        """Record one replay frame; contain recorder failures."""
        try:
            self._recorder.record_frame(
                trace_id,
                operation,
                input_data=input_data,
                output_data=output_data,
            )
            return True
        except Exception as exc:
            self._record_trace_failure(exc, trace_id=trace_id)
            return False

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
        except Exception as exc:
            self._record_trace_failure(exc)
            # Trace start failed — run workflow without tracing
            result = self._engine.execute(
                task_id=task_id, description=description,
                capability=capability, payload=payload,
                tenant_id=tenant_id, budget_id=budget_id,
            )
            return result, None

        # Record input frame
        if not self._record_frame(
            trace_id, "workflow.input",
            input_data={
                "task_id": task_id,
                "description": description,
                "capability": capability.value,
                "tenant_id": tenant_id,
                "budget_id": budget_id,
            },
            output_data={"status": "submitted"},
        ):
            result = self._engine.execute(
                task_id=task_id, description=description,
                capability=capability, payload=payload,
                tenant_id=tenant_id, budget_id=budget_id,
            )
            return result, None

        # Execute workflow
        result = self._engine.execute(
            task_id=task_id, description=description,
            capability=capability, payload=payload,
            tenant_id=tenant_id, budget_id=budget_id,
        )

        # Record each step as a frame
        for step in result.steps:
            if not self._record_frame(
                trace_id, f"workflow.step.{step.step_name}",
                input_data={"step_name": step.step_name},
                output_data={"status": step.status, "detail": step.detail},
            ):
                return result, None

        # Record output frame
        if not self._record_frame(
            trace_id, "workflow.output",
            input_data={"task_id": task_id},
            output_data={
                "status": result.status,
                "agent_id": result.agent_id,
                "workflow_id": result.workflow_id,
                "has_output": bool(result.output),
                "error": result.error,
            },
        ):
            return result, None

        # Complete trace
        try:
            trace = self._recorder.complete_trace(trace_id)
        except Exception as exc:
            self._record_trace_failure(exc, trace_id=trace_id)

        return result, trace

    @property
    def workflow_engine(self) -> AgentWorkflowEngine:
        return self._engine

    @property
    def replay_recorder(self) -> ReplayRecorder:
        return self._recorder
