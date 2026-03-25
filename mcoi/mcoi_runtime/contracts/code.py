"""Purpose: canonical code/repository automation contracts.
Governance scope: repository, workspace, patch, build, test, and review typing.
Dependencies: shared contract base helpers.
Invariants:
  - All file paths MUST be validated against workspace root before use.
  - Patches are typed and bounded — malformed patches fail closed.
  - Build/test results carry structured output, not raw strings only.
  - Code review records are explicit and attributable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_negative_int


class PatchStatus(StrEnum):
    APPLIED = "applied"
    FAILED = "failed"
    MALFORMED = "malformed"
    BLOCKED = "blocked"


class BuildStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class TestStatus(StrEnum):
    ALL_PASSED = "all_passed"
    SOME_FAILED = "some_failed"
    ALL_FAILED = "all_failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class ReviewVerdict(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class RepositoryDescriptor(ContractRecord):
    """Identity and metadata for a local code repository."""

    repo_id: str
    name: str
    root_path: str
    language_hints: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_id", require_non_empty_text(self.repo_id, "repo_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "root_path", require_non_empty_text(self.root_path, "root_path"))
        object.__setattr__(self, "language_hints", freeze_value(list(self.language_hints)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SourceFile(ContractRecord):
    """A typed reference to a source file with content hash."""

    file_path: str
    relative_path: str
    content_hash: str
    size_bytes: int
    line_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", require_non_empty_text(self.file_path, "file_path"))
        object.__setattr__(self, "relative_path", require_non_empty_text(self.relative_path, "relative_path"))
        object.__setattr__(self, "content_hash", require_non_empty_text(self.content_hash, "content_hash"))
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if not isinstance(self.line_count, int) or self.line_count < 0:
            raise ValueError("line_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class WorkspaceState(ContractRecord):
    """Snapshot of workspace file listing."""

    repo_id: str
    root_path: str
    files: tuple[SourceFile, ...] = ()
    total_files: int = 0
    total_bytes: int = 0
    captured_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_id", require_non_empty_text(self.repo_id, "repo_id"))
        object.__setattr__(self, "root_path", require_non_empty_text(self.root_path, "root_path"))
        object.__setattr__(self, "files", freeze_value(list(self.files)))
        object.__setattr__(self, "total_files", require_non_negative_int(self.total_files, "total_files"))
        object.__setattr__(self, "total_bytes", require_non_negative_int(self.total_bytes, "total_bytes"))
        if self.captured_at is not None:
            require_datetime_text(self.captured_at, "captured_at")


@dataclass(frozen=True, slots=True)
class PatchProposal(ContractRecord):
    """A unified diff patch proposal."""

    patch_id: str
    target_file: str
    description: str
    unified_diff: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "patch_id", require_non_empty_text(self.patch_id, "patch_id"))
        object.__setattr__(self, "target_file", require_non_empty_text(self.target_file, "target_file"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "unified_diff", require_non_empty_text(self.unified_diff, "unified_diff"))


@dataclass(frozen=True, slots=True)
class PatchApplicationResult(ContractRecord):
    """Result of applying a patch."""

    patch_id: str
    status: PatchStatus
    target_file: str
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "patch_id", require_non_empty_text(self.patch_id, "patch_id"))
        if not isinstance(self.status, PatchStatus):
            raise ValueError("status must be a PatchStatus value")
        object.__setattr__(self, "target_file", require_non_empty_text(self.target_file, "target_file"))

    @property
    def succeeded(self) -> bool:
        return self.status is PatchStatus.APPLIED


@dataclass(frozen=True, slots=True)
class BuildResult(ContractRecord):
    """Typed build command outcome."""

    build_id: str
    status: BuildStatus
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "build_id", require_non_empty_text(self.build_id, "build_id"))
        if not isinstance(self.status, BuildStatus):
            raise ValueError("status must be a BuildStatus value")
        object.__setattr__(self, "command", require_non_empty_text(self.command, "command"))
        object.__setattr__(self, "exit_code", require_non_negative_int(self.exit_code, "exit_code"))
        object.__setattr__(self, "duration_ms", require_non_negative_int(self.duration_ms, "duration_ms"))

    @property
    def succeeded(self) -> bool:
        return self.status is BuildStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class TestResult(ContractRecord):
    """Typed test command outcome with pass/fail/error counts."""

    test_id: str
    status: TestStatus
    command: str
    exit_code: int
    passed: int = 0
    failed: int = 0
    errors: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "test_id", require_non_empty_text(self.test_id, "test_id"))
        if not isinstance(self.status, TestStatus):
            raise ValueError("status must be a TestStatus value")
        object.__setattr__(self, "command", require_non_empty_text(self.command, "command"))
        object.__setattr__(self, "exit_code", require_non_negative_int(self.exit_code, "exit_code"))
        object.__setattr__(self, "passed", require_non_negative_int(self.passed, "passed"))
        object.__setattr__(self, "failed", require_non_negative_int(self.failed, "failed"))
        object.__setattr__(self, "errors", require_non_negative_int(self.errors, "errors"))
        object.__setattr__(self, "duration_ms", require_non_negative_int(self.duration_ms, "duration_ms"))

    @property
    def all_passed(self) -> bool:
        return self.status is TestStatus.ALL_PASSED


@dataclass(frozen=True, slots=True)
class CodeReviewRecord(ContractRecord):
    """Summary of a code review assessment."""

    review_id: str
    repo_id: str
    reviewer_id: str
    verdict: ReviewVerdict
    files_reviewed: tuple[str, ...]
    comments: tuple[str, ...] = ()
    reviewed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", require_non_empty_text(self.review_id, "review_id"))
        object.__setattr__(self, "repo_id", require_non_empty_text(self.repo_id, "repo_id"))
        object.__setattr__(self, "reviewer_id", require_non_empty_text(self.reviewer_id, "reviewer_id"))
        if not isinstance(self.verdict, ReviewVerdict):
            raise ValueError("verdict must be a ReviewVerdict value")
        object.__setattr__(self, "files_reviewed", freeze_value(list(self.files_reviewed)))
        object.__setattr__(self, "comments", freeze_value(list(self.comments)))
        if self.reviewed_at is not None:
            require_datetime_text(self.reviewed_at, "reviewed_at")
