"""Purpose: verify integration engine — connector registry, routing, and failure handling.
Governance scope: integration core tests only.
Dependencies: integration engine, contracts.
Invariants: disabled connectors MUST NOT be invoked; missing connectors fail closed.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.core.integration import (
    IntegrationEngine,
    InvocationRequest,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


_CLOCK = "2026-03-19T00:00:00+00:00"


class FakeConnectorAdapter:
    def __init__(self, response_digest: str = "resp-digest") -> None:
        self._digest = response_digest
        self.invoked: list[dict] = []

    def invoke(self, connector: ConnectorDescriptor, request: dict) -> ConnectorResult:
        self.invoked.append(request)
        return ConnectorResult(
            result_id=stable_identifier("res", {"connector_id": connector.connector_id}),
            connector_id=connector.connector_id,
            status=ConnectorStatus.SUCCEEDED,
            response_digest=self._digest,
            started_at=_CLOCK,
            finished_at=_CLOCK,
        )


def _descriptor(connector_id: str = "conn-1", enabled: bool = True) -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id=connector_id,
        name="Test API",
        provider="test",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-1",
        enabled=enabled,
    )


def test_register_and_invoke() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    adapter = FakeConnectorAdapter()
    engine.register(_descriptor(), adapter)

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="list_repos",
        parameters={"org": "mullu"},
    ))

    assert result.status is ConnectorStatus.SUCCEEDED
    assert len(adapter.invoked) == 1


def test_invoke_unregistered_connector_fails() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)

    result = engine.invoke(InvocationRequest(
        connector_id="nonexistent",
        operation="op",
        parameters={},
    ))

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "connector_not_registered"


def test_invoke_disabled_connector_fails() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(enabled=False), FakeConnectorAdapter())

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="op",
        parameters={},
    ))

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "connector_disabled"


def test_duplicate_registration_rejected() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeConnectorAdapter())

    with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
        engine.register(_descriptor(), FakeConnectorAdapter())


def test_list_connectors() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("conn-a"), FakeConnectorAdapter())
    engine.register(_descriptor("conn-b", enabled=False), FakeConnectorAdapter())

    assert len(engine.list_connectors()) == 2
    assert len(engine.list_connectors(enabled_only=True)) == 1


def test_get_connector() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("conn-1"), FakeConnectorAdapter())

    assert engine.get_connector("conn-1") is not None
    assert engine.get_connector("nonexistent") is None
