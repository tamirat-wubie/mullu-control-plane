"""GitHub Operations Workroom governed intake projection.

Purpose: build the first read-only GitHub Workroom path from a dashboard or
    GitHub surface request into universal capability-fabric contracts.
Governance scope: local projection only; no GitHub connector call, repository
    mutation, comment write, merge, deployment, or memory promotion authority.
Dependencies: Python standard-library hashing and universal fabric contracts.
Invariants:
  - PR safety intake is compiled as preparation, not execution.
  - Merge, deploy, branch deletion, and connector writes remain blocked.
  - Non-blocked receipts require concrete evidence references.
  - Memory stores receipt metadata only; discussion content is not persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import escape
import json
from pathlib import Path
from typing import Any, Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request

from mcoi_runtime.contracts._base import ContractRecord, require_datetime_text, require_non_empty_text
from mcoi_runtime.contracts.universal_capability_fabric import (
    CAUSAL_EPISODE_STAGE_ORDER,
    AuthorityResolution,
    CausalCapabilityReceipt,
    CausalEpisodePlan,
    CausalEpisodeStage,
    CausalEpisodeStep,
    FabricMemoryClass,
    FabricMemoryDecisionStatus,
    FabricPolicyDecision,
    FabricRiskClass,
    FabricSensitivity,
    MemoryGateDecision,
    RiskPolicyResult,
    SymbolicEventCompilation,
    UniversalCapabilityPassport,
    UniversalGovernedEvent,
)


GITHUB_PR_SAFETY_CAPABILITY_ID = "github.pr_safety_review.read_only.v1"
GITHUB_ACTIONS_FAILURE_CAPABILITY_ID = "github.actions_failure_diagnosis.read_only.v1"
GITHUB_REPO_STATUS_CAPABILITY_ID = "github.repo_status_summary.read_only.v1"
GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID = "connector.github.read"
GITHUB_PR_SAFETY_INTENT = "REVIEW_PR_MERGE_SAFETY"
GITHUB_ACTIONS_FAILURE_INTENT = "DIAGNOSE_GITHUB_ACTIONS_FAILURE"
GITHUB_REPO_STATUS_INTENT = "SUMMARIZE_GITHUB_REPOSITORY_STATUS"
GITHUB_WORKROOM_SURFACE = "github_operations_workroom"

_REQUIRED_EVIDENCE = (
    "github_pr_diff",
    "github_pr_changed_files",
    "github_pr_ci_status",
    "github_policy_match",
)
_BLOCKED_ACTIONS = (
    "merge_pull_request_without_explicit_approval",
    "deploy_release_without_release_witness",
    "delete_branch_without_explicit_approval",
    "post_github_comment_without_write_admission",
)
_ACTIONS_FAILURE_BLOCKED_ACTIONS = (
    "rerun_workflow_without_explicit_approval",
    "cancel_workflow_without_explicit_approval",
    "dispatch_workflow_without_explicit_approval",
    "post_github_comment_without_write_admission",
    "mutate_repository_without_write_admission",
)
_REPO_STATUS_BLOCKED_ACTIONS = (
    "create_issue_without_explicit_approval",
    "post_github_comment_without_write_admission",
    "mutate_repository_without_write_admission",
    "trigger_workflow_without_explicit_approval",
    "claim_release_ready_without_required_evidence",
)
_ALLOWED_TOOLS = (
    "github.read.pull_request",
    "github.read.diff",
    "github.read.checks",
    "github.read.changed_files",
)
_LIVE_READ_ALLOWED_TOOLS = ("connector_worker.github_read",)
_LIVE_READ_ALLOWED_NETWORKS = ("api.github.com",)
_LIVE_READ_SECRET_SCOPE = "oauth:github.read"
_SUPPORTED_LIVE_EVIDENCE_KINDS = ("pull_request", "diff", "checks", "changed_files")
_SUPPORTED_ACTIONS_FAILURE_EVIDENCE_KINDS = ("workflow_run", "jobs", "failed_job_logs")
_SUPPORTED_REPO_STATUS_EVIDENCE_KINDS = ("repository", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs")
_EFFECT_BOUNDARY = {
    "execution_allowed": False,
    "live_connector_execution_allowed": False,
    "github_call_allowed": False,
    "repository_read_allowed": False,
    "repository_mutation_allowed": False,
    "pull_request_mutation_allowed": False,
    "branch_push_allowed": False,
    "issue_creation_allowed": False,
    "review_submission_allowed": False,
    "deployment_mutation_allowed": False,
    "system_of_record_write_allowed": False,
}


@dataclass(frozen=True, slots=True)
class GitHubPrSafetyWorkroomRequest(ContractRecord):
    """Input contract for the governed GitHub PR safety workroom projection."""

    actor_id: str
    workspace_id: str
    repo: str
    pull_request_number: int
    surface_event_id: str
    occurred_at: str
    evidence_refs: tuple[str, ...]
    channel_id: str = ""
    trace_ref: str = ""
    authority_ref: str = "policy.github.pr_review.local_read_only"
    assumptions: tuple[str, ...] = (
        "Evidence references are already authorized for this actor and workspace.",
        "This projection does not perform live GitHub reads or writes.",
    )
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("actor_id", "workspace_id", "repo", "surface_event_id", "authority_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.channel_id:
            object.__setattr__(self, "channel_id", require_non_empty_text(self.channel_id, "channel_id"))
        if not isinstance(self.pull_request_number, int) or isinstance(self.pull_request_number, bool):
            raise ValueError("pull_request_number must be an integer")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be greater than zero")
        object.__setattr__(self, "occurred_at", require_datetime_text(self.occurred_at, "occurred_at"))
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one evidence reference")
        for index, evidence_ref in enumerate(self.evidence_refs):
            require_non_empty_text(evidence_ref, f"evidence_refs[{index}]")
        if not isinstance(self.assumptions, tuple) or not self.assumptions:
            raise ValueError("assumptions must contain at least one assumption")
        for index, assumption in enumerate(self.assumptions):
            require_non_empty_text(assumption, f"assumptions[{index}]")
        if self.trace_ref:
            object.__setattr__(self, "trace_ref", require_non_empty_text(self.trace_ref, "trace_ref"))
        else:
            object.__setattr__(self, "trace_ref", f"trace:github-pr:{self.repo}#{self.pull_request_number}")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class GitHubPrSafetyWorkroomProjection(ContractRecord):
    """Read-only workroom projection emitted from one PR safety request."""

    event: UniversalGovernedEvent
    compilation: SymbolicEventCompilation
    authority: AuthorityResolution
    policy: RiskPolicyResult
    passport: UniversalCapabilityPassport
    episode: CausalEpisodePlan
    receipt: CausalCapabilityReceipt
    memory_gate: MemoryGateDecision
    connector_write_performed: bool = False

    def __post_init__(self) -> None:
        if self.connector_write_performed:
            raise ValueError("GitHub Operations Workroom projection cannot perform connector writes")


@dataclass(frozen=True, slots=True)
class GitHubReadOnlyEvidenceAdmissionRequest(ContractRecord):
    """Admission request for live read-only GitHub PR evidence collection."""

    actor_id: str
    workspace_id: str
    repo: str
    pull_request_number: int
    requested_evidence_kinds: tuple[str, ...]
    requested_at: str
    surface_event_id: str
    authority_ref: str = "policy.github.pr_review.live_read_only"

    def __post_init__(self) -> None:
        for field_name in ("actor_id", "workspace_id", "repo", "surface_event_id", "authority_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.pull_request_number, int) or isinstance(self.pull_request_number, bool):
            raise ValueError("pull_request_number must be an integer")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be greater than zero")
        if not isinstance(self.requested_evidence_kinds, tuple) or not self.requested_evidence_kinds:
            raise ValueError("requested_evidence_kinds must contain at least one evidence kind")
        for index, evidence_kind in enumerate(self.requested_evidence_kinds):
            normalized_kind = require_non_empty_text(evidence_kind, f"requested_evidence_kinds[{index}]")
            if normalized_kind not in _SUPPORTED_LIVE_EVIDENCE_KINDS:
                raise ValueError(f"unsupported GitHub evidence kind: {normalized_kind}")
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class GitHubReadOnlyEvidenceAdmission(ContractRecord):
    """Admission decision for live read-only GitHub PR evidence collection."""

    admission_id: str
    capability_id: str
    actor_id: str
    workspace_id: str
    repo: str
    pull_request_number: int
    requested_evidence_kinds: tuple[str, ...]
    planned_evidence_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_networks: tuple[str, ...]
    required_secret_scope: str
    blocked_actions: tuple[str, ...]
    authority_ref: str
    policy_decision: str
    solver_outcome: str
    live_connector_read_admitted: bool
    live_connector_call_performed: bool
    write_authority_granted: bool
    admitted_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "admission_id",
            "capability_id",
            "actor_id",
            "workspace_id",
            "repo",
            "required_secret_scope",
            "authority_ref",
            "policy_decision",
            "solver_outcome",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub read-only evidence admission must use connector.github.read")
        if not isinstance(self.pull_request_number, int) or isinstance(self.pull_request_number, bool):
            raise ValueError("pull_request_number must be an integer")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be greater than zero")
        for field_name in ("requested_evidence_kinds", "planned_evidence_refs", "allowed_tools", "allowed_networks"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.blocked_actions, tuple) or not self.blocked_actions:
            raise ValueError("blocked_actions must contain at least one item")
        for index, action in enumerate(self.blocked_actions):
            require_non_empty_text(action, f"blocked_actions[{index}]")
        if self.live_connector_read_admitted is not True:
            raise ValueError("live_connector_read_admitted must be true")
        if self.live_connector_call_performed is not False:
            raise ValueError("admission must not claim a live connector call was performed")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub read-only evidence admission cannot grant write authority")
        object.__setattr__(self, "admitted_at", require_datetime_text(self.admitted_at, "admitted_at"))


@dataclass(frozen=True, slots=True)
class GitHubActionsFailureEvidenceAdmissionRequest(ContractRecord):
    """Admission request for read-only GitHub Actions failure evidence."""

    actor_id: str
    workspace_id: str
    repo: str
    workflow_run_id: int
    requested_evidence_kinds: tuple[str, ...]
    requested_at: str
    surface_event_id: str
    authority_ref: str = "policy.github.actions_failure.live_read_only"
    max_failed_job_logs: int = 3

    def __post_init__(self) -> None:
        for field_name in ("actor_id", "workspace_id", "repo", "surface_event_id", "authority_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.workflow_run_id, int) or isinstance(self.workflow_run_id, bool):
            raise ValueError("workflow_run_id must be an integer")
        if self.workflow_run_id < 1:
            raise ValueError("workflow_run_id must be greater than zero")
        if not isinstance(self.requested_evidence_kinds, tuple) or not self.requested_evidence_kinds:
            raise ValueError("requested_evidence_kinds must contain at least one evidence kind")
        for index, evidence_kind in enumerate(self.requested_evidence_kinds):
            normalized_kind = require_non_empty_text(evidence_kind, f"requested_evidence_kinds[{index}]")
            if normalized_kind not in _SUPPORTED_ACTIONS_FAILURE_EVIDENCE_KINDS:
                raise ValueError(f"unsupported GitHub Actions evidence kind: {normalized_kind}")
        if not isinstance(self.max_failed_job_logs, int) or isinstance(self.max_failed_job_logs, bool):
            raise ValueError("max_failed_job_logs must be an integer")
        if not 0 <= self.max_failed_job_logs <= 10:
            raise ValueError("max_failed_job_logs must be between 0 and 10")
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class GitHubActionsFailureEvidenceAdmission(ContractRecord):
    """Admission decision for read-only GitHub Actions failure evidence."""

    admission_id: str
    capability_id: str
    actor_id: str
    workspace_id: str
    repo: str
    workflow_run_id: int
    requested_evidence_kinds: tuple[str, ...]
    planned_evidence_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_networks: tuple[str, ...]
    required_secret_scope: str
    blocked_actions: tuple[str, ...]
    authority_ref: str
    policy_decision: str
    solver_outcome: str
    live_connector_read_admitted: bool
    live_connector_call_performed: bool
    write_authority_granted: bool
    max_failed_job_logs: int
    admitted_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "admission_id",
            "capability_id",
            "actor_id",
            "workspace_id",
            "repo",
            "required_secret_scope",
            "authority_ref",
            "policy_decision",
            "solver_outcome",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub Actions evidence admission must use connector.github.read")
        if not isinstance(self.workflow_run_id, int) or isinstance(self.workflow_run_id, bool):
            raise ValueError("workflow_run_id must be an integer")
        if self.workflow_run_id < 1:
            raise ValueError("workflow_run_id must be greater than zero")
        for field_name in ("requested_evidence_kinds", "planned_evidence_refs", "allowed_tools", "allowed_networks"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.blocked_actions, tuple) or not self.blocked_actions:
            raise ValueError("blocked_actions must contain at least one item")
        for index, action in enumerate(self.blocked_actions):
            require_non_empty_text(action, f"blocked_actions[{index}]")
        if self.live_connector_read_admitted is not True:
            raise ValueError("live_connector_read_admitted must be true")
        if self.live_connector_call_performed is not False:
            raise ValueError("admission must not claim a live connector call was performed")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub Actions evidence admission cannot grant write authority")
        if not isinstance(self.max_failed_job_logs, int) or isinstance(self.max_failed_job_logs, bool):
            raise ValueError("max_failed_job_logs must be an integer")
        if not 0 <= self.max_failed_job_logs <= 10:
            raise ValueError("max_failed_job_logs must be between 0 and 10")
        object.__setattr__(self, "admitted_at", require_datetime_text(self.admitted_at, "admitted_at"))


@dataclass(frozen=True, slots=True)
class GitHubRepoStatusEvidenceAdmissionRequest(ContractRecord):
    """Admission request for read-only GitHub repository status evidence."""

    actor_id: str
    workspace_id: str
    repo: str
    requested_evidence_kinds: tuple[str, ...]
    requested_at: str
    surface_event_id: str
    authority_ref: str = "policy.github.repo_status.live_read_only"
    max_items_per_kind: int = 10

    def __post_init__(self) -> None:
        for field_name in ("actor_id", "workspace_id", "repo", "surface_event_id", "authority_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.requested_evidence_kinds, tuple) or not self.requested_evidence_kinds:
            raise ValueError("requested_evidence_kinds must contain at least one evidence kind")
        for index, evidence_kind in enumerate(self.requested_evidence_kinds):
            normalized_kind = require_non_empty_text(evidence_kind, f"requested_evidence_kinds[{index}]")
            if normalized_kind not in _SUPPORTED_REPO_STATUS_EVIDENCE_KINDS:
                raise ValueError(f"unsupported GitHub repository status evidence kind: {normalized_kind}")
        if not isinstance(self.max_items_per_kind, int) or isinstance(self.max_items_per_kind, bool):
            raise ValueError("max_items_per_kind must be an integer")
        if not 1 <= self.max_items_per_kind <= 30:
            raise ValueError("max_items_per_kind must be between 1 and 30")
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class GitHubRepoStatusEvidenceAdmission(ContractRecord):
    """Admission decision for read-only GitHub repository status evidence."""

    admission_id: str
    capability_id: str
    actor_id: str
    workspace_id: str
    repo: str
    requested_evidence_kinds: tuple[str, ...]
    planned_evidence_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_networks: tuple[str, ...]
    required_secret_scope: str
    blocked_actions: tuple[str, ...]
    authority_ref: str
    policy_decision: str
    solver_outcome: str
    live_connector_read_admitted: bool
    live_connector_call_performed: bool
    write_authority_granted: bool
    max_items_per_kind: int
    admitted_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "admission_id",
            "capability_id",
            "actor_id",
            "workspace_id",
            "repo",
            "required_secret_scope",
            "authority_ref",
            "policy_decision",
            "solver_outcome",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub repository status admission must use connector.github.read")
        for field_name in ("requested_evidence_kinds", "planned_evidence_refs", "allowed_tools", "allowed_networks"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.blocked_actions, tuple) or not self.blocked_actions:
            raise ValueError("blocked_actions must contain at least one item")
        for index, action in enumerate(self.blocked_actions):
            require_non_empty_text(action, f"blocked_actions[{index}]")
        if self.live_connector_read_admitted is not True:
            raise ValueError("live_connector_read_admitted must be true")
        if self.live_connector_call_performed is not False:
            raise ValueError("admission must not claim a live connector call was performed")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub repository status admission cannot grant write authority")
        if not isinstance(self.max_items_per_kind, int) or isinstance(self.max_items_per_kind, bool):
            raise ValueError("max_items_per_kind must be an integer")
        if not 1 <= self.max_items_per_kind <= 30:
            raise ValueError("max_items_per_kind must be between 1 and 30")
        object.__setattr__(self, "admitted_at", require_datetime_text(self.admitted_at, "admitted_at"))


@dataclass(frozen=True, slots=True)
class GitHubReadOnlyEvidenceFetchResult(ContractRecord):
    """Bounded result from an admitted read-only GitHub evidence fetch."""

    fetch_id: str
    admission_id: str
    capability_id: str
    repo: str
    pull_request_number: int
    fetched_evidence_kinds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    payload_hashes: Mapping[str, str]
    observed_pull_request: Mapping[str, Any]
    observed_checks: Mapping[str, Any]
    changed_files: tuple[str, ...]
    diff_digest: str
    blocked_actions: tuple[str, ...]
    solver_outcome: str
    live_connector_call_performed: bool
    write_authority_granted: bool
    fetched_at: str
    partial_failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fetch_id", "admission_id", "capability_id", "repo", "solver_outcome"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub read-only fetch must use connector.github.read")
        if not isinstance(self.pull_request_number, int) or isinstance(self.pull_request_number, bool):
            raise ValueError("pull_request_number must be an integer")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be greater than zero")
        for field_name in ("fetched_evidence_kinds", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.changed_files, tuple):
            raise ValueError("changed_files must be a tuple")
        for index, changed_file in enumerate(self.changed_files):
            require_non_empty_text(changed_file, f"changed_files[{index}]")
        object.__setattr__(self, "payload_hashes", dict(self.payload_hashes))
        object.__setattr__(self, "observed_pull_request", dict(self.observed_pull_request))
        object.__setattr__(self, "observed_checks", dict(self.observed_checks))
        if self.diff_digest:
            object.__setattr__(self, "diff_digest", require_non_empty_text(self.diff_digest, "diff_digest"))
        if self.live_connector_call_performed is not True:
            raise ValueError("live_connector_call_performed must be true for fetch results")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub read-only fetch cannot grant write authority")
        if not isinstance(self.partial_failure_reasons, tuple):
            raise ValueError("partial_failure_reasons must be a tuple")
        for index, reason in enumerate(self.partial_failure_reasons):
            require_non_empty_text(reason, f"partial_failure_reasons[{index}]")
        object.__setattr__(self, "fetched_at", require_datetime_text(self.fetched_at, "fetched_at"))


@dataclass(frozen=True, slots=True)
class GitHubActionsFailureEvidenceFetchResult(ContractRecord):
    """Bounded read-only result from GitHub Actions failure evidence collection."""

    fetch_id: str
    admission_id: str
    capability_id: str
    repo: str
    workflow_run_id: int
    fetched_evidence_kinds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    payload_hashes: Mapping[str, str]
    observed_workflow_run: Mapping[str, Any]
    observed_jobs: tuple[Mapping[str, Any], ...]
    failed_log_summaries: tuple[Mapping[str, Any], ...]
    blocked_actions: tuple[str, ...]
    solver_outcome: str
    live_connector_call_performed: bool
    write_authority_granted: bool
    fetched_at: str
    partial_failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fetch_id", "admission_id", "capability_id", "repo", "solver_outcome"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub Actions evidence fetch must use connector.github.read")
        if not isinstance(self.workflow_run_id, int) or isinstance(self.workflow_run_id, bool):
            raise ValueError("workflow_run_id must be an integer")
        if self.workflow_run_id < 1:
            raise ValueError("workflow_run_id must be greater than zero")
        for field_name in ("fetched_evidence_kinds", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        object.__setattr__(self, "payload_hashes", dict(self.payload_hashes))
        object.__setattr__(self, "observed_workflow_run", dict(self.observed_workflow_run))
        if not isinstance(self.observed_jobs, tuple):
            raise ValueError("observed_jobs must be a tuple")
        object.__setattr__(self, "observed_jobs", tuple(dict(job) for job in self.observed_jobs))
        if not isinstance(self.failed_log_summaries, tuple):
            raise ValueError("failed_log_summaries must be a tuple")
        object.__setattr__(self, "failed_log_summaries", tuple(dict(summary) for summary in self.failed_log_summaries))
        if self.live_connector_call_performed is not True:
            raise ValueError("live_connector_call_performed must be true for fetch results")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub Actions evidence fetch cannot grant write authority")
        if not isinstance(self.partial_failure_reasons, tuple):
            raise ValueError("partial_failure_reasons must be a tuple")
        for index, reason in enumerate(self.partial_failure_reasons):
            require_non_empty_text(reason, f"partial_failure_reasons[{index}]")
        object.__setattr__(self, "fetched_at", require_datetime_text(self.fetched_at, "fetched_at"))


@dataclass(frozen=True, slots=True)
class GitHubRepoStatusEvidenceFetchResult(ContractRecord):
    """Bounded read-only result from GitHub repository status evidence collection."""

    fetch_id: str
    admission_id: str
    capability_id: str
    repo: str
    fetched_evidence_kinds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    payload_hashes: Mapping[str, str]
    repository_summary: Mapping[str, Any]
    recent_commits: tuple[Mapping[str, Any], ...]
    open_pull_requests: tuple[Mapping[str, Any], ...]
    open_issues: tuple[Mapping[str, Any], ...]
    workflow_runs: tuple[Mapping[str, Any], ...]
    blocked_actions: tuple[str, ...]
    solver_outcome: str
    live_connector_call_performed: bool
    write_authority_granted: bool
    fetched_at: str
    partial_failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fetch_id", "admission_id", "capability_id", "repo", "solver_outcome"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
            raise ValueError("GitHub repository status fetch must use connector.github.read")
        for field_name in ("fetched_evidence_kinds", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        object.__setattr__(self, "payload_hashes", dict(self.payload_hashes))
        object.__setattr__(self, "repository_summary", dict(self.repository_summary))
        object.__setattr__(self, "recent_commits", tuple(dict(item) for item in self.recent_commits))
        object.__setattr__(self, "open_pull_requests", tuple(dict(item) for item in self.open_pull_requests))
        object.__setattr__(self, "open_issues", tuple(dict(item) for item in self.open_issues))
        object.__setattr__(self, "workflow_runs", tuple(dict(item) for item in self.workflow_runs))
        if self.live_connector_call_performed is not True:
            raise ValueError("live_connector_call_performed must be true for fetch results")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub repository status fetch cannot grant write authority")
        if not isinstance(self.partial_failure_reasons, tuple):
            raise ValueError("partial_failure_reasons must be a tuple")
        for index, reason in enumerate(self.partial_failure_reasons):
            require_non_empty_text(reason, f"partial_failure_reasons[{index}]")
        object.__setattr__(self, "fetched_at", require_datetime_text(self.fetched_at, "fetched_at"))


class GitHubReadOnlyEvidenceFetcher:
    """Execute admitted GitHub PR evidence reads with GET-only HTTP requests."""

    def __init__(
        self,
        *,
        access_token: str,
        urlopen: Callable[..., Any] | None = None,
        timeout_seconds: float = 10.0,
        base_url: str = "https://api.github.com",
    ) -> None:
        self._access_token = require_non_empty_text(access_token, "access_token")
        self._urlopen = urlopen or urllib.request.urlopen
        self._timeout_seconds = timeout_seconds
        self._base_url = require_non_empty_text(base_url, "base_url").rstrip("/")
        if self._base_url != "https://api.github.com":
            raise ValueError("GitHub read-only evidence fetcher only allows https://api.github.com")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

    def fetch(
        self,
        admission: GitHubReadOnlyEvidenceAdmission,
        *,
        clock: Callable[[], str],
    ) -> GitHubReadOnlyEvidenceFetchResult:
        """Fetch admitted GitHub evidence and return bounded hashes/summaries."""

        _validate_fetch_admission(admission)
        fetched_at = require_datetime_text(clock(), "fetched_at")
        payload_hashes: dict[str, str] = {}
        evidence_refs: list[str] = []
        partial_failures: list[str] = []
        observed_pull_request: dict[str, Any] = {}
        observed_checks: dict[str, Any] = {"total_count": 0, "conclusion_counts": {}}
        changed_files: tuple[str, ...] = ()
        diff_digest = ""

        if "pull_request" in admission.requested_evidence_kinds or "checks" in admission.requested_evidence_kinds:
            try:
                pr_payload = self._get_json(f"/repos/{admission.repo}/pulls/{admission.pull_request_number}")
                payload_hashes["pull_request"] = _payload_hash(pr_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/pulls/{admission.pull_request_number}/pull_request")
                observed_pull_request = _summarize_pull_request(pr_payload)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"pull_request:{exc}")

        if "diff" in admission.requested_evidence_kinds:
            try:
                diff_payload = self._get_text(
                    f"/repos/{admission.repo}/pulls/{admission.pull_request_number}",
                    accept="application/vnd.github.v3.diff",
                )
                diff_digest = _text_hash(diff_payload)
                payload_hashes["diff"] = diff_digest
                evidence_refs.append(f"github-live-read://{admission.repo}/pulls/{admission.pull_request_number}/diff")
            except GitHubReadOnlyEvidenceFetchError as exc:
                partial_failures.append(f"diff:{exc}")

        if "changed_files" in admission.requested_evidence_kinds:
            try:
                files_payload = self._get_json(f"/repos/{admission.repo}/pulls/{admission.pull_request_number}/files")
                payload_hashes["changed_files"] = _payload_hash(files_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/pulls/{admission.pull_request_number}/changed_files")
                changed_files = _summarize_changed_files(files_payload)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"changed_files:{exc}")

        if "checks" in admission.requested_evidence_kinds:
            head_sha = str(observed_pull_request.get("head_sha", ""))
            if not head_sha:
                partial_failures.append("checks:missing_pull_request_head_sha")
            else:
                try:
                    checks_payload = self._get_json(f"/repos/{admission.repo}/commits/{head_sha}/check-runs")
                    payload_hashes["checks"] = _payload_hash(checks_payload)
                    evidence_refs.append(f"github-live-read://{admission.repo}/pulls/{admission.pull_request_number}/checks")
                    observed_checks = _summarize_checks(checks_payload)
                except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                    partial_failures.append(f"checks:{exc}")

        if not evidence_refs:
            raise GitHubReadOnlyEvidenceFetchError("no_evidence_collected")

        fetch_hash = _stable_hash(
            {
                "admission_id": admission.admission_id,
                "evidence_refs": tuple(evidence_refs),
                "payload_hashes": payload_hashes,
                "fetched_at": fetched_at,
            }
        )
        return GitHubReadOnlyEvidenceFetchResult(
            fetch_id=f"github-read-fetch:{fetch_hash}",
            admission_id=admission.admission_id,
            capability_id=admission.capability_id,
            repo=admission.repo,
            pull_request_number=admission.pull_request_number,
            fetched_evidence_kinds=tuple(payload_hashes),
            evidence_refs=tuple(evidence_refs),
            payload_hashes=payload_hashes,
            observed_pull_request=observed_pull_request,
            observed_checks=observed_checks,
            changed_files=changed_files,
            diff_digest=diff_digest,
            blocked_actions=admission.blocked_actions,
            solver_outcome="SolvedUnverified" if partial_failures else "SolvedVerified",
            live_connector_call_performed=True,
            write_authority_granted=False,
            fetched_at=fetched_at,
            partial_failure_reasons=tuple(partial_failures),
        )

    def fetch_actions_failure(
        self,
        admission: GitHubActionsFailureEvidenceAdmission,
        *,
        clock: Callable[[], str],
    ) -> GitHubActionsFailureEvidenceFetchResult:
        """Fetch admitted GitHub Actions failure evidence with GET-only requests."""

        _validate_actions_failure_fetch_admission(admission)
        fetched_at = require_datetime_text(clock(), "fetched_at")
        payload_hashes: dict[str, str] = {}
        evidence_refs: list[str] = []
        partial_failures: list[str] = []
        observed_workflow_run: dict[str, Any] = {}
        observed_jobs: tuple[Mapping[str, Any], ...] = ()
        failed_log_summaries: list[Mapping[str, Any]] = []

        if "workflow_run" in admission.requested_evidence_kinds:
            try:
                run_payload = self._get_json(f"/repos/{admission.repo}/actions/runs/{admission.workflow_run_id}")
                payload_hashes["workflow_run"] = _payload_hash(run_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/actions/runs/{admission.workflow_run_id}")
                observed_workflow_run = _summarize_workflow_run(run_payload)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"workflow_run:{exc}")

        if "jobs" in admission.requested_evidence_kinds or "failed_job_logs" in admission.requested_evidence_kinds:
            try:
                jobs_payload = self._get_json(f"/repos/{admission.repo}/actions/runs/{admission.workflow_run_id}/jobs")
                payload_hashes["jobs"] = _payload_hash(jobs_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/actions/runs/{admission.workflow_run_id}/jobs")
                observed_jobs = _summarize_workflow_jobs(jobs_payload)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"jobs:{exc}")

        if "failed_job_logs" in admission.requested_evidence_kinds and admission.max_failed_job_logs > 0:
            failed_jobs = tuple(
                job for job in observed_jobs if str(job.get("conclusion") or "") not in {"success", "skipped", "neutral", ""}
            )
            for job in failed_jobs[: admission.max_failed_job_logs]:
                job_id = job.get("job_id")
                try:
                    if not isinstance(job_id, int):
                        raise GitHubReadOnlyEvidenceFetchError("failed_job_missing_id")
                    log_payload = self._get_text(f"/repos/{admission.repo}/actions/jobs/{job_id}/logs", accept="text/plain")
                    log_digest = _text_hash(log_payload)
                    payload_hashes[f"job_log:{job_id}"] = log_digest
                    evidence_refs.append(f"github-live-read://{admission.repo}/actions/jobs/{job_id}/logs")
                    failed_log_summaries.append(_summarize_failed_job_log(job=job, log_payload=log_payload, log_digest=log_digest))
                except GitHubReadOnlyEvidenceFetchError as exc:
                    partial_failures.append(f"failed_job_logs:{job_id}:{exc}")

        if not evidence_refs:
            raise GitHubReadOnlyEvidenceFetchError("no_actions_failure_evidence_collected")

        fetch_hash = _stable_hash(
            {
                "admission_id": admission.admission_id,
                "evidence_refs": tuple(evidence_refs),
                "payload_hashes": payload_hashes,
                "fetched_at": fetched_at,
            }
        )
        return GitHubActionsFailureEvidenceFetchResult(
            fetch_id=f"github-actions-failure-fetch:{fetch_hash}",
            admission_id=admission.admission_id,
            capability_id=admission.capability_id,
            repo=admission.repo,
            workflow_run_id=admission.workflow_run_id,
            fetched_evidence_kinds=tuple(payload_hashes),
            evidence_refs=tuple(evidence_refs),
            payload_hashes=payload_hashes,
            observed_workflow_run=observed_workflow_run,
            observed_jobs=observed_jobs,
            failed_log_summaries=tuple(failed_log_summaries),
            blocked_actions=admission.blocked_actions,
            solver_outcome="SolvedUnverified" if partial_failures else "SolvedVerified",
            live_connector_call_performed=True,
            write_authority_granted=False,
            fetched_at=fetched_at,
            partial_failure_reasons=tuple(partial_failures),
        )

    def fetch_repo_status(
        self,
        admission: GitHubRepoStatusEvidenceAdmission,
        *,
        clock: Callable[[], str],
    ) -> GitHubRepoStatusEvidenceFetchResult:
        """Fetch admitted GitHub repository status evidence with GET-only requests."""

        _validate_repo_status_fetch_admission(admission)
        fetched_at = require_datetime_text(clock(), "fetched_at")
        payload_hashes: dict[str, str] = {}
        evidence_refs: list[str] = []
        partial_failures: list[str] = []
        repository_summary: dict[str, Any] = {}
        recent_commits: tuple[Mapping[str, Any], ...] = ()
        open_pull_requests: tuple[Mapping[str, Any], ...] = ()
        open_issues: tuple[Mapping[str, Any], ...] = ()
        workflow_runs: tuple[Mapping[str, Any], ...] = ()

        if "repository" in admission.requested_evidence_kinds:
            try:
                repo_payload = self._get_json(f"/repos/{admission.repo}")
                payload_hashes["repository"] = _payload_hash(repo_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/repository")
                repository_summary = _summarize_repository(repo_payload)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"repository:{exc}")

        if "recent_commits" in admission.requested_evidence_kinds:
            try:
                commits_payload = self._get_json(f"/repos/{admission.repo}/commits")
                payload_hashes["recent_commits"] = _payload_hash(commits_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/commits")
                recent_commits = _summarize_recent_commits(commits_payload, max_items=admission.max_items_per_kind)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"recent_commits:{exc}")

        if "open_pull_requests" in admission.requested_evidence_kinds:
            try:
                pulls_payload = self._get_json(f"/repos/{admission.repo}/pulls")
                payload_hashes["open_pull_requests"] = _payload_hash(pulls_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/pulls")
                open_pull_requests = _summarize_open_pull_requests(pulls_payload, max_items=admission.max_items_per_kind)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"open_pull_requests:{exc}")

        if "open_issues" in admission.requested_evidence_kinds:
            try:
                issues_payload = self._get_json(f"/repos/{admission.repo}/issues")
                payload_hashes["open_issues"] = _payload_hash(issues_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/issues")
                open_issues = _summarize_open_issues(issues_payload, max_items=admission.max_items_per_kind)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"open_issues:{exc}")

        if "workflow_runs" in admission.requested_evidence_kinds:
            try:
                runs_payload = self._get_json(f"/repos/{admission.repo}/actions/runs")
                payload_hashes["workflow_runs"] = _payload_hash(runs_payload)
                evidence_refs.append(f"github-live-read://{admission.repo}/actions/runs")
                workflow_runs = _summarize_workflow_runs(runs_payload, max_items=admission.max_items_per_kind)
            except (GitHubReadOnlyEvidenceFetchError, ValueError) as exc:
                partial_failures.append(f"workflow_runs:{exc}")

        if not evidence_refs:
            raise GitHubReadOnlyEvidenceFetchError("no_repo_status_evidence_collected")

        fetch_hash = _stable_hash(
            {
                "admission_id": admission.admission_id,
                "evidence_refs": tuple(evidence_refs),
                "payload_hashes": payload_hashes,
                "fetched_at": fetched_at,
            }
        )
        return GitHubRepoStatusEvidenceFetchResult(
            fetch_id=f"github-repo-status-fetch:{fetch_hash}",
            admission_id=admission.admission_id,
            capability_id=admission.capability_id,
            repo=admission.repo,
            fetched_evidence_kinds=tuple(payload_hashes),
            evidence_refs=tuple(evidence_refs),
            payload_hashes=payload_hashes,
            repository_summary=repository_summary,
            recent_commits=recent_commits,
            open_pull_requests=open_pull_requests,
            open_issues=open_issues,
            workflow_runs=workflow_runs,
            blocked_actions=admission.blocked_actions,
            solver_outcome="SolvedUnverified" if partial_failures else "SolvedVerified",
            live_connector_call_performed=True,
            write_authority_granted=False,
            fetched_at=fetched_at,
            partial_failure_reasons=tuple(partial_failures),
        )

    def _get_json(self, path: str) -> Any:
        body = self._get_bytes(path, accept="application/vnd.github+json")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubReadOnlyEvidenceFetchError("invalid_github_json_response") from exc

    def _get_text(self, path: str, *, accept: str) -> str:
        body = self._get_bytes(path, accept=accept)
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitHubReadOnlyEvidenceFetchError("invalid_github_text_response") from exc

    def _get_bytes(self, path: str, *, accept: str) -> bytes:
        if not path.startswith("/"):
            raise GitHubReadOnlyEvidenceFetchError("github_path_must_be_absolute")
        url = f"{self._base_url}{_quote_github_path(path)}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": accept,
                "Authorization": f"Bearer {self._access_token}",
                "User-Agent": "mullusi-github-read-only-evidence-fetcher",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        try:
            with self._urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise GitHubReadOnlyEvidenceFetchError(f"github_http_error:{exc.code}") from exc
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            raise GitHubReadOnlyEvidenceFetchError("github_read_failed") from exc


class GitHubReadOnlyEvidenceFetchError(RuntimeError):
    """Raised when an admitted read-only GitHub evidence fetch cannot complete."""


@dataclass(frozen=True, slots=True)
class GitHubPrSafetyJudgment(ContractRecord):
    """Bounded PR safety judgment from read-only GitHub evidence."""

    judgment_id: str
    repo: str
    pull_request_number: int
    status: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    required_next_action: str
    confidence: float
    merge_authority_granted: bool
    write_authority_granted: bool
    judged_at: str

    def __post_init__(self) -> None:
        for field_name in ("judgment_id", "repo", "status", "required_next_action"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.status not in {"ready_for_review", "blocked", "needs_evidence"}:
            raise ValueError("status must be ready_for_review, blocked, or needs_evidence")
        if not isinstance(self.pull_request_number, int) or isinstance(self.pull_request_number, bool):
            raise ValueError("pull_request_number must be an integer")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be greater than zero")
        for field_name in ("reasons", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise ValueError("confidence must be a number")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "confidence", float(self.confidence))
        if self.merge_authority_granted is not False:
            raise ValueError("PR safety judgment cannot grant merge authority")
        if self.write_authority_granted is not False:
            raise ValueError("PR safety judgment cannot grant write authority")
        object.__setattr__(self, "judged_at", require_datetime_text(self.judged_at, "judged_at"))


@dataclass(frozen=True, slots=True)
class GitHubActionsFailureDiagnosis(ContractRecord):
    """Bounded diagnosis from read-only GitHub Actions evidence."""

    diagnosis_id: str
    repo: str
    workflow_run_id: int
    status: str
    failure_summary: str
    suspected_failed_jobs: tuple[str, ...]
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    recommended_next_action: str
    confidence: float
    write_authority_granted: bool
    diagnosed_at: str

    def __post_init__(self) -> None:
        for field_name in ("diagnosis_id", "repo", "status", "failure_summary", "recommended_next_action"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.status not in {"diagnosed", "needs_evidence", "not_failed"}:
            raise ValueError("status must be diagnosed, needs_evidence, or not_failed")
        if not isinstance(self.workflow_run_id, int) or isinstance(self.workflow_run_id, bool):
            raise ValueError("workflow_run_id must be an integer")
        if self.workflow_run_id < 1:
            raise ValueError("workflow_run_id must be greater than zero")
        for field_name in ("suspected_failed_jobs", "reasons", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise ValueError("confidence must be a number")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "confidence", float(self.confidence))
        if self.write_authority_granted is not False:
            raise ValueError("Actions failure diagnosis cannot grant write authority")
        object.__setattr__(self, "diagnosed_at", require_datetime_text(self.diagnosed_at, "diagnosed_at"))


@dataclass(frozen=True, slots=True)
class GitHubReadOnlyEvidenceReceiptStorageResult(ContractRecord):
    """Workspace-local storage witness for a read-only GitHub evidence bundle."""

    storage_id: str
    receipt_id: str
    receipt_path: str
    payload_sha256: str
    stored_at: str
    token_persisted: bool
    write_authority_granted: bool

    def __post_init__(self) -> None:
        for field_name in ("storage_id", "receipt_id", "receipt_path", "payload_sha256"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not self.payload_sha256.startswith("sha256:"):
            raise ValueError("payload_sha256 must use sha256: prefix")
        object.__setattr__(self, "stored_at", require_datetime_text(self.stored_at, "stored_at"))
        if self.token_persisted is not False:
            raise ValueError("GitHub receipt storage cannot persist tokens")
        if self.write_authority_granted is not False:
            raise ValueError("GitHub receipt storage cannot grant write authority")


def persist_github_read_only_evidence_receipt_bundle(
    *,
    receipt_store_root: Path,
    admission: GitHubReadOnlyEvidenceAdmission,
    fetch_result: GitHubReadOnlyEvidenceFetchResult,
    fetch_receipt: CausalCapabilityReceipt,
    pr_safety_projection: GitHubPrSafetyWorkroomProjection,
    pr_safety_judgment: GitHubPrSafetyJudgment,
    stored_at: str,
) -> GitHubReadOnlyEvidenceReceiptStorageResult:
    """Persist a bounded read-only evidence bundle under a local receipt root."""

    if not isinstance(admission, GitHubReadOnlyEvidenceAdmission):
        raise ValueError("admission must be a GitHubReadOnlyEvidenceAdmission")
    if not isinstance(fetch_result, GitHubReadOnlyEvidenceFetchResult):
        raise ValueError("fetch_result must be a GitHubReadOnlyEvidenceFetchResult")
    if not isinstance(fetch_receipt, CausalCapabilityReceipt):
        raise ValueError("fetch_receipt must be a CausalCapabilityReceipt")
    if not isinstance(pr_safety_projection, GitHubPrSafetyWorkroomProjection):
        raise ValueError("pr_safety_projection must be a GitHubPrSafetyWorkroomProjection")
    if not isinstance(pr_safety_judgment, GitHubPrSafetyJudgment):
        raise ValueError("pr_safety_judgment must be a GitHubPrSafetyJudgment")
    if fetch_receipt.intent != "COLLECT_GITHUB_PR_READ_ONLY_EVIDENCE":
        raise ValueError("fetch_receipt must come from GitHub read-only evidence collection")
    if fetch_receipt.policy_decision is not FabricPolicyDecision.ALLOW_READ_ONLY:
        raise ValueError("fetch_receipt must be read-only")
    if pr_safety_judgment.write_authority_granted or pr_safety_judgment.merge_authority_granted:
        raise ValueError("PR safety judgment cannot grant write or merge authority")

    stored_at = require_datetime_text(stored_at, "stored_at")
    root = receipt_store_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    receipt_hash = _stable_hash({"receipt_id": fetch_receipt.receipt_id})
    receipt_path = (root / f"github-read-evidence-{receipt_hash}.json").resolve()
    if root not in receipt_path.parents:
        raise ValueError("receipt path must stay inside receipt_store_root")

    payload = {
        "schema_ref": "urn:mullusi:receipt-bundle:github-read-only-evidence:1",
        "stored_at": stored_at,
        "admission": admission.to_json_dict(),
        "fetch_result": fetch_result.to_json_dict(),
        "fetch_receipt": fetch_receipt.to_json_dict(),
        "pr_safety_projection": pr_safety_projection.to_json_dict(),
        "pr_safety_judgment": pr_safety_judgment.to_json_dict(),
        "token_persisted": False,
        "write_authority_granted": False,
        "merge_authority_granted": False,
    }
    encoded_payload = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    forbidden_markers = ("access_token", "Authorization", "Bearer ")
    if any(marker in encoded_payload for marker in forbidden_markers):
        raise ValueError("receipt bundle contains forbidden credential marker")
    payload_sha256 = f"sha256:{hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()}"
    temp_path = receipt_path.with_suffix(".tmp")
    temp_path.write_text(encoded_payload, encoding="utf-8")
    temp_path.replace(receipt_path)

    storage_hash = _stable_hash(
        {
            "receipt_id": fetch_receipt.receipt_id,
            "receipt_path": str(receipt_path),
            "payload_sha256": payload_sha256,
            "stored_at": stored_at,
        }
    )
    return GitHubReadOnlyEvidenceReceiptStorageResult(
        storage_id=f"github-read-storage:{storage_hash}",
        receipt_id=fetch_receipt.receipt_id,
        receipt_path=str(receipt_path),
        payload_sha256=payload_sha256,
        stored_at=stored_at,
        token_persisted=False,
        write_authority_granted=False,
    )


def read_github_read_only_evidence_receipt_bundle(
    *,
    receipt_store_root: Path,
    receipt_filename: str,
) -> dict[str, Any]:
    """Read one stored GitHub evidence bundle by filename from the receipt root."""

    filename = require_non_empty_text(receipt_filename, "receipt_filename")
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise ValueError("receipt_filename must be a filename, not a path")
    if not filename.startswith("github-read-evidence-") or not filename.endswith(".json"):
        raise ValueError("receipt_filename must be a GitHub read evidence bundle filename")
    root = receipt_store_root.resolve()
    receipt_path = (root / filename).resolve()
    if root not in receipt_path.parents:
        raise ValueError("receipt path must stay inside receipt_store_root")
    if not receipt_path.exists():
        raise FileNotFoundError(filename)
    receipt_text = receipt_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(receipt_text)
    except json.JSONDecodeError as exc:
        raise ValueError("stored receipt bundle is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("stored receipt bundle must be a JSON object")
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    forbidden_markers = ("access_token", "Authorization", "Bearer ")
    if any(marker in encoded_payload for marker in forbidden_markers):
        raise ValueError("stored receipt bundle contains forbidden credential marker")
    return {
        "receipt_filename": filename,
        "receipt_path": str(receipt_path),
        "payload_sha256": f"sha256:{hashlib.sha256(receipt_text.encode('utf-8')).hexdigest()}",
        "bundle": payload,
        "token_persisted": False,
        "write_authority_granted": False,
        "merge_authority_granted": False,
    }


def evaluate_github_pr_safety_judgment(
    *,
    fetch_result: GitHubReadOnlyEvidenceFetchResult,
    fetch_receipt: CausalCapabilityReceipt,
    clock: Callable[[], str],
) -> GitHubPrSafetyJudgment:
    """Evaluate read-only GitHub evidence into a bounded PR safety status."""

    if not isinstance(fetch_result, GitHubReadOnlyEvidenceFetchResult):
        raise ValueError("fetch_result must be a GitHubReadOnlyEvidenceFetchResult")
    if not isinstance(fetch_receipt, CausalCapabilityReceipt):
        raise ValueError("fetch_receipt must be a CausalCapabilityReceipt")
    if fetch_receipt.intent != "COLLECT_GITHUB_PR_READ_ONLY_EVIDENCE":
        raise ValueError("fetch_receipt must come from GitHub read-only evidence collection")
    if fetch_receipt.policy_decision is not FabricPolicyDecision.ALLOW_READ_ONLY:
        raise ValueError("fetch_receipt must be read-only")

    judged_at = require_datetime_text(clock(), "judged_at")
    reasons: list[str] = []
    missing = _missing_pr_safety_evidence(fetch_result)
    if missing:
        reasons.extend(f"missing_{item}" for item in missing)
    if fetch_result.partial_failure_reasons:
        reasons.extend(f"partial_failure:{reason}" for reason in fetch_result.partial_failure_reasons)

    pull_request = fetch_result.observed_pull_request
    checks = fetch_result.observed_checks
    if pull_request.get("state") != "open":
        reasons.append("pull_request_not_open")
    if bool(pull_request.get("draft", False)):
        reasons.append("pull_request_is_draft")
    if bool(pull_request.get("merged", False)):
        reasons.append("pull_request_already_merged")
    if pull_request.get("mergeable") is False:
        reasons.append("github_reports_not_mergeable")
    if pull_request.get("mergeable") is None and "pull_request" in fetch_result.fetched_evidence_kinds:
        reasons.append("mergeability_unknown")

    check_conclusions = checks.get("conclusion_counts", {})
    if isinstance(check_conclusions, Mapping):
        failing_conclusions = tuple(
            conclusion
            for conclusion, count in check_conclusions.items()
            if count and conclusion not in {"success", "neutral", "skipped"}
        )
        if failing_conclusions:
            reasons.append("checks_not_passing:" + ",".join(sorted(failing_conclusions)))
    else:
        reasons.append("checks_summary_invalid")

    if missing or fetch_result.partial_failure_reasons or "mergeability_unknown" in reasons:
        status = "needs_evidence"
        required_next_action = "collect_missing_or_fresher_read_only_github_evidence"
        confidence = 0.45
    elif any(
        reason
        for reason in reasons
        if reason
        in {
            "pull_request_not_open",
            "pull_request_is_draft",
            "pull_request_already_merged",
            "github_reports_not_mergeable",
            "checks_summary_invalid",
        }
        or reason.startswith("checks_not_passing:")
    ):
        status = "blocked"
        required_next_action = "resolve_blocking_pr_conditions_before_review_continuation"
        confidence = 0.82
    else:
        status = "ready_for_review"
        required_next_action = "continue_human_or_governed_review_without_auto_merge"
        reasons.append("required_read_only_evidence_present")
        confidence = 0.74

    judgment_hash = _stable_hash(
        {
            "fetch_id": fetch_result.fetch_id,
            "receipt_id": fetch_receipt.receipt_id,
            "status": status,
            "reasons": tuple(reasons),
            "judged_at": judged_at,
        }
    )
    return GitHubPrSafetyJudgment(
        judgment_id=f"github-pr-safety-judgment:{judgment_hash}",
        repo=fetch_result.repo,
        pull_request_number=fetch_result.pull_request_number,
        status=status,
        reasons=tuple(dict.fromkeys(reasons)),
        evidence_refs=tuple(dict.fromkeys((fetch_receipt.receipt_id, *fetch_result.evidence_refs))),
        blocked_actions=fetch_result.blocked_actions,
        required_next_action=required_next_action,
        confidence=confidence,
        merge_authority_granted=False,
        write_authority_granted=False,
        judged_at=judged_at,
    )


def build_github_read_only_evidence_fetch_receipt(
    result: GitHubReadOnlyEvidenceFetchResult,
    *,
    actor_id: str,
    surface_event_id: str,
    occurred_at: str,
) -> CausalCapabilityReceipt:
    """Emit a causal receipt for an executed read-only GitHub evidence fetch."""

    if not isinstance(result, GitHubReadOnlyEvidenceFetchResult):
        raise ValueError("result must be a GitHubReadOnlyEvidenceFetchResult")
    occurred_at = require_datetime_text(occurred_at, "occurred_at")
    actor_id = require_non_empty_text(actor_id, "actor_id")
    surface_event_id = require_non_empty_text(surface_event_id, "surface_event_id")
    receipt_hash = _stable_hash(
        {
            "actor_id": actor_id,
            "fetch_id": result.fetch_id,
            "surface_event_id": surface_event_id,
            "occurred_at": occurred_at,
            "payload_hashes": result.payload_hashes,
        }
    )
    verification_result = (
        "Read-only GitHub evidence collected with partial gaps."
        if result.partial_failure_reasons
        else "Read-only GitHub evidence collected and hash-bound."
    )
    return CausalCapabilityReceipt(
        receipt_id=f"github-read-receipt:{receipt_hash}",
        event_id=result.admission_id,
        actor_id=actor_id,
        surface=GITHUB_WORKROOM_SURFACE,
        intent="COLLECT_GITHUB_PR_READ_ONLY_EVIDENCE",
        target_object=f"github_pull_request:{result.repo}#{result.pull_request_number}",
        risk_class=FabricRiskClass.CLASS_0_OBSERVE,
        evidence_used=result.evidence_refs,
        policy_decision=FabricPolicyDecision.ALLOW_READ_ONLY,
        actions_taken=("performed_get_only_github_reads", "hashed_payloads", "summarized_pr_evidence"),
        actions_blocked=result.blocked_actions,
        assumptions=("Access token scope is limited to oauth:github.read.", "Receipt does not assert merge safety."),
        verification_result=verification_result,
        final_judgment="GitHub read evidence is available for PR safety projection; no mutation performed.",
        memory_update=FabricMemoryDecisionStatus.STORE,
        timestamp=occurred_at,
        partial_failure_reasons=result.partial_failure_reasons,
    )


def build_github_actions_failure_diagnosis_receipt(
    result: GitHubActionsFailureEvidenceFetchResult,
    *,
    diagnosis: GitHubActionsFailureDiagnosis,
    actor_id: str,
    surface_event_id: str,
    occurred_at: str,
) -> CausalCapabilityReceipt:
    """Emit a causal receipt for read-only GitHub Actions failure diagnosis."""

    if not isinstance(result, GitHubActionsFailureEvidenceFetchResult):
        raise ValueError("result must be a GitHubActionsFailureEvidenceFetchResult")
    if not isinstance(diagnosis, GitHubActionsFailureDiagnosis):
        raise ValueError("diagnosis must be a GitHubActionsFailureDiagnosis")
    occurred_at = require_datetime_text(occurred_at, "occurred_at")
    actor_id = require_non_empty_text(actor_id, "actor_id")
    surface_event_id = require_non_empty_text(surface_event_id, "surface_event_id")
    receipt_hash = _stable_hash(
        {
            "actor_id": actor_id,
            "diagnosis_id": diagnosis.diagnosis_id,
            "fetch_id": result.fetch_id,
            "surface_event_id": surface_event_id,
            "occurred_at": occurred_at,
            "payload_hashes": result.payload_hashes,
        }
    )
    verification_result = (
        "Read-only Actions evidence collected with partial gaps."
        if result.partial_failure_reasons
        else "Read-only Actions evidence collected, hash-bound, and diagnosed."
    )
    return CausalCapabilityReceipt(
        receipt_id=f"github-actions-failure-receipt:{receipt_hash}",
        event_id=result.admission_id,
        actor_id=actor_id,
        surface=GITHUB_WORKROOM_SURFACE,
        intent=GITHUB_ACTIONS_FAILURE_INTENT,
        target_object=f"github_actions_run:{result.repo}#{result.workflow_run_id}",
        risk_class=FabricRiskClass.CLASS_0_OBSERVE,
        evidence_used=result.evidence_refs,
        policy_decision=FabricPolicyDecision.ALLOW_READ_ONLY,
        actions_taken=("performed_get_only_github_actions_reads", "hashed_payloads", "diagnosed_failed_run"),
        actions_blocked=result.blocked_actions,
        assumptions=(
            "Access token scope is limited to oauth:github.read.",
            "Diagnosis recommends next steps but does not rerun, cancel, dispatch, comment, or mutate repository state.",
        ),
        verification_result=verification_result,
        final_judgment=diagnosis.failure_summary,
        memory_update=FabricMemoryDecisionStatus.STORE,
        timestamp=occurred_at,
        partial_failure_reasons=result.partial_failure_reasons,
    )


def evaluate_github_actions_failure_diagnosis(
    *,
    fetch_result: GitHubActionsFailureEvidenceFetchResult,
    clock: Callable[[], str],
) -> GitHubActionsFailureDiagnosis:
    """Evaluate read-only GitHub Actions evidence into a bounded diagnosis."""

    if not isinstance(fetch_result, GitHubActionsFailureEvidenceFetchResult):
        raise ValueError("fetch_result must be a GitHubActionsFailureEvidenceFetchResult")
    diagnosed_at = require_datetime_text(clock(), "diagnosed_at")
    reasons: list[str] = []
    suspected_failed_jobs: list[str] = []
    if "workflow_run" not in fetch_result.fetched_evidence_kinds or not fetch_result.observed_workflow_run:
        reasons.append("missing_workflow_run")
    if "jobs" not in fetch_result.fetched_evidence_kinds or not fetch_result.observed_jobs:
        reasons.append("missing_jobs")
    if fetch_result.partial_failure_reasons:
        reasons.extend(f"partial_failure:{reason}" for reason in fetch_result.partial_failure_reasons)

    run_conclusion = str(fetch_result.observed_workflow_run.get("conclusion") or "")
    failed_jobs = tuple(
        job for job in fetch_result.observed_jobs if str(job.get("conclusion") or "") not in {"success", "skipped", "neutral", ""}
    )
    for job in failed_jobs:
        suspected_failed_jobs.append(str(job.get("name") or job.get("job_id") or "unknown_job"))
    if run_conclusion and run_conclusion in {"success", "skipped", "neutral"} and not failed_jobs:
        status = "not_failed"
        failure_summary = "Workflow run is not currently failed based on read-only GitHub evidence."
        recommended_next_action = "no_failure_patch_plan_required"
        confidence = 0.72
        reasons.append("workflow_run_not_failed")
    elif reasons:
        status = "needs_evidence"
        failure_summary = "Actions failure diagnosis needs fresher or more complete run, job, or log evidence."
        recommended_next_action = "collect_missing_or_fresher_actions_evidence"
        confidence = 0.46
    else:
        status = "diagnosed"
        if fetch_result.failed_log_summaries:
            first_log = fetch_result.failed_log_summaries[0]
            first_signal = str(first_log.get("first_failure_signal") or "failed job log captured")
            failure_summary = f"Workflow failed in {', '.join(suspected_failed_jobs)}; first signal: {first_signal}"
            reasons.append("failed_job_log_signal_available")
            confidence = 0.78
        else:
            failure_summary = f"Workflow failed in {', '.join(suspected_failed_jobs)}; failed job logs were not collected."
            reasons.append("failed_jobs_without_logs")
            confidence = 0.62
        recommended_next_action = "prepare_patch_plan_from_failed_job_signal_without_mutating_github"

    if not suspected_failed_jobs:
        suspected_failed_jobs.append("none")
    if not reasons:
        reasons.append("read_only_actions_evidence_evaluated")
    diagnosis_hash = _stable_hash(
        {
            "fetch_id": fetch_result.fetch_id,
            "status": status,
            "reasons": tuple(reasons),
            "suspected_failed_jobs": tuple(suspected_failed_jobs),
            "diagnosed_at": diagnosed_at,
        }
    )
    return GitHubActionsFailureDiagnosis(
        diagnosis_id=f"github-actions-failure-diagnosis:{diagnosis_hash}",
        repo=fetch_result.repo,
        workflow_run_id=fetch_result.workflow_run_id,
        status=status,
        failure_summary=failure_summary,
        suspected_failed_jobs=tuple(dict.fromkeys(suspected_failed_jobs)),
        reasons=tuple(dict.fromkeys(reasons)),
        evidence_refs=tuple(fetch_result.evidence_refs),
        blocked_actions=fetch_result.blocked_actions,
        recommended_next_action=recommended_next_action,
        confidence=confidence,
        write_authority_granted=False,
        diagnosed_at=diagnosed_at,
    )


@dataclass(frozen=True, slots=True)
class GitHubRepoStatusSummary(ContractRecord):
    """Bounded repository status summary from read-only GitHub evidence."""

    summary_id: str
    repo: str
    status: str
    summary: str
    signals: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    recommended_next_action: str
    confidence: float
    write_authority_granted: bool
    summarized_at: str

    def __post_init__(self) -> None:
        for field_name in ("summary_id", "repo", "status", "summary", "recommended_next_action"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.status not in {"summarized", "needs_evidence", "attention_required"}:
            raise ValueError("status must be summarized, needs_evidence, or attention_required")
        for field_name in ("signals", "evidence_refs", "blocked_actions"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for index, value in enumerate(values):
                require_non_empty_text(value, f"{field_name}[{index}]")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise ValueError("confidence must be a number")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "confidence", float(self.confidence))
        if self.write_authority_granted is not False:
            raise ValueError("repository status summary cannot grant write authority")
        object.__setattr__(self, "summarized_at", require_datetime_text(self.summarized_at, "summarized_at"))


def admit_github_repo_status_evidence_collection(
    request: GitHubRepoStatusEvidenceAdmissionRequest,
    *,
    clock: Callable[[], str],
) -> GitHubRepoStatusEvidenceAdmission:
    """Admit a live read-only GitHub repository status evidence plan without execution."""

    admitted_at = require_datetime_text(clock(), "admitted_at")
    identity_hash = _stable_hash(
        {
            "actor_id": request.actor_id,
            "repo": request.repo,
            "requested_evidence_kinds": request.requested_evidence_kinds,
            "requested_at": request.requested_at,
            "surface_event_id": request.surface_event_id,
            "workspace_id": request.workspace_id,
            "max_items_per_kind": request.max_items_per_kind,
        }
    )
    planned_refs = tuple(f"github-live-read://{request.repo}/status/{kind}" for kind in request.requested_evidence_kinds)
    return GitHubRepoStatusEvidenceAdmission(
        admission_id=f"github-repo-status-admission:{identity_hash}",
        capability_id=GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID,
        actor_id=request.actor_id,
        workspace_id=request.workspace_id,
        repo=request.repo,
        requested_evidence_kinds=request.requested_evidence_kinds,
        planned_evidence_refs=planned_refs,
        allowed_tools=_LIVE_READ_ALLOWED_TOOLS,
        allowed_networks=_LIVE_READ_ALLOWED_NETWORKS,
        required_secret_scope=_LIVE_READ_SECRET_SCOPE,
        blocked_actions=_REPO_STATUS_BLOCKED_ACTIONS,
        authority_ref=request.authority_ref,
        policy_decision="allow_read_only_connector_lease",
        solver_outcome="AwaitingEvidence",
        live_connector_read_admitted=True,
        live_connector_call_performed=False,
        write_authority_granted=False,
        max_items_per_kind=request.max_items_per_kind,
        admitted_at=admitted_at,
    )


def evaluate_github_repo_status_summary(
    *,
    fetch_result: GitHubRepoStatusEvidenceFetchResult,
    clock: Callable[[], str],
) -> GitHubRepoStatusSummary:
    """Evaluate read-only repository evidence into a bounded status summary."""

    if not isinstance(fetch_result, GitHubRepoStatusEvidenceFetchResult):
        raise ValueError("fetch_result must be a GitHubRepoStatusEvidenceFetchResult")
    summarized_at = require_datetime_text(clock(), "summarized_at")
    signals: list[str] = []
    if "repository" not in fetch_result.fetched_evidence_kinds or not fetch_result.repository_summary:
        signals.append("missing_repository_metadata")
    if fetch_result.partial_failure_reasons:
        signals.extend(f"partial_failure:{reason}" for reason in fetch_result.partial_failure_reasons)
    failed_runs = tuple(run for run in fetch_result.workflow_runs if str(run.get("conclusion") or "") == "failure")
    open_pr_count = len(fetch_result.open_pull_requests)
    open_issue_count = len(fetch_result.open_issues)
    recent_commit_count = len(fetch_result.recent_commits)
    if failed_runs:
        signals.append(f"failed_workflow_runs:{len(failed_runs)}")
    if open_pr_count:
        signals.append(f"open_pull_requests:{open_pr_count}")
    if open_issue_count:
        signals.append(f"open_issues:{open_issue_count}")
    if recent_commit_count:
        signals.append(f"recent_commits:{recent_commit_count}")
    if not signals:
        signals.append("repository_status_evidence_collected")

    if "missing_repository_metadata" in signals:
        status = "needs_evidence"
        summary = "Repository status summary needs repository metadata before a bounded status judgment."
        recommended_next_action = "collect_repository_metadata"
        confidence = 0.42
    elif failed_runs:
        status = "attention_required"
        summary = f"Repository has {open_pr_count} open pull requests, {open_issue_count} open issues, and {len(failed_runs)} recent failed workflow runs."
        recommended_next_action = "inspect_failed_workflow_run_before_release_or_merge_claims"
        confidence = 0.72
    else:
        status = "summarized"
        summary = f"Repository has {open_pr_count} open pull requests, {open_issue_count} open issues, and {recent_commit_count} recent commits in bounded read-only evidence."
        recommended_next_action = "continue_read_only_project_review_or_select_specific_pr_or_ci_run"
        confidence = 0.68

    summary_hash = _stable_hash(
        {
            "fetch_id": fetch_result.fetch_id,
            "status": status,
            "signals": tuple(signals),
            "summarized_at": summarized_at,
        }
    )
    return GitHubRepoStatusSummary(
        summary_id=f"github-repo-status-summary:{summary_hash}",
        repo=fetch_result.repo,
        status=status,
        summary=summary,
        signals=tuple(dict.fromkeys(signals)),
        evidence_refs=tuple(fetch_result.evidence_refs),
        blocked_actions=fetch_result.blocked_actions,
        recommended_next_action=recommended_next_action,
        confidence=confidence,
        write_authority_granted=False,
        summarized_at=summarized_at,
    )


def build_github_repo_status_summary_receipt(
    result: GitHubRepoStatusEvidenceFetchResult,
    *,
    summary: GitHubRepoStatusSummary,
    actor_id: str,
    surface_event_id: str,
    occurred_at: str,
) -> CausalCapabilityReceipt:
    """Emit a causal receipt for read-only GitHub repository status summary."""

    if not isinstance(result, GitHubRepoStatusEvidenceFetchResult):
        raise ValueError("result must be a GitHubRepoStatusEvidenceFetchResult")
    if not isinstance(summary, GitHubRepoStatusSummary):
        raise ValueError("summary must be a GitHubRepoStatusSummary")
    occurred_at = require_datetime_text(occurred_at, "occurred_at")
    actor_id = require_non_empty_text(actor_id, "actor_id")
    surface_event_id = require_non_empty_text(surface_event_id, "surface_event_id")
    receipt_hash = _stable_hash(
        {
            "actor_id": actor_id,
            "summary_id": summary.summary_id,
            "fetch_id": result.fetch_id,
            "surface_event_id": surface_event_id,
            "occurred_at": occurred_at,
            "payload_hashes": result.payload_hashes,
        }
    )
    verification_result = (
        "Read-only repository status evidence collected with partial gaps."
        if result.partial_failure_reasons
        else "Read-only repository status evidence collected, hash-bound, and summarized."
    )
    return CausalCapabilityReceipt(
        receipt_id=f"github-repo-status-receipt:{receipt_hash}",
        event_id=result.admission_id,
        actor_id=actor_id,
        surface=GITHUB_WORKROOM_SURFACE,
        intent=GITHUB_REPO_STATUS_INTENT,
        target_object=f"github_repository:{result.repo}",
        risk_class=FabricRiskClass.CLASS_0_OBSERVE,
        evidence_used=result.evidence_refs,
        policy_decision=FabricPolicyDecision.ALLOW_READ_ONLY,
        actions_taken=("performed_get_only_github_repo_reads", "hashed_payloads", "summarized_repository_status"),
        actions_blocked=result.blocked_actions,
        assumptions=(
            "Access token scope is limited to oauth:github.read.",
            "Summary cannot create issues, comment, trigger workflows, mutate repository state, or claim release readiness.",
        ),
        verification_result=verification_result,
        final_judgment=summary.summary,
        memory_update=FabricMemoryDecisionStatus.STORE,
        timestamp=occurred_at,
        partial_failure_reasons=result.partial_failure_reasons,
    )


def build_pr_safety_projection_from_github_fetch_receipt(
    *,
    fetch_receipt: CausalCapabilityReceipt,
    actor_id: str,
    workspace_id: str,
    repo: str,
    pull_request_number: int,
    surface_event_id: str,
    occurred_at: str,
    clock: Callable[[], str],
) -> GitHubPrSafetyWorkroomProjection:
    """Feed completed GitHub read receipt evidence into the PR safety projection."""

    if not isinstance(fetch_receipt, CausalCapabilityReceipt):
        raise ValueError("fetch_receipt must be a CausalCapabilityReceipt")
    if fetch_receipt.intent != "COLLECT_GITHUB_PR_READ_ONLY_EVIDENCE":
        raise ValueError("fetch_receipt must come from GitHub read-only evidence collection")
    if fetch_receipt.policy_decision is not FabricPolicyDecision.ALLOW_READ_ONLY:
        raise ValueError("fetch_receipt must be read-only")
    evidence_refs = tuple(dict.fromkeys((fetch_receipt.receipt_id, *fetch_receipt.evidence_used)))
    request = GitHubPrSafetyWorkroomRequest(
        actor_id=actor_id,
        workspace_id=workspace_id,
        repo=repo,
        pull_request_number=pull_request_number,
        surface_event_id=surface_event_id,
        occurred_at=occurred_at,
        evidence_refs=evidence_refs,
        trace_ref=fetch_receipt.receipt_id,
        assumptions=(
            "GitHub read evidence receipt was produced by connector.github.read.",
            "Projection still cannot merge, deploy, comment, or mutate repository state.",
        ),
        metadata={"source_fetch_receipt_id": fetch_receipt.receipt_id},
    )
    return build_github_pr_safety_workroom_projection(request, clock=clock)


def admit_github_read_only_evidence_collection(
    request: GitHubReadOnlyEvidenceAdmissionRequest,
    *,
    clock: Callable[[], str],
) -> GitHubReadOnlyEvidenceAdmission:
    """Admit a live read-only GitHub evidence collection plan without execution."""

    admitted_at = require_datetime_text(clock(), "admitted_at")
    identity_hash = _stable_hash(
        {
            "actor_id": request.actor_id,
            "repo": request.repo,
            "pull_request_number": request.pull_request_number,
            "requested_evidence_kinds": request.requested_evidence_kinds,
            "requested_at": request.requested_at,
            "surface_event_id": request.surface_event_id,
            "workspace_id": request.workspace_id,
        }
    )
    planned_refs = tuple(
        f"github-live-read://{request.repo}/pulls/{request.pull_request_number}/{kind}"
        for kind in request.requested_evidence_kinds
    )
    return GitHubReadOnlyEvidenceAdmission(
        admission_id=f"github-read-admission:{identity_hash}",
        capability_id=GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID,
        actor_id=request.actor_id,
        workspace_id=request.workspace_id,
        repo=request.repo,
        pull_request_number=request.pull_request_number,
        requested_evidence_kinds=request.requested_evidence_kinds,
        planned_evidence_refs=planned_refs,
        allowed_tools=_LIVE_READ_ALLOWED_TOOLS,
        allowed_networks=_LIVE_READ_ALLOWED_NETWORKS,
        required_secret_scope=_LIVE_READ_SECRET_SCOPE,
        blocked_actions=_BLOCKED_ACTIONS,
        authority_ref=request.authority_ref,
        policy_decision="allow_read_only_connector_lease",
        solver_outcome="AwaitingEvidence",
        live_connector_read_admitted=True,
        live_connector_call_performed=False,
        write_authority_granted=False,
        admitted_at=admitted_at,
    )


def admit_github_actions_failure_evidence_collection(
    request: GitHubActionsFailureEvidenceAdmissionRequest,
    *,
    clock: Callable[[], str],
) -> GitHubActionsFailureEvidenceAdmission:
    """Admit a live read-only GitHub Actions failure evidence plan without execution."""

    admitted_at = require_datetime_text(clock(), "admitted_at")
    identity_hash = _stable_hash(
        {
            "actor_id": request.actor_id,
            "repo": request.repo,
            "workflow_run_id": request.workflow_run_id,
            "requested_evidence_kinds": request.requested_evidence_kinds,
            "requested_at": request.requested_at,
            "surface_event_id": request.surface_event_id,
            "workspace_id": request.workspace_id,
            "max_failed_job_logs": request.max_failed_job_logs,
        }
    )
    planned_refs = tuple(
        f"github-live-read://{request.repo}/actions/runs/{request.workflow_run_id}/{kind}"
        for kind in request.requested_evidence_kinds
    )
    return GitHubActionsFailureEvidenceAdmission(
        admission_id=f"github-actions-failure-admission:{identity_hash}",
        capability_id=GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID,
        actor_id=request.actor_id,
        workspace_id=request.workspace_id,
        repo=request.repo,
        workflow_run_id=request.workflow_run_id,
        requested_evidence_kinds=request.requested_evidence_kinds,
        planned_evidence_refs=planned_refs,
        allowed_tools=_LIVE_READ_ALLOWED_TOOLS,
        allowed_networks=_LIVE_READ_ALLOWED_NETWORKS,
        required_secret_scope=_LIVE_READ_SECRET_SCOPE,
        blocked_actions=_ACTIONS_FAILURE_BLOCKED_ACTIONS,
        authority_ref=request.authority_ref,
        policy_decision="allow_read_only_connector_lease",
        solver_outcome="AwaitingEvidence",
        live_connector_read_admitted=True,
        live_connector_call_performed=False,
        write_authority_granted=False,
        max_failed_job_logs=request.max_failed_job_logs,
        admitted_at=admitted_at,
    )


def build_github_pr_safety_workroom_projection(
    request: GitHubPrSafetyWorkroomRequest,
    *,
    clock: Callable[[], str],
) -> GitHubPrSafetyWorkroomProjection:
    """Build the governed read-only PR safety projection for the workroom."""

    decided_at = require_datetime_text(clock(), "decided_at")
    target_object = f"github_pull_request:{request.repo}#{request.pull_request_number}"
    identity_seed = {
        "actor_id": request.actor_id,
        "intent": GITHUB_PR_SAFETY_INTENT,
        "occurred_at": request.occurred_at,
        "repo": request.repo,
        "surface_event_id": request.surface_event_id,
        "workspace_id": request.workspace_id,
        "pull_request_number": request.pull_request_number,
    }
    identity_hash = _stable_hash(identity_seed)
    event_id = f"uge:{identity_hash}"

    event = UniversalGovernedEvent(
        event_id=event_id,
        surface_event_id=request.surface_event_id,
        actor_id=request.actor_id,
        workspace_id=request.workspace_id,
        surface=GITHUB_WORKROOM_SURFACE,
        channel_id=request.channel_id,
        intent=GITHUB_PR_SAFETY_INTENT,
        target_object=target_object,
        requested_action="inspect_and_recommend_only",
        context_refs=request.evidence_refs,
        risk_class=FabricRiskClass.CLASS_1_PREPARE,
        authority_ref=request.authority_ref,
        occurred_at=request.occurred_at,
        trace_ref=request.trace_ref,
        metadata={
            "repo": request.repo,
            "pull_request_number": request.pull_request_number,
            "projection": GITHUB_PR_SAFETY_CAPABILITY_ID,
            **dict(request.metadata or {}),
        },
    )
    compilation = SymbolicEventCompilation(
        compilation_id=f"compile:{identity_hash}",
        event_id=event.event_id,
        interpreted_intent=GITHUB_PR_SAFETY_INTENT,
        target_kind="github_pull_request",
        requested_action="inspect_diff_ci_policy_and_recommend",
        blocked_actions=_BLOCKED_ACTIONS,
        evidence_needed=_REQUIRED_EVIDENCE,
        assumptions=request.assumptions,
        compiled_at=decided_at,
    )
    authority = AuthorityResolution(
        resolution_id=f"authority:{identity_hash}",
        event_id=event.event_id,
        actor_id=request.actor_id,
        workspace_id=request.workspace_id,
        surface=GITHUB_WORKROOM_SURFACE,
        channel_id=request.channel_id,
        target_object=target_object,
        decision=FabricPolicyDecision.ALLOW_DRAFT_ONLY,
        allowed_scope=f"{request.workspace_id}:{request.repo}:pull_request:{request.pull_request_number}:read_only",
        allowed_actions=("inspect_pr_evidence", "draft_merge_safety_recommendation", "emit_receipt"),
        blocked_actions=_BLOCKED_ACTIONS,
        reason="Local workroom authority permits read-only PR safety preparation only.",
        resolved_at=decided_at,
    )
    policy = RiskPolicyResult(
        policy_result_id=f"policy:{identity_hash}",
        event_id=event.event_id,
        risk_class=FabricRiskClass.CLASS_1_PREPARE,
        decision=FabricPolicyDecision.ALLOW_DRAFT_ONLY,
        allowed_tools=_ALLOWED_TOOLS,
        blocked_actions=_BLOCKED_ACTIONS,
        required_approvals=("explicit_human_approval_required_for_merge_or_deploy",),
        policy_refs=("policy.github.pr_review.local_read_only", "policy.fabric.risk_tiers.v2"),
        reason="Class 1 preparation may inspect and recommend but cannot mutate GitHub state.",
        decided_at=decided_at,
    )
    passport = UniversalCapabilityPassport(
        passport_id=GITHUB_PR_SAFETY_CAPABILITY_ID,
        name="GitHub Pull Request Safety Review",
        domain="software_governance",
        inputs=("repo", "pull_request_number", "actor_id", "evidence_refs"),
        outputs=("merge_safety_judgment", "risk_summary", "recommendation", "receipt"),
        required_evidence=_REQUIRED_EVIDENCE,
        allowed_tools=_ALLOWED_TOOLS,
        blocked_actions=_BLOCKED_ACTIONS,
        risk_class=FabricRiskClass.CLASS_1_PREPARE,
        verification_rules=(
            "no_merge_safety_judgment_without_ci_status",
            "no_merge_recommendation_without_diff_or_changed_files",
            "no_completion_claim_without_causal_receipt",
        ),
        receipt_fields=(
            "actor",
            "repo",
            "pull_request",
            "evidence_used",
            "policy_decision",
            "actions_taken",
            "actions_blocked",
        ),
        memory_policy="Store receipt metadata only; do not store private review discussion.",
    )
    episode = CausalEpisodePlan(
        episode_id=f"episode:{identity_hash}",
        event_id=event.event_id,
        capability_id=GITHUB_PR_SAFETY_CAPABILITY_ID,
        steps=_build_episode_steps(event, compilation, policy, request.evidence_refs),
        planned_at=decided_at,
    )
    receipt = CausalCapabilityReceipt(
        receipt_id=f"receipt:{identity_hash}",
        event_id=event.event_id,
        actor_id=request.actor_id,
        surface=GITHUB_WORKROOM_SURFACE,
        intent=GITHUB_PR_SAFETY_INTENT,
        target_object=target_object,
        risk_class=FabricRiskClass.CLASS_1_PREPARE,
        evidence_used=request.evidence_refs,
        policy_decision=FabricPolicyDecision.ALLOW_DRAFT_ONLY,
        actions_taken=("compiled_pr_safety_request", "planned_read_only_review", "blocked_mutating_actions"),
        actions_blocked=_BLOCKED_ACTIONS,
        assumptions=request.assumptions,
        verification_result="Projection verified as read-only; live PR evidence inspection is not claimed.",
        final_judgment="Awaiting live PR evidence inspection before merge safety judgment.",
        memory_update=FabricMemoryDecisionStatus.STORE,
        timestamp=decided_at,
        partial_failure_reasons=("live_github_evidence_not_collected_by_projection",),
    )
    memory_gate = MemoryGateDecision(
        decision_id=f"memory:{identity_hash}",
        event_id=event.event_id,
        receipt_id=receipt.receipt_id,
        memory_class=FabricMemoryClass.RECEIPT,
        status=FabricMemoryDecisionStatus.STORE,
        scope_ref=f"project:{request.workspace_id}:{request.repo}",
        validated=True,
        durable=True,
        sensitivity=FabricSensitivity.OPERATIONAL,
        reasons=("Receipt metadata is durable operational evidence; private discussion is excluded.",),
        decided_at=decided_at,
        can_delete=True,
        audit_ref=receipt.receipt_id,
    )
    return GitHubPrSafetyWorkroomProjection(
        event=event,
        compilation=compilation,
        authority=authority,
        policy=policy,
        passport=passport,
        episode=episode,
        receipt=receipt,
        memory_gate=memory_gate,
    )


def build_github_pr_safety_workroom_read_model(
    *,
    actor_id: str,
    workspace_id: str,
    repo: str,
    pull_request_number: int,
    surface_event_id: str,
    occurred_at: str,
    evidence_refs: tuple[str, ...],
    clock: Callable[[], str],
    channel_id: str = "",
    trace_ref: str = "",
    authority_ref: str = "policy.github.pr_review.local_read_only",
) -> dict[str, Any]:
    """Build the operator Workroom read model without live GitHub effects."""

    generated_at = require_datetime_text(clock(), "generated_at")
    read_model: dict[str, Any] = {
        "schema_ref": "urn:mullusi:read-model:github-operations-pr-safety-workroom:1",
        "generated_at": generated_at,
        "capability_id": GITHUB_PR_SAFETY_CAPABILITY_ID,
        "surface": GITHUB_WORKROOM_SURFACE,
        "actor_id": require_non_empty_text(actor_id, "actor_id"),
        "workspace_id": require_non_empty_text(workspace_id, "workspace_id"),
        "repo": require_non_empty_text(repo, "repo"),
        "pull_request_number": pull_request_number,
        "required_evidence": list(_REQUIRED_EVIDENCE),
        "evidence_refs": list(evidence_refs),
        "evidence_ref_count": len(evidence_refs),
        "allowed_tools": list(_ALLOWED_TOOLS),
        "blocked_actions": list(_BLOCKED_ACTIONS),
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "raw_tool_surface_exposed": False,
        "governed": True,
        "execution_allowed": False,
    }
    live_read_admission = admit_github_read_only_evidence_collection(
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id=actor_id,
            workspace_id=workspace_id,
            repo=repo,
            pull_request_number=pull_request_number,
            requested_evidence_kinds=("pull_request", "diff", "checks", "changed_files"),
            requested_at=generated_at,
            surface_event_id=surface_event_id,
        ),
        clock=clock,
    )
    read_model["live_read_admission"] = live_read_admission.to_json_dict()
    if not evidence_refs:
        return {
            **read_model,
            "status": "awaiting_evidence",
            "outcome": "AwaitingEvidence",
            "projection": None,
            "receipt": None,
            "missing_evidence": list(_REQUIRED_EVIDENCE),
        }

    request = GitHubPrSafetyWorkroomRequest(
        actor_id=actor_id,
        workspace_id=workspace_id,
        repo=repo,
        pull_request_number=pull_request_number,
        surface_event_id=surface_event_id,
        occurred_at=occurred_at,
        evidence_refs=evidence_refs,
        channel_id=channel_id,
        trace_ref=trace_ref,
        authority_ref=authority_ref,
    )
    projection = build_github_pr_safety_workroom_projection(request, clock=clock)
    return {
        **read_model,
        "status": "projection_ready",
        "outcome": "AwaitingEvidence",
        "projection": projection.to_json_dict(),
        "receipt": projection.receipt.to_json_dict(),
        "missing_evidence": [],
    }


def build_github_actions_failure_workroom_read_model(
    *,
    actor_id: str,
    workspace_id: str,
    repo: str,
    workflow_run_id: int,
    surface_event_id: str,
    occurred_at: str,
    clock: Callable[[], str],
    requested_evidence_kinds: tuple[str, ...] = ("workflow_run", "jobs", "failed_job_logs"),
) -> dict[str, Any]:
    """Build the operator Workroom read model for Actions failure diagnosis."""

    generated_at = require_datetime_text(clock(), "generated_at")
    admission = admit_github_actions_failure_evidence_collection(
        GitHubActionsFailureEvidenceAdmissionRequest(
            actor_id=actor_id,
            workspace_id=workspace_id,
            repo=repo,
            workflow_run_id=workflow_run_id,
            requested_evidence_kinds=requested_evidence_kinds,
            requested_at=occurred_at,
            surface_event_id=surface_event_id,
        ),
        clock=clock,
    )
    passport = UniversalCapabilityPassport(
        passport_id=GITHUB_ACTIONS_FAILURE_CAPABILITY_ID,
        name="GitHub Actions Failure Diagnosis",
        domain="software_governance",
        inputs=("repo", "workflow_run_id", "actor_id", "requested_evidence_kinds"),
        outputs=("failure_summary", "suspected_failed_jobs", "recommended_next_action", "receipt"),
        required_evidence=("github_actions_workflow_run", "github_actions_jobs", "failed_job_log_digest"),
        allowed_tools=("github.read.workflow_run", "github.read.workflow_jobs", "github.read.job_logs"),
        blocked_actions=_ACTIONS_FAILURE_BLOCKED_ACTIONS,
        risk_class=FabricRiskClass.CLASS_0_OBSERVE,
        verification_rules=(
            "no_failure_diagnosis_without_workflow_run_and_jobs",
            "no_log_claim_without_hash_bound_log_digest",
            "no_github_mutation_from_diagnosis",
        ),
        receipt_fields=("actor", "repo", "workflow_run", "evidence_used", "diagnosis", "actions_blocked"),
        memory_policy="Store receipt metadata and bounded log signals only; do not store raw full job logs.",
    )
    return {
        "schema_ref": "urn:mullusi:read-model:github-operations-actions-failure-workroom:1",
        "generated_at": generated_at,
        "capability_id": GITHUB_ACTIONS_FAILURE_CAPABILITY_ID,
        "surface": GITHUB_WORKROOM_SURFACE,
        "actor_id": require_non_empty_text(actor_id, "actor_id"),
        "workspace_id": require_non_empty_text(workspace_id, "workspace_id"),
        "repo": require_non_empty_text(repo, "repo"),
        "workflow_run_id": workflow_run_id,
        "status": "awaiting_evidence",
        "outcome": "AwaitingEvidence",
        "required_evidence": list(passport.required_evidence),
        "allowed_tools": list(passport.allowed_tools),
        "blocked_actions": list(_ACTIONS_FAILURE_BLOCKED_ACTIONS),
        "live_read_admission": admission.to_json_dict(),
        "passport": passport.to_json_dict(),
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "raw_tool_surface_exposed": False,
        "governed": True,
        "execution_allowed": False,
    }


def build_github_repo_status_workroom_read_model(
    *,
    actor_id: str,
    workspace_id: str,
    repo: str,
    surface_event_id: str,
    occurred_at: str,
    clock: Callable[[], str],
    requested_evidence_kinds: tuple[str, ...] = (
        "repository",
        "recent_commits",
        "open_pull_requests",
        "open_issues",
        "workflow_runs",
    ),
    max_items_per_kind: int = 10,
) -> dict[str, Any]:
    """Build the operator Workroom read model for repository status summary."""

    generated_at = require_datetime_text(clock(), "generated_at")
    admission = admit_github_repo_status_evidence_collection(
        GitHubRepoStatusEvidenceAdmissionRequest(
            actor_id=actor_id,
            workspace_id=workspace_id,
            repo=repo,
            requested_evidence_kinds=requested_evidence_kinds,
            requested_at=occurred_at,
            surface_event_id=surface_event_id,
            max_items_per_kind=max_items_per_kind,
        ),
        clock=clock,
    )
    passport = UniversalCapabilityPassport(
        passport_id=GITHUB_REPO_STATUS_CAPABILITY_ID,
        name="GitHub Repository Status Summary",
        domain="software_governance",
        inputs=("repo", "actor_id", "requested_evidence_kinds"),
        outputs=("repository_summary", "status_signals", "recommended_next_action", "receipt"),
        required_evidence=("github_repository_metadata", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs"),
        allowed_tools=("github.read.repository", "github.read.commits", "github.read.pull_requests", "github.read.issues", "github.read.workflow_runs"),
        blocked_actions=_REPO_STATUS_BLOCKED_ACTIONS,
        risk_class=FabricRiskClass.CLASS_0_OBSERVE,
        verification_rules=(
            "no_repository_status_without_repository_metadata",
            "no_release_readiness_claim_from_summary_only",
            "no_github_mutation_from_status_summary",
        ),
        receipt_fields=("actor", "repo", "evidence_used", "summary", "actions_blocked"),
        memory_policy="Store receipt metadata and bounded status signals only; do not store raw issue or commit bodies.",
    )
    return {
        "schema_ref": "urn:mullusi:read-model:github-operations-repo-status-workroom:1",
        "generated_at": generated_at,
        "capability_id": GITHUB_REPO_STATUS_CAPABILITY_ID,
        "surface": GITHUB_WORKROOM_SURFACE,
        "actor_id": require_non_empty_text(actor_id, "actor_id"),
        "workspace_id": require_non_empty_text(workspace_id, "workspace_id"),
        "repo": require_non_empty_text(repo, "repo"),
        "status": "awaiting_evidence",
        "outcome": "AwaitingEvidence",
        "required_evidence": list(passport.required_evidence),
        "allowed_tools": list(passport.allowed_tools),
        "blocked_actions": list(_REPO_STATUS_BLOCKED_ACTIONS),
        "live_read_admission": admission.to_json_dict(),
        "passport": passport.to_json_dict(),
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "raw_tool_surface_exposed": False,
        "governed": True,
        "execution_allowed": False,
    }


def render_github_pr_safety_workroom_html(read_model: Mapping[str, Any]) -> str:
    """Render the browser-facing operator Workroom panel."""

    repo = _html(read_model.get("repo", ""))
    pull_request_number = _html(str(read_model.get("pull_request_number", "")))
    status = _html(read_model.get("status", "awaiting_evidence"))
    outcome = _html(read_model.get("outcome", "AwaitingEvidence"))
    evidence_refs = "\n".join(str(ref) for ref in read_model.get("evidence_refs", ()))
    blocked_actions = "".join(f"<li>{_html(action)}</li>" for action in read_model.get("blocked_actions", ()))
    required_evidence = "".join(f"<li>{_html(item)}</li>" for item in read_model.get("required_evidence", ()))
    receipt = read_model.get("receipt") or {}
    receipt_id = _html(receipt.get("receipt_id", "none") if isinstance(receipt, Mapping) else "none")
    judgment = _html(receipt.get("final_judgment", "Awaiting evidence") if isinstance(receipt, Mapping) else "Awaiting evidence")
    github_call_allowed = str(read_model.get("effect_boundary", {}).get("github_call_allowed", False)).lower()
    mutation_allowed = str(read_model.get("effect_boundary", {}).get("pull_request_mutation_allowed", False)).lower()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullusi GitHub Operations Workroom</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #17202a; background: #f7f9fb; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section, form {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
    label {{ display: block; font-weight: 650; margin-top: .75rem; }}
    input, textarea {{ width: 100%; box-sizing: border-box; margin-top: .25rem; padding: .55rem; border: 1px solid #aeb8c7; border-radius: 6px; }}
    textarea {{ min-height: 7rem; }}
    button {{ margin-top: .9rem; padding: .55rem .85rem; border: 1px solid #1f5f9f; border-radius: 6px; background: #1f5f9f; color: #fff; font-weight: 700; }}
    pre {{ overflow: auto; background: #0f1720; color: #e8eef7; padding: .85rem; border-radius: 6px; min-height: 4rem; }}
    dl {{ display: grid; grid-template-columns: 190px 1fr; gap: .5rem 1rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; }}
    code {{ background: #eef2f6; padding: .15rem .35rem; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Mullusi GitHub Operations Workroom</h1>
  <section>
    <dl>
      <dt>Status</dt><dd><code>{status}</code></dd>
      <dt>Outcome</dt><dd><code>{outcome}</code></dd>
      <dt>Repository</dt><dd>{repo}</dd>
      <dt>Pull request</dt><dd>{pull_request_number}</dd>
      <dt>Receipt</dt><dd><code>{receipt_id}</code></dd>
      <dt>GitHub call allowed</dt><dd><code>{github_call_allowed}</code></dd>
      <dt>PR mutation allowed</dt><dd><code>{mutation_allowed}</code></dd>
      <dt>Judgment</dt><dd>{judgment}</dd>
    </dl>
  </section>
  <form method="get" action="/operator/github-operations/pr-safety">
    <label>Repository <input name="repo" value="{repo}"></label>
    <label>Pull request <input name="pull_request_number" value="{pull_request_number}" inputmode="numeric"></label>
    <label>Evidence refs <textarea name="evidence_refs">{_html(evidence_refs)}</textarea></label>
    <button type="submit">Preview</button>
  </form>
  <form id="github-live-read-form">
    <label>GitHub read token <input id="github-read-token" name="access_token" type="password" autocomplete="off"></label>
    <input id="github-live-repo" name="repo" type="hidden" value="{repo}">
    <input id="github-live-pr" name="pull_request_number" type="hidden" value="{pull_request_number}">
    <button type="submit">Read Evidence</button>
  </form>
  <section>
    <h2>Live Read Result</h2>
    <pre id="github-live-read-result">Awaiting read-only evidence execution.</pre>
  </section>
  <section>
    <h2>Required Evidence</h2>
    <ul>{required_evidence}</ul>
  </section>
  <section>
    <h2>Blocked Actions</h2>
    <ul>{blocked_actions}</ul>
  </section>
</main>
<script>
const liveReadForm = document.getElementById("github-live-read-form");
const liveReadResult = document.getElementById("github-live-read-result");
liveReadForm.addEventListener("submit", async (event) => {{
  event.preventDefault();
  liveReadResult.textContent = "Running read-only GitHub evidence collection...";
  const tokenInput = document.getElementById("github-read-token");
  const payload = {{
    repo: document.getElementById("github-live-repo").value,
    pull_request_number: Number(document.getElementById("github-live-pr").value),
    requested_evidence_kinds: ["pull_request", "diff", "checks", "changed_files"],
    access_token: tokenInput.value
  }};
  tokenInput.value = "";
  try {{
    const response = await fetch("/operator/github-operations/pr-safety/read-evidence", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify(payload)
    }});
    const result = await response.json();
    liveReadResult.textContent = JSON.stringify(result, null, 2);
  }} catch (error) {{
    liveReadResult.textContent = JSON.stringify({{
      governed: true,
      error_code: "github_live_read_ui_failed",
      error: String(error)
    }}, null, 2);
  }}
}});
</script>
</body>
</html>"""


