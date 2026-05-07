"""Purpose: typed lease and receipt contracts for sandboxed code workers.
Governance scope: lease identity, repository boundary, allowed paths, allowed
    commands, network/resource limits, command receipts, and sandbox evidence.
Dependencies: shared contract utilities, dataclasses, enum, hashlib, json, and
    typing.
Invariants:
  - Worker leases bind one tenant, repository, commit, path set, command set,
    timeout, memory limit, and expiry.
  - Paths are repository-relative POSIX strings; "." denotes workspace root.
  - Commands are argv tuples; shell strings are not accepted.
  - Receipts carry command/output hashes and sandbox receipt references.
  - Blocked commands still emit receipts with explicit violation reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_positive_int,
)


class CodeWorkerReceiptStatus(StrEnum):
    """Terminal status for one lease-bound code-worker command."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen_values = freeze_value(list(values))
    if not isinstance(frozen_values, tuple):
        raise ValueError(f"{field_name} must be a tuple of strings")
    for index, item in enumerate(frozen_values):
        require_non_empty_text(item, f"{field_name}[{index}]")
    return frozen_values


def _freeze_command_tuple(
    values: tuple[tuple[str, ...], ...],
    field_name: str,
) -> tuple[tuple[str, ...], ...]:
    frozen_commands: list[tuple[str, ...]] = []
    for index, command in enumerate(values):
        if not isinstance(command, tuple):
            raise ValueError(f"{field_name}[{index}] must be an argv tuple")
        normalized_command = _freeze_text_tuple(command, f"{field_name}[{index}]")
        if not normalized_command:
            raise ValueError(f"{field_name}[{index}] must contain at least one item")
        frozen_commands.append(normalized_command)
    return freeze_value(frozen_commands)


def _normalize_relative_path(path_text: str) -> str:
    normalized = require_non_empty_text(path_text, "path").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == ".":
        return "."
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("path must stay inside repository root")
    return normalized


def _freeze_path_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen_values = tuple(_normalize_relative_path(value) for value in values)
    if not frozen_values:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(sorted(set(frozen_values)))


@dataclass(frozen=True, slots=True)
class CodeWorkerLease(ContractRecord):
    """Authority lease for one sandboxed code-worker command family."""

    lease_id: str
    tenant_id: str
    repository: str
    commit_sha: str
    allowed_paths: tuple[str, ...]
    allowed_commands: tuple[tuple[str, ...], ...]
    network_enabled: bool = False
    timeout_seconds: int = 120
    memory_mb: int = 1024
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lease_id", require_non_empty_text(self.lease_id, "lease_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(self, "allowed_paths", _freeze_path_tuple(tuple(self.allowed_paths), "allowed_paths"))
        allowed_commands = _freeze_command_tuple(tuple(self.allowed_commands), "allowed_commands")
        if not allowed_commands:
            raise ValueError("allowed_commands must contain at least one command")
        object.__setattr__(self, "allowed_commands", allowed_commands)
        if not isinstance(self.network_enabled, bool):
            raise ValueError("network_enabled must be a bool")
        object.__setattr__(
            self,
            "timeout_seconds",
            require_positive_int(self.timeout_seconds, "timeout_seconds"),
        )
        object.__setattr__(self, "memory_mb", require_positive_int(self.memory_mb, "memory_mb"))
        object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CodeWorkerReceipt(ContractRecord):
    """Receipt for one lease-bound sandboxed code-worker command."""

    receipt_id: str
    lease_id: str
    command_id: str
    tenant_id: str
    repository: str
    commit_sha: str
    status: CodeWorkerReceiptStatus
    command_hash: str
    stdout_hash: str
    stderr_hash: str
    network_enabled: bool
    started_at: str
    finished_at: str
    returncode: int | None = None
    sandbox_receipt_id: str | None = None
    changed_file_refs: tuple[str, ...] = ()
    violation_reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "lease_id",
            "command_id",
            "tenant_id",
            "repository",
            "commit_sha",
            "command_hash",
            "stdout_hash",
            "stderr_hash",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, CodeWorkerReceiptStatus):
            raise ValueError("status must be a CodeWorkerReceiptStatus")
        if not isinstance(self.network_enabled, bool):
            raise ValueError("network_enabled must be a bool")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        if self.returncode is not None and not isinstance(self.returncode, int):
            raise ValueError("returncode must be an int when provided")
        if self.sandbox_receipt_id is not None:
            object.__setattr__(
                self,
                "sandbox_receipt_id",
                require_non_empty_text(self.sandbox_receipt_id, "sandbox_receipt_id"),
            )
        object.__setattr__(
            self,
            "changed_file_refs",
            _freeze_text_tuple(tuple(self.changed_file_refs), "changed_file_refs"),
        )
        object.__setattr__(
            self,
            "violation_reasons",
            _freeze_text_tuple(tuple(self.violation_reasons), "violation_reasons"),
        )
        evidence_refs = _freeze_text_tuple(tuple(self.evidence_refs), "evidence_refs")
        if not evidence_refs:
            raise ValueError("evidence_refs must contain at least one item")
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CodeWorkerCommandResult(ContractRecord):
    """Command output plus receipt returned by a sandboxed code worker."""

    status: CodeWorkerReceiptStatus
    stdout: str
    stderr: str
    receipt: CodeWorkerReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.status, CodeWorkerReceiptStatus):
            raise ValueError("status must be a CodeWorkerReceiptStatus")
        if not isinstance(self.stdout, str):
            raise ValueError("stdout must be a string")
        if not isinstance(self.stderr, str):
            raise ValueError("stderr must be a string")
        if not isinstance(self.receipt, CodeWorkerReceipt):
            raise ValueError("receipt must be a CodeWorkerReceipt")
