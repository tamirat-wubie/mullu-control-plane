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
from typing import cast

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_positive_int


def _freeze_string_array(
    values: tuple[str, ...] | list[str],
    field_name: str,
    *,
    require_non_empty_items: bool,
    empty_item_message: str | None = None,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[str, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        if require_non_empty_items:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(empty_item_message or f"{field_name}[{idx}] must be a non-empty string")
        elif not isinstance(value, str):
            raise ValueError(f"{field_name}[{idx}] must be a string")
    return frozen


@dataclass(frozen=True, slots=True)
class ShellCommandPolicy(ContractRecord):
    """Immutable allowlist policy for shell command execution."""

    policy_id: str
    allowed_executables: tuple[str, ...]
    denied_patterns: tuple[str, ...] = ()
    enabled: bool = True
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
            _freeze_string_array(
                self.allowed_executables,
                "allowed_executables",
                require_non_empty_items=True,
                empty_item_message="allowed executable entry must be a non-empty string",
            ),
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must contain at least one entry")
        object.__setattr__(
            self,
            "denied_patterns",
            _freeze_string_array(
                self.denied_patterns,
                "denied_patterns",
                require_non_empty_items=True,
                empty_item_message="denied pattern entry must be a non-empty string",
            ),
        )
        for pat in self.denied_patterns:
            try:
                re.compile(pat)
            except re.error as exc:
                raise ValueError("denied pattern must be a valid regex") from exc
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
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
            "deny_disabled",
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
            raise ValueError("verdict has unsupported value")
        object.__setattr__(
            self, "matched_rule", require_non_empty_text(self.matched_rule, "matched_rule")
        )
        # Truncate argv_summary to first 3 elements for audit safety.
        summary = _freeze_string_array(self.argv_summary, "argv_summary", require_non_empty_items=False)
        object.__setattr__(self, "argv_summary", summary[:3])
