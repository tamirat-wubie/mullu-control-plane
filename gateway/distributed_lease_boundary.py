"""Distributed lease claim receipt planner.

Purpose: build hash-bound distributed lease claim plans and receipts without
    calling a lease backend in-process.
Governance scope: scheduler job identity, worker identity, lease backend,
    request payload hash, operation payload hash, adapter receipt refs,
    fencing token, lease expiry, and secret absence.
Dependencies: dataclasses, datetime, re, and command-spine canonical hashing.
Invariants:
  - The planner never calls a distributed lease service.
  - Plan-only and dry-run modes cannot claim live lease response evidence.
  - Claim-approved mode must bind approval, adapter claim receipt, 2xx
    response, response hash, observed payload hash, lease expiry, and fencing
    token evidence before an external lease claim is admitted.
  - Raw secret-shaped material blocks receipt admission.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash


DISTRIBUTED_LEASE_CLAIM_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:distributed-lease-claim-receipt:1"
)
DISTRIBUTED_LEASE_BACKENDS = (
    "sqlite_compare_and_swap",
    "postgres_advisory_lock",
    "redis_redlock",
    "etcd_lease",
    "consul_session",
    "external_http_gateway",
)
DISTRIBUTED_LEASE_MODES = ("plan_only", "dry_run", "claim_approved")
DISTRIBUTED_LEASE_STATUSES = (
    "planned",
    "dry_run_accepted",
    "claim_receipt_bound",
    "blocked",
)
DISTRIBUTED_LEASE_CLAIM_OUTCOMES = (
    "not_observed",
    "granted",
    "rejected",
    "conflict",
    "deferred",
)
SHA256_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SERVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:/-]+$")
ENDPOINT_PATTERN = re.compile(r"^https://[^\s]+$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
BASE_DISTRIBUTED_LEASE_CONTROLS = (
    "distributed_lease_policy_hash",
    "distributed_lease_request_hash",
    "distributed_lease_operation_hash",
    "distributed_lease_plan_hash",
    "scheduled_job_identity",
    "worker_identity",
    "payload_hash_binding",
    "backend_kind",
    "fencing_token_policy",
    "lease_expiry",
    "readiness_evidence",
    "secret_absence",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class DistributedLeaseBoundaryPolicy:
    """Lease backend policy for one distributed scheduler claim boundary."""

    policy_id: str
    backend_kind: str
    service_id: str
    default_lease_seconds: int
    max_lease_seconds: int
    endpoint: str = ""
    fencing_tokens_required: bool = True
    receipt_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "backend_kind", "service_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.backend_kind not in DISTRIBUTED_LEASE_BACKENDS:
            raise ValueError("distributed_lease_backend_kind_invalid")
        if not SERVICE_ID_PATTERN.fullmatch(self.service_id):
            raise ValueError("distributed_lease_service_id_invalid")
        endpoint = str(self.endpoint).strip()
        if self.backend_kind == "external_http_gateway" and not endpoint:
            raise ValueError("distributed_lease_endpoint_required")
        if endpoint and not ENDPOINT_PATTERN.fullmatch(endpoint):
            raise ValueError("distributed_lease_endpoint_invalid")
        object.__setattr__(self, "endpoint", endpoint)
        if not isinstance(self.default_lease_seconds, int) or self.default_lease_seconds < 1:
            raise ValueError("default_lease_seconds_positive_required")
        if not isinstance(self.max_lease_seconds, int) or self.max_lease_seconds < 1:
            raise ValueError("max_lease_seconds_positive_required")
        if self.default_lease_seconds > self.max_lease_seconds:
            raise ValueError("default_lease_seconds_exceeds_max")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DistributedLeaseJob:
    """Scheduled job identity to bind before a distributed lease claim."""

    job_id: str
    target: str
    attempt: int
    expected_payload_hash: str
    idempotency_key: str
    scheduler_receipt_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("job_id", "target", "expected_payload_hash", "idempotency_key"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "scheduler_receipt_ref", str(self.scheduler_receipt_ref).strip())
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("distributed_lease_attempt_positive_required")
        if not SHA256_REF_PATTERN.fullmatch(self.expected_payload_hash):
            raise ValueError("expected_payload_hash_invalid")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DistributedLeaseClaimBoundaryRequest:
    """One request to plan or bind a distributed scheduler lease claim."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    policy: DistributedLeaseBoundaryPolicy
    job: DistributedLeaseJob
    worker_id: str
    mode: str
    runtime_now_utc: str
    evidence_refs: list[str]
    lease_seconds: int = 0
    approval_ref: str = ""
    adapter_claim_receipt_ref: str = ""
    response_status_code: int = 0
    response_payload_hash: str = ""
    observed_payload_hash: str = ""
    lease_expires_at: str = ""
    fencing_token: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "worker_id",
            "mode",
            "runtime_now_utc",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.mode not in DISTRIBUTED_LEASE_MODES:
            raise ValueError("distributed_lease_mode_invalid")
        if not isinstance(self.policy, DistributedLeaseBoundaryPolicy):
            raise ValueError("distributed_lease_policy_required")
        if not isinstance(self.job, DistributedLeaseJob):
            raise ValueError("distributed_lease_job_required")
        _parse_required_instant(self.runtime_now_utc)
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        for field_name in (
            "approval_ref",
            "adapter_claim_receipt_ref",
            "response_payload_hash",
            "observed_payload_hash",
            "lease_expires_at",
            "fencing_token",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        if not isinstance(self.lease_seconds, int) or self.lease_seconds < 0:
            raise ValueError("lease_seconds_nonnegative_required")
        if not isinstance(self.response_status_code, int) or not 0 <= self.response_status_code <= 599:
            raise ValueError("response_status_code_invalid")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DistributedLeaseClaimReceipt:
    """Schema-backed non-terminal receipt for distributed lease claims."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    mode: str
    status: str
    backend_kind: str
    service_id: str
    endpoint: str
    policy: dict[str, Any]
    policy_hash: str
    job: dict[str, Any]
    job_id: str
    worker_id: str
    target: str
    attempt: int
    expected_payload_hash: str
    lease_seconds: int
    runtime_now_utc: str
    request_payload: dict[str, Any]
    request_payload_hash: str
    operation_payload: dict[str, Any]
    operation_payload_hash: str
    plan_hash: str
    approval_ref: str
    adapter_claim_receipt_ref: str
    response_status_code: int
    response_payload_hash: str
    observed_payload_hash: str
    lease_expires_at: str
    fencing_token: str
    claim_outcome: str
    blocked_reasons: list[str]
    required_actions: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    external_claim_admitted: bool
    lease_service_call_performed: bool
    request_authentication_performed: bool
    raw_secret_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in DISTRIBUTED_LEASE_MODES:
            raise ValueError("distributed_lease_mode_invalid")
        if self.status not in DISTRIBUTED_LEASE_STATUSES:
            raise ValueError("distributed_lease_status_invalid")
        if self.claim_outcome not in DISTRIBUTED_LEASE_CLAIM_OUTCOMES:
            raise ValueError("distributed_lease_claim_outcome_invalid")
        object.__setattr__(self, "policy", dict(self.policy))
        object.__setattr__(self, "job", dict(self.job))
        object.__setattr__(self, "request_payload", dict(self.request_payload))
        object.__setattr__(self, "operation_payload", dict(self.operation_payload))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_actions", _normalize_list(self.required_actions))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class DistributedLeaseClaimPlanner:
    """Deterministic distributed lease claim planner."""

    def evaluate(
        self,
        request: DistributedLeaseClaimBoundaryRequest,
    ) -> DistributedLeaseClaimReceipt:
        """Return a distributed lease claim receipt without executing a backend claim."""
        lease_seconds = request.lease_seconds or request.policy.default_lease_seconds
        policy = asdict(request.policy)
        job = asdict(request.job)
        request_payload = _request_payload(request, lease_seconds)
        operation_payload = _operation_payload(request, lease_seconds)
        policy_hash = canonical_hash(policy)
        request_payload_hash = canonical_hash(request_payload)
        operation_payload_hash = canonical_hash(operation_payload)
        plan_hash = canonical_hash(
            {
                "request_id": request.request_id,
                "mode": request.mode,
                "policy_hash": policy_hash,
                "request_payload_hash": request_payload_hash,
                "operation_payload_hash": operation_payload_hash,
                "backend_kind": request.policy.backend_kind,
                "service_id": request.policy.service_id,
                "job_id": request.job.job_id,
                "worker_id": request.worker_id,
                "expected_payload_hash": request.job.expected_payload_hash,
                "lease_seconds": lease_seconds,
                "runtime_now_utc": _normalized_instant_text(request.runtime_now_utc),
            }
        )
        blocked_reasons = _blocked_reasons(request, lease_seconds)
        status = _status(request.mode, blocked_reasons)
        external_claim_admitted = status == "claim_receipt_bound"
        required_controls = _required_controls(request, status)

        receipt = DistributedLeaseClaimReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            mode=request.mode,
            status=status,
            backend_kind=request.policy.backend_kind,
            service_id=request.policy.service_id,
            endpoint=request.policy.endpoint,
            policy=policy,
            policy_hash=policy_hash,
            job=job,
            job_id=request.job.job_id,
            worker_id=request.worker_id,
            target=request.job.target,
            attempt=request.job.attempt,
            expected_payload_hash=request.job.expected_payload_hash,
            lease_seconds=lease_seconds,
            runtime_now_utc=_normalized_instant_text(request.runtime_now_utc),
            request_payload=request_payload,
            request_payload_hash=request_payload_hash,
            operation_payload=operation_payload,
            operation_payload_hash=operation_payload_hash,
            plan_hash=plan_hash,
            approval_ref=request.approval_ref,
            adapter_claim_receipt_ref=request.adapter_claim_receipt_ref,
            response_status_code=request.response_status_code,
            response_payload_hash=request.response_payload_hash,
            observed_payload_hash=request.observed_payload_hash,
            lease_expires_at=request.lease_expires_at,
            fencing_token=request.fencing_token,
            claim_outcome="granted" if external_claim_admitted else "not_observed",
            blocked_reasons=_unique(blocked_reasons),
            required_actions=_required_actions(status),
            required_controls=required_controls,
            evidence_refs=request.evidence_refs,
            receipt_schema_ref=DISTRIBUTED_LEASE_CLAIM_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            external_claim_admitted=external_claim_admitted,
            lease_service_call_performed=False,
            request_authentication_performed=False,
            raw_secret_stored=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "lease_service_not_called": True,
                "request_authentication_not_performed": True,
                "raw_secret_not_stored": True,
                "external_claim_admitted": external_claim_admitted,
                "policy_hash_bound": bool(policy_hash),
                "request_hash_bound": bool(request_payload_hash),
                "operation_hash_bound": bool(operation_payload_hash),
                "plan_hash_bound": bool(plan_hash),
                "payload_hash_bound": bool(request.job.expected_payload_hash),
                "fencing_token_checked": request.mode == "claim_approved",
                "lease_expiry_checked": request.mode == "claim_approved",
                "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"distributed-lease-claim-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _request_payload(
    request: DistributedLeaseClaimBoundaryRequest,
    lease_seconds: int,
) -> dict[str, Any]:
    return {
        "job_id": request.job.job_id,
        "worker_id": request.worker_id,
        "target": request.job.target,
        "attempt": request.job.attempt,
        "expected_payload_hash": request.job.expected_payload_hash,
        "lease_seconds": lease_seconds,
        "idempotency_key": request.job.idempotency_key,
        "scheduler_receipt_ref": request.job.scheduler_receipt_ref,
    }


def _operation_payload(
    request: DistributedLeaseClaimBoundaryRequest,
    lease_seconds: int,
) -> dict[str, Any]:
    base = _request_payload(request, lease_seconds)
    backend = request.policy.backend_kind
    if backend == "sqlite_compare_and_swap":
        return {
            "adapter": backend,
            "where": {
                "job_id": request.job.job_id,
                "status": "pending",
                "attempt": request.job.attempt,
                "payload_hash": request.job.expected_payload_hash,
            },
            "set": {
                "claimed_by": request.worker_id,
                "lease_seconds": lease_seconds,
            },
        }
    if backend == "postgres_advisory_lock":
        return {
            "adapter": backend,
            "sql": (
                "SELECT pg_try_advisory_xact_lock(hashtext($1)); "
                "UPDATE scheduled_jobs SET status='claimed' "
                "WHERE job_id=$2 AND status='pending' AND payload_hash=$3;"
            ),
            "lock_key_material": [request.job.job_id, request.worker_id],
            "claim": base,
        }
    if backend == "etcd_lease":
        return {
            "adapter": "etcd_txn_lease",
            "compare": {
                "key": f"/mullu/scheduler/jobs/{request.job.job_id}/owner",
                "version": 0,
            },
            "success": {
                "put": request.worker_id,
                "lease_seconds": lease_seconds,
            },
            "claim": base,
        }
    if backend == "external_http_gateway":
        return {
            "adapter": backend,
            "endpoint": request.policy.endpoint,
            "method": "POST",
            "claim": base,
        }
    return {
        "adapter": backend,
        "status": "boundary_defined_execution_pending",
        "claim": base,
    }


def _blocked_reasons(
    request: DistributedLeaseClaimBoundaryRequest,
    lease_seconds: int,
) -> list[str]:
    blocked: list[str] = []
    if not request.evidence_refs:
        blocked.append("readiness_evidence_refs_required")
    if lease_seconds < 1:
        blocked.append("lease_seconds_positive_required")
    if lease_seconds > request.policy.max_lease_seconds:
        blocked.append("lease_seconds_exceeds_policy")
    if not request.policy.receipt_required:
        blocked.append("lease_receipt_policy_required")
    if request.mode in {"plan_only", "dry_run"}:
        blocked.extend(_forbidden_claim_evidence(request))
    if request.mode == "claim_approved":
        blocked.extend(_claim_approval_violations(request))
    if _contains_secret_material(request.metadata) or _contains_secret_material(request.policy.metadata):
        blocked.append("secret_values_disclosed")
    if _contains_secret_material(request.job.metadata) or _contains_secret_material(
        [
            request.approval_ref,
            request.adapter_claim_receipt_ref,
            request.response_payload_hash,
            request.observed_payload_hash,
            request.fencing_token,
        ]
    ):
        blocked.append("secret_values_disclosed")
    return blocked


def _forbidden_claim_evidence(request: DistributedLeaseClaimBoundaryRequest) -> list[str]:
    blocked: list[str] = []
    if request.approval_ref:
        blocked.append("non_claim_approval_ref_forbidden")
    if request.adapter_claim_receipt_ref:
        blocked.append("non_claim_adapter_receipt_forbidden")
    if request.response_status_code:
        blocked.append("non_claim_response_status_forbidden")
    if request.response_payload_hash:
        blocked.append("non_claim_response_payload_hash_forbidden")
    if request.observed_payload_hash:
        blocked.append("non_claim_observed_payload_hash_forbidden")
    if request.lease_expires_at:
        blocked.append("non_claim_lease_expiry_forbidden")
    if request.fencing_token:
        blocked.append("non_claim_fencing_token_forbidden")
    return blocked


def _claim_approval_violations(request: DistributedLeaseClaimBoundaryRequest) -> list[str]:
    blocked: list[str] = []
    if not request.approval_ref:
        blocked.append("approval_ref_required")
    if not request.adapter_claim_receipt_ref:
        blocked.append("adapter_claim_receipt_ref_required")
    if not 200 <= request.response_status_code <= 299:
        blocked.append("response_status_code_2xx_required")
    if not request.response_payload_hash:
        blocked.append("response_payload_hash_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.response_payload_hash):
        blocked.append("response_payload_hash_invalid")
    if not request.observed_payload_hash:
        blocked.append("observed_payload_hash_required")
    elif not SHA256_REF_PATTERN.fullmatch(request.observed_payload_hash):
        blocked.append("observed_payload_hash_invalid")
    elif request.observed_payload_hash != request.job.expected_payload_hash:
        blocked.append("observed_payload_hash_mismatch")
    if request.policy.fencing_tokens_required and not request.fencing_token:
        blocked.append("fencing_token_required")
    if not request.lease_expires_at:
        blocked.append("lease_expires_at_required")
    else:
        blocked.extend(_lease_expiry_violations(request.runtime_now_utc, request.lease_expires_at))
    return blocked


def _lease_expiry_violations(runtime_now_utc: str, lease_expires_at: str) -> list[str]:
    try:
        now = _parse_required_instant(runtime_now_utc)
        expires = _parse_required_instant(lease_expires_at)
    except ValueError:
        return ["lease_expires_at_invalid"]
    if expires <= now:
        return ["lease_expiry_not_future"]
    return []


def _status(mode: str, blocked_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if mode == "plan_only":
        return "planned"
    if mode == "dry_run":
        return "dry_run_accepted"
    return "claim_receipt_bound"


def _required_actions(status: str) -> list[str]:
    if status == "blocked":
        return ["resolve_distributed_lease_block", "retain_blocked_claim_receipt"]
    if status == "dry_run_accepted":
        return ["retain_dry_run_plan", "withhold_external_lease_claim"]
    if status == "claim_receipt_bound":
        return [
            "retain_adapter_claim_receipt",
            "run_temporal_lease_window_after_grant",
            "retain_terminal_closure_evidence",
        ]
    return [
        "submit_external_lease_claim_through_authorized_adapter",
        "verify_distributed_lease_claim_receipt",
        "run_temporal_lease_window_after_grant",
    ]


def _required_controls(
    request: DistributedLeaseClaimBoundaryRequest,
    status: str,
) -> list[str]:
    controls = [*BASE_DISTRIBUTED_LEASE_CONTROLS]
    if request.policy.backend_kind == "external_http_gateway":
        controls.append("external_gateway_endpoint")
    if request.policy.fencing_tokens_required:
        controls.append("fencing_token_required")
    if request.mode == "claim_approved":
        controls.extend(
            [
                "operator_approval",
                "adapter_claim_receipt",
                "adapter_response_status",
                "adapter_response_hash",
                "observed_payload_hash",
            ]
        )
    if status == "blocked":
        controls.append("distributed_lease_claim_block")
    return _unique(controls)


def _contains_secret_material(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_secret_material(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_secret_material(item) for item in value)
    return False


def _parse_required_instant(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("instant_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("instant_timezone_required")
    return parsed.astimezone(timezone.utc)


def _normalized_instant_text(value: str) -> str:
    return _parse_required_instant(value).isoformat()


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
