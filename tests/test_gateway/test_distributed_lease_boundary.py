"""Gateway distributed lease claim receipt tests.

Purpose: verify distributed lease claim planning is hash-bound, schema-backed,
and non-live unless external approval and adapter receipt evidence are bound.
Governance scope: lease backend policy, scheduled job identity, worker claim
identity, operation payload hash, fencing token, lease expiry, and secret
absence.
Dependencies: gateway.distributed_lease_boundary and distributed lease schema.
Invariants:
  - Plan-only and dry-run modes do not call a lease backend.
  - Claim-approved mode requires approval and adapter receipt evidence.
  - Expected and observed job payload hashes must match before admission.
  - Raw tokens, JWTs, and private keys are never accepted as receipt evidence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.distributed_lease_boundary import (
    DistributedLeaseBoundaryPolicy,
    DistributedLeaseClaimBoundaryRequest,
    DistributedLeaseClaimPlanner,
    DistributedLeaseJob,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "distributed_lease_claim_receipt.schema.json"
HEX_DIGITS = set("0123456789abcdef")
PAYLOAD_HASH = "sha256:" + ("a" * 64)
RESPONSE_HASH = "sha256:" + ("b" * 64)
MISMATCHED_PAYLOAD_HASH = "sha256:" + ("c" * 64)
NOW = "2026-06-15T16:00:00+00:00"
LEASE_EXPIRES_AT = "2026-06-15T16:01:00+00:00"


def test_distributed_lease_plan_is_hash_bound_and_non_live() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.mode == "plan_only"
    assert receipt.backend_kind == "postgres_advisory_lock"
    assert receipt.operation_payload["adapter"] == "postgres_advisory_lock"
    assert receipt.operation_payload["claim"]["job_id"] == "scheduled-job-1"
    assert receipt.operation_payload["claim"]["worker_id"] == "worker-a"
    assert receipt.expected_payload_hash == PAYLOAD_HASH
    assert receipt.lease_seconds == 60
    assert len(receipt.policy_hash) == 64
    assert set(receipt.policy_hash) <= HEX_DIGITS
    assert len(receipt.request_payload_hash) == 64
    assert len(receipt.operation_payload_hash) == 64
    assert len(receipt.plan_hash) == 64
    assert len(receipt.receipt_hash) == 64
    assert receipt.external_claim_admitted is False
    assert receipt.lease_service_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_secret_stored is False
    assert receipt.metadata["policy_hash_bound"] is True
    assert receipt.metadata["request_hash_bound"] is True
    assert receipt.metadata["operation_hash_bound"] is True
    assert receipt.metadata["plan_hash_bound"] is True


def test_distributed_lease_external_gateway_operation_is_endpoint_bound() -> None:
    request = replace(
        _request(),
        policy=DistributedLeaseBoundaryPolicy(
            policy_id="policy-lease-gateway-1",
            backend_kind="external_http_gateway",
            service_id="lease-gateway-prod",
            endpoint="https://leases.internal.example/claim",
            default_lease_seconds=45,
            max_lease_seconds=120,
        ),
    )
    receipt = DistributedLeaseClaimPlanner().evaluate(request)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.backend_kind == "external_http_gateway"
    assert receipt.endpoint == "https://leases.internal.example/claim"
    assert receipt.operation_payload["method"] == "POST"
    assert receipt.operation_payload["endpoint"] == "https://leases.internal.example/claim"
    assert receipt.operation_payload["claim"]["lease_seconds"] == 45
    assert "external_gateway_endpoint" in receipt.required_controls
    assert receipt.external_claim_admitted is False


def test_distributed_lease_dry_run_rejects_claim_response_evidence() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(
        replace(
            _request(mode="dry_run"),
            approval_ref="approval://lease/claim-1",
            adapter_claim_receipt_ref="receipt://lease/adapter-claim-1",
            response_status_code=200,
            response_payload_hash=RESPONSE_HASH,
            observed_payload_hash=PAYLOAD_HASH,
            lease_expires_at=LEASE_EXPIRES_AT,
            fencing_token="fence-1",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "non_claim_approval_ref_forbidden" in receipt.blocked_reasons
    assert "non_claim_adapter_receipt_forbidden" in receipt.blocked_reasons
    assert "non_claim_response_status_forbidden" in receipt.blocked_reasons
    assert "non_claim_response_payload_hash_forbidden" in receipt.blocked_reasons
    assert "non_claim_observed_payload_hash_forbidden" in receipt.blocked_reasons
    assert "non_claim_lease_expiry_forbidden" in receipt.blocked_reasons
    assert "non_claim_fencing_token_forbidden" in receipt.blocked_reasons
    assert "distributed_lease_claim_block" in receipt.required_controls
    assert receipt.external_claim_admitted is False
    assert receipt.metadata["lease_service_not_called"] is True


def test_distributed_lease_claim_approved_requires_external_receipts() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(_request(mode="claim_approved"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval_ref_required" in receipt.blocked_reasons
    assert "adapter_claim_receipt_ref_required" in receipt.blocked_reasons
    assert "response_status_code_2xx_required" in receipt.blocked_reasons
    assert "response_payload_hash_required" in receipt.blocked_reasons
    assert "observed_payload_hash_required" in receipt.blocked_reasons
    assert "fencing_token_required" in receipt.blocked_reasons
    assert "lease_expires_at_required" in receipt.blocked_reasons
    assert "operator_approval" in receipt.required_controls
    assert "adapter_claim_receipt" in receipt.required_controls
    assert receipt.external_claim_admitted is False
    assert receipt.metadata["fencing_token_checked"] is True
    assert receipt.metadata["lease_expiry_checked"] is True


def test_distributed_lease_claim_approved_binds_adapter_receipt() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(_approved_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "claim_receipt_bound"
    assert receipt.claim_outcome == "granted"
    assert receipt.approval_ref == "approval://lease/claim-1"
    assert receipt.adapter_claim_receipt_ref == "receipt://lease/adapter-claim-1"
    assert receipt.response_status_code == 201
    assert receipt.response_payload_hash == RESPONSE_HASH
    assert receipt.observed_payload_hash == PAYLOAD_HASH
    assert receipt.lease_expires_at == LEASE_EXPIRES_AT
    assert receipt.fencing_token == "lease-service-a:scheduled-job-1:1"
    assert receipt.blocked_reasons == []
    assert receipt.external_claim_admitted is True
    assert receipt.lease_service_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_secret_stored is False
    assert receipt.metadata["external_claim_admitted"] is True


def test_distributed_lease_claim_allows_unfenced_policy_without_token() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(
        replace(
            _approved_request(),
            policy=replace(_policy(), fencing_tokens_required=False),
            fencing_token="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "claim_receipt_bound"
    assert receipt.claim_outcome == "granted"
    assert receipt.policy["fencing_tokens_required"] is False
    assert receipt.fencing_token == ""
    assert "fencing_token_required" not in receipt.required_controls
    assert receipt.blocked_reasons == []
    assert receipt.external_claim_admitted is True
    assert receipt.metadata["fencing_token_checked"] is True


def test_distributed_lease_claim_blocks_observed_payload_mismatch() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(
        replace(_approved_request(), observed_payload_hash=MISMATCHED_PAYLOAD_HASH)
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.expected_payload_hash == PAYLOAD_HASH
    assert receipt.observed_payload_hash == MISMATCHED_PAYLOAD_HASH
    assert "observed_payload_hash_mismatch" in receipt.blocked_reasons
    assert "distributed_lease_claim_block" in receipt.required_controls
    assert receipt.external_claim_admitted is False
    assert receipt.claim_outcome == "not_observed"


def test_distributed_lease_claim_blocks_expired_or_unfenced_grant() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(
        replace(
            _approved_request(),
            lease_expires_at="2026-06-15T15:59:59+00:00",
            fencing_token="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "lease_expiry_not_future" in receipt.blocked_reasons
    assert "fencing_token_required" in receipt.blocked_reasons
    assert "distributed_lease_claim_block" in receipt.required_controls
    assert receipt.external_claim_admitted is False
    assert receipt.metadata["fencing_token_checked"] is True
    assert receipt.metadata["lease_expiry_checked"] is True


def test_distributed_lease_claim_rejects_secret_value_disclosure() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(
        replace(
            _request(),
            metadata={"debug_installation_token": "ghs_" + ("d" * 32)},
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.external_claim_admitted is False
    assert receipt.raw_secret_stored is False
    assert receipt.lease_service_call_performed is False


def test_distributed_lease_policy_blocks_oversized_lease_window() -> None:
    receipt = DistributedLeaseClaimPlanner().evaluate(replace(_request(), lease_seconds=999))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.lease_seconds == 999
    assert "lease_seconds_exceeds_policy" in receipt.blocked_reasons
    assert "distributed_lease_claim_block" in receipt.required_controls
    assert receipt.external_claim_admitted is False
    assert receipt.required_actions == [
        "resolve_distributed_lease_block",
        "retain_blocked_claim_receipt",
    ]


def _approved_request() -> DistributedLeaseClaimBoundaryRequest:
    return replace(
        _request(mode="claim_approved"),
        approval_ref="approval://lease/claim-1",
        adapter_claim_receipt_ref="receipt://lease/adapter-claim-1",
        response_status_code=201,
        response_payload_hash=RESPONSE_HASH,
        observed_payload_hash=PAYLOAD_HASH,
        lease_expires_at=LEASE_EXPIRES_AT,
        fencing_token="lease-service-a:scheduled-job-1:1",
    )


def _request(*, mode: str = "plan_only") -> DistributedLeaseClaimBoundaryRequest:
    return DistributedLeaseClaimBoundaryRequest(
        request_id="distributed-lease-claim-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        policy=_policy(),
        job=_job(),
        worker_id="worker-a",
        mode=mode,
        runtime_now_utc=NOW,
        evidence_refs=["proof://distributed-lease/readiness-1"],
    )


def _policy() -> DistributedLeaseBoundaryPolicy:
    return DistributedLeaseBoundaryPolicy(
        policy_id="policy-lease-postgres-1",
        backend_kind="postgres_advisory_lock",
        service_id="lease-service-a",
        default_lease_seconds=60,
        max_lease_seconds=120,
    )


def _job() -> DistributedLeaseJob:
    return DistributedLeaseJob(
        job_id="scheduled-job-1",
        target="capability://worker/document-sync",
        attempt=1,
        expected_payload_hash=PAYLOAD_HASH,
        idempotency_key="idem-scheduled-job-1-worker-a",
        scheduler_receipt_ref="receipt://temporal/scheduler/scheduled-job-1",
    )
