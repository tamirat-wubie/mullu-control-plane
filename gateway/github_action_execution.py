"""GitHub action execution receipt planner.

Purpose: build hash-bound GitHub REST action execution plans and receipts
    without performing a GitHub network mutation in-process.
Governance scope: repository identity, token plan repository identity,
    action payload hash, approval refs, token-exchange receipt refs, external
    execution receipt refs, response evidence, and secret absence.
Dependencies: dataclasses, re, and command-spine canonical hashing.
Invariants:
  - The planner never calls GitHub and never authenticates a request.
  - Token plan repository identity must match the action repository identity.
  - Plan-only and dry-run modes cannot claim live execution response evidence.
  - Execute-approved mode must bind approval, token-exchange, external
    execution, 2xx response, and response payload hash evidence.
  - Raw secret-shaped material blocks receipt admission.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


GITHUB_ACTION_EXECUTION_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:github-action-execution-receipt:1"
)
ACTION_EXECUTION_KINDS = ("check_run_write", "branch_protection_reconcile")
ACTION_EXECUTION_MODES = ("plan_only", "dry_run", "execute_approved")
ACTION_EXECUTION_STATUSES = (
    "planned",
    "dry_run_accepted",
    "execution_receipt_bound",
    "blocked",
)
REPOSITORY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
BRANCH_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
BASE_ACTION_EXECUTION_CONTROLS = (
    "github_action_execution_endpoint",
    "github_action_payload_hash",
    "token_plan_repository_boundary",
    "action_plan_reference",
    "readiness_evidence",
    "secret_absence",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class GitHubActionExecutionRequest:
    """One governed request to plan or bind a GitHub REST action execution."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    repository_owner: str
    repository_name: str
    token_repository_owner: str
    token_repository_name: str
    token_plan_ref: str
    action_kind: str
    action_plan_ref: str
    request_payload: dict[str, Any]
    mode: str
    evidence_refs: list[str]
    branch_name: str = ""
    approval_ref: str = ""
    token_exchange_receipt_ref: str = ""
    external_execution_receipt_ref: str = ""
    response_status_code: int = 0
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
            "token_repository_owner",
            "token_repository_name",
            "token_plan_ref",
            "action_kind",
            "action_plan_ref",
            "mode",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "repository_owner",
            "repository_name",
            "token_repository_owner",
            "token_repository_name",
        ):
            if not REPOSITORY_SEGMENT_PATTERN.fullmatch(str(getattr(self, field_name))):
                raise ValueError(f"{field_name}_invalid")
        if self.action_kind not in ACTION_EXECUTION_KINDS:
            raise ValueError("github_action_execution_kind_invalid")
        if self.mode not in ACTION_EXECUTION_MODES:
            raise ValueError("github_action_execution_mode_invalid")
        branch_name = str(self.branch_name).strip()
        if self.action_kind == "branch_protection_reconcile":
            if not branch_name:
                raise ValueError("branch_name_required")
            if not BRANCH_SEGMENT_PATTERN.fullmatch(branch_name):
                raise ValueError("branch_name_invalid")
        elif branch_name:
            raise ValueError("branch_name_forbidden")
        object.__setattr__(self, "branch_name", branch_name)
        if not isinstance(self.request_payload, dict) or not self.request_payload:
            raise ValueError("request_payload_required")
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        for field_name in (
            "approval_ref",
            "token_exchange_receipt_ref",
            "external_execution_receipt_ref",
            "response_payload_hash",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        if not isinstance(self.response_status_code, int) or not 0 <= self.response_status_code <= 599:
            raise ValueError("response_status_code_invalid")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class GitHubActionExecutionReceipt:
    """Schema-backed non-terminal receipt for GitHub REST action execution."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    mode: str
    status: str
    action_kind: str
    repository_owner: str
    repository_name: str
    token_repository_owner: str
    token_repository_name: str
    token_plan_ref: str
    action_plan_ref: str
    branch_name: str
    endpoint: str
    method: str
    request_payload: dict[str, Any]
    request_payload_hash: str
    approval_ref: str
    token_exchange_receipt_ref: str
    external_execution_receipt_ref: str
    response_status_code: int
    response_payload_hash: str
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    external_execution_admitted: bool
    network_call_performed: bool
    request_authentication_performed: bool
    raw_token_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action_kind not in ACTION_EXECUTION_KINDS:
            raise ValueError("github_action_execution_kind_invalid")
        if self.mode not in ACTION_EXECUTION_MODES:
            raise ValueError("github_action_execution_mode_invalid")
        if self.status not in ACTION_EXECUTION_STATUSES:
            raise ValueError("github_action_execution_status_invalid")
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class GitHubActionExecution:
    """Deterministic GitHub REST action execution planner."""

    def evaluate(self, request: GitHubActionExecutionRequest) -> GitHubActionExecutionReceipt:
        """Return an action execution receipt without executing the GitHub action."""
        endpoint = _endpoint(request)
        method = _method(request.action_kind)
        request_payload_hash = canonical_hash(request.request_payload)
        blocked_reasons = _blocked_reasons(request)
        required_controls = [*BASE_ACTION_EXECUTION_CONTROLS]
        if request.mode == "execute_approved":
            required_controls.extend(
                [
                    "operator_approval",
                    "github_app_token_exchange_receipt",
                    "github_external_action_execution_receipt",
                    "github_action_response_status",
                    "github_action_response_hash",
                ]
            )
        if request.action_kind == "branch_protection_reconcile":
            required_controls.append("branch_protection_target_branch")
        if blocked_reasons:
            required_controls.append("github_action_execution_block")

        status = _status(request.mode, blocked_reasons)
        external_execution_admitted = status == "execution_receipt_bound"
        receipt = GitHubActionExecutionReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            mode=request.mode,
            status=status,
            action_kind=request.action_kind,
            repository_owner=request.repository_owner,
            repository_name=request.repository_name,
            token_repository_owner=request.token_repository_owner,
            token_repository_name=request.token_repository_name,
            token_plan_ref=request.token_plan_ref,
            action_plan_ref=request.action_plan_ref,
            branch_name=request.branch_name,
            endpoint=endpoint,
            method=method,
            request_payload=request.request_payload,
            request_payload_hash=request_payload_hash,
            approval_ref=request.approval_ref,
            token_exchange_receipt_ref=request.token_exchange_receipt_ref,
            external_execution_receipt_ref=request.external_execution_receipt_ref,
            response_status_code=request.response_status_code,
            response_payload_hash=request.response_payload_hash,
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(required_controls),
            evidence_refs=request.evidence_refs,
            receipt_schema_ref=GITHUB_ACTION_EXECUTION_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            external_execution_admitted=external_execution_admitted,
            network_call_performed=False,
            request_authentication_performed=False,
            raw_token_stored=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "github_api_not_called": True,
                "request_authentication_not_performed": True,
                "raw_token_not_stored": True,
                "external_execution_admitted": external_execution_admitted,
                "payload_hash_bound": bool(request_payload_hash),
                "token_repository_match": _token_repository_matches(request),
                "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"github-action-execution-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _endpoint(request: GitHubActionExecutionRequest) -> str:
    if request.action_kind == "check_run_write":
        return f"/repos/{request.repository_owner}/{request.repository_name}/check-runs"
    return (
        f"/repos/{request.repository_owner}/{request.repository_name}"
        f"/branches/{request.branch_name}/protection"
    )


def _method(action_kind: str) -> str:
    if action_kind == "check_run_write":
        return "POST"
    return "PUT"


def _blocked_reasons(request: GitHubActionExecutionRequest) -> list[str]:
    blocked: list[str] = []
    if not request.evidence_refs:
        blocked.append("readiness_evidence_refs_required")
    if not _token_repository_matches(request):
        blocked.append("token_plan_repository_mismatch")
    if request.mode in {"plan_only", "dry_run"}:
        blocked.extend(_forbidden_execution_evidence(request))
    if request.mode == "execute_approved":
        blocked.extend(_execute_approval_violations(request))
    if _contains_secret_material(request.metadata) or _contains_secret_material(request.request_payload):
        blocked.append("secret_values_disclosed")
    if _contains_secret_material(
        [
            request.token_plan_ref,
            request.token_exchange_receipt_ref,
            request.external_execution_receipt_ref,
            request.response_payload_hash,
        ]
    ):
        blocked.append("secret_values_disclosed")
    return blocked


def _token_repository_matches(request: GitHubActionExecutionRequest) -> bool:
    return (
        request.repository_owner == request.token_repository_owner
        and request.repository_name == request.token_repository_name
    )


def _forbidden_execution_evidence(request: GitHubActionExecutionRequest) -> list[str]:
    blocked: list[str] = []
    if request.approval_ref:
        blocked.append("non_execute_approval_ref_forbidden")
    if request.token_exchange_receipt_ref:
        blocked.append("non_execute_token_exchange_receipt_forbidden")
    if request.external_execution_receipt_ref:
        blocked.append("non_execute_external_receipt_forbidden")
    if request.response_status_code:
        blocked.append("non_execute_response_status_forbidden")
    if request.response_payload_hash:
        blocked.append("non_execute_response_payload_hash_forbidden")
    return blocked


def _execute_approval_violations(request: GitHubActionExecutionRequest) -> list[str]:
    blocked: list[str] = []
    if not request.approval_ref:
        blocked.append("approval_ref_required")
    if not request.token_exchange_receipt_ref:
        blocked.append("token_exchange_receipt_ref_required")
    if not request.external_execution_receipt_ref:
        blocked.append("external_execution_receipt_ref_required")
    if not 200 <= request.response_status_code <= 299:
        blocked.append("response_status_code_2xx_required")
    if not request.response_payload_hash:
        blocked.append("response_payload_hash_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.response_payload_hash):
        blocked.append("response_payload_hash_invalid")
    return blocked


def _status(mode: str, blocked_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if mode == "plan_only":
        return "planned"
    if mode == "dry_run":
        return "dry_run_accepted"
    return "execution_receipt_bound"


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
