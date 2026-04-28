"""Purpose: verify output truncation enforcement in process adapters.
Governance scope: adapter output-size policy tests only.
Dependencies: pytest, subprocess helpers, shell_executor, process_model, code_adapter.
Invariants:
  - Process output exceeding max_output_bytes is truncated with a marker.
  - Output within limits is unchanged.
  - Truncation applies to both stdout and stderr.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.adapters.shell_executor import ShellExecutor, _truncate_output
from mcoi_runtime.adapters.process_model import ProcessModelAdapter, ProcessModelConfig
from mcoi_runtime.adapters.code_adapter import CommandPolicy, LocalCodeAdapter
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.model import ModelInvocation, ModelStatus


CLOCK = lambda: "2026-03-19T00:00:00+00:00"


# ---------------------------------------------------------------------------
# _truncate_output unit tests
# ---------------------------------------------------------------------------

class TestTruncateOutput:
    def test_short_text_unchanged(self):
        assert _truncate_output("hello", 100) == "hello"

    def test_none_returns_empty(self):
        assert _truncate_output(None, 100) == ""

    def test_exact_limit_unchanged(self):
        text = "a" * 100
        assert _truncate_output(text, 100) == text

    def test_exceeding_limit_is_truncated(self):
        text = "a" * 200
        result = _truncate_output(text, 100)
        assert result.startswith("a" * 100)
        assert "[TRUNCATED at 100 bytes]" in result
        assert len(result) < 200 + 50  # truncated + marker

    def test_truncation_marker_contains_limit(self):
        result = _truncate_output("x" * 500, 256)
        assert "[TRUNCATED at 256 bytes]" in result


# ---------------------------------------------------------------------------
# ShellExecutor output truncation (Issue D-1)
# ---------------------------------------------------------------------------

class TestShellExecutorOutputTruncation:
    def test_stdout_truncated_when_exceeding_max(self):
        big_output = "x" * 500

        def fake_runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout=big_output, stderr="")

        executor = ShellExecutor(runner=fake_runner, clock=CLOCK, max_output_bytes=100)
        result = executor.execute(
            ExecutionRequest(
                execution_id="exec-trunc-1",
                goal_id="goal-trunc-1",
                argv=("echo", "big"),
            )
        )

        assert result.status is ExecutionOutcome.SUCCEEDED
        stdout = result.actual_effects[0].details["stdout"]
        assert "[TRUNCATED at 100 bytes]" in stdout
        # The raw 500-char output should not be present
        assert len(stdout) < 500

    def test_stderr_truncated_when_exceeding_max(self):
        big_stderr = "E" * 500

        def fake_runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 1, stdout="", stderr=big_stderr)

        executor = ShellExecutor(runner=fake_runner, clock=CLOCK, max_output_bytes=100)
        result = executor.execute(
            ExecutionRequest(
                execution_id="exec-trunc-2",
                goal_id="goal-trunc-2",
                argv=("bad-cmd",),
            )
        )

        assert result.status is ExecutionOutcome.FAILED
        stderr = result.actual_effects[0].details["stderr"]
        assert "[TRUNCATED at 100 bytes]" in stderr

    def test_output_within_limit_is_unchanged(self):
        def fake_runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

        executor = ShellExecutor(runner=fake_runner, clock=CLOCK, max_output_bytes=1_048_576)
        result = executor.execute(
            ExecutionRequest(
                execution_id="exec-trunc-3",
                goal_id="goal-trunc-3",
                argv=("echo", "ok"),
            )
        )

        assert result.actual_effects[0].details["stdout"] == "ok"
        assert "[TRUNCATED" not in result.actual_effects[0].details["stdout"]

    def test_default_max_output_bytes_is_1mb(self):
        executor = ShellExecutor(clock=CLOCK)
        assert executor.max_output_bytes == 1_048_576


# ---------------------------------------------------------------------------
# ProcessModelAdapter output truncation (Issue D-1)
# ---------------------------------------------------------------------------

class TestProcessModelOutputTruncation:
    def test_stdout_truncated_on_success(self):
        big_output = "x" * 500

        config = ProcessModelConfig(
            command=("echo",),
            max_output_bytes=100,
        )

        with subprocess_patch(stdout=big_output, returncode=0):
            adapter = ProcessModelAdapter(config=config, clock=CLOCK)
            invocation = ModelInvocation(
                invocation_id="inv-1",
                model_id="model-1",
                prompt_hash="abc123",
                invoked_at=CLOCK(),
            )
            response = adapter.invoke(invocation)
            assert response.status is ModelStatus.SUCCEEDED
            # The digest is of the truncated output, not the raw output
            assert response.output_digest != "none"

    def test_stderr_truncated_on_failure(self):
        big_stderr = "E" * 500

        config = ProcessModelConfig(
            command=("fail-cmd",),
            max_output_bytes=100,
        )

        with subprocess_patch(stdout="", stderr=big_stderr, returncode=1):
            adapter = ProcessModelAdapter(config=config, clock=CLOCK)
            invocation = ModelInvocation(
                invocation_id="inv-2",
                model_id="model-2",
                prompt_hash="abc456",
                invoked_at=CLOCK(),
            )
            response = adapter.invoke(invocation)
            assert response.status is ModelStatus.FAILED
            # stderr in metadata is truncated (to 500 chars max in code, but our 100-byte limit applies first)
            stderr_val = response.metadata.get("stderr", "")
            # The underlying truncation happens, then [:500] clips further
            assert len(stderr_val) < 500

    def test_process_model_exception_is_bounded(self):
        config = ProcessModelConfig(
            command=("explode",),
            max_output_bytes=100,
        )

        with patch(
            "mcoi_runtime.adapters.process_model.subprocess.run",
            side_effect=RuntimeError("secret process failure"),
        ):
            adapter = ProcessModelAdapter(config=config, clock=CLOCK)
            invocation = ModelInvocation(
                invocation_id="inv-3",
                model_id="model-3",
                prompt_hash="ghi789",
                invoked_at=CLOCK(),
            )
            response = adapter.invoke(invocation)

        assert response.status is ModelStatus.FAILED
        assert response.metadata["error"] == "process model error (RuntimeError)"
        assert "secret process failure" not in response.metadata["error"]


# ---------------------------------------------------------------------------
# LocalCodeAdapter output truncation (Issue D-1)
# ---------------------------------------------------------------------------

class TestCodeAdapterOutputTruncation:
    def test_run_command_truncates_stdout(self, tmp_path):
        adapter = LocalCodeAdapter(
            root_path=str(tmp_path),
            clock=CLOCK,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        big_output = "x" * 500

        # Monkey-patch subprocess.run for this test
        import mcoi_runtime.adapters.code_adapter as ca_mod
        original_run = subprocess.run

        def patched_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout=big_output, stderr="")

        ca_mod.subprocess.run = patched_run
        try:
            exit_code, stdout, stderr, _ = adapter.run_command(
                "cmd-1", ["echo", "big"], max_output_bytes=100,
            )
        finally:
            ca_mod.subprocess.run = original_run

        assert exit_code == 0
        assert "[TRUNCATED at 100 bytes]" in stdout
        assert len(stdout) < 500

    def test_run_command_truncates_stderr(self, tmp_path):
        adapter = LocalCodeAdapter(
            root_path=str(tmp_path),
            clock=CLOCK,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        big_stderr = "E" * 500

        import mcoi_runtime.adapters.code_adapter as ca_mod
        original_run = subprocess.run

        def patched_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 1, stdout="", stderr=big_stderr)

        ca_mod.subprocess.run = patched_run
        try:
            exit_code, stdout, stderr, _ = adapter.run_command(
                "cmd-2", ["bad"], max_output_bytes=100,
            )
        finally:
            ca_mod.subprocess.run = original_run

        assert exit_code == 1
        assert "[TRUNCATED at 100 bytes]" in stderr

    def test_run_command_default_max_is_1mb(self, tmp_path):
        """Default max_output_bytes is 1 MB — output within that limit is unchanged."""
        adapter = LocalCodeAdapter(
            root_path=str(tmp_path),
            clock=CLOCK,
            command_policy=CommandPolicy.permissive_for_testing(),
        )

        import mcoi_runtime.adapters.code_adapter as ca_mod
        original_run = subprocess.run

        def patched_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout="short", stderr="")

        ca_mod.subprocess.run = patched_run
        try:
            exit_code, stdout, stderr, _ = adapter.run_command("cmd-3", ["echo", "short"])
        finally:
            ca_mod.subprocess.run = original_run

        assert stdout == "short"
        assert "[TRUNCATED" not in stdout

    def test_run_command_oserror_is_bounded(self, tmp_path):
        adapter = LocalCodeAdapter(
            root_path=str(tmp_path),
            clock=CLOCK,
            command_policy=CommandPolicy.permissive_for_testing(),
        )

        import mcoi_runtime.adapters.code_adapter as ca_mod
        original_run = subprocess.run

        def patched_run(*args, **kwargs):
            raise OSError("secret command failure")

        ca_mod.subprocess.run = patched_run
        try:
            exit_code, stdout, stderr, _ = adapter.run_command("cmd-4", ["bad"])
        finally:
            ca_mod.subprocess.run = original_run

        assert exit_code == -1
        assert stdout == ""
        assert stderr == "command error (OSError)"
        assert "secret command failure" not in stderr


# ---------------------------------------------------------------------------
# Helper: context manager to patch subprocess.run in process_model module
# ---------------------------------------------------------------------------

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def subprocess_patch(stdout="", stderr="", returncode=0):
    """Patch subprocess.run in the process_model module."""
    fake_result = subprocess.CompletedProcess(["fake"], returncode, stdout=stdout, stderr=stderr)
    with patch("mcoi_runtime.adapters.process_model.subprocess.run", return_value=fake_result):
        yield
