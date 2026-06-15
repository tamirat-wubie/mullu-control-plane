"""GitHub check-run write receipt planner.

Purpose: build hash-bound GitHub check-run write plans and receipts without
    performing the GitHub network mutation in-process.
Governance scope: repository/head identity, GitHub App installation boundary,
    check-run payload hash, readiness evidence refs, approval refs, external
    execution receipt refs, response evidence, and secret absence.
Dependencies: dataclasses, re, and command-spine canonical hashing.
Invariants:
  - The planner never calls GitHub and never authenticates a request.
  - Plan-only and dry-run modes cannot claim external check-run writes.
  - Write-approved mode must bind approval, installation, external execution,
    response id, and response payload hash evidence.
  - Raw secret-shaped material blocks receipt admission.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


GITHUB_CHECK_RUN_WRITE_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:github-check-run-write-receipt:1"
CHECK_RUN_WRITE_MODES = ("plan_only", "dry_run", "write_approved")
CHECK_RUN_WRITE_STATUSES = ("planned", "dry_run_accepted", "write_receipt_bound", "blocked")
CHECK_RUN_STATUSES = ("queued", "in_progress", "completed")
CHECK_RUN_CONCLUSIONS = (
    "action_required",
    "cancelled",
    "failure",
    "neutral",
    "success",
    "skipped",
    "stale",
    "timed_out",
)
REPOSITORY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
HEAD_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
RESPONSE_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
BASE_CHECK_RUN_CONTROLS = (
    "github_checks_api_endpoint",
    "check_run_payload_hash",
    "head_sha",
    "readiness_evidence",
    "secret_absence",
    "github_app_installation_boundary",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class GitHubCheckRunWriteRequest:
    """One governed request to plan or bind a GitHub check-run write."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    repository_owner: str
    repository_name: str
    head_sha: str
    check_name: str
    check_status: str
    conclusion: str
    output_title: str
    output_summary: str
    mode: str
    evidence_refs: list[str]
    output_text: str = ""
    details_url: str = ""
    external_id: str = ""
    installation_id: str = ""
    approval_ref: str = ""
    execution_receipt_ref: str = ""
    response_check_run_id: str = ""
    response_payload_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "repository_owner",
            "repository_name",
            "head_sha",
            "check_name",
            "check_status",
            "output_title",
            "output_summary",
            "mode",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if not REPOSITORY_SEGMENT_PATTERN.fullmatch(self.repository_owner):
            raise ValueError("repository_owner_invalid")
        if not REPOSITORY_SEGMENT_PATTERN.fullmatch(self.repository_name):
            raise ValueError("repository_name_invalid")
        if not HEAD_SHA_PATTERN.fullmatch(self.head_sha):
            raise ValueError("head_sha_invalid")
        if self.check_status not in CHECK_RUN_STATUSES:
            raise ValueError("check_status_invalid")
        if self.mode not in CHECK_RUN_WRITE_MODES:
            raise ValueError("github_check_run_write_mode_invalid")
        object.__setattr__(self, "conclusion", str(self.conclusion).strip())
        if self.conclusion and self.conclusion not in CHECK_RUN_CONCLUSIONS:
            raise ValueError("check_run_conclusion_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        for field_name in (
            "output_text",
            "details_url",
            "external_id",
            "installation_id",
            "approval_ref",
            "execution_receipt_ref",
            "response_check_run_id",
            "response_payload_hash",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class GitHubCheckRunWriteReceipt:
    """Schema-backed non-terminal receipt for check-run write planning."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    mode: str
    status: str
    repository_owner: str
    repository_name: str
    head_sha: str
    check_name: str
    check_status: str
    conclusion: str
    endpoint: str
    method: str
    request_payload: dict[str, Any]
    request_payload_hash: str
    installation_id: str
    approval_ref: str
    execution_receipt_ref: str
    response_check_run_id: str
    response_payload_hash: str
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    external_write_admitted: bool
    network_call_performed: bool
    request_authentication_performed: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in CHECK_RUN_WRITE_MODES:
            raise ValueError("github_check_run_write_mode_invalid")
        if self.status not in CHECK_RUN_WRITE_STATUSES:
            raise ValueError("github_check_run_write_status_invalid")
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class GitHubCheckRunWriter:
    """Deterministic GitHub check-run write planner."""

    def evaluate(self, request: GitHubCheckRunWriteRequest) -> GitHubCheckRunWriteReceipt:
        """Return a check-run write receipt without executing the GitHub write."""
        endpoint = f"/repos/{request.repository_owner}/{request.repository_name}/check-runs"
        request_payload = _request_payload(request)
        request_payload_hash = canonical_hash(request_payload)
        blocked_reasons = _blocked_reasons(request)
        required_controls = [*BASE_CHECK_RUN_CONTROLS]
        if request.mode == "write_approved":
            required_controls.extend(
                [
                    "operator_approval",
                    "github_app_installation_id",
                    "github_app_execution_receipt",
                    "github_check_run_response",
                    "github_check_run_response_hash",
                ]
            )
        if blocked_reasons:
            required_controls.append("github_check_run_write_block")

        status = _status(request.mode, blocked_reasons)
        external_write_admitted = status == "write_receipt_bound"
        receipt = GitHubCheckRunWriteReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            mode=request.mode,
            status=status,
            repository_owner=request.repository_owner,
            repository_name=request.repository_name,
            head_sha=request.head_sha.lower(),
            check_name=request.check_name,
            check_status=request.check_status,
            conclusion=request.conclusion,
            endpoint=endpoint,
            method="POST",
            request_payload=request_payload,
            request_payload_hash=request_payload_hash,
            installation_id=request.installation_id,
            approval_ref=request.approval_ref,
            execution_receipt_ref=request.execution_receipt_ref,
            response_check_run_id=request.response_check_run_id,
            response_payload_hash=request.response_payload_hash,
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(required_controls),
            evidence_refs=request.evidence_refs,
            receipt_schema_ref=GITHUB_CHECK_RUN_WRITE_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            external_write_admitted=external_write_admitted,
            network_call_performed=False,
            request_authentication_performed=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "github_api_not_called": True,
                "request_authentication_not_performed": True,
                "external_write_admitted": external_write_admitted,
                "payload_hash_bound": bool(request_payload_hash),
                "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"github-check-run-write-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _request_payload(request: GitHubCheckRunWriteRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": request.check_name,
        "head_sha": request.head_sha.lower(),
        "status": request.check_status,
        "output": {
            "title": request.output_title,
            "summary": request.output_summary,
        },
    }
    if request.conclusion:
        payload["conclusion"] = request.conclusion
    if request.output_text:
        payload["output"]["text"] = request.output_text
    if request.details_url:
        payload["details_url"] = request.details_url
    if request.external_id:
        payload["external_id"] = request.external_id
    return payload


def _blocked_reasons(request: GitHubCheckRunWriteRequest) -> list[str]:
    blocked: list[str] = []
    if not request.evidence_refs:
        blocked.append("readiness_evidence_refs_required")
    if request.check_status == "completed" and not request.conclusion:
        blocked.append("completed_check_run_conclusion_required")
    if request.check_status != "completed" and request.conclusion:
        blocked.append("non_completed_check_run_conclusion_forbidden")
    if request.mode in {"plan_only", "dry_run"}:
        blocked.extend(_forbidden_response_evidence(request))
    if request.mode == "write_approved":
        blocked.extend(_write_approval_violations(request))
    if _contains_secret_material(request.metadata) or _contains_secret_material(_request_payload(request)):
        blocked.append("secret_values_disclosed")
    return blocked


def _forbidden_response_evidence(request: GitHubCheckRunWriteRequest) -> list[str]:
    blocked: list[str] = []
    if request.execution_receipt_ref:
        blocked.append("non_write_execution_receipt_forbidden")
    if request.response_check_run_id:
        blocked.append("non_write_response_check_run_id_forbidden")
    if request.response_payload_hash:
        blocked.append("non_write_response_payload_hash_forbidden")
    return blocked


def _write_approval_violations(request: GitHubCheckRunWriteRequest) -> list[str]:
    blocked: list[str] = []
    if not request.approval_ref:
        blocked.append("approval_ref_required")
    if not request.installation_id:
        blocked.append("installation_id_required")
    if not request.execution_receipt_ref:
        blocked.append("execution_receipt_ref_required")
    if not request.response_check_run_id:
        blocked.append("response_check_run_id_required")
    if not request.response_payload_hash:
        blocked.append("response_payload_hash_required")
    elif not RESPONSE_HASH_PATTERN.fullmatch(request.response_payload_hash):
        blocked.append("response_payload_hash_invalid")
    return blocked


def _status(mode: str, blocked_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if mode == "plan_only":
        return "planned"
    if mode == "dry_run":
        return "dry_run_accepted"
    return "write_receipt_bound"


def _contains_secret_material(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_secret_material(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_secret_material(item) for item in value)
    return False


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
