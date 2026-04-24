"""Purpose: execute explicit argv-based shell requests for the MCOI runtime.
Governance scope: execution-slice shell adapter only.
Dependencies: Python subprocess, canonical execution contracts, executor-base typing, and optional shell policy engine.
Invariants: execution is argv-only, bounded by explicit input, policy-gated when engine is present, and free of retries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import subprocess
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.shell_execution import ShellExecutionReceipt

from .executor_base import ExecutionFailure, ExecutionRequest, build_execution_result, utc_now_text


Runner = Callable[..., subprocess.CompletedProcess[str]]

_DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
_TRUNCATION_MARKER: str = "\n[TRUNCATED at {limit} bytes]"


def _classify_spawn_exception(exc: OSError) -> str:
    """Return a bounded shell spawn failure message without OS detail leakage."""
    exc_type = type(exc).__name__
    if isinstance(exc, FileNotFoundError):
        return f"shell command not found ({exc_type})"
    if isinstance(exc, PermissionError):
        return f"shell access denied ({exc_type})"
    return f"shell spawn failed ({exc_type})"


def _truncate_output(text: str | None, max_bytes: int) -> str:
    """Truncate output to max_bytes, appending a marker if truncated."""
    if text is None:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
    return truncated + _TRUNCATION_MARKER.format(limit=max_bytes)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return _sha256_text(payload)


def _argv_summary(argv: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(argv[:3])


def _build_shell_receipt(
    *,
    request: ExecutionRequest,
    outcome: ExecutionOutcome,
    started_at: str,
    finished_at: str,
    stdout: str,
    stderr: str,
    returncode: int | None,
    policy_id: str | None,
    policy_verdict: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> ShellExecutionReceipt:
    command_hash = _sha256_json(
        {
            "argv": list(request.argv),
            "cwd": request.cwd,
            "environment_keys": sorted(request.environment),
            "timeout_seconds": request.timeout_seconds,
        }
    )
    receipt_material = {
        "execution_id": request.execution_id,
        "goal_id": request.goal_id,
        "outcome": outcome.value,
        "command_hash": command_hash,
        "returncode": returncode,
        "stdout_hash": _sha256_text(stdout),
        "stderr_hash": _sha256_text(stderr),
        "policy_id": policy_id,
        "policy_verdict": policy_verdict,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    receipt_hash = _sha256_json(receipt_material)
    return ShellExecutionReceipt(
        receipt_id=f"shell-receipt-{receipt_hash[:16]}",
        execution_id=request.execution_id,
        goal_id=request.goal_id,
        outcome=outcome,
        command_hash=command_hash,
        argv_summary=_argv_summary(request.argv),
        stdout_hash=receipt_material["stdout_hash"],
        stderr_hash=receipt_material["stderr_hash"],
        output_truncated=_TRUNCATION_MARKER.split("{", 1)[0].strip() in stdout
        or _TRUNCATION_MARKER.split("{", 1)[0].strip() in stderr,
        started_at=started_at,
        finished_at=finished_at,
        evidence_ref=f"shell-receipt:{request.execution_id}:{receipt_hash[:16]}",
        returncode=returncode,
        timeout_seconds=request.timeout_seconds,
        cwd_hash=_sha256_text(request.cwd) if request.cwd else None,
        environment_keys=tuple(sorted(request.environment)),
        policy_id=policy_id,
        policy_verdict=policy_verdict,
        metadata=dict(metadata or {}),
    )


def _build_shell_failure_result(
    *,
    request: ExecutionRequest,
    started_at: str,
    finished_at: str,
    failure: ExecutionFailure,
    effect_name: str,
    receipt: ShellExecutionReceipt,
    status: ExecutionOutcome = ExecutionOutcome.FAILED,
) -> ExecutionResult:
    receipt_payload = receipt.to_json_dict()
    return build_execution_result(
        execution_id=request.execution_id,
        goal_id=request.goal_id,
        status=status,
        actual_effects=(
            EffectRecord(
                name=effect_name,
                details={
                    "code": failure.code,
                    "message": failure.message,
                    "details": {**dict(failure.details), "receipt": receipt_payload},
                    "evidence_ref": receipt.evidence_ref,
                    "source": request.execution_id,
                    "observed_value": receipt_payload,
                },
            ),
        ),
        started_at=started_at,
        finished_at=finished_at,
        metadata={"adapter": "shell", "shell_receipt": receipt_payload},
    )


@dataclass(slots=True)
class ShellExecutor:
    runner: Runner = field(default=subprocess.run)
    clock: Callable[[], str] = field(default=utc_now_text)
    max_output_bytes: int = field(default=_DEFAULT_MAX_OUTPUT_BYTES)
    policy_engine: object | None = field(default=None)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started_at = self.clock()
        policy_id: str | None = None
        policy_verdict: str | None = None

        # --- Policy gate: deny before any subprocess activity ---
        if self.policy_engine is not None:
            from mcoi_runtime.core.shell_policy_engine import ShellPolicyEngine

            if isinstance(self.policy_engine, ShellPolicyEngine):
                verdict = self.policy_engine.evaluate(request.argv)
                policy_id = self.policy_engine.policy.policy_id
                policy_verdict = verdict.verdict
                if verdict.verdict != "allow":
                    finished_at = self.clock()
                    receipt = _build_shell_receipt(
                        request=request,
                        outcome=ExecutionOutcome.FAILED,
                        started_at=started_at,
                        finished_at=finished_at,
                        stdout="",
                        stderr="",
                        returncode=None,
                        policy_id=policy_id,
                        policy_verdict=policy_verdict,
                        metadata={"failure_code": "policy_denied"},
                    )
                    return _build_shell_failure_result(
                        request=request,
                        started_at=started_at,
                        finished_at=finished_at,
                        failure=ExecutionFailure(
                            code="policy_denied",
                            message="Shell policy denied",
                            details={
                                "verdict": verdict.verdict,
                                "matched_rule": verdict.matched_rule,
                                "argv_summary": list(verdict.argv_summary),
                            },
                        ),
                        effect_name="policy_denied",
                        receipt=receipt,
                    )

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
            stdout = _truncate_output(exc.output, self.max_output_bytes)
            stderr = _truncate_output(exc.stderr, self.max_output_bytes)
            receipt = _build_shell_receipt(
                request=request,
                outcome=ExecutionOutcome.CANCELLED,
                started_at=started_at,
                finished_at=finished_at,
                stdout=stdout,
                stderr=stderr,
                returncode=None,
                policy_id=policy_id,
                policy_verdict=policy_verdict,
                metadata={"failure_code": "timeout"},
            )
            return _build_shell_failure_result(
                request=request,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="timeout",
                    message="shell execution timed out",
                    details={
                        "argv": list(request.argv),
                        "timeout_seconds": request.timeout_seconds,
                        "stdout": stdout,
                        "stderr": stderr,
                    },
                ),
                effect_name="process_timed_out",
                receipt=receipt,
                status=ExecutionOutcome.CANCELLED,
            )
        except OSError as exc:
            finished_at = self.clock()
            receipt = _build_shell_receipt(
                request=request,
                outcome=ExecutionOutcome.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                stdout="",
                stderr="",
                returncode=None,
                policy_id=policy_id,
                policy_verdict=policy_verdict,
                metadata={"failure_code": "spawn_failed"},
            )
            return _build_shell_failure_result(
                request=request,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="spawn_failed",
                    message=_classify_spawn_exception(exc),
                    details={"argv": list(request.argv)},
                ),
                effect_name="process_start_failed",
                receipt=receipt,
            )

        finished_at = self.clock()
        stdout = _truncate_output(completed.stdout, self.max_output_bytes)
        stderr = _truncate_output(completed.stderr, self.max_output_bytes)
        status = ExecutionOutcome.SUCCEEDED if completed.returncode == 0 else ExecutionOutcome.FAILED
        effect_name = "process_completed" if status is ExecutionOutcome.SUCCEEDED else "process_failed"
        receipt = _build_shell_receipt(
            request=request,
            outcome=status,
            started_at=started_at,
            finished_at=finished_at,
            stdout=stdout,
            stderr=stderr,
            returncode=completed.returncode,
            policy_id=policy_id,
            policy_verdict=policy_verdict,
        )
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
                        "receipt": receipt.to_json_dict(),
                        "evidence_ref": receipt.evidence_ref,
                        "source": request.execution_id,
                        "observed_value": receipt.to_json_dict(),
                    },
                ),
            ),
            started_at=started_at,
            finished_at=finished_at,
            metadata={"adapter": "shell", "shell_receipt": receipt.to_json_dict()},
        )
