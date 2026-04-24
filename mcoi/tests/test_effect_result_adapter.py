"""Purpose: verify receipt-bearing results adapt into execution actual effects.
Governance scope: effect-assurance bridge tests only.
Dependencies: communication, connector, execution, and effect assurance contracts.
Invariants: receipts become observed effects; missing receipts fail closed; assumed effects remain empty.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication import CommunicationChannel, DeliveryResult, DeliveryStatus
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.effect_result_adapter import (
    execution_result_from_connector,
    execution_result_from_delivery,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


NOW = "2026-03-19T00:00:00+00:00"


def _delivery_receipt(**overrides: object) -> dict[str, object]:
    receipt = {
        "receipt_id": "delivery-receipt-1",
        "evidence_ref": "communication-delivery:msg-1:receipt-1",
        "attempted_at": NOW,
        "delivered_at": NOW,
        "status": "delivered",
    }
    receipt.update(overrides)
    return receipt


def test_delivery_receipt_adapts_to_observed_effect() -> None:
    delivery = DeliveryResult(
        delivery_id="delivery-1",
        message_id="msg-1",
        status=DeliveryStatus.DELIVERED,
        channel=CommunicationChannel.NOTIFICATION,
        delivered_at=NOW,
        metadata={"delivery_receipt": _delivery_receipt()},
    )

    result = execution_result_from_delivery(delivery, goal_id="goal-1")
    observed = EffectAssuranceGate(clock=lambda: NOW).observe(result)

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.assumed_effects == ()
    assert result.actual_effects[0].name == "communication_delivered"
    assert observed[0].evidence_ref == "communication-delivery:msg-1:receipt-1"
    assert observed[0].source == "delivery-1"


def test_file_write_receipt_adapts_to_file_effect() -> None:
    delivery = DeliveryResult(
        delivery_id="delivery-file-1",
        message_id="msg-file-1",
        status=DeliveryStatus.DELIVERED,
        channel=CommunicationChannel.APPROVAL,
        delivered_at=NOW,
        metadata={
            "file_write_receipt": {
                "receipt_id": "file-receipt-1",
                "evidence_ref": "file-write:msg-file-1:file-receipt-1",
                "written_at": NOW,
                "operation": "write",
            }
        },
    )

    result = execution_result_from_delivery(delivery, goal_id="goal-1", execution_id="exec-file-1")
    observed = EffectAssuranceGate(clock=lambda: NOW).observe(result)

    assert result.execution_id == "exec-file-1"
    assert result.actual_effects[0].name == "file_write_completed"
    assert observed[0].evidence_ref == "file-write:msg-file-1:file-receipt-1"
    assert observed[0].observed_value["operation"] == "write"
    assert result.metadata["receipt_key"] == "file_write_receipt"


def test_connector_receipt_adapts_to_observed_effect() -> None:
    connector = ConnectorResult(
        result_id="result-1",
        connector_id="connector-1",
        status=ConnectorStatus.SUCCEEDED,
        response_digest="digest-1",
        started_at=NOW,
        finished_at=NOW,
        metadata={
            "connector_receipt": {
                "receipt_id": "connector-receipt-1",
                "evidence_ref": "connector-invocation:connector-1:receipt-1",
                "status": "succeeded",
                "response_digest": "digest-1",
            }
        },
    )

    result = execution_result_from_connector(connector, goal_id="goal-2")
    observed = EffectAssuranceGate(clock=lambda: NOW).observe(result)

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert result.actual_effects[0].name == "connector_invocation_succeeded"
    assert observed[0].evidence_ref == "connector-invocation:connector-1:receipt-1"
    assert observed[0].observed_value["response_digest"] == "digest-1"
    assert result.metadata["connector_id"] == "connector-1"


def test_missing_receipt_fails_closed() -> None:
    delivery = DeliveryResult(
        delivery_id="delivery-2",
        message_id="msg-2",
        status=DeliveryStatus.DELIVERED,
        channel=CommunicationChannel.NOTIFICATION,
        delivered_at=NOW,
        metadata={},
    )

    with pytest.raises(RuntimeCoreInvariantError, match="required for effect observation") as exc_info:
        execution_result_from_delivery(delivery, goal_id="goal-1")

    message = str(exc_info.value)
    assert "receipt" in message
    assert "msg-2" not in message
    assert "effect observation" in message
