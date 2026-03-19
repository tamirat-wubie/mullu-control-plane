"""Purpose: verify real provider adapters — HTTP connector, file communication, stub model.
Governance scope: provider adapter tests only.
Dependencies: provider adapters, contracts.
Invariants: HTTP is read-only; file comm persists messages; stub model is deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.adapters.file_communication import FileCommunicationAdapter
from mcoi_runtime.adapters.stub_model import StubModelAdapter
from mcoi_runtime.contracts.communication import (
    CommunicationChannel,
    CommunicationMessage,
    DeliveryStatus,
)
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.contracts.model import ModelInvocation, ModelStatus, ValidationStatus
from mcoi_runtime.adapters.http_connector import HttpConnector


_CLOCK = "2026-03-19T00:00:00+00:00"


# --- HTTP Connector ---


def _http_connector_descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="http-1",
        name="HTTP Test",
        provider="test",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-http",
        enabled=True,
    )


def test_http_connector_missing_url() -> None:
    connector = HttpConnector(clock=lambda: _CLOCK)
    result = connector.invoke(_http_connector_descriptor(), {})
    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "missing_url"


def test_http_connector_invalid_url() -> None:
    from mcoi_runtime.adapters.http_connector import HttpConnectorConfig
    connector = HttpConnector(clock=lambda: _CLOCK, config=HttpConnectorConfig(timeout_seconds=5.0))
    result = connector.invoke(_http_connector_descriptor(), {"url": "not-a-url"})
    assert result.status is ConnectorStatus.FAILED
    assert result.error_code is not None


# --- File Communication ---


def test_file_communication_delivers(tmp_path: Path) -> None:
    adapter = FileCommunicationAdapter(outbox_path=tmp_path / "outbox", clock=lambda: _CLOCK)
    msg = CommunicationMessage(
        message_id="msg-1",
        sender_id="agent-1",
        recipient_id="operator-1",
        channel=CommunicationChannel.APPROVAL,
        message_type="approval_request",
        payload={"action": "delete /tmp/old"},
        correlation_id="corr-1",
        created_at=_CLOCK,
    )
    result = adapter.deliver(msg)

    assert result.status is DeliveryStatus.DELIVERED
    assert result.message_id == "msg-1"

    # Verify file exists with message content
    file_path = tmp_path / "outbox" / "msg-1.json"
    assert file_path.exists()
    content = json.loads(file_path.read_text(encoding="utf-8"))
    assert content["message_id"] == "msg-1"
    assert content["channel"] == "approval"


def test_file_communication_multiple_messages(tmp_path: Path) -> None:
    adapter = FileCommunicationAdapter(outbox_path=tmp_path / "outbox", clock=lambda: _CLOCK)
    for i in range(3):
        msg = CommunicationMessage(
            message_id=f"msg-{i}",
            sender_id="agent-1",
            recipient_id="operator-1",
            channel=CommunicationChannel.NOTIFICATION,
            message_type="notification",
            payload={"event": f"event-{i}"},
            correlation_id=f"corr-{i}",
            created_at=_CLOCK,
        )
        result = adapter.deliver(msg)
        assert result.status is DeliveryStatus.DELIVERED

    files = list((tmp_path / "outbox").glob("*.json"))
    assert len(files) == 3


# --- Stub Model ---


def test_stub_model_produces_deterministic_output() -> None:
    adapter = StubModelAdapter(clock=lambda: _CLOCK)
    inv = ModelInvocation(
        invocation_id="inv-1",
        model_id="stub-model",
        prompt_hash="prompt-abc",
        invoked_at=_CLOCK,
    )
    resp1 = adapter.invoke(inv)
    resp2 = adapter.invoke(inv)

    assert resp1.status is ModelStatus.SUCCEEDED
    assert resp1.validation_status is ValidationStatus.PENDING
    assert resp1.output_digest == resp2.output_digest  # Deterministic
    assert resp1.output_tokens is not None
    assert resp1.actual_cost == 0.0


def test_stub_model_different_prompts_differ() -> None:
    adapter = StubModelAdapter(clock=lambda: _CLOCK)
    resp1 = adapter.invoke(ModelInvocation(
        invocation_id="inv-1", model_id="m-1",
        prompt_hash="hash-a", invoked_at=_CLOCK,
    ))
    resp2 = adapter.invoke(ModelInvocation(
        invocation_id="inv-2", model_id="m-1",
        prompt_hash="hash-b", invoked_at=_CLOCK,
    ))
    assert resp1.output_digest != resp2.output_digest
