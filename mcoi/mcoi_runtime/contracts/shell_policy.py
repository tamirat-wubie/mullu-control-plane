"""Purpose: shell command allowlist policy contracts for bounded execution.
Governance scope: shell policy validation and verdict typing only.
Dependencies: contract base, standard library dataclasses and typing.
Invariants:
  - Policies are frozen and immutable once constructed.
  - Verdicts capture the matched rule for audit without leaking full argv.
  - Denied patterns are compiled-safe regex strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_positive_int


@dataclass(frozen=True, slots=True)
class ShellCommandPolicy(ContractRecord):
    """Immutable allowlist policy for shell command execution."""

    policy_id: str
    allowed_executables: tuple[str, ...]
    denied_patterns: tuple[str, ...] = ()
    max_argv_length: int = 100
    max_single_arg_bytes: int = 65536
    allow_absolute_paths: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_id", require_non_empty_text(self.policy_id, "policy_id")
        )
        object.__setattr__(
            self,
            "allowed_executables",
            freeze_value(list(self.allowed_executables)),
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must contain at least one entry")
        for idx, exe in enumerate(self.allowed_executables):
            if not isinstance(exe, str) or not exe.strip():
                raise ValueError(
                    f"allowed_executables[{idx}] must be a non-empty string"
                )
        object.__setattr__(
            self, "denied_patterns", freeze_value(list(self.denied_patterns))
        )
        for idx, pat in enumerate(self.denied_patterns):
            if not isinstance(pat, str) or not pat.strip():
                raise ValueError(f"denied_patterns[{idx}] must be a non-empty string")
            try:
                re.compile(pat)
            except re.error as exc:
                raise ValueError(
                    f"denied_patterns[{idx}] is not a valid regex: {exc}"
                ) from exc
        object.__setattr__(
            self,
            "max_argv_length",
            require_positive_int(self.max_argv_length, "max_argv_length"),
        )
        object.__setattr__(
            self,
            "max_single_arg_bytes",
            require_positive_int(self.max_single_arg_bytes, "max_single_arg_bytes"),
        )
        if not isinstance(self.allow_absolute_paths, bool):
            raise ValueError("allow_absolute_paths must be a boolean")


@dataclass(frozen=True, slots=True)
class ShellPolicyVerdict(ContractRecord):
    """Result of evaluating an argv against a ShellCommandPolicy."""

    verdict: str
    matched_rule: str
    argv_summary: tuple[str, ...] = field(default_factory=tuple)

    _VALID_VERDICTS = frozenset(
        {
            "allow",
            "deny_executable",
            "deny_pattern",
            "deny_argv_length",
            "deny_arg_size",
            "deny_absolute_path",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "verdict", require_non_empty_text(self.verdict, "verdict")
        )
        if self.verdict not in self._VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(self._VALID_VERDICTS)}"
            )
        object.__setattr__(
            self, "matched_rule", require_non_empty_text(self.matched_rule, "matched_rule")
        )
        # Truncate argv_summary to first 3 elements for audit safety.
        summary = freeze_value(list(self.argv_summary))
        object.__setattr__(self, "argv_summary", summary[:3])
