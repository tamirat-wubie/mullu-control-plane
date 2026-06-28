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
GITHUB_READ_ONLY_CONNECTOR_CAPABILITY_ID = "connector.github.read"
GITHUB_PR_SAFETY_INTENT = "REVIEW_PR_MERGE_SAFETY"
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


def _quote_github_path(path: str) -> str:
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise GitHubReadOnlyEvidenceFetchError("github_path_must_not_include_external_url_parts")
    return urllib.parse.quote(path, safe="/")


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
