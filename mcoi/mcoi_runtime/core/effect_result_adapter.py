"""Purpose: convert receipt-bearing provider results into execution actual effects.
Governance scope: effect-assurance observation bridge only.
Dependencies: communication, connector, execution contracts, and runtime invariants.
Invariants:
  - Only observed result receipts become actual effects.
  - Missing receipts fail closed instead of fabricating evidence.
  - Assumed effects are never emitted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcoi_runtime.contracts.communication import DeliveryResult, DeliveryStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _require_receipt(metadata: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    receipt = metadata.get(key)
    if not isinstance(receipt, Mapping):
        raise RuntimeCoreInvariantError(f"{key} required for effect observation")
    evidence_ref = receipt.get("evidence_ref")
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise RuntimeCoreInvariantError("receipt evidence_ref required for effect observation")
    return receipt


def _delivery_outcome(status: DeliveryStatus) -> ExecutionOutcome:
    if status is DeliveryStatus.DELIVERED:
        return ExecutionOutcome.SUCCEEDED
    if status is DeliveryStatus.PENDING:
        return ExecutionOutcome.CANCELLED
    return ExecutionOutcome.FAILED


def _delivery_effect_name(status: DeliveryStatus, receipt_key: str) -> str:
    if receipt_key == "file_write_receipt":
        return "file_write_completed" if status is DeliveryStatus.DELIVERED else "file_write_failed"
    if status is DeliveryStatus.DELIVERED:
        return "communication_delivered"
    if status is DeliveryStatus.PENDING:
        return "communication_pending"
    return "communication_failed"


def execution_result_from_delivery(
    delivery_result: DeliveryResult,
    *,
    goal_id: str,
    execution_id: str | None = None,
) -> ExecutionResult:
    """Adapt a delivery result with a receipt into an ExecutionResult."""
    receipt_key = (
        "delivery_receipt"
        if "delivery_receipt" in delivery_result.metadata
        else "file_write_receipt"
    )
    receipt = _require_receipt(delivery_result.metadata, receipt_key)
    receipt_time = str(
        receipt.get("delivered_at")
        or receipt.get("written_at")
        or receipt.get("attempted_at")
        or delivery_result.delivered_at
        or ""
    )
    if not receipt_time:
        raise RuntimeCoreInvariantError("receipt timestamp required for effect observation")
    effect_name = _delivery_effect_name(delivery_result.status, receipt_key)
    return ExecutionResult(
        execution_id=execution_id or f"delivery:{delivery_result.delivery_id}",
        goal_id=goal_id,
        status=_delivery_outcome(delivery_result.status),
        actual_effects=(
            EffectRecord(
                name=effect_name,
                details={
                    "effect_id": effect_name,
                    "source": delivery_result.delivery_id,
                    "evidence_ref": receipt["evidence_ref"],
                    "observed_value": dict(receipt),
                },
            ),
        ),
        assumed_effects=(),
        started_at=str(receipt.get("attempted_at") or receipt_time),
        finished_at=receipt_time,
        metadata={
            "adapter": "delivery",
            "receipt_key": receipt_key,
            "delivery_id": delivery_result.delivery_id,
        },
    )


def _connector_outcome(status: ConnectorStatus) -> ExecutionOutcome:
    if status is ConnectorStatus.SUCCEEDED:
        return ExecutionOutcome.SUCCEEDED
    if status is ConnectorStatus.TIMEOUT:
        return ExecutionOutcome.CANCELLED
    return ExecutionOutcome.FAILED


def _connector_effect_name(status: ConnectorStatus) -> str:
    if status is ConnectorStatus.SUCCEEDED:
        return "connector_invocation_succeeded"
    if status is ConnectorStatus.TIMEOUT:
        return "connector_invocation_timed_out"
    return "connector_invocation_failed"


def execution_result_from_connector(
    connector_result: ConnectorResult,
    *,
    goal_id: str,
    execution_id: str | None = None,
) -> ExecutionResult:
    """Adapt a connector result with a receipt into an ExecutionResult."""
    receipt = _require_receipt(connector_result.metadata, "connector_receipt")
    effect_name = _connector_effect_name(connector_result.status)
    return ExecutionResult(
        execution_id=execution_id or f"connector:{connector_result.result_id}",
        goal_id=goal_id,
        status=_connector_outcome(connector_result.status),
        actual_effects=(
            EffectRecord(
                name=effect_name,
                details={
                    "effect_id": effect_name,
                    "source": connector_result.result_id,
                    "evidence_ref": receipt["evidence_ref"],
                    "observed_value": dict(receipt),
                },
            ),
        ),
        assumed_effects=(),
        started_at=connector_result.started_at,
        finished_at=connector_result.finished_at,
        metadata={
            "adapter": "connector",
            "connector_id": connector_result.connector_id,
            "result_id": connector_result.result_id,
        },
    )
