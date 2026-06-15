"""Gateway distributed lease execution receipt tests.

Purpose: verify distributed lease execution receipts compose claim and adapter
registry evidence without executing live scheduler lease work.
Governance scope: execution plan hash, adapter registry receipt hash, claim
receipt hash, execution mode, delegation status, no-live-backend-call flags,
and secret absence.
Dependencies: gateway.distributed_lease_execution, gateway.distributed_lease_adapters,
gateway.distributed_lease_boundary, and distributed lease execution schema.
Invariants:
  - Execution receipts never call a lease backend or dispatch a worker.
  - Local execution readiness is limited to ready compare-and-swap adapters.
  - External gateway execution is delegated and receipt-bound.
  - Adapter or claim blocks propagate into execution_blocked.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.distributed_lease_adapters import (
    DistributedLeaseAdapterCapability,
    DistributedLeaseAdapterRegistry,
)
from gateway.distributed_lease_boundary import (
    DistributedLeaseBoundaryPolicy,
    DistributedLeaseClaimBoundaryRequest,
    DistributedLeaseJob,
)
from gateway.distributed_lease_execution import DistributedLeaseExecutionReceiptEvaluator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "distributed_lease_execution_receipt.schema.json"
HEX_DIGITS = set("0123456789abcdef")
PAYLOAD_HASH = "sha256:" + ("a" * 64)
RESPONSE_HASH = "sha256:" + ("b" * 64)
NOW = "2026-06-15T16:00:00+00:00"
LEASE_EXPIRES_AT = "2026-06-15T16:01:00+00:00"


def test_execution_receipt_ready_for_sqlite_compare_and_swap_without_live_call() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        _request(policy=_sqlite_policy()),
        _registry(),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_receipt_ready"
    assert receipt.execution_mode == "local_compare_and_swap"
    assert receipt.backend_kind == "sqlite_compare_and_swap"
    assert receipt.adapter_status == "adapter_ready"
    assert receipt.claim_receipt_status == "planned"
    assert receipt.execution_admissible is True
    assert receipt.external_gateway_delegated is False
    assert receipt.blocked_reasons == []
    assert receipt.operation_payload["adapter"] == "sqlite_compare_and_swap"
    assert receipt.execution_plan["operation_payload_hash"] == receipt.operation_payload_hash
    assert receipt.execution_plan["adapter_registry_receipt_hash"] == receipt.adapter_registry_receipt_hash
    assert receipt.execution_plan["claim_receipt_hash"] == receipt.claim_receipt_hash
    assert len(receipt.execution_plan_hash) == 64
    assert set(receipt.execution_plan_hash) <= HEX_DIGITS
    assert len(receipt.adapter_registry_receipt_hash) == 64
    assert len(receipt.claim_receipt_hash) == 64
    assert len(receipt.receipt_hash) == 64
    assert receipt.lease_service_call_performed is False
    assert receipt.adapter_backend_call_performed is False
    assert receipt.scheduler_mutation_performed is False
    assert receipt.worker_dispatch_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_secret_stored is False
    assert receipt.metadata["execution_plan_hash_bound"] is True
    assert receipt.metadata["adapter_registry_receipt_hash_bound"] is True
    assert receipt.metadata["claim_receipt_hash_bound"] is True
    assert receipt.metadata["worker_dispatch_not_performed"] is True


def test_execution_receipt_delegates_external_gateway_without_http_call() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        _request(policy=_external_gateway_policy()),
        _registry(),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_delegated"
    assert receipt.execution_mode == "external_gateway"
    assert receipt.adapter_status == "adapter_delegated"
    assert receipt.claim_receipt_status == "planned"
    assert receipt.execution_admissible is True
    assert receipt.external_gateway_delegated is True
    assert receipt.operation_payload["adapter"] == "external_http_gateway"
    assert receipt.operation_payload["endpoint"] == "https://leases.internal.example/claim"
    assert "external_gateway_delegation" in receipt.required_controls
    assert "delegate_execution_through_receipt_producing_gateway" in receipt.required_actions
    assert receipt.lease_service_call_performed is False
    assert receipt.adapter_backend_call_performed is False
    assert receipt.worker_dispatch_performed is False
    assert receipt.metadata["external_gateway_delegated"] is True


def test_execution_blocks_native_adapter_without_production_readiness() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(_request(), _registry())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_blocked"
    assert receipt.execution_mode == "plan_only"
    assert receipt.adapter_status == "adapter_blocked"
    assert receipt.execution_admissible is False
    assert receipt.external_gateway_delegated is False
    assert "distributed_lease_adapter_not_production_ready" in receipt.blocked_reasons
    assert "distributed_lease_execution_block" in receipt.required_controls
    assert "resolve_distributed_lease_execution_block" in receipt.required_actions
    assert receipt.scheduler_mutation_performed is False
    assert receipt.worker_dispatch_performed is False


def test_execution_blocks_claim_receipt_violations_before_dispatch() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        replace(_request(policy=_sqlite_policy()), evidence_refs=[]),
        _registry(),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_blocked"
    assert receipt.adapter_status == "adapter_blocked"
    assert receipt.claim_receipt_status == "blocked"
    assert "readiness_evidence_refs_required" in receipt.blocked_reasons
    assert receipt.execution_admissible is False
    assert receipt.adapter_registry_receipt["claim_receipt"]["status"] == "blocked"
    assert receipt.adapter_registry_receipt["claim_receipt_hash"] == receipt.claim_receipt_hash
    assert receipt.lease_service_call_performed is False
    assert receipt.worker_dispatch_performed is False


def test_execution_binds_claim_approved_external_gateway_grant() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        replace(
            _request(policy=_external_gateway_policy(), mode="claim_approved"),
            approval_ref="approval://lease/claim-1",
            adapter_claim_receipt_ref="receipt://lease/adapter-claim-1",
            response_status_code=201,
            response_payload_hash=RESPONSE_HASH,
            observed_payload_hash=PAYLOAD_HASH,
            lease_expires_at=LEASE_EXPIRES_AT,
            fencing_token="lease-gateway-prod:scheduled-job-1:1",
        ),
        _registry(),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_delegated"
    assert receipt.execution_mode == "external_gateway"
    assert receipt.claim_receipt_status == "claim_receipt_bound"
    assert receipt.claim_outcome == "granted"
    assert receipt.execution_admissible is True
    assert receipt.external_gateway_delegated is True
    assert receipt.blocked_reasons == []
    assert receipt.adapter_registry_receipt["claim_receipt"]["adapter_claim_receipt_ref"] == (
        "receipt://lease/adapter-claim-1"
    )
    assert receipt.adapter_registry_receipt["claim_receipt"]["fencing_token"] == (
        "lease-gateway-prod:scheduled-job-1:1"
    )
    assert receipt.execution_plan["expected_payload_hash"] == PAYLOAD_HASH
    assert receipt.metadata["payload_hash_bound"] is True


def test_execution_blocks_fencing_required_backend_without_token_support() -> None:
    registry = DistributedLeaseAdapterRegistry(
        registry_id="registry-no-fence",
        generated_at=NOW,
        capabilities=[
            DistributedLeaseAdapterCapability(
                backend_kind="redis_redlock",
                mode="native_client",
                fencing_tokens_supported=False,
                compare_and_swap_supported=False,
                production_ready=True,
                reasons=["test capability intentionally lacks fencing support"],
            )
        ],
    )
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        _request(policy=replace(_policy(), backend_kind="redis_redlock")),
        registry,
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_blocked"
    assert receipt.backend_kind == "redis_redlock"
    assert receipt.execution_admissible is False
    assert "distributed_lease_adapter_fencing_token_unsupported" in receipt.blocked_reasons
    assert receipt.adapter_backend_call_performed is False
    assert receipt.worker_dispatch_performed is False
    assert receipt.metadata["adapter_backend_not_called"] is True


def test_execution_rejects_secret_value_disclosure() -> None:
    receipt = DistributedLeaseExecutionReceiptEvaluator().evaluate(
        replace(
            _request(policy=_sqlite_policy()),
            metadata={"debug_installation_token": "ghs_" + ("d" * 32)},
        ),
        _registry(),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.execution_status == "execution_blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.execution_admissible is False
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.raw_secret_stored is False
    assert receipt.lease_service_call_performed is False
    assert receipt.worker_dispatch_performed is False


def _registry() -> DistributedLeaseAdapterRegistry:
    return DistributedLeaseAdapterRegistry.production_default(generated_at=NOW)


def _request(
    *,
    policy: DistributedLeaseBoundaryPolicy | None = None,
    mode: str = "plan_only",
) -> DistributedLeaseClaimBoundaryRequest:
    return DistributedLeaseClaimBoundaryRequest(
        request_id="distributed-lease-execution-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        policy=policy or _policy(),
        job=_job(),
        worker_id="worker-a",
        mode=mode,
        runtime_now_utc=NOW,
        evidence_refs=["proof://distributed-lease/execution-readiness-1"],
    )


def _policy() -> DistributedLeaseBoundaryPolicy:
    return DistributedLeaseBoundaryPolicy(
        policy_id="policy-lease-postgres-1",
        backend_kind="postgres_advisory_lock",
        service_id="lease-service-a",
        default_lease_seconds=60,
        max_lease_seconds=120,
    )


def _sqlite_policy() -> DistributedLeaseBoundaryPolicy:
    return DistributedLeaseBoundaryPolicy(
        policy_id="policy-lease-sqlite-1",
        backend_kind="sqlite_compare_and_swap",
        service_id="lease-service-sqlite",
        default_lease_seconds=60,
        max_lease_seconds=120,
    )


def _external_gateway_policy() -> DistributedLeaseBoundaryPolicy:
    return DistributedLeaseBoundaryPolicy(
        policy_id="policy-lease-gateway-1",
        backend_kind="external_http_gateway",
        service_id="lease-gateway-prod",
        endpoint="https://leases.internal.example/claim",
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
