"""Purpose: verify shell command allowlist policy contracts, engine, and executor integration.
Governance scope: shell policy validation and enforcement tests only.
Dependencies: pytest, shell_policy contracts, shell_policy_engine, shell_executor adapter.
Invariants: denied commands never reach subprocess; absence of policy preserves original behavior.
"""

from __future__ import annotations

import subprocess

import pytest

from mcoi_runtime.contracts.shell_policy import ShellCommandPolicy, ShellPolicyVerdict
from mcoi_runtime.core.shell_policy_engine import ShellPolicyEngine
from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.adapters.shell_executor import ShellExecutor
from mcoi_runtime.contracts.execution import ExecutionOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basic_policy(**overrides: object) -> ShellCommandPolicy:
    defaults = dict(
        policy_id="test-policy",
        allowed_executables=("python3", "echo", "ls"),
        denied_patterns=(r"\brm\s+.*-\s*r\s*f\b",),
        max_argv_length=10,
        max_single_arg_bytes=256,
        allow_absolute_paths=False,
    )
    defaults.update(overrides)
    return ShellCommandPolicy(**defaults)


def _make_request(argv: tuple[str, ...]) -> ExecutionRequest:
    return ExecutionRequest(
        execution_id="exec-1",
        goal_id="goal-1",
        argv=argv,
        timeout_seconds=5,
    )


FIXED_CLOCK = lambda: "2026-03-26T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestShellCommandPolicyContract:
    def test_valid_construction(self) -> None:
        policy = _basic_policy()
        assert policy.policy_id == "test-policy"
        assert "python3" in policy.allowed_executables
        assert policy.max_argv_length == 10

    def test_empty_policy_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="policy_id"):
            _basic_policy(policy_id="  ")

    def test_empty_allowed_executables_rejected(self) -> None:
        with pytest.raises(ValueError, match="allowed_executables"):
            _basic_policy(allowed_executables=())

    def test_invalid_regex_denied_pattern_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^denied pattern must be a valid regex$") as exc_info:
            _basic_policy(denied_patterns=("[invalid",))
        assert "[invalid" not in str(exc_info.value)

    def test_blank_allowed_executable_entry_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^allowed executable entry must be a non-empty string$") as exc_info:
            _basic_policy(allowed_executables=("python3", ""))
        assert "[1]" not in str(exc_info.value)

    def test_blank_denied_pattern_entry_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^denied pattern entry must be a non-empty string$") as exc_info:
            _basic_policy(denied_patterns=("",))
        assert "[0]" not in str(exc_info.value)

    def test_frozen(self) -> None:
        policy = _basic_policy()
        with pytest.raises(AttributeError):
            policy.policy_id = "changed"


class TestShellPolicyVerdictContract:
    def test_valid_allow(self) -> None:
        v = ShellPolicyVerdict(verdict="allow", matched_rule="ok", argv_summary=("echo", "hi"))
        assert v.verdict == "allow"

    def test_invalid_verdict_rejected(self) -> None:
        with pytest.raises(ValueError, match="^verdict has unsupported value$") as exc_info:
            ShellPolicyVerdict(verdict="bogus", matched_rule="x")
        message = str(exc_info.value)
        assert "bogus" not in message
        assert "allow" not in message

    def test_argv_summary_truncated_to_three(self) -> None:
        v = ShellPolicyVerdict(
            verdict="allow",
            matched_rule="ok",
            argv_summary=("a", "b", "c", "d", "e"),
        )
        assert len(v.argv_summary) == 3


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------

