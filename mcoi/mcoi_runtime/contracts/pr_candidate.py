"""Purpose: pull-request candidate contracts for governed software changes.
Governance scope: local branch candidates, local commit candidates, review
    packets, approval-gated GitHub open intents, and evidence references.
Dependencies: dataclasses, enum, pathlib, typing, and shared contract helpers.
Invariants:
  - Local git commands never include push, pull, fetch, clone, remote,
    submodule, or credential operations.
  - Pull-request open intent is effect-bearing and cannot execute by default.
  - Review approval is required before a GitHub PR-open intent may execute.
  - Candidate bundles are planning receipts only; they do not run git or GitHub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class PullRequestCandidateStatus(StrEnum):
    """Lifecycle state for a pull-request candidate bundle."""

    DRAFT = "draft"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED_FOR_OPEN = "approved_for_open"
    BLOCKED = "blocked"


_DENIED_LOCAL_GIT_SUBCOMMANDS = frozenset({"push", "pull", "fetch", "clone", "remote", "submodule", "credential"})


@dataclass(frozen=True, slots=True)
class LocalGitCommandCandidate(ContractRecord):
    """One local git command candidate that may be run by a governed worker."""

    command_id: str
    purpose: str
    command: tuple[str, ...]
    requires_clean_worktree: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_id", require_non_empty_text(self.command_id, "command_id"))
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        command = _normalize_text_tuple(tuple(self.command), "command")
        if not command or command[0] != "git":
            raise ValueError("local_git_command_must_start_with_git")
        subcommand = _git_subcommand(command)
        if subcommand in _DENIED_LOCAL_GIT_SUBCOMMANDS:
            raise ValueError(f"denied_local_git_subcommand:{subcommand}")
        if not isinstance(self.requires_clean_worktree, bool):
            raise ValueError("requires_clean_worktree must be a bool")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PullRequestBranchCandidate(ContractRecord):
    """Local branch candidate for a future pull request."""

    branch_name: str
    base_branch: str
    create_command: LocalGitCommandCandidate
    rollback_command: LocalGitCommandCandidate

    def __post_init__(self) -> None:
        object.__setattr__(self, "branch_name", _normalize_git_ref(self.branch_name, "branch_name"))
        object.__setattr__(self, "base_branch", _normalize_git_ref(self.base_branch, "base_branch"))
        if not isinstance(self.create_command, LocalGitCommandCandidate):
            raise ValueError("create_command must be a LocalGitCommandCandidate")
        if not isinstance(self.rollback_command, LocalGitCommandCandidate):
            raise ValueError("rollback_command must be a LocalGitCommandCandidate")
        if self.branch_name not in self.create_command.command:
            raise ValueError("branch_create_command_must_reference_branch")
        if self.base_branch not in self.rollback_command.command:
            raise ValueError("branch_rollback_command_must_reference_base_branch")


@dataclass(frozen=True, slots=True)
class PullRequestCommitCandidate(ContractRecord):
    """Local commit candidate created after patch and gates have evidence."""

    commit_message: str
    affected_files: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    quality_gate_refs: tuple[str, ...]
    local_commands: tuple[LocalGitCommandCandidate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "commit_message", require_non_empty_text(self.commit_message, "commit_message"))
        object.__setattr__(self, "affected_files", _normalize_path_tuple(tuple(self.affected_files), "affected_files"))
        object.__setattr__(self, "receipt_refs", _normalize_text_tuple(tuple(self.receipt_refs), "receipt_refs"))
        object.__setattr__(self, "quality_gate_refs", _normalize_text_tuple(tuple(self.quality_gate_refs), "quality_gate_refs"))
        if not self.local_commands:
            raise ValueError("local_commands must contain at least one command")
        for command in self.local_commands:
            if not isinstance(command, LocalGitCommandCandidate):
                raise ValueError("local_commands must contain LocalGitCommandCandidate records")
        object.__setattr__(self, "local_commands", freeze_value(list(self.local_commands)))


@dataclass(frozen=True, slots=True)
class PullRequestReviewPacket(ContractRecord):
    """Review packet that a human approval gate can inspect before PR opening."""

    packet_id: str
    title: str
    summary: str
    affected_files: tuple[str, ...]
    quality_gate_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    markdown_body: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "packet_id", require_non_empty_text(self.packet_id, "packet_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "summary", require_non_empty_text(self.summary, "summary"))
        object.__setattr__(self, "affected_files", _normalize_path_tuple(tuple(self.affected_files), "affected_files"))
        object.__setattr__(self, "quality_gate_refs", _normalize_text_tuple(tuple(self.quality_gate_refs), "quality_gate_refs"))
        object.__setattr__(self, "receipt_refs", _normalize_text_tuple(tuple(self.receipt_refs), "receipt_refs"))
        object.__setattr__(self, "risk_flags", _normalize_text_tuple(tuple(self.risk_flags), "risk_flags"))
        object.__setattr__(self, "rollback_plan", _normalize_text_tuple(tuple(self.rollback_plan), "rollback_plan"))
        object.__setattr__(self, "markdown_body", require_non_empty_text(self.markdown_body, "markdown_body"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PullRequestOpenIntent(ContractRecord):
    """Approval-gated GitHub pull-request opening intent."""

    intent_id: str
    repository: str
    title: str
    body: str
    base_branch: str
    head_branch: str
    capability_id: str
    approval_request_id: str
    requires_approval: bool = True
    world_mutating: bool = True
    execution_allowed: bool = False
    approval_decision_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "intent_id", require_non_empty_text(self.intent_id, "intent_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "body", require_non_empty_text(self.body, "body"))
        object.__setattr__(self, "base_branch", _normalize_git_ref(self.base_branch, "base_branch"))
        object.__setattr__(self, "head_branch", _normalize_git_ref(self.head_branch, "head_branch"))
        object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
        object.__setattr__(self, "approval_request_id", require_non_empty_text(self.approval_request_id, "approval_request_id"))
        if self.execution_allowed and not self.requires_approval:
            raise ValueError("pr_open_intent_must_require_approval")
        if self.execution_allowed and not self.approval_decision_id:
            raise ValueError("approval_decision_required_for_execution")
        object.__setattr__(self, "approval_decision_id", str(self.approval_decision_id).strip())
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PullRequestCandidateBundle(ContractRecord):
    """Complete pull-request candidate planning receipt."""

    candidate_id: str
    status: PullRequestCandidateStatus
    repository: str
    branch_candidate: PullRequestBranchCandidate
    commit_candidate: PullRequestCommitCandidate
    review_packet: PullRequestReviewPacket
    open_intent: PullRequestOpenIntent
    evidence_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        if not isinstance(self.status, PullRequestCandidateStatus):
            raise ValueError("status must be a PullRequestCandidateStatus")
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        if self.open_intent.repository != self.repository:
            raise ValueError("open_intent_repository_must_match_candidate")
        if self.open_intent.head_branch != self.branch_candidate.branch_name:
            raise ValueError("open_intent_head_branch_must_match_branch_candidate")
        if self.status is PullRequestCandidateStatus.APPROVED_FOR_OPEN and not self.open_intent.execution_allowed:
            raise ValueError("approved_candidate_requires_executable_open_intent")
        if self.status is not PullRequestCandidateStatus.APPROVED_FOR_OPEN and self.open_intent.execution_allowed:
            raise ValueError("only_approved_candidate_may_execute_open_intent")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
        metadata = dict(self.metadata)
        if metadata.get("local_git_push_allowed") is not False:
            raise ValueError("local_git_push_allowed_must_be_false")
        if metadata.get("github_open_requires_approval") is not True:
            raise ValueError("github_open_requires_approval_must_be_true")
        object.__setattr__(self, "metadata", freeze_value(metadata))


def pull_request_candidate_to_json_dict(candidate: PullRequestCandidateBundle) -> dict[str, Any]:
    """Return the JSON-contract representation of a PR candidate bundle."""
    return candidate.to_json_dict()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(normalized)


def _normalize_path_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        path = value.replace("\\", "/").strip()
        parts = PurePosixPath(path).parts
        if not path:
            continue
        if path.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
            raise ValueError(f"{field_name}[{index}] must be repository-relative")
        if path not in normalized:
            normalized.append(path)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(normalized)


def _normalize_git_ref(value: str, field_name: str) -> str:
    ref = require_non_empty_text(value, field_name).strip()
    if ref.startswith("/") or ref.endswith("/") or "//" in ref:
        raise ValueError(f"{field_name}_invalid_git_ref")
    if ref.startswith(".") or ref.endswith(".") or ref.endswith(".lock"):
        raise ValueError(f"{field_name}_invalid_git_ref")
    if any(part in {"", ".", ".."} for part in ref.split("/")):
        raise ValueError(f"{field_name}_invalid_git_ref")
    if any(char in frozenset(" ~^:?*[]\\") or ord(char) < 32 for char in ref):
        raise ValueError(f"{field_name}_invalid_git_ref")
    return ref


def _git_subcommand(command: tuple[str, ...]) -> str:
    for item in command[1:]:
        if not item.startswith("-"):
            return item.lower()
    raise ValueError("local_git_command_requires_subcommand")
