"""Purpose: typed shell execution receipts for observed effect assurance.
Governance scope: shell command observation and reconciliation evidence only.
Dependencies: contract base, execution outcome typing, and Python dataclasses.
Invariants: receipts carry hashed command/output identity, bounded argv evidence, and explicit policy verdict state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)
from .execution import ExecutionOutcome


@dataclass(frozen=True, slots=True)
class ShellExecutionReceipt(ContractRecord):
    """Observed shell execution evidence suitable for effect reconciliation."""

    receipt_id: str
    execution_id: str
    goal_id: str
    outcome: ExecutionOutcome
    command_hash: str
    argv_summary: tuple[str, ...]
    stdout_hash: str
    stderr_hash: str
    output_truncated: bool
    started_at: str
    finished_at: str
    evidence_ref: str
    returncode: int | None = None
    timeout_seconds: float | None = None
    cwd_hash: str | None = None
    environment_keys: tuple[str, ...] = field(default_factory=tuple)
    policy_id: str | None = None
    policy_verdict: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "execution_id",
            "goal_id",
            "command_hash",
            "stdout_hash",
            "stderr_hash",
            "evidence_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.outcome, ExecutionOutcome):
            raise ValueError("outcome must be an ExecutionOutcome value")
        summary = freeze_value(list(self.argv_summary))
        if not isinstance(summary, tuple) or not summary:
            raise ValueError("argv_summary must contain at least one item")
        for item in summary:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("argv_summary items must be non-empty strings")
        object.__setattr__(self, "argv_summary", summary[:3])
        if not isinstance(self.output_truncated, bool):
            raise ValueError("output_truncated must be a boolean")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        if self.returncode is not None and not isinstance(self.returncode, int):
            raise ValueError("returncode must be an integer when provided")
        if self.timeout_seconds is not None:
            if not isinstance(self.timeout_seconds, (int, float)) or isinstance(self.timeout_seconds, bool):
                raise ValueError("timeout_seconds must be numeric when provided")
            if self.timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be greater than zero when provided")
        for optional_text in ("cwd_hash", "policy_id", "policy_verdict"):
            value = getattr(self, optional_text)
            if value is not None:
                object.__setattr__(self, optional_text, require_non_empty_text(value, optional_text))
        keys = freeze_value(sorted(self.environment_keys))
        for key in keys:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("environment_keys items must be non-empty strings")
        object.__setattr__(self, "environment_keys", keys)
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
