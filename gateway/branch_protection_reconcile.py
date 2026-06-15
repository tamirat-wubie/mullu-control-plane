"""GitHub branch-protection reconcile receipt planner.

Purpose: build hash-bound GitHub branch-protection reconcile plans and receipts
    without performing a GitHub network mutation in-process.
Governance scope: protected-branch policy, observed drift, REST payload hash,
    approval refs, token-exchange refs, action-execution refs, response
    evidence, and secret absence.
Dependencies: dataclasses, re, and command-spine canonical hashing.
Invariants:
  - The planner never calls GitHub and never authenticates a request.
  - Plan-only and dry-run modes cannot claim live apply response evidence.
  - Apply-approved mode must bind approval, token-exchange, external action
    execution, 2xx response, and response payload hash evidence.
  - Raw secret-shaped material blocks receipt admission.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


BRANCH_PROTECTION_RECONCILE_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:github-branch-protection-reconcile-receipt:1"
)
BRANCH_PROTECTION_RECONCILE_MODES = ("plan_only", "dry_run", "apply_approved")
BRANCH_PROTECTION_RECONCILE_STATUSES = (
    "noop",
    "planned",
    "dry_run_accepted",
    "apply_receipt_bound",
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
BASE_BRANCH_PROTECTION_CONTROLS = (
    "branch_protection_policy_hash",
    "branch_protection_observed_state",
    "branch_protection_drift_report",
    "github_branch_protection_payload_hash",
    "github_branch_protection_endpoint",
    "readiness_evidence",
    "secret_absence",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class BranchProtectionReviewPolicy:
    """Pull-request review policy embedded in protected-branch governance."""

    required_approving_review_count: int = 1
    require_code_owner_reviews: bool = True
    dismiss_stale_reviews: bool = True
    require_last_push_approval: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.required_approving_review_count, int):
            raise ValueError("required_approving_review_count_invalid")
        if not 0 <= self.required_approving_review_count <= 6:
            raise ValueError("required_approving_review_count_invalid")


@dataclass(frozen=True, slots=True)
class BranchProtectionPolicy:
    """Desired GitHub protected-branch policy for one repository branch."""

    policy_id: str
    repository_owner: str
    repository_name: str
    branch_name: str
    required_status_checks: list[str]
    enforce_admins: bool = True
    require_linear_history: bool = True
    require_conversation_resolution: bool = True
    require_signed_commits: bool = False
    require_status_checks: bool = True
    review_policy: BranchProtectionReviewPolicy = field(
        default_factory=BranchProtectionReviewPolicy
    )

    def __post_init__(self) -> None:
        for field_name in (
            "policy_id",
            "repository_owner",
            "repository_name",
            "branch_name",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        for field_name in ("repository_owner", "repository_name"):
            if not REPOSITORY_SEGMENT_PATTERN.fullmatch(str(getattr(self, field_name))):
                raise ValueError(f"{field_name}_invalid")
        if not BRANCH_SEGMENT_PATTERN.fullmatch(self.branch_name):
            raise ValueError("branch_name_invalid")
        checks = _normalize_unique_list(self.required_status_checks)
        if self.require_status_checks and not checks:
            raise ValueError("required_status_checks_required")
        object.__setattr__(self, "required_status_checks", checks)
        if not isinstance(self.review_policy, BranchProtectionReviewPolicy):
            raise ValueError("review_policy_invalid")


@dataclass(frozen=True, slots=True)
class BranchProtectionObservedState:
    """Observed GitHub protected-branch state used for drift evaluation."""

    required_status_checks: list[str]
    enforce_admins: bool
    required_approving_review_count: int
    require_code_owner_reviews: bool
    require_conversation_resolution: bool
    require_linear_history: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_status_checks",
            _normalize_unique_list(self.required_status_checks),
        )
        if not isinstance(self.required_approving_review_count, int):
            raise ValueError("observed_required_approving_review_count_invalid")
        if not 0 <= self.required_approving_review_count <= 6:
            raise ValueError("observed_required_approving_review_count_invalid")


@dataclass(frozen=True, slots=True)
class BranchProtectionReconcileRequest:
    """One governed request to plan or bind branch-protection reconciliation."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    policy: BranchProtectionPolicy
    mode: str
    evidence_refs: list[str]
    observed_state: BranchProtectionObservedState | None = None
    approval_ref: str = ""
    token_exchange_receipt_ref: str = ""
    action_execution_receipt_ref: str = ""
    response_status_code: int = 0
    response_payload_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "command_id", "mode"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if not isinstance(self.policy, BranchProtectionPolicy):
            raise ValueError("branch_protection_policy_required")
        if self.observed_state is not None and not isinstance(
            self.observed_state, BranchProtectionObservedState
        ):
            raise ValueError("observed_state_invalid")
        if self.mode not in BRANCH_PROTECTION_RECONCILE_MODES:
            raise ValueError("branch_protection_reconcile_mode_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        for field_name in (
            "approval_ref",
            "token_exchange_receipt_ref",
            "action_execution_receipt_ref",
            "response_payload_hash",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        if not isinstance(self.response_status_code, int) or not 0 <= self.response_status_code <= 599:
            raise ValueError("response_status_code_invalid")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class BranchProtectionReconcileReceipt:
    """Schema-backed non-terminal receipt for branch-protection reconcile."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    mode: str
    status: str
    repository_owner: str
    repository_name: str
    branch_name: str
    endpoint: str
    method: str
    policy: dict[str, Any]
    policy_hash: str
    observed_state: dict[str, Any] | None
    missing_required_checks: list[str]
    extra_required_checks: list[str]
    drift: list[str]
    required_actions: list[str]
    request_payload: dict[str, Any]
    request_payload_hash: str
    plan_hash: str
    approval_ref: str
    token_exchange_receipt_ref: str
    action_execution_receipt_ref: str
    response_status_code: int
    response_payload_hash: str
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    external_apply_admitted: bool
    network_call_performed: bool
    request_authentication_performed: bool
    raw_token_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in BRANCH_PROTECTION_RECONCILE_MODES:
            raise ValueError("branch_protection_reconcile_mode_invalid")
        if self.status not in BRANCH_PROTECTION_RECONCILE_STATUSES:
            raise ValueError("branch_protection_reconcile_status_invalid")
        object.__setattr__(self, "policy", dict(self.policy))
        if self.observed_state is not None:
            object.__setattr__(self, "observed_state", dict(self.observed_state))
        object.__setattr__(self, "missing_required_checks", _normalize_unique_list(self.missing_required_checks))
        object.__setattr__(self, "extra_required_checks", _normalize_unique_list(self.extra_required_checks))
        object.__setattr__(self, "drift", _normalize_list(self.drift))
        object.__setattr__(self, "required_actions", _normalize_list(self.required_actions))
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class BranchProtectionReconciler:
    """Deterministic GitHub branch-protection reconcile planner."""

    def evaluate(self, request: BranchProtectionReconcileRequest) -> BranchProtectionReconcileReceipt:
        """Return a reconcile receipt without executing a GitHub protected-branch write."""
        policy = asdict(request.policy)
        observed_state = asdict(request.observed_state) if request.observed_state else None
        endpoint = (
            f"/repos/{request.policy.repository_owner}/{request.policy.repository_name}"
            f"/branches/{request.policy.branch_name}/protection"
        )
        request_payload = _github_branch_protection_payload(request.policy)
        policy_hash = canonical_hash(policy)
        request_payload_hash = canonical_hash(request_payload)
        missing_checks, extra_checks, drift = _evaluate_drift(
            request.policy,
            request.observed_state,
        )
        required_actions = _required_actions(drift)
        plan_hash = canonical_hash(
            {
                "request_id": request.request_id,
                "mode": request.mode,
                "policy_hash": policy_hash,
                "observed_state": observed_state,
                "drift": drift,
                "required_actions": required_actions,
                "endpoint": endpoint,
                "method": "PUT",
                "request_payload_hash": request_payload_hash,
            }
        )
        blocked_reasons = _blocked_reasons(request, request_payload, drift)
        required_controls = [*BASE_BRANCH_PROTECTION_CONTROLS]
        if request.mode == "apply_approved":
            required_controls.extend(
                [
                    "operator_approval",
                    "github_app_token_exchange_receipt",
                    "github_action_execution_receipt",
                    "github_branch_protection_response_status",
                    "github_branch_protection_response_hash",
                ]
            )
        if request.observed_state is None:
            required_controls.append("branch_protection_observed_state_gap")
        if blocked_reasons:
            required_controls.append("branch_protection_reconcile_block")

        status = _status(request.mode, drift, blocked_reasons)
        external_apply_admitted = status == "apply_receipt_bound"
        receipt = BranchProtectionReconcileReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            mode=request.mode,
            status=status,
            repository_owner=request.policy.repository_owner,
            repository_name=request.policy.repository_name,
            branch_name=request.policy.branch_name,
            endpoint=endpoint,
            method="PUT",
            policy=policy,
            policy_hash=policy_hash,
            observed_state=observed_state,
            missing_required_checks=missing_checks,
            extra_required_checks=extra_checks,
            drift=drift,
            required_actions=required_actions,
            request_payload=request_payload,
            request_payload_hash=request_payload_hash,
            plan_hash=plan_hash,
            approval_ref=request.approval_ref,
            token_exchange_receipt_ref=request.token_exchange_receipt_ref,
            action_execution_receipt_ref=request.action_execution_receipt_ref,
            response_status_code=request.response_status_code,
            response_payload_hash=request.response_payload_hash,
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(required_controls),
            evidence_refs=request.evidence_refs,
            receipt_schema_ref=BRANCH_PROTECTION_RECONCILE_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            external_apply_admitted=external_apply_admitted,
            network_call_performed=False,
            request_authentication_performed=False,
            raw_token_stored=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "github_api_not_called": True,
                "request_authentication_not_performed": True,
                "raw_token_not_stored": True,
                "external_apply_admitted": external_apply_admitted,
                "policy_hash_bound": bool(policy_hash),
                "payload_hash_bound": bool(request_payload_hash),
                "plan_hash_bound": bool(plan_hash),
                "observed_state_present": request.observed_state is not None,
                "drift_detected": bool(drift),
                "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"github-branch-protection-reconcile-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _github_branch_protection_payload(policy: BranchProtectionPolicy) -> dict[str, Any]:
    status_checks: dict[str, Any] | None = None
    if policy.require_status_checks:
        status_checks = {
            "strict": True,
            "checks": [{"context": check} for check in policy.required_status_checks],
        }
    return {
        "required_status_checks": status_checks,
        "enforce_admins": policy.enforce_admins,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": policy.review_policy.dismiss_stale_reviews,
            "require_code_owner_reviews": policy.review_policy.require_code_owner_reviews,
            "required_approving_review_count": (
                policy.review_policy.required_approving_review_count
            ),
            "require_last_push_approval": policy.review_policy.require_last_push_approval,
        },
        "restrictions": None,
        "required_linear_history": policy.require_linear_history,
        "required_conversation_resolution": policy.require_conversation_resolution,
        "required_signatures": policy.require_signed_commits,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": True,
        "required_deployments": None,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }


def _evaluate_drift(
    policy: BranchProtectionPolicy,
    observed_state: BranchProtectionObservedState | None,
) -> tuple[list[str], list[str], list[str]]:
    if observed_state is None:
        return (
            policy.required_status_checks,
            [],
            ["observed_branch_protection_state_missing"],
        )
    required = set(policy.required_status_checks)
    observed = set(observed_state.required_status_checks)
    missing_checks = sorted(required - observed)
    extra_checks = sorted(observed - required)
    drift: list[str] = []
    if missing_checks:
        drift.append("missing_required_status_checks")
    if not observed_state.enforce_admins and policy.enforce_admins:
        drift.append("admin_enforcement_disabled")
    if (
        observed_state.required_approving_review_count
        < policy.review_policy.required_approving_review_count
    ):
        drift.append("insufficient_required_approving_reviews")
    if policy.review_policy.require_code_owner_reviews and not observed_state.require_code_owner_reviews:
        drift.append("code_owner_review_requirement_disabled")
    if policy.require_conversation_resolution and not observed_state.require_conversation_resolution:
        drift.append("conversation_resolution_requirement_disabled")
    if policy.require_linear_history and not observed_state.require_linear_history:
        drift.append("linear_history_requirement_disabled")
    return missing_checks, extra_checks, drift


def _required_actions(drift: list[str]) -> list[str]:
    if not drift:
        return ["noop_observed_protection_satisfies_policy"]
    return [
        "put_branch_protection",
        "verify_branch_protection_after_apply",
        "retain_branch_protection_response_receipt",
    ]


def _blocked_reasons(
    request: BranchProtectionReconcileRequest,
    request_payload: dict[str, Any],
    drift: list[str],
) -> list[str]:
    blocked: list[str] = []
    if not request.evidence_refs:
        blocked.append("readiness_evidence_refs_required")
    if request.mode in {"plan_only", "dry_run"}:
        blocked.extend(_forbidden_apply_evidence(request))
    if request.mode == "apply_approved":
        blocked.extend(_apply_approval_violations(request))
        if not drift:
            blocked.append("branch_protection_drift_required_for_apply")
    if _contains_secret_material(request.metadata) or _contains_secret_material(request_payload):
        blocked.append("secret_values_disclosed")
    if _contains_secret_material(
        [
            request.approval_ref,
            request.token_exchange_receipt_ref,
            request.action_execution_receipt_ref,
            request.response_payload_hash,
        ]
    ):
        blocked.append("secret_values_disclosed")
    return blocked


def _forbidden_apply_evidence(request: BranchProtectionReconcileRequest) -> list[str]:
    blocked: list[str] = []
    if request.approval_ref:
        blocked.append("non_apply_approval_ref_forbidden")
    if request.token_exchange_receipt_ref:
        blocked.append("non_apply_token_exchange_receipt_forbidden")
    if request.action_execution_receipt_ref:
        blocked.append("non_apply_action_execution_receipt_forbidden")
    if request.response_status_code:
        blocked.append("non_apply_response_status_forbidden")
    if request.response_payload_hash:
        blocked.append("non_apply_response_payload_hash_forbidden")
    return blocked


def _apply_approval_violations(request: BranchProtectionReconcileRequest) -> list[str]:
    blocked: list[str] = []
    if not request.approval_ref:
        blocked.append("approval_ref_required")
    if not request.token_exchange_receipt_ref:
        blocked.append("token_exchange_receipt_ref_required")
    if not request.action_execution_receipt_ref:
        blocked.append("action_execution_receipt_ref_required")
    if not 200 <= request.response_status_code <= 299:
        blocked.append("response_status_code_2xx_required")
    if not request.response_payload_hash:
        blocked.append("response_payload_hash_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.response_payload_hash):
        blocked.append("response_payload_hash_invalid")
    return blocked


def _status(mode: str, drift: list[str], blocked_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if mode == "plan_only":
        return "planned" if drift else "noop"
    if mode == "dry_run":
        return "dry_run_accepted"
    return "apply_receipt_bound"


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


def _normalize_unique_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted(dict.fromkeys(_normalize_list(values)))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
