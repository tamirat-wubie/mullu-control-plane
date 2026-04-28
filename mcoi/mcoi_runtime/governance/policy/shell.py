"""Purpose: pure-function shell command policy evaluation engine.
Governance scope: shell allowlist enforcement only.
Dependencies: shell_policy contracts, Python re module.
Invariants:
  - Evaluation is a pure function with no side effects.
  - Denied commands never reach execution.
  - Absolute-path detection uses os.sep-agnostic forward/back-slash check.
"""

from __future__ import annotations

import os
import re

from mcoi_runtime.contracts.shell_policy import ShellCommandPolicy, ShellPolicyVerdict


def _argv_summary(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Return at most the first 3 elements for audit logging."""
    return tuple(argv[:3])


class ShellPolicyEngine:
    """Stateless evaluator that checks argv against a ShellCommandPolicy."""

    __slots__ = ("_policy", "_denied_compiled")

    def __init__(self, policy: ShellCommandPolicy) -> None:
        self._policy = policy
        self._denied_compiled: tuple[re.Pattern[str], ...] = tuple(
            re.compile(p) for p in policy.denied_patterns
        )

    @property
    def policy(self) -> ShellCommandPolicy:
        return self._policy

    def evaluate(self, argv: tuple[str, ...]) -> ShellPolicyVerdict:
        """Evaluate *argv* against the loaded policy and return a verdict.

        Checks are applied in this order:
        1. policy enabled state
        2. argv length
        3. individual arg byte size
        4. absolute-path presence (when disallowed)
        5. executable allowlist
        6. denied regex patterns
        """
        summary = _argv_summary(argv)

        # 1. policy enabled state
        if not self._policy.enabled:
            return ShellPolicyVerdict(
                verdict="deny_disabled",
                matched_rule="shell execution disabled",
                argv_summary=summary,
            )

        # 2. argv length
        if len(argv) > self._policy.max_argv_length:
            return ShellPolicyVerdict(
                verdict="deny_argv_length",
                matched_rule=f"max_argv_length={self._policy.max_argv_length}",
                argv_summary=summary,
            )

        # 3. individual arg byte size
        for arg in argv:
            if len(arg.encode("utf-8", errors="replace")) > self._policy.max_single_arg_bytes:
                return ShellPolicyVerdict(
                    verdict="deny_arg_size",
                    matched_rule=f"max_single_arg_bytes={self._policy.max_single_arg_bytes}",
                    argv_summary=summary,
                )

        # 4. absolute-path check
        if not self._policy.allow_absolute_paths:
            for arg in argv[1:]:  # skip executable itself
                if arg.startswith("/") or arg.startswith("\\") or (
                    len(arg) >= 3 and arg[1] == ":" and arg[2] in ("/", "\\")
                ):
                    return ShellPolicyVerdict(
                        verdict="deny_absolute_path",
                        matched_rule="allow_absolute_paths=False",
                        argv_summary=summary,
                    )

        # 5. executable allowlist
        executable = os.path.basename(argv[0]) if argv else ""
        if executable not in self._policy.allowed_executables:
            return ShellPolicyVerdict(
                verdict="deny_executable",
                matched_rule=f"executable '{executable}' not in allowed_executables",
                argv_summary=summary,
            )

        # 6. denied patterns match against the full joined argv string.
        joined = " ".join(argv)
        for idx, pattern in enumerate(self._denied_compiled):
            if pattern.search(joined):
                return ShellPolicyVerdict(
                    verdict="deny_pattern",
                    matched_rule=f"denied_patterns[{idx}]: {self._policy.denied_patterns[idx]}",
                    argv_summary=summary,
                )

        return ShellPolicyVerdict(
            verdict="allow",
            matched_rule="all_checks_passed",
            argv_summary=summary,
        )