class TestShellPolicyEngine:
    def test_allowed_passes(self) -> None:
        engine = ShellPolicyEngine(_basic_policy())
        verdict = engine.evaluate(("echo", "hello"))
        assert verdict.verdict == "allow"

    def test_denied_executable_blocked(self) -> None:
        engine = ShellPolicyEngine(_basic_policy())
        verdict = engine.evaluate(("curl", "http://example.com"))
        assert verdict.verdict == "deny_executable"
        assert "curl" in verdict.matched_rule

    def test_denied_pattern_blocked(self) -> None:
        engine = ShellPolicyEngine(_basic_policy(
            allowed_executables=("rm",),
            allow_absolute_paths=True,
        ))
        verdict = engine.evaluate(("rm", "-rf", "/"))
        assert verdict.verdict == "deny_pattern"

    def test_argv_too_long(self) -> None:
        engine = ShellPolicyEngine(_basic_policy(max_argv_length=3))
        argv = ("echo",) + tuple(f"arg{i}" for i in range(5))
        verdict = engine.evaluate(argv)
        assert verdict.verdict == "deny_argv_length"

    def test_arg_too_large(self) -> None:
        engine = ShellPolicyEngine(_basic_policy(max_single_arg_bytes=10))
        verdict = engine.evaluate(("echo", "x" * 100))
        assert verdict.verdict == "deny_arg_size"

    def test_absolute_path_denied(self) -> None:
        engine = ShellPolicyEngine(_basic_policy(allow_absolute_paths=False))
        verdict = engine.evaluate(("ls", "/etc/passwd"))
        assert verdict.verdict == "deny_absolute_path"

    def test_absolute_path_allowed_when_enabled(self) -> None:
        engine = ShellPolicyEngine(_basic_policy(allow_absolute_paths=True))
        verdict = engine.evaluate(("ls", "/etc"))
        assert verdict.verdict == "allow"


# ---------------------------------------------------------------------------
# Executor integration tests
# ---------------------------------------------------------------------------

class TestExecutorWithPolicy:
    def test_executor_with_policy_denies_before_running(self) -> None:
        """When policy denies, the runner must never be called."""
        runner_called = False

        def spy_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal runner_called
            runner_called = True
            return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

        policy = _basic_policy()
        engine = ShellPolicyEngine(policy)
        executor = ShellExecutor(
            runner=spy_runner,
            clock=FIXED_CLOCK,
            policy_engine=engine,
        )

        result = executor.execute(_make_request(("curl", "http://evil.example")))

        assert result.status is ExecutionOutcome.FAILED
        assert not runner_called, "runner was called despite policy denial"
        effect = result.actual_effects[0]
        assert effect.details["code"] == "policy_denied"

    def test_executor_with_policy_allows_valid_command(self) -> None:
        def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args[0], 0, stdout="hello", stderr="")

        policy = _basic_policy()
        engine = ShellPolicyEngine(policy)
        executor = ShellExecutor(
            runner=fake_runner,
            clock=FIXED_CLOCK,
            policy_engine=engine,
        )

        result = executor.execute(_make_request(("echo", "hello")))
        assert result.status is ExecutionOutcome.SUCCEEDED

    def test_executor_without_policy_unchanged(self) -> None:
        """Without a policy engine, all commands execute as before."""
        def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

        executor = ShellExecutor(
            runner=fake_runner,
            clock=FIXED_CLOCK,
            policy_engine=None,
        )

        # Even a 'dangerous' command goes through when no policy is set.
        result = executor.execute(_make_request(("curl", "http://example.com")))
        assert result.status is ExecutionOutcome.SUCCEEDED


# ---------------------------------------------------------------------------
# Default policy smoke tests
# ---------------------------------------------------------------------------

class TestDefaultPolicies:
    def test_builtin_policies_loadable(self) -> None:
        from mcoi_runtime.app.shell_policies import list_shell_policies, get_shell_policy

        policies = list_shell_policies()
        assert len(policies) >= 3
        assert get_shell_policy("shell-sandboxed") is not None
        assert get_shell_policy("shell-local-dev") is not None
        assert get_shell_policy("shell-pilot-prod") is not None

    def test_sandboxed_allows_echo(self) -> None:
        from mcoi_runtime.app.shell_policies import SANDBOXED

        engine = ShellPolicyEngine(SANDBOXED)
        assert engine.evaluate(("echo", "test")).verdict == "allow"

    def test_sandboxed_denies_curl(self) -> None:
        from mcoi_runtime.app.shell_policies import SANDBOXED

        engine = ShellPolicyEngine(SANDBOXED)
        assert engine.evaluate(("curl", "http://x")).verdict == "deny_executable"

    def test_pilot_prod_denies_grep(self) -> None:
        from mcoi_runtime.app.shell_policies import PILOT_PROD

        engine = ShellPolicyEngine(PILOT_PROD)
        assert engine.evaluate(("grep", "foo", "bar")).verdict == "deny_executable"

    def test_local_dev_allows_grep(self) -> None:
        from mcoi_runtime.app.shell_policies import LOCAL_DEV

        engine = ShellPolicyEngine(LOCAL_DEV)
        assert engine.evaluate(("grep", "foo", "bar")).verdict == "allow"
