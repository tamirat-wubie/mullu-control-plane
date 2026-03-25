"""Purpose: execute explicit argv-based shell requests for the MCOI runtime.
Governance scope: execution-slice shell adapter only.
Dependencies: Python subprocess, canonical execution contracts, and executor-base typing.
Invariants: execution is argv-only, bounded by explicit input, and free of retries or policy logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
from typing import Callable

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult

from .executor_base import ExecutionFailure, ExecutionRequest, build_execution_result, build_failure_result, utc_now_text


Runner = Callable[..., subprocess.CompletedProcess[str]]

_DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
_TRUNCATION_MARKER: str = "\n[TRUNCATED at {limit} bytes]"


def _truncate_output(text: str | None, max_bytes: int) -> str:
    """Truncate output to max_bytes, appending a marker if truncated."""
    if text is None:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
    return truncated + _TRUNCATION_MARKER.format(limit=max_bytes)


@dataclass(slots=True)
class ShellExecutor:
    runner: Runner = field(default=subprocess.run)
    clock: Callable[[], str] = field(default=utc_now_text)
    max_output_bytes: int = field(default=_DEFAULT_MAX_OUTPUT_BYTES)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started_at = self.clock()

        try:
            completed = self.runner(
                list(request.argv),
                capture_output=True,
                check=False,
                cwd=request.cwd,
                env=dict(request.environment) if request.environment else None,
                shell=False,
                text=True,
                timeout=request.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=request.execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="timeout",
                    message="shell execution timed out",
                    details={
                        "argv": list(request.argv),
                        "timeout_seconds": request.timeout_seconds,
                        "stdout": _truncate_output(exc.output, self.max_output_bytes),
                        "stderr": _truncate_output(exc.stderr, self.max_output_bytes),
                    },
                ),
                effect_name="process_timed_out",
                status=ExecutionOutcome.CANCELLED,
                metadata={"adapter": "shell"},
            )
        except OSError as exc:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=request.execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="spawn_failed",
                    message=str(exc),
                    details={"argv": list(request.argv)},
                ),
                effect_name="process_start_failed",
                metadata={"adapter": "shell"},
            )

        finished_at = self.clock()
        stdout = _truncate_output(completed.stdout, self.max_output_bytes)
        stderr = _truncate_output(completed.stderr, self.max_output_bytes)
        status = ExecutionOutcome.SUCCEEDED if completed.returncode == 0 else ExecutionOutcome.FAILED
        effect_name = "process_completed" if status is ExecutionOutcome.SUCCEEDED else "process_failed"
        return build_execution_result(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=status,
            actual_effects=(
                EffectRecord(
                    name=effect_name,
                    details={
                        "argv": list(request.argv),
                        "returncode": completed.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                    },
                ),
            ),
            started_at=started_at,
            finished_at=finished_at,
            metadata={"adapter": "shell"},
        )