def render_github_actions_failure_workroom_html(read_model: Mapping[str, Any]) -> str:
    """Render the browser-facing Actions failure diagnosis panel."""

    repo = _html(read_model.get("repo", ""))
    workflow_run_id = _html(str(read_model.get("workflow_run_id", "")))
    status = _html(read_model.get("status", "awaiting_evidence"))
    outcome = _html(read_model.get("outcome", "AwaitingEvidence"))
    blocked_actions = "".join(f"<li>{_html(action)}</li>" for action in read_model.get("blocked_actions", ()))
    required_evidence = "".join(f"<li>{_html(item)}</li>" for item in read_model.get("required_evidence", ()))
    github_call_allowed = str(read_model.get("effect_boundary", {}).get("github_call_allowed", False)).lower()
    mutation_allowed = str(read_model.get("effect_boundary", {}).get("repository_mutation_allowed", False)).lower()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullusi GitHub Actions Failure Diagnosis</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #17202a; background: #f7f9fb; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section, form {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
    label {{ display: block; font-weight: 650; margin-top: .75rem; }}
    input {{ width: 100%; box-sizing: border-box; margin-top: .25rem; padding: .55rem; border: 1px solid #aeb8c7; border-radius: 6px; }}
    button {{ margin-top: .9rem; padding: .55rem .85rem; border: 1px solid #1f5f9f; border-radius: 6px; background: #1f5f9f; color: #fff; font-weight: 700; }}
    pre {{ overflow: auto; background: #0f1720; color: #e8eef7; padding: .85rem; border-radius: 6px; min-height: 4rem; }}
    dl {{ display: grid; grid-template-columns: 210px 1fr; gap: .5rem 1rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; }}
    code {{ background: #eef2f6; padding: .15rem .35rem; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Mullusi GitHub Actions Failure Diagnosis</h1>
  <section>
    <dl>
      <dt>Status</dt><dd><code>{status}</code></dd>
      <dt>Outcome</dt><dd><code>{outcome}</code></dd>
      <dt>Repository</dt><dd>{repo}</dd>
      <dt>Workflow run</dt><dd>{workflow_run_id}</dd>
      <dt>GitHub call allowed</dt><dd><code>{github_call_allowed}</code></dd>
      <dt>Repository mutation allowed</dt><dd><code>{mutation_allowed}</code></dd>
    </dl>
  </section>
  <form method="get" action="/operator/github-operations/actions-failure">
    <label>Repository <input name="repo" value="{repo}"></label>
    <label>Workflow run id <input name="workflow_run_id" value="{workflow_run_id}" inputmode="numeric"></label>
    <button type="submit">Preview</button>
  </form>
  <form id="github-actions-read-form">
    <label>GitHub read token <input id="github-actions-read-token" name="access_token" type="password" autocomplete="off"></label>
    <input id="github-actions-repo" name="repo" type="hidden" value="{repo}">
    <input id="github-actions-run" name="workflow_run_id" type="hidden" value="{workflow_run_id}">
    <button type="submit">Diagnose Failure</button>
  </form>
  <section>
    <h2>Diagnosis Result</h2>
    <pre id="github-actions-read-result">Awaiting read-only Actions evidence execution.</pre>
  </section>
  <section>
    <h2>Required Evidence</h2>
    <ul>{required_evidence}</ul>
  </section>
  <section>
    <h2>Blocked Actions</h2>
    <ul>{blocked_actions}</ul>
  </section>
</main>
<script>
const actionsReadForm = document.getElementById("github-actions-read-form");
const actionsReadResult = document.getElementById("github-actions-read-result");
actionsReadForm.addEventListener("submit", async (event) => {{
  event.preventDefault();
  actionsReadResult.textContent = "Running read-only GitHub Actions failure diagnosis...";
  const tokenInput = document.getElementById("github-actions-read-token");
  const payload = {{
    repo: document.getElementById("github-actions-repo").value,
    workflow_run_id: Number(document.getElementById("github-actions-run").value),
    requested_evidence_kinds: ["workflow_run", "jobs", "failed_job_logs"],
    access_token: tokenInput.value
  }};
  tokenInput.value = "";
  try {{
    const response = await fetch("/operator/github-operations/actions-failure/read-evidence", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify(payload)
    }});
    const result = await response.json();
    actionsReadResult.textContent = JSON.stringify(result, null, 2);
  }} catch (error) {{
    actionsReadResult.textContent = JSON.stringify({{
      governed: true,
      error_code: "github_actions_failure_ui_failed",
      error: String(error)
    }}, null, 2);
  }}
}});
</script>
</body>
</html>"""


def _build_episode_steps(
    event: UniversalGovernedEvent,
    compilation: SymbolicEventCompilation,
    policy: RiskPolicyResult,
    evidence_refs: tuple[str, ...],
) -> tuple[CausalEpisodeStep, ...]:
    reason_by_stage = {
        CausalEpisodeStage.CAUSE: "Actor requested PR merge-safety inspection through the workroom.",
        CausalEpisodeStage.INTERPRETATION: "Request compiled to REVIEW_PR_MERGE_SAFETY.",
        CausalEpisodeStage.CONSTRAINT: "Policy allows draft/read-only preparation and blocks GitHub mutation.",
        CausalEpisodeStage.EVIDENCE: "Evidence references are bound but not live-fetched by this projection.",
        CausalEpisodeStage.OPTIONS: "Available options are explain, recommend, or request missing evidence.",
        CausalEpisodeStage.DECISION: "Choose read-only preparation and receipt emission.",
        CausalEpisodeStage.ACTION: "Create governed projection without connector writes.",
        CausalEpisodeStage.CONSEQUENCE: "No repository, PR, branch, deployment, or comment state changes.",
        CausalEpisodeStage.RECEIPT: "Emit causal receipt with evidence gap and blocked actions.",
        CausalEpisodeStage.MEMORY_GATE: "Store receipt metadata only under project scope.",
    }
    steps: list[CausalEpisodeStep] = []
    for stage in CAUSAL_EPISODE_STAGE_ORDER:
        input_refs: tuple[str, ...] = (event.event_id,)
        if stage is CausalEpisodeStage.INTERPRETATION:
            input_refs = (event.event_id, compilation.compilation_id)
        if stage is CausalEpisodeStage.CONSTRAINT:
            input_refs = (event.event_id, policy.policy_result_id)
        if stage is CausalEpisodeStage.EVIDENCE:
            input_refs = evidence_refs
        steps.append(
            CausalEpisodeStep(
                stage=stage,
                status="planned",
                input_refs=input_refs,
                output_refs=(f"{event.event_id}:{stage.value}",),
                reason=reason_by_stage[stage],
            )
        )
    return tuple(steps)


def render_github_repo_status_workroom_html(read_model: Mapping[str, Any]) -> str:
    """Render the repository status operator Workroom panel."""

    repo = _html(read_model.get("repo", ""))
    status = _html(read_model.get("status", "awaiting_evidence"))
    outcome = _html(read_model.get("outcome", "AwaitingEvidence"))
    blocked_actions = "".join(f"<li>{_html(action)}</li>" for action in read_model.get("blocked_actions", ()))
    required_evidence = "".join(f"<li>{_html(item)}</li>" for item in read_model.get("required_evidence", ()))
    github_call_allowed = str(read_model.get("effect_boundary", {}).get("github_call_allowed", False)).lower()
    mutation_allowed = str(read_model.get("effect_boundary", {}).get("repository_mutation_allowed", False)).lower()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullusi GitHub Repository Status Workroom</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #17202a; background: #f7f9fb; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section, form {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
    label {{ display: block; font-weight: 650; margin-top: .75rem; }}
    input {{ width: 100%; box-sizing: border-box; margin-top: .25rem; padding: .55rem; border: 1px solid #aeb8c7; border-radius: 6px; }}
    button {{ margin-top: .9rem; padding: .55rem .85rem; border: 1px solid #1f5f9f; border-radius: 6px; background: #1f5f9f; color: #fff; font-weight: 700; }}
    pre {{ overflow: auto; background: #0f1720; color: #e8eef7; padding: .85rem; border-radius: 6px; min-height: 4rem; }}
    dl {{ display: grid; grid-template-columns: 190px 1fr; gap: .5rem 1rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; }}
    code {{ background: #eef2f6; padding: .15rem .35rem; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Mullusi GitHub Repository Status Workroom</h1>
  <section>
    <dl>
      <dt>Repository</dt><dd><code>{repo}</code></dd>
      <dt>Status</dt><dd>{status}</dd>
      <dt>Outcome</dt><dd>{outcome}</dd>
      <dt>GitHub call allowed now</dt><dd>{github_call_allowed}</dd>
      <dt>Repository mutation allowed</dt><dd>{mutation_allowed}</dd>
    </dl>
  </section>
  <form method="get" action="/operator/github-operations/repo-status">
    <label>Repository <input name="repo" value="{repo}"></label>
    <button type="submit">Preview Governed Status Path</button>
  </form>
  <section>
    <h2>Required Evidence</h2>
    <ul>{required_evidence}</ul>
  </section>
  <section>
    <h2>Blocked Actions</h2>
    <ul>{blocked_actions}</ul>
  </section>
  <section>
    <h2>Live Read Execution</h2>
    <form id="repo-status-read">
      <label>Access token <input name="access_token" type="password" autocomplete="off"></label>
      <button type="submit">Collect Read-Only Repository Status Evidence</button>
    </form>
    <pre id="repo-status-output">Awaiting explicit local token input. No token is persisted or rendered.</pre>
  </section>
</main>
<script>
document.getElementById("repo-status-read").addEventListener("submit", async (event) => {{
  event.preventDefault();
  const tokenInput = event.target.querySelector('input[name="access_token"]');
  const form = new FormData(event.target);
  const payload = {{
    repo: "{repo}",
    access_token: tokenInput.value,
    requested_evidence_kinds: ["repository", "recent_commits", "open_pull_requests", "open_issues", "workflow_runs"]
  }};
  tokenInput.value = "";
  const response = await fetch("/operator/github-operations/repo-status/read-evidence", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify(payload)
  }});
  const data = await response.json();
  document.getElementById("repo-status-output").textContent = JSON.stringify(data, null, 2);
}});
</script>
</body>
</html>"""


def _stable_hash(payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _payload_hash(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _text_hash(payload: str) -> str:
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _validate_fetch_admission(admission: GitHubReadOnlyEvidenceAdmission) -> None:
    if not isinstance(admission, GitHubReadOnlyEvidenceAdmission):
        raise ValueError("admission must be a GitHubReadOnlyEvidenceAdmission")
    if admission.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
        raise ValueError("admission capability must be connector.github.read")
    if admission.live_connector_read_admitted is not True:
        raise ValueError("live connector read must be admitted before fetch")
    if admission.live_connector_call_performed is not False:
        raise ValueError("admission must not already claim connector execution")
    if admission.write_authority_granted is not False:
        raise ValueError("read-only fetch cannot use write authority")
    if admission.allowed_tools != _LIVE_READ_ALLOWED_TOOLS:
        raise ValueError("admission allowed tools do not match GitHub read-only worker")
    if admission.allowed_networks != _LIVE_READ_ALLOWED_NETWORKS:
        raise ValueError("admission allowed networks do not match GitHub read-only network")
    if admission.required_secret_scope != _LIVE_READ_SECRET_SCOPE:
        raise ValueError("admission secret scope does not match GitHub read-only scope")


def _validate_actions_failure_fetch_admission(admission: GitHubActionsFailureEvidenceAdmission) -> None:
    if not isinstance(admission, GitHubActionsFailureEvidenceAdmission):
        raise ValueError("admission must be a GitHubActionsFailureEvidenceAdmission")
    if admission.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
        raise ValueError("admission capability must be connector.github.read")
    if admission.live_connector_read_admitted is not True:
        raise ValueError("live connector read must be admitted before fetch")
    if admission.live_connector_call_performed is not False:
        raise ValueError("admission must not already claim connector execution")
    if admission.write_authority_granted is not False:
        raise ValueError("read-only fetch cannot use write authority")
    if admission.allowed_tools != _LIVE_READ_ALLOWED_TOOLS:
        raise ValueError("admission allowed tools do not match GitHub read-only worker")
    if admission.allowed_networks != _LIVE_READ_ALLOWED_NETWORKS:
        raise ValueError("admission allowed networks do not match GitHub read-only network")
    if admission.required_secret_scope != _LIVE_READ_SECRET_SCOPE:
        raise ValueError("admission secret scope does not match GitHub read-only scope")


def _validate_repo_status_fetch_admission(admission: GitHubRepoStatusEvidenceAdmission) -> None:
    if not isinstance(admission, GitHubRepoStatusEvidenceAdmission):
        raise ValueError("admission must be a GitHubRepoStatusEvidenceAdmission")
    if admission.capability_id != GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID:
        raise ValueError("admission capability must be connector.github.read")
    if admission.live_connector_read_admitted is not True:
        raise ValueError("live connector read must be admitted before fetch")
    if admission.live_connector_call_performed is not False:
        raise ValueError("admission must not already claim connector execution")
    if admission.write_authority_granted is not False:
        raise ValueError("read-only fetch cannot use write authority")
    if admission.allowed_tools != _LIVE_READ_ALLOWED_TOOLS:
        raise ValueError("admission allowed tools do not match GitHub read-only worker")
    if admission.allowed_networks != _LIVE_READ_ALLOWED_NETWORKS:
        raise ValueError("admission allowed networks do not match GitHub read-only network")
    if admission.required_secret_scope != _LIVE_READ_SECRET_SCOPE:
        raise ValueError("admission secret scope does not match GitHub read-only scope")


def _quote_github_path(path: str) -> str:
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise GitHubReadOnlyEvidenceFetchError("github_path_must_not_include_external_url_parts")
    return urllib.parse.quote(path, safe="/")


def _summarize_repository(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("repository response must be an object")
    owner = payload.get("owner", {})
    owner_login = owner.get("login", "") if isinstance(owner, Mapping) else ""
    return {
        "full_name": payload.get("full_name", ""),
        "default_branch": payload.get("default_branch", ""),
        "private": bool(payload.get("private", False)),
        "archived": bool(payload.get("archived", False)),
        "disabled": bool(payload.get("disabled", False)),
        "fork": bool(payload.get("fork", False)),
        "open_issues_count": payload.get("open_issues_count", 0),
        "stargazers_count": payload.get("stargazers_count", 0),
        "owner": owner_login,
        "pushed_at": payload.get("pushed_at", ""),
        "updated_at": payload.get("updated_at", ""),
    }


def _summarize_recent_commits(payload: Any, *, max_items: int) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError("commits response must be an array")
    summaries: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload[:max_items]):
        if not isinstance(item, Mapping):
            raise ValueError(f"commit entry {index} must be an object")
        commit = item.get("commit", {})
        author = commit.get("author", {}) if isinstance(commit, Mapping) else {}
        summaries.append(
            {
                "sha": str(item.get("sha", ""))[:40],
                "message_head": str(commit.get("message", "") if isinstance(commit, Mapping) else "").splitlines()[0][:160],
                "author_name": str(author.get("name", "") if isinstance(author, Mapping) else ""),
                "authored_at": str(author.get("date", "") if isinstance(author, Mapping) else ""),
            }
        )
    return tuple(summaries)


def _summarize_open_pull_requests(payload: Any, *, max_items: int) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError("pulls response must be an array")
    summaries: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload[:max_items]):
        if not isinstance(item, Mapping):
            raise ValueError(f"pull request entry {index} must be an object")
        summaries.append(
            {
                "number": item.get("number"),
                "title": str(item.get("title", ""))[:180],
                "draft": bool(item.get("draft", False)),
                "state": item.get("state", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
            }
        )
    return tuple(summaries)


def _summarize_open_issues(payload: Any, *, max_items: int) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError("issues response must be an array")
    summaries: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload[:max_items]):
        if not isinstance(item, Mapping):
            raise ValueError(f"issue entry {index} must be an object")
        if "pull_request" in item:
            continue
        labels = item.get("labels", [])
        label_names = [str(label.get("name", "")) for label in labels if isinstance(label, Mapping)][:8] if isinstance(labels, list) else []
        summaries.append(
            {
                "number": item.get("number"),
                "title": str(item.get("title", ""))[:180],
                "state": item.get("state", ""),
                "labels": label_names,
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
            }
        )
    return tuple(summaries)


def _summarize_workflow_runs(payload: Any, *, max_items: int) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, Mapping):
        raise ValueError("workflow runs response must be an object")
    runs = payload.get("workflow_runs", [])
    if not isinstance(runs, list):
        raise ValueError("workflow runs response workflow_runs must be an array")
    return tuple(_summarize_workflow_run(item) for item in runs[:max_items] if isinstance(item, Mapping))


def _summarize_pull_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("pull request response must be an object")
    head = payload.get("head")
    base = payload.get("base")
    if not isinstance(head, Mapping) or not isinstance(base, Mapping):
        raise ValueError("pull request response missing head or base")
    return {
        "number": payload.get("number"),
        "state": payload.get("state", ""),
        "draft": bool(payload.get("draft", False)),
        "merged": bool(payload.get("merged", False)),
        "mergeable": payload.get("mergeable"),
        "head_ref": head.get("ref", ""),
        "head_sha": head.get("sha", ""),
        "base_ref": base.get("ref", ""),
        "changed_files_count": payload.get("changed_files", 0),
        "commits_count": payload.get("commits", 0),
    }


def _summarize_changed_files(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError("changed files response must be an array")
    filenames: list[str] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"changed file entry {index} must be an object")
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError(f"changed file entry {index} missing filename")
        filenames.append(filename)
    return tuple(filenames)


def _summarize_checks(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("check-runs response must be an object")
    check_runs = payload.get("check_runs", [])
    if not isinstance(check_runs, list):
        raise ValueError("check-runs response check_runs must be an array")
    conclusion_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in check_runs:
        if not isinstance(item, Mapping):
            continue
        conclusion = str(item.get("conclusion") or "unknown")
        status = str(item.get("status") or "unknown")
        conclusion_counts[conclusion] = conclusion_counts.get(conclusion, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "total_count": int(payload.get("total_count", len(check_runs))),
        "conclusion_counts": conclusion_counts,
        "status_counts": status_counts,
    }


def _summarize_workflow_run(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("workflow run response must be an object")
    return {
        "run_id": payload.get("id"),
        "name": payload.get("name", ""),
        "display_title": payload.get("display_title", ""),
        "status": payload.get("status", ""),
        "conclusion": payload.get("conclusion", ""),
        "event": payload.get("event", ""),
        "head_branch": payload.get("head_branch", ""),
        "head_sha": payload.get("head_sha", ""),
        "run_number": payload.get("run_number", 0),
        "html_url": payload.get("html_url", ""),
    }


def _summarize_workflow_jobs(payload: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, Mapping):
        raise ValueError("workflow jobs response must be an object")
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError("workflow jobs response jobs must be an array")
    summaries: list[Mapping[str, Any]] = []
    for index, item in enumerate(jobs):
        if not isinstance(item, Mapping):
            raise ValueError(f"workflow job entry {index} must be an object")
        steps = item.get("steps", [])
        failed_steps: list[str] = []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, Mapping) and str(step.get("conclusion") or "") not in {"success", "skipped", "neutral", ""}:
                    failed_steps.append(str(step.get("name") or "unnamed_step"))
        summaries.append(
            {
                "job_id": item.get("id"),
                "name": item.get("name", ""),
                "status": item.get("status", ""),
                "conclusion": item.get("conclusion", ""),
                "started_at": item.get("started_at", ""),
                "completed_at": item.get("completed_at", ""),
                "failed_steps": failed_steps,
            }
        )
    return tuple(summaries)


def _summarize_failed_job_log(*, job: Mapping[str, Any], log_payload: str, log_digest: str) -> Mapping[str, Any]:
    if not log_digest.startswith("sha256:"):
        raise ValueError("log_digest must use sha256: prefix")
    candidate_lines: list[str] = []
    for line in log_payload.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(marker in lowered for marker in ("error", "failed", "failure", "exception", "traceback")):
            candidate_lines.append(stripped[:240])
        if len(candidate_lines) >= 5:
            break
    if not candidate_lines:
        for line in log_payload.splitlines():
            stripped = line.strip()
            if stripped:
                candidate_lines.append(stripped[:240])
            if len(candidate_lines) >= 3:
                break
    return {
        "job_id": job.get("job_id"),
        "job_name": job.get("name", ""),
        "log_digest": log_digest,
        "first_failure_signal": candidate_lines[0] if candidate_lines else "no_bounded_failure_signal_found",
        "bounded_failure_signals": candidate_lines,
        "raw_log_persisted": False,
    }


def _missing_pr_safety_evidence(fetch_result: GitHubReadOnlyEvidenceFetchResult) -> tuple[str, ...]:
    required = ("pull_request", "diff", "checks", "changed_files")
    fetched = set(fetch_result.fetched_evidence_kinds)
    missing = [kind for kind in required if kind not in fetched]
    if "pull_request" in fetched and not fetch_result.observed_pull_request:
        missing.append("pull_request_summary")
    if "checks" in fetched and not fetch_result.observed_checks:
        missing.append("checks_summary")
    if "changed_files" in fetched and not fetch_result.changed_files:
        missing.append("changed_files_summary")
    if "diff" in fetched and not fetch_result.diff_digest:
        missing.append("diff_digest")
    return tuple(dict.fromkeys(missing))


def _html(value: Any) -> str:
    return escape(str(value), quote=True)
