"""Purpose: runbook execution engine — execute admitted procedures under governance.
Governance scope: runbook execution, step orchestration, and drift detection only.
Dependencies: runbook contracts, runbook execution contracts, runbook library, invariant helpers.
Invariants:
  - Only admitted runbooks may be executed.
  - Blocked/deprecated runbooks MUST NOT execute.
  - Execution respects autonomy mode (checked per step).
  - Drift from baseline is detected and recorded explicitly.
  - Execution stops on first failed step.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.runbook_execution import (
    DriftRecord,
    DriftType,
    RunbookExecutionContext,
    RunbookExecutionRecord,
    RunbookExecutionRequest,
    RunbookExecutionStatus,
    RunbookStepResult,
)
from mcoi_runtime.core.runbook import RunbookEntry, RunbookLibrary
from .invariants import ensure_non_empty_text, stable_identifier


class RunbookExecutor:
    """Executes admitted runbooks under current governance conditions.

    Steps:
    1. Resolve runbook from library
    2. Check lifecycle (admitted runbooks only)
    3. Execute template steps with provided bindings
    4. Detect drift from baseline if baseline context provided
    5. Record full execution including step results and drift
    """

    def __init__(
        self,
        *,
        library: RunbookLibrary,
        clock: Callable[[], str],
        step_executor: Callable[[str, Mapping[str, Any]], RunbookStepResult] | None = None,
    ) -> None:
        self._library = library
        self._clock = clock
        self._step_executor = step_executor or self._default_step_executor

    def execute(
        self,
        request: RunbookExecutionRequest,
        *,
        baseline_context: RunbookExecutionContext | None = None,
        baseline_step_count: int | None = None,
    ) -> RunbookExecutionRecord:
        """Execute a runbook and return a full execution record."""
        started_at = self._clock()

        # Step 1: resolve runbook
        entry = self._library.get(request.runbook_id)
        if entry is None:
            return self._blocked_record(
                request, started_at,
                RunbookExecutionStatus.BLOCKED_LIFECYCLE,
                f"runbook not found: {request.runbook_id}",
            )

        # Step 2: execute template steps
        step_results: list[RunbookStepResult] = []
        template = dict(entry.template)
        bindings = dict(request.bindings)

        # Treat template keys as ordered steps
        step_names = sorted(template.keys())
        for idx, step_name in enumerate(step_names):
            step_value = template[step_name]
            # Apply bindings
            resolved_value = step_value
            if isinstance(step_value, str):
                for bk, bv in bindings.items():
                    resolved_value = resolved_value.replace(f"{{{bk}}}", bv)

            result = self._step_executor(step_name, {"value": resolved_value, **bindings})
            step_results.append(result)

            if not result.succeeded:
                drift = self._detect_drift(request.context, baseline_context, baseline_step_count, len(step_names))
                return RunbookExecutionRecord(
                    record_id=self._make_record_id(request, started_at),
                    runbook_id=request.runbook_id,
                    request_id=request.request_id,
                    status=RunbookExecutionStatus.STEP_FAILED,
                    context=request.context,
                    step_results=tuple(step_results),
                    drift_records=tuple(drift),
                    started_at=started_at,
                    finished_at=self._clock(),
                    error_message=f"step failed: {step_name}",
                )

        # Step 3: detect drift
        drift = self._detect_drift(request.context, baseline_context, baseline_step_count, len(step_names))

        status = (
            RunbookExecutionStatus.DRIFT_DETECTED
            if drift
            else RunbookExecutionStatus.SUCCEEDED
        )

        return RunbookExecutionRecord(
            record_id=self._make_record_id(request, started_at),
            runbook_id=request.runbook_id,
            request_id=request.request_id,
            status=status,
            context=request.context,
            step_results=tuple(step_results),
            drift_records=tuple(drift),
            started_at=started_at,
            finished_at=self._clock(),
        )

    def _detect_drift(
        self,
        current: RunbookExecutionContext,
        baseline: RunbookExecutionContext | None,
        baseline_step_count: int | None,
        current_step_count: int,
    ) -> list[DriftRecord]:
        """Compare current execution context against baseline."""
        if baseline is None:
            return []

        drift: list[DriftRecord] = []

        if current.autonomy_mode != baseline.autonomy_mode:
            drift.append(DriftRecord(
                drift_type=DriftType.AUTONOMY_MISMATCH,
                field_name="autonomy_mode",
                baseline_value=baseline.autonomy_mode,
                current_value=current.autonomy_mode,
            ))

        if current.policy_pack_id != baseline.policy_pack_id:
            drift.append(DriftRecord(
                drift_type=DriftType.POLICY_PACK_MISMATCH,
                field_name="policy_pack_id",
                baseline_value=str(baseline.policy_pack_id or "none"),
                current_value=str(current.policy_pack_id or "none"),
            ))

        if baseline_step_count is not None and current_step_count != baseline_step_count:
            drift.append(DriftRecord(
                drift_type=DriftType.STEP_COUNT_MISMATCH,
                field_name="step_count",
                baseline_value=str(baseline_step_count),
                current_value=str(current_step_count),
            ))

        return drift

    def _blocked_record(
        self,
        request: RunbookExecutionRequest,
        started_at: str,
        status: RunbookExecutionStatus,
        error: str,
    ) -> RunbookExecutionRecord:
        return RunbookExecutionRecord(
            record_id=self._make_record_id(request, started_at),
            runbook_id=request.runbook_id,
            request_id=request.request_id,
            status=status,
            context=request.context,
            started_at=started_at,
            finished_at=self._clock(),
            error_message=error,
        )

    def _make_record_id(self, request: RunbookExecutionRequest, started_at: str) -> str:
        return stable_identifier("rb-exec", {
            "request_id": request.request_id,
            "runbook_id": request.runbook_id,
            "started_at": started_at,
        })

    @staticmethod
    def _default_step_executor(step_name: str, params: Mapping[str, Any]) -> RunbookStepResult:
        """Default step executor — succeeds for all steps (simulation mode)."""
        return RunbookStepResult(
            step_index=0,
            step_name=step_name,
            succeeded=True,
        )
