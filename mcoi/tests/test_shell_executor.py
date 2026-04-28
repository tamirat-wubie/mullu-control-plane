"""Purpose: verify argv-only shell execution for the MCOI runtime.
Governance scope: execution-slice tests only.
Dependencies: pytest, subprocess helpers, and the execution-slice shell adapter.
Invariants: shell execution is explicit, captures output, and never uses shell=True or retries.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.adapters.shell_executor import ShellExecutor, ShellSandboxPolicy
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.shell_policy import ShellCommandPolicy
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.governance.policy.shell import ShellPolicyEngine


def test_shell_executor_runs_explicit_argv_without_shell_mode() -> None:
    captured: dict[str, object] = {}

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = args[0]
        captured["shell"] = kwargs["shell"]
        captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    executor = ShellExecutor(runner=fake_runner, clock=lambda: "2026-03-18T12:00:00+00:00")
    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-1",
            goal_id="goal-1",
            argv=("python", "-c", "print('ok')"),
            timeout_seconds=5,
        )
    )

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.actual_effects[0].details["stdout"] == "ok"
    receipt = result.actual_effects[0].details["receipt"]
    assert receipt["execution_id"] == "execution-1"
    assert receipt["outcome"] == "succeeded"
    assert receipt["returncode"] == 0
    assert receipt["stdout_hash"] != receipt["stderr_hash"]
    assert result.metadata["shell_receipt"]["receipt_id"] == receipt["receipt_id"]
    assert result.actual_effects[0].details["evidence_ref"] == receipt["evidence_ref"]
    assert captured["argv"] == ["python", "-c", "print('ok')"]
    assert captured["shell"] is False
    assert captured["timeout"] == 5


def test_shell_executor_maps_timeout_to_typed_cancellation() -> None:
    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    executor = ShellExecutor(runner=fake_runner, clock=lambda: "2026-03-18T12:00:00+00:00")
    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-2",
            goal_id="goal-2",
            argv=("python", "-c", "print('ok')"),
            timeout_seconds=0.1,
        )
    )

    assert result.status is ExecutionOutcome.CANCELLED
    assert result.actual_effects[0].name == "process_timed_out"
    assert result.actual_effects[0].details["code"] == "timeout"
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["outcome"] == "cancelled"
    assert receipt["returncode"] is None
    assert receipt["timeout_seconds"] == 0.1


def test_shell_executor_maps_nonzero_exit_to_failed_result() -> None:
    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 3, stdout="", stderr="failure")

    executor = ShellExecutor(runner=fake_runner, clock=lambda: "2026-03-18T12:00:00+00:00")
    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-3",
            goal_id="goal-3",
            argv=("python", "-c", "raise SystemExit(3)"),
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].name == "process_failed"
    assert result.actual_effects[0].details["returncode"] == 3
    assert result.actual_effects[0].details["stderr"] == "failure"
    receipt = result.actual_effects[0].details["receipt"]
    assert receipt["outcome"] == "failed"
    assert receipt["returncode"] == 3
    assert receipt["stderr_hash"] != receipt["stdout_hash"]


def test_shell_executor_sanitizes_spawn_failure() -> None:
    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("secret executable path")

    executor = ShellExecutor(runner=fake_runner, clock=lambda: "2026-03-18T12:00:00+00:00")
    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-4",
            goal_id="goal-4",
            argv=("missing-tool", "--flag"),
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].details["code"] == "spawn_failed"
    assert result.actual_effects[0].details["message"] == "shell command not found (FileNotFoundError)"
    assert "secret executable path" not in result.actual_effects[0].details["message"]
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["outcome"] == "failed"
    assert receipt["returncode"] is None
    assert receipt["evidence_ref"].startswith("shell-receipt:execution-4:")


def test_execution_request_bounds_invalid_argv_items() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="^argv items must be non-empty strings$") as exc_info:
        ExecutionRequest(
            execution_id="execution-5",
            goal_id="goal-5",
            argv=("python", " ", "print('ok')"),
        )

    message = str(exc_info.value)
    assert message == "argv items must be non-empty strings"
    assert "[1]" not in message
    assert "argv items" in message


def test_shell_executor_bounds_policy_denial_message() -> None:
    executor = ShellExecutor(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        policy_engine=ShellPolicyEngine(
            ShellCommandPolicy(
                policy_id="policy-1",
                allowed_executables=("echo",),
            )
        ),
    )

    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-6",
            goal_id="goal-6",
            argv=("python", "-c", "print('ok')"),
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].details["code"] == "policy_denied"
    assert result.actual_effects[0].details["message"] == "Shell policy denied"
    assert "deny_executable" not in result.actual_effects[0].details["message"]
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["policy_id"] == "policy-1"
    assert receipt["policy_verdict"] == "deny_executable"
    assert receipt["outcome"] == "failed"


def test_shell_executor_sandbox_denies_missing_required_cwd() -> None:
    executor = ShellExecutor(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        sandbox_policy=ShellSandboxPolicy(
            sandbox_id="sandbox-1",
            require_cwd=True,
        ),
    )

    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-sandbox-1",
            goal_id="goal-sandbox-1",
            argv=("echo", "blocked"),
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].name == "sandbox_denied"
    assert result.actual_effects[0].details["code"] == "sandbox_denied"
    assert result.actual_effects[0].details["details"]["reason"] == "cwd_required"
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["metadata"]["sandbox_id"] == "sandbox-1"
    assert receipt["metadata"]["failure_code"] == "sandbox_denied"
    assert receipt["metadata"]["environment_isolated"] is True


def test_shell_executor_sandbox_denies_cwd_outside_allowed_root(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    blocked_root = tmp_path / "blocked"
    allowed_root.mkdir()
    blocked_root.mkdir()
    executor = ShellExecutor(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        sandbox_policy=ShellSandboxPolicy(
            sandbox_id="sandbox-2",
            allowed_cwd_roots=(str(allowed_root),),
            require_cwd=True,
        ),
    )

    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-sandbox-2",
            goal_id="goal-sandbox-2",
            argv=("echo", "blocked"),
            cwd=str(blocked_root),
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].name == "sandbox_denied"
    assert result.actual_effects[0].details["code"] == "sandbox_denied"
    assert result.actual_effects[0].details["details"]["reason"] == "cwd_outside_allowed_roots"
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["metadata"]["cwd_root_enforced"] is True
    assert receipt["metadata"]["sandbox_id"] == "sandbox-2"
    assert receipt["outcome"] == "failed"


def test_shell_executor_sandbox_passes_isolated_environment(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    captured: dict[str, object] = {}

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        captured["shell"] = kwargs["shell"]
        return subprocess.CompletedProcess(args[0], 0, stdout="sandboxed", stderr="")

    executor = ShellExecutor(
        runner=fake_runner,
        clock=lambda: "2026-03-18T12:00:00+00:00",
        sandbox_policy=ShellSandboxPolicy(
            sandbox_id="sandbox-3",
            allowed_cwd_roots=(str(allowed_root),),
            allowed_environment_keys=("MULLU_TRACE_ID",),
            require_cwd=True,
        ),
    )

    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-sandbox-3",
            goal_id="goal-sandbox-3",
            argv=("echo", "allowed"),
            cwd=str(allowed_root),
            environment={"MULLU_TRACE_ID": "trace-1"},
        )
    )

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.actual_effects[0].details["stdout"] == "sandboxed"
    assert captured["cwd"] == str(allowed_root)
    assert captured["env"] == {"MULLU_TRACE_ID": "trace-1"}
    assert captured["shell"] is False
    receipt = result.actual_effects[0].details["receipt"]
    assert receipt["metadata"]["sandbox_id"] == "sandbox-3"
    assert receipt["metadata"]["environment_isolated"] is True
    assert receipt["metadata"]["allowed_environment_keys"] == ("MULLU_TRACE_ID",)


def test_shell_executor_sandbox_rejects_unapproved_environment_key(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    executor = ShellExecutor(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        sandbox_policy=ShellSandboxPolicy(
            sandbox_id="sandbox-4",
            allowed_cwd_roots=(str(allowed_root),),
            allowed_environment_keys=("MULLU_TRACE_ID",),
            require_cwd=True,
        ),
    )

    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-sandbox-4",
            goal_id="goal-sandbox-4",
            argv=("echo", "blocked"),
            cwd=str(allowed_root),
            environment={"SECRET_TOKEN": "blocked"},
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].name == "sandbox_denied"
    assert result.actual_effects[0].details["code"] == "sandbox_denied"
    assert result.actual_effects[0].details["details"]["reason"] == "environment_key_not_allowed"
    assert result.actual_effects[0].details["details"]["environment_keys"] == ("SECRET_TOKEN",)
    receipt = result.actual_effects[0].details["details"]["receipt"]
    assert receipt["metadata"]["allowed_environment_keys"] == ("MULLU_TRACE_ID",)
    assert receipt["metadata"]["environment_isolated"] is True


def test_shell_receipt_becomes_effect_assurance_evidence_ref() -> None:
    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, stdout="observed", stderr="")

    executor = ShellExecutor(runner=fake_runner, clock=lambda: "2026-03-18T12:00:00+00:00")
    result = executor.execute(
        ExecutionRequest(
            execution_id="execution-7",
            goal_id="goal-7",
            argv=("echo", "observed"),
        )
    )

    observed = EffectAssuranceGate(clock=lambda: "2026-03-18T12:00:01+00:00").observe(result)
    receipt = result.metadata["shell_receipt"]
    assert observed[0].evidence_ref == receipt["evidence_ref"]
    assert observed[0].observed_value["receipt_id"] == receipt["receipt_id"]
    assert observed[0].source == "execution-7"
